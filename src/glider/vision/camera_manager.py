"""
Camera Manager - Enumerate and manage webcam devices.

Provides thread-safe webcam capture with configurable settings
and frame callbacks for video recording and CV processing.
"""

import cv2
import numpy as np
import threading
import time
import logging
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
from enum import Enum, auto
from queue import Queue, Empty

logger = logging.getLogger(__name__)


def _get_camera_backend() -> int:
    """Get the appropriate camera backend for the current platform."""
    if sys.platform == "win32":
        return cv2.CAP_DSHOW
    elif sys.platform == "linux":
        return cv2.CAP_V4L2
    else:
        # macOS and others - let OpenCV auto-select
        return cv2.CAP_ANY


@dataclass
class CameraInfo:
    """Information about an available camera."""
    index: int
    name: str
    resolutions: List[Tuple[int, int]] = field(default_factory=list)
    max_fps: float = 30.0
    is_available: bool = True

    def __str__(self) -> str:
        return f"{self.name} (Index {self.index})"


@dataclass
class CameraSettings:
    """Camera configuration settings."""
    camera_index: int = 0
    resolution: Tuple[int, int] = (640, 480)
    fps: int = 30
    exposure: int = -1  # -1 = auto
    brightness: int = 128
    contrast: int = 128
    saturation: int = 128
    auto_focus: bool = True
    auto_exposure: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "camera_index": self.camera_index,
            "resolution": list(self.resolution),
            "fps": self.fps,
            "exposure": self.exposure,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "auto_focus": self.auto_focus,
            "auto_exposure": self.auto_exposure,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CameraSettings":
        """Deserialize from dictionary."""
        return cls(
            camera_index=data.get("camera_index", 0),
            resolution=tuple(data.get("resolution", [640, 480])),
            fps=data.get("fps", 30),
            exposure=data.get("exposure", -1),
            brightness=data.get("brightness", 128),
            contrast=data.get("contrast", 128),
            saturation=data.get("saturation", 128),
            auto_focus=data.get("auto_focus", True),
            auto_exposure=data.get("auto_exposure", True),
        )


class CameraState(Enum):
    """State of the camera connection."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    STREAMING = auto()
    ERROR = auto()


class CameraManager:
    """
    Manages camera devices for video capture.

    Features:
    - Enumerate available webcams
    - Thread-safe frame capture
    - Configurable camera settings
    - Frame callbacks for processing pipelines
    """

    # Common resolutions to test
    COMMON_RESOLUTIONS = [
        (640, 480),
        (800, 600),
        (1280, 720),
        (1920, 1080),
    ]

    def __init__(self):
        """Initialize the camera manager."""
        self._capture: Optional[cv2.VideoCapture] = None
        self._settings = CameraSettings()
        self._state = CameraState.DISCONNECTED
        self._capture_thread: Optional[threading.Thread] = None
        self._frame_queue: Queue = Queue(maxsize=2)  # Double buffer
        self._running = False
        self._frame_callbacks: List[Callable[[np.ndarray, float], None]] = []
        self._lock = threading.Lock()
        self._last_frame: Optional[np.ndarray] = None
        self._last_timestamp: float = 0.0
        self._fps_counter = 0
        self._fps_timer = time.time()
        self._current_fps = 0.0

    @property
    def state(self) -> CameraState:
        """Current camera state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Whether a camera is connected."""
        return self._state in (CameraState.CONNECTED, CameraState.STREAMING)

    @property
    def is_streaming(self) -> bool:
        """Whether camera is actively streaming."""
        return self._state == CameraState.STREAMING

    @property
    def settings(self) -> CameraSettings:
        """Current camera settings."""
        return self._settings

    @property
    def current_fps(self) -> float:
        """Current frames per second."""
        return self._current_fps

    @staticmethod
    def enumerate_cameras(max_cameras: int = 10) -> List[CameraInfo]:
        """
        Enumerate all available camera devices.

        Args:
            max_cameras: Maximum number of camera indices to check

        Returns:
            List of available cameras
        """
        cameras = []

        # Suppress OpenCV warnings during enumeration by redirecting stderr
        import sys
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        try:
            backend = _get_camera_backend()
            for i in range(max_cameras):
                # Use platform-appropriate backend
                cap = cv2.VideoCapture(i, backend)
                if cap.isOpened():
                    # Try to get camera name (not always available)
                    name = f"Camera {i}"

                    # Test which resolutions are supported
                    supported_resolutions = []
                    for res in CameraManager.COMMON_RESOLUTIONS:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, res[0])
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
                        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        if (actual_w, actual_h) == res:
                            supported_resolutions.append(res)

                    # Get max FPS
                    max_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

                    cameras.append(CameraInfo(
                        index=i,
                        name=name,
                        resolutions=supported_resolutions or [(640, 480)],
                        max_fps=max_fps,
                        is_available=True
                    ))
                    cap.release()
        finally:
            # Restore stderr
            sys.stderr = old_stderr

        logger.info(f"Found {len(cameras)} camera(s)")
        return cameras

    def connect(self, settings: Optional[CameraSettings] = None) -> bool:
        """
        Connect to a camera with given settings.

        Args:
            settings: Camera settings to apply, or None for defaults

        Returns:
            True if connection successful
        """
        if self._state == CameraState.STREAMING:
            self.stop_streaming()

        if self._capture is not None:
            self._capture.release()

        self._state = CameraState.CONNECTING

        if settings is not None:
            self._settings = settings

        try:
            # Use platform-appropriate backend
            backend = _get_camera_backend()
            self._capture = cv2.VideoCapture(
                self._settings.camera_index,
                backend
            )

            if not self._capture.isOpened():
                logger.error(f"Failed to open camera {self._settings.camera_index}")
                self._state = CameraState.ERROR
                return False

            # Set buffer size to reduce latency (especially helpful for V4L2)
            if backend == cv2.CAP_V4L2:
                self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Apply settings
            self._apply_camera_settings()

            # Warmup: grab a few frames to flush the buffer
            # This is especially important for V4L2 on Linux
            for _ in range(5):
                self._capture.grab()

            self._state = CameraState.CONNECTED
            logger.info(f"Connected to camera {self._settings.camera_index}")
            return True

        except Exception as e:
            logger.error(f"Camera connection error: {e}")
            self._state = CameraState.ERROR
            return False

    def disconnect(self) -> None:
        """Disconnect from the current camera."""
        if self._state == CameraState.STREAMING:
            self.stop_streaming()

        if self._capture is not None:
            self._capture.release()
            self._capture = None

        self._state = CameraState.DISCONNECTED
        self._last_frame = None
        logger.info("Camera disconnected")

    def start_streaming(self) -> bool:
        """
        Start capturing frames in background thread.

        Returns:
            True if streaming started successfully
        """
        if self._state == CameraState.STREAMING:
            return True

        if self._capture is None or not self._capture.isOpened():
            logger.error("Cannot start streaming: camera not connected")
            return False

        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="CameraCapture"
        )
        self._capture_thread.start()

        self._state = CameraState.STREAMING
        logger.info("Camera streaming started")
        return True

    def stop_streaming(self) -> None:
        """Stop frame capture."""
        if not self._running:
            return

        self._running = False

        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)
            self._capture_thread = None

        # Clear queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Empty:
                break

        if self._state == CameraState.STREAMING:
            self._state = CameraState.CONNECTED

        logger.info("Camera streaming stopped")

    def get_frame(self) -> Optional[Tuple[np.ndarray, float]]:
        """
        Get the latest frame (non-blocking).

        Returns:
            Tuple of (frame, timestamp) or None if no frame available
        """
        try:
            return self._frame_queue.get_nowait()
        except Empty:
            # Return last frame if available
            if self._last_frame is not None:
                return (self._last_frame.copy(), self._last_timestamp)
            return None

    def on_frame(self, callback: Callable[[np.ndarray, float], None]) -> None:
        """
        Register callback for each new frame.

        Args:
            callback: Function called with (frame, timestamp) for each frame
        """
        self._frame_callbacks.append(callback)

    def remove_frame_callback(self, callback: Callable[[np.ndarray, float], None]) -> None:
        """Remove a frame callback."""
        if callback in self._frame_callbacks:
            self._frame_callbacks.remove(callback)

    def apply_settings(self, settings: CameraSettings) -> None:
        """
        Apply new camera settings.

        Args:
            settings: New settings to apply
        """
        old_index = self._settings.camera_index
        self._settings = settings

        # If camera index changed, reconnect
        if old_index != settings.camera_index:
            was_streaming = self._state == CameraState.STREAMING
            self.disconnect()
            self.connect(settings)
            if was_streaming:
                self.start_streaming()
        elif self._capture is not None and self._capture.isOpened():
            self._apply_camera_settings()

    def _apply_camera_settings(self) -> None:
        """Apply current settings to the camera."""
        if self._capture is None:
            return

        # On Linux with V4L2, set MJPEG format for better compatibility
        if sys.platform == "linux":
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            self._capture.set(cv2.CAP_PROP_FOURCC, fourcc)

        # Resolution
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._settings.resolution[0])
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._settings.resolution[1])

        # FPS
        self._capture.set(cv2.CAP_PROP_FPS, self._settings.fps)

        # Exposure
        if self._settings.auto_exposure:
            self._capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        else:
            self._capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self._capture.set(cv2.CAP_PROP_EXPOSURE, self._settings.exposure)

        # Brightness, contrast, saturation
        self._capture.set(cv2.CAP_PROP_BRIGHTNESS, self._settings.brightness)
        self._capture.set(cv2.CAP_PROP_CONTRAST, self._settings.contrast)
        self._capture.set(cv2.CAP_PROP_SATURATION, self._settings.saturation)

        # Auto focus
        if self._settings.auto_focus:
            self._capture.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        else:
            self._capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)

        # Verify resolution
        actual_w = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (actual_w, actual_h) != self._settings.resolution:
            logger.warning(
                f"Requested {self._settings.resolution}, got ({actual_w}, {actual_h})"
            )
            self._settings.resolution = (actual_w, actual_h)

        logger.debug(f"Applied camera settings: {self._settings.resolution} @ {self._settings.fps}fps")

    def _capture_loop(self) -> None:
        """Background thread for frame capture."""
        logger.debug("Capture loop started")

        while self._running:
            if self._capture is None or not self._capture.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self._capture.read()
            if not ret:
                logger.warning("Failed to read frame")
                time.sleep(0.01)
                continue

            timestamp = time.time()

            # Update FPS counter
            self._fps_counter += 1
            elapsed = timestamp - self._fps_timer
            if elapsed >= 1.0:
                self._current_fps = self._fps_counter / elapsed
                self._fps_counter = 0
                self._fps_timer = timestamp

            # Store last frame
            with self._lock:
                self._last_frame = frame.copy()
                self._last_timestamp = timestamp

            # Update queue (drop old frames if full)
            if self._frame_queue.full():
                try:
                    self._frame_queue.get_nowait()
                except Empty:
                    pass
            self._frame_queue.put((frame, timestamp))

            # Notify callbacks
            for callback in self._frame_callbacks:
                try:
                    callback(frame, timestamp)
                except Exception as e:
                    logger.error(f"Frame callback error: {e}")

        logger.debug("Capture loop ended")

    def capture_single_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame (blocking).

        Useful for taking snapshots without streaming.

        Returns:
            Frame as numpy array, or None if capture failed
        """
        if self._capture is None or not self._capture.isOpened():
            return None

        ret, frame = self._capture.read()
        return frame if ret else None

    def get_property(self, prop_id: int) -> float:
        """Get a camera property value."""
        if self._capture is None:
            return 0.0
        return self._capture.get(prop_id)

    def set_property(self, prop_id: int, value: float) -> bool:
        """Set a camera property value."""
        if self._capture is None:
            return False
        return self._capture.set(prop_id, value)
