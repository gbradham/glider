"""
Computer Vision Processor - Real-time frame analysis.

Provides configurable CV processing including:
- Object detection (YOLO, background subtraction)
- Multi-object tracking with persistent IDs
- Motion detection
"""

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.spatial import distance as dist

if TYPE_CHECKING:
    from glider.vision.zones import ZoneConfiguration, ZoneState, ZoneTracker

logger = logging.getLogger(__name__)


class DetectionBackend(Enum):
    """Available detection backends."""
    BACKGROUND_SUBTRACTION = auto()  # Fast, no model required
    YOLO_V8 = auto()                 # Requires ultralytics (detection only)
    YOLO_BYTETRACK = auto()          # YOLO + ByteTrack multi-object tracking
    MOTION_ONLY = auto()             # Just motion detection


@dataclass
class Detection:
    """Single detection result."""
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    centroid: Tuple[int, int] = field(default=(0, 0))
    track_id: Optional[int] = None  # ByteTrack assigned ID

    def __post_init__(self):
        # Calculate centroid from bbox
        x, y, w, h = self.bbox
        self.centroid = (x + w // 2, y + h // 2)


@dataclass
class TrackedObject:
    """Tracked object with persistent ID."""
    track_id: int
    class_name: str
    bbox: Tuple[int, int, int, int]
    confidence: float
    centroid: Tuple[int, int]
    age: int = 0  # Frames since first seen
    disappeared: int = 0  # Frames since last seen

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "centroid": self.centroid,
            "age": self.age,
        }


@dataclass
class MotionResult:
    """Motion detection result."""
    motion_detected: bool
    motion_area: float  # Percentage of frame with motion (0.0 to 1.0)
    motion_contours: List[np.ndarray] = field(default_factory=list)
    motion_mask: Optional[np.ndarray] = None


@dataclass
class CVSettings:
    """Computer vision processing settings."""
    enabled: bool = True
    backend: DetectionBackend = DetectionBackend.BACKGROUND_SUBTRACTION
    model_path: Optional[str] = None  # For YOLO
    confidence_threshold: float = 0.5
    min_detection_area: int = 500  # Minimum contour area for detection
    motion_threshold: float = 25.0  # Threshold for motion detection
    motion_area_threshold: float = 0.01  # 1% of frame for motion trigger
    tracking_enabled: bool = True
    max_disappeared: int = 50  # Frames before dropping track
    draw_overlays: bool = True
    overlay_color: Tuple[int, int, int] = (0, 255, 0)  # BGR green
    overlay_thickness: int = 2
    show_labels: bool = True
    show_trails: bool = False
    process_every_n_frames: int = 1  # Process CV every N frames (1 = every frame)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "backend": self.backend.name,
            "model_path": self.model_path,
            "confidence_threshold": self.confidence_threshold,
            "min_detection_area": self.min_detection_area,
            "motion_threshold": self.motion_threshold,
            "motion_area_threshold": self.motion_area_threshold,
            "tracking_enabled": self.tracking_enabled,
            "max_disappeared": self.max_disappeared,
            "draw_overlays": self.draw_overlays,
            "overlay_color": self.overlay_color,
            "overlay_thickness": self.overlay_thickness,
            "show_labels": self.show_labels,
            "show_trails": self.show_trails,
            "process_every_n_frames": self.process_every_n_frames,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CVSettings":
        backend_name = data.get("backend", "BACKGROUND_SUBTRACTION")
        backend = DetectionBackend[backend_name] if isinstance(backend_name, str) else DetectionBackend.BACKGROUND_SUBTRACTION

        return cls(
            enabled=data.get("enabled", True),
            backend=backend,
            model_path=data.get("model_path"),
            confidence_threshold=data.get("confidence_threshold", 0.5),
            min_detection_area=data.get("min_detection_area", 500),
            motion_threshold=data.get("motion_threshold", 25.0),
            motion_area_threshold=data.get("motion_area_threshold", 0.01),
            tracking_enabled=data.get("tracking_enabled", True),
            max_disappeared=data.get("max_disappeared", 50),
            draw_overlays=data.get("draw_overlays", True),
            overlay_color=tuple(data.get("overlay_color", [0, 255, 0])),
            overlay_thickness=data.get("overlay_thickness", 2),
            show_labels=data.get("show_labels", True),
            show_trails=data.get("show_trails", False),
            process_every_n_frames=data.get("process_every_n_frames", 1),
        )


class ObjectTracker:
    """
    Simple centroid-based multi-object tracker.

    Assigns persistent IDs to detected objects across frames
    using centroid distance matching.
    """

    def __init__(self, max_disappeared: int = 50):
        """
        Initialize the tracker.

        Args:
            max_disappeared: Maximum frames before dropping a track
        """
        self._next_id = 0
        self._objects: OrderedDict[int, TrackedObject] = OrderedDict()
        self._max_disappeared = max_disappeared

    def reset(self) -> None:
        """Reset the tracker, clearing all tracks."""
        self._next_id = 0
        self._objects.clear()

    def _register(self, detection: Detection) -> int:
        """Register a new object."""
        track_id = self._next_id
        self._objects[track_id] = TrackedObject(
            track_id=track_id,
            class_name=detection.class_name,
            bbox=detection.bbox,
            confidence=detection.confidence,
            centroid=detection.centroid,
            age=0,
            disappeared=0,
        )
        self._next_id += 1
        return track_id

    def _deregister(self, track_id: int) -> None:
        """Deregister an object."""
        del self._objects[track_id]

    def update(self, detections: List[Detection]) -> List[TrackedObject]:
        """
        Update tracker with new detections.

        Args:
            detections: List of detections from current frame

        Returns:
            List of currently tracked objects
        """
        # If no detections, mark all objects as disappeared
        if len(detections) == 0:
            for track_id in list(self._objects.keys()):
                self._objects[track_id].disappeared += 1
                if self._objects[track_id].disappeared > self._max_disappeared:
                    self._deregister(track_id)
            return list(self._objects.values())

        # If no existing objects, register all detections
        if len(self._objects) == 0:
            for detection in detections:
                self._register(detection)
            return list(self._objects.values())

        # Get current object IDs and centroids
        object_ids = list(self._objects.keys())
        object_centroids = [self._objects[oid].centroid for oid in object_ids]

        # Get detection centroids
        input_centroids = [d.centroid for d in detections]

        # Compute distance matrix
        D = dist.cdist(np.array(object_centroids), np.array(input_centroids))

        # Find minimum distance assignments
        rows = D.min(axis=1).argsort()
        cols = D.argmin(axis=1)[rows]

        used_rows = set()
        used_cols = set()

        for (row, col) in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue

            # Update existing object with new detection
            track_id = object_ids[row]
            detection = detections[col]

            self._objects[track_id].centroid = detection.centroid
            self._objects[track_id].bbox = detection.bbox
            self._objects[track_id].confidence = detection.confidence
            self._objects[track_id].class_name = detection.class_name
            self._objects[track_id].disappeared = 0
            self._objects[track_id].age += 1

            used_rows.add(row)
            used_cols.add(col)

        # Handle unmatched existing objects (disappeared)
        unused_rows = set(range(D.shape[0])) - used_rows
        for row in unused_rows:
            track_id = object_ids[row]
            self._objects[track_id].disappeared += 1
            if self._objects[track_id].disappeared > self._max_disappeared:
                self._deregister(track_id)

        # Handle unmatched detections (new objects)
        unused_cols = set(range(D.shape[1])) - used_cols
        for col in unused_cols:
            self._register(detections[col])

        return list(self._objects.values())


class CVProcessor:
    """
    Real-time computer vision processor.

    Provides configurable CV processing including:
    - Object detection (bounding boxes)
    - Multi-object tracking with persistent IDs
    - Motion detection

    Can be toggled on/off for performance.
    """

    def __init__(self, settings: Optional[CVSettings] = None):
        """
        Initialize the CV processor.

        Args:
            settings: CV settings, or None for defaults
        """
        self._settings = settings or CVSettings()
        self._bg_subtractor: Optional[cv2.BackgroundSubtractor] = None
        self._yolo_model = None
        self._tracker: Optional[ObjectTracker] = None
        self._initialized = False
        self._lock = threading.Lock()

        # Results callbacks
        self._detection_callbacks: List[Callable] = []
        self._tracking_callbacks: List[Callable] = []
        self._motion_callbacks: List[Callable] = []

        # Trail history for visualization
        self._trail_history: Dict[int, List[Tuple[int, int]]] = {}
        self._max_trail_length = 30

        # ByteTrack age tracking (since ByteTrack doesn't expose this)
        self._bytetrack_ages: Dict[int, int] = {}

        # Frame skipping state
        self._frame_counter = 0
        self._last_detections: List[Detection] = []
        self._last_tracked: List[TrackedObject] = []
        self._last_motion: MotionResult = MotionResult(False, 0.0)

        # Zone tracking
        self._zone_tracker: Optional[ZoneTracker] = None
        self._zone_config: Optional[ZoneConfiguration] = None
        self._zone_callbacks: List[Callable[[Dict[str, ZoneState]], None]] = []

    @property
    def settings(self) -> CVSettings:
        """Current CV settings."""
        return self._settings

    @property
    def is_initialized(self) -> bool:
        """Whether CV processor is initialized."""
        return self._initialized

    def set_zone_configuration(self, config: "ZoneConfiguration") -> None:
        """
        Set zone configuration for zone tracking.

        Args:
            config: ZoneConfiguration instance
        """
        from glider.vision.zones import ZoneTracker
        self._zone_config = config
        if config and config.zones:
            if self._zone_tracker is None:
                self._zone_tracker = ZoneTracker()
            self._zone_tracker.set_zone_configuration(config)
            logger.info(f"Set zone configuration with {len(config.zones)} zones")
        else:
            self._zone_tracker = None

    def get_zone_states(self) -> Dict[str, "ZoneState"]:
        """
        Get current zone states.

        Returns:
            Dictionary of zone_id -> ZoneState
        """
        if self._zone_tracker:
            return self._zone_tracker.get_zone_states()
        return {}

    def on_zone_update(self, callback: Callable[[Dict[str, "ZoneState"]], None]) -> None:
        """Register callback for zone state updates."""
        self._zone_callbacks.append(callback)

    def initialize(self) -> bool:
        """
        Initialize CV backends based on settings.

        Returns:
            True if initialization successful
        """
        try:
            with self._lock:
                # Initialize background subtractor
                if self._settings.backend in (
                    DetectionBackend.BACKGROUND_SUBTRACTION,
                    DetectionBackend.MOTION_ONLY
                ):
                    self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                        history=500,
                        varThreshold=self._settings.motion_threshold,
                        detectShadows=True
                    )
                    logger.info("Initialized background subtractor")

                # Initialize YOLO if selected
                elif self._settings.backend in (DetectionBackend.YOLO_V8, DetectionBackend.YOLO_BYTETRACK):
                    self._load_yolo_model()

                # Initialize tracker
                if self._settings.tracking_enabled:
                    self._tracker = ObjectTracker(
                        max_disappeared=self._settings.max_disappeared
                    )
                    logger.info("Initialized object tracker")

                self._initialized = True
                return True

        except Exception as e:
            logger.error(f"CV initialization failed: {e}")
            return False

    def _load_yolo_model(self) -> None:
        """Load YOLO model for detection."""
        try:
            from ultralytics import YOLO
            model_path = self._settings.model_path or "yolov8n.pt"
            self._yolo_model = YOLO(model_path)
            logger.info(f"Loaded YOLO model: {model_path}")
        except ImportError:
            logger.warning(
                "ultralytics not installed, falling back to background subtraction. "
                "Install with: pip install ultralytics"
            )
            self._settings.backend = DetectionBackend.BACKGROUND_SUBTRACTION
            self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=500,
                varThreshold=self._settings.motion_threshold,
                detectShadows=True
            )
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self._settings.backend = DetectionBackend.BACKGROUND_SUBTRACTION
            self._bg_subtractor = cv2.createBackgroundSubtractorMOG2()

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp: float
    ) -> Tuple[List[Detection], List[TrackedObject], MotionResult]:
        """
        Process a frame for detections, tracking, and motion.

        Args:
            frame: BGR image from camera
            timestamp: Frame timestamp

        Returns:
            Tuple of (detections, tracked_objects, motion_result)
        """
        if not self._settings.enabled:
            return [], [], MotionResult(False, 0.0)

        if not self._initialized:
            self.initialize()

        # Frame skipping for performance
        self._frame_counter += 1
        skip_n = self._settings.process_every_n_frames
        if skip_n > 1 and (self._frame_counter % skip_n) != 1:
            # Return cached results (but don't fire callbacks for skipped frames)
            return self._last_detections, self._last_tracked, self._last_motion

        with self._lock:
            # Run detection
            detections = self._detect(frame)

            # Run tracking
            tracked = []
            if self._settings.tracking_enabled:
                # ByteTrack provides its own tracking - convert detections to TrackedObjects
                if self._settings.backend == DetectionBackend.YOLO_BYTETRACK:
                    tracked = self._bytetrack_to_tracked(detections)
                elif self._tracker:
                    # Use centroid tracker for other backends
                    tracked = self._tracker.update(detections)

                # Update trail history
                self._update_trails(tracked)

            # Run motion detection
            motion = self._detect_motion(frame)

            # Update zone tracking
            zone_states = {}
            if self._zone_tracker and tracked:
                h, w = frame.shape[:2]
                zone_states = self._zone_tracker.update(tracked, w, h)

            # Cache results for frame skipping
            self._last_detections = detections
            self._last_tracked = tracked
            self._last_motion = motion

        # Notify zone callbacks
        if zone_states:
            for cb in self._zone_callbacks:
                try:
                    cb(zone_states)
                except Exception as e:
                    logger.error(f"Zone callback error: {e}")

        # Notify callbacks
        for cb in self._detection_callbacks:
            try:
                cb(detections, timestamp)
            except Exception as e:
                logger.error(f"Detection callback error: {e}")

        for cb in self._tracking_callbacks:
            try:
                cb(tracked, timestamp)
            except Exception as e:
                logger.error(f"Tracking callback error: {e}")

        for cb in self._motion_callbacks:
            try:
                cb(motion, timestamp)
            except Exception as e:
                logger.error(f"Motion callback error: {e}")

        return detections, tracked, motion

    def _detect(self, frame: np.ndarray) -> List[Detection]:
        """Run detection on frame."""
        if self._settings.backend == DetectionBackend.YOLO_V8 and self._yolo_model:
            return self._detect_yolo(frame)
        elif self._settings.backend == DetectionBackend.YOLO_BYTETRACK and self._yolo_model:
            return self._detect_yolo_bytetrack(frame)
        elif self._settings.backend == DetectionBackend.MOTION_ONLY:
            return []  # Motion-only mode, no object detection
        else:
            return self._detect_background_subtraction(frame)

    def _detect_yolo(self, frame: np.ndarray) -> List[Detection]:
        """YOLO-based detection."""
        if self._yolo_model is None:
            return []

        results = self._yolo_model(
            frame,
            conf=self._settings.confidence_threshold,
            verbose=False
        )

        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                class_id = int(box.cls)
                detections.append(Detection(
                    class_id=class_id,
                    class_name=r.names[class_id],
                    confidence=float(box.conf),
                    bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1))
                ))
        return detections

    def _bytetrack_to_tracked(self, detections: List[Detection]) -> List[TrackedObject]:
        """
        Convert ByteTrack detection results to TrackedObjects.

        ByteTrack assigns persistent IDs via the model.track() method,
        so we just need to convert the format.
        """
        tracked = []
        for det in detections:
            if det.track_id is not None:
                # Update age tracking for ByteTrack objects
                if det.track_id not in self._bytetrack_ages:
                    self._bytetrack_ages[det.track_id] = 0
                self._bytetrack_ages[det.track_id] += 1

                tracked.append(TrackedObject(
                    track_id=det.track_id,
                    class_name=det.class_name,
                    bbox=det.bbox,
                    confidence=det.confidence,
                    centroid=det.centroid,
                    age=self._bytetrack_ages[det.track_id],
                    disappeared=0
                ))
        return tracked

    def _detect_yolo_bytetrack(self, frame: np.ndarray) -> List[Detection]:
        """
        YOLO detection with ByteTrack multi-object tracking.

        Uses ultralytics built-in ByteTrack tracker for robust
        multi-object tracking with persistent IDs across frames.
        """
        if self._yolo_model is None:
            return []

        # Use model.track() for ByteTrack integration
        results = self._yolo_model.track(
            frame,
            conf=self._settings.confidence_threshold,
            persist=True,  # Persist tracks across frames
            tracker="bytetrack.yaml",  # Use ByteTrack
            verbose=False
        )

        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for i, box in enumerate(r.boxes):
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                class_id = int(box.cls)

                # Get track ID if available (ByteTrack assigns these)
                track_id = None
                if box.id is not None:
                    track_id = int(box.id[0])

                detection = Detection(
                    class_id=class_id,
                    class_name=r.names[class_id],
                    confidence=float(box.conf),
                    bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                    track_id=track_id
                )
                detections.append(detection)

        return detections

    def _detect_background_subtraction(self, frame: np.ndarray) -> List[Detection]:
        """Background subtraction based detection."""
        if self._bg_subtractor is None:
            return []

        # Apply background subtraction
        fg_mask = self._bg_subtractor.apply(frame)

        # Threshold to remove shadows (shadows are gray, foreground is white)
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > self._settings.min_detection_area:
                x, y, w, h = cv2.boundingRect(contour)
                # Confidence based on contour area
                confidence = min(1.0, area / 10000)
                detections.append(Detection(
                    class_id=0,
                    class_name="object",
                    confidence=confidence,
                    bbox=(x, y, w, h)
                ))

        return detections

    def _detect_motion(self, frame: np.ndarray) -> MotionResult:
        """Detect motion in frame."""
        if self._bg_subtractor is None:
            return MotionResult(False, 0.0)

        # Get foreground mask
        fg_mask = self._bg_subtractor.apply(frame)

        # Calculate motion area
        motion_pixels = np.sum(fg_mask > 200)
        total_pixels = fg_mask.size
        motion_area = motion_pixels / total_pixels

        # Find motion contours
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        return MotionResult(
            motion_detected=motion_area > self._settings.motion_area_threshold,
            motion_area=motion_area,
            motion_contours=contours,
            motion_mask=fg_mask
        )

    def _update_trails(self, tracked: List[TrackedObject]) -> None:
        """Update trail history for tracked objects."""
        current_ids = set()
        for obj in tracked:
            current_ids.add(obj.track_id)
            if obj.track_id not in self._trail_history:
                self._trail_history[obj.track_id] = []
            self._trail_history[obj.track_id].append(obj.centroid)
            # Limit trail length
            if len(self._trail_history[obj.track_id]) > self._max_trail_length:
                self._trail_history[obj.track_id].pop(0)

        # Remove trails for objects no longer tracked
        for track_id in list(self._trail_history.keys()):
            if track_id not in current_ids:
                del self._trail_history[track_id]

    def draw_overlays(
        self,
        frame: np.ndarray,
        detections: List[Detection],
        tracked: List[TrackedObject],
        motion: Optional[MotionResult] = None
    ) -> np.ndarray:
        """
        Draw detection/tracking overlays on frame.

        Args:
            frame: Input frame
            detections: Detection results
            tracked: Tracking results
            motion: Optional motion result

        Returns:
            Frame with overlays drawn
        """
        if not self._settings.draw_overlays:
            return frame

        output = frame.copy()
        color = self._settings.overlay_color
        thickness = self._settings.overlay_thickness

        # Draw tracked objects (preferred over raw detections)
        if tracked:
            for obj in tracked:
                x, y, w, h = obj.bbox
                cv2.rectangle(output, (x, y), (x + w, y + h), color, thickness)

                if self._settings.show_labels:
                    label = f"ID:{obj.track_id} {obj.class_name}"
                    label_size, _ = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                    )
                    cv2.rectangle(
                        output,
                        (x, y - label_size[1] - 10),
                        (x + label_size[0], y),
                        color,
                        -1
                    )
                    cv2.putText(
                        output, label, (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1
                    )

                # Draw trail
                if self._settings.show_trails and obj.track_id in self._trail_history:
                    trail = self._trail_history[obj.track_id]
                    for i in range(1, len(trail)):
                        alpha = i / len(trail)
                        pt1 = trail[i - 1]
                        pt2 = trail[i]
                        cv2.line(output, pt1, pt2, color, max(1, int(thickness * alpha)))

        # Draw raw detections if no tracking
        elif detections:
            for det in detections:
                x, y, w, h = det.bbox
                cv2.rectangle(output, (x, y), (x + w, y + h), color, thickness)

                if self._settings.show_labels:
                    label = f"{det.class_name} {det.confidence:.2f}"
                    cv2.putText(
                        output, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, thickness
                    )

        return output

    def on_detection(self, callback: Callable[[List[Detection], float], None]) -> None:
        """Register callback for detection results."""
        self._detection_callbacks.append(callback)

    def on_tracking(self, callback: Callable[[List[TrackedObject], float], None]) -> None:
        """Register callback for tracking results."""
        self._tracking_callbacks.append(callback)

    def on_motion(self, callback: Callable[[MotionResult, float], None]) -> None:
        """Register callback for motion results."""
        self._motion_callbacks.append(callback)

    def update_settings(self, settings: CVSettings) -> None:
        """
        Update CV settings (may require reinitialization).

        Args:
            settings: New settings to apply
        """
        old_backend = self._settings.backend
        self._settings = settings

        # Reinitialize if backend changed
        if old_backend != settings.backend:
            self._initialized = False
            self.initialize()

        # Update tracker settings
        if self._tracker:
            self._tracker._max_disappeared = settings.max_disappeared

    def reset(self) -> None:
        """Reset the processor state."""
        if self._tracker:
            self._tracker.reset()
        self._trail_history.clear()
        self._bytetrack_ages.clear()
        # Reset frame skipping state
        self._frame_counter = 0
        self._last_detections = []
        self._last_tracked = []
        self._last_motion = MotionResult(False, 0.0)
        # Reset zone tracker
        if self._zone_tracker:
            self._zone_tracker.reset()
        if self._bg_subtractor:
            # Recreate background subtractor to reset learning
            self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=500,
                varThreshold=self._settings.motion_threshold,
                detectShadows=True
            )
