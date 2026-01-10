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


def _is_raspberry_pi() -> bool:
    """Check if running on a Raspberry Pi."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().lower()
            return 'raspberry pi' in model
    except (FileNotFoundError, PermissionError):
        return False


# Picamera2 is imported lazily to avoid crashes from numpy version conflicts
_picamera2_available = None  # None = not checked yet, True/False = checked
_Picamera2 = None  # Will hold the class if available


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
        self._picamera2 = None  # Picamera2 instance for Pi cameras
        self._using_picamera2 = False
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

    def _try_connect_with_backend(self, backend: int) -> bool:
        """
        Try to connect to the camera with a specific backend.

        Args:
            backend: OpenCV backend (e.g., cv2.CAP_V4L2, cv2.CAP_ANY)

        Returns:
            True if connection successful and frames can be read
        """
        if self._capture is not None:
            self._capture.release()

        self._capture = cv2.VideoCapture(
            self._settings.camera_index,
            backend
        )

        if not self._capture.isOpened():
            logger.debug(f"Failed to open camera with backend {backend}")
            return False

        # Set buffer size to reduce latency (especially helpful for V4L2)
        if backend == cv2.CAP_V4L2:
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Apply settings
        self._apply_camera_settings()

        # Warmup and verify we can actually read frames
        success_count = 0
        for _ in range(10):
            if self._capture.grab():
                ret, frame = self._capture.retrieve()
                if ret and frame is not None:
                    success_count += 1
                    if success_count >= 3:
                        logger.debug(f"Camera working with backend {backend}")
                        return True
            time.sleep(0.05)

        logger.debug(f"Camera opened but failed to read frames with backend {backend}")
        self._capture.release()
        self._capture = None
        return False

    def _try_connect_picamera2(self) -> bool:
        """
        Try to connect using picamera2 (for Raspberry Pi camera modules).

        Returns:
            True if connection successful and frames can be read
        """
        global _picamera2_available, _Picamera2

        # Lazy import of picamera2 to avoid crashes from numpy version conflicts
        if _picamera2_available is None:
            try:
                from picamera2 import Picamera2
                _Picamera2 = Picamera2
                _picamera2_available = True
                logger.debug("picamera2 imported successfully")
            except (ImportError, ValueError) as e:
                logger.debug(f"picamera2 not available: {e}")
                _picamera2_available = False

        if not _picamera2_available:
            logger.debug("picamera2 not available")
            return False

        try:
            # Clean up any existing capture
            if self._capture is not None:
                self._capture.release()
                self._capture = None

            if self._picamera2 is not None:
                self._picamera2.close()
                self._picamera2 = None

            # Create Picamera2 instance
            self._picamera2 = _Picamera2()

            # Configure for video capture
            width, height = self._settings.resolution
            config = self._picamera2.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"},
                controls={"FrameRate": self._settings.fps}
            )
            self._picamera2.configure(config)

            # Start the camera
            self._picamera2.start()
            time.sleep(0.5)  # Give camera time to warm up

            # Verify we can capture frames
            for _ in range(5):
                frame = self._picamera2.capture_array()
                if frame is not None and frame.size > 0:
                    # Update resolution to actual
                    self._settings.resolution = (frame.shape[1], frame.shape[0])
                    self._using_picamera2 = True
                    logger.info(f"picamera2 working: {self._settings.resolution}")
                    return True
                time.sleep(0.1)

            # Failed to get frames
            self._picamera2.close()
            self._picamera2 = None
            return False

        except Exception as e:
            logger.debug(f"picamera2 failed: {e}")
            if self._picamera2 is not None:
                try:
                    self._picamera2.close()
                except Exception:
                    pass
                self._picamera2 = None
            return False

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

            # On Raspberry Pi, try picamera2 first (for Pi Camera modules)
            if _is_raspberry_pi():
                logger.info("Raspberry Pi detected, trying picamera2 first")
                if self._try_connect_picamera2():
                    self._state = CameraState.CONNECTED
                    logger.info(f"Connected to Pi camera via picamera2")
                    return True
                logger.info("picamera2 failed, falling back to V4L2")

            # Try connecting with the preferred backend
            if not self._try_connect_with_backend(backend):
                # If V4L2 failed on Linux, try CAP_ANY as fallback
                if backend == cv2.CAP_V4L2:
                    logger.info("V4L2 failed, trying auto-detect backend")
                    if not self._try_connect_with_backend(cv2.CAP_ANY):
                        self._state = CameraState.ERROR
                        return False
                else:
                    self._state = CameraState.ERROR
                    return False

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

        if self._picamera2 is not None:
            try:
                self._picamera2.close()
            except Exception:
                pass
            self._picamera2 = None
            self._using_picamera2 = False

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

        # Check if we have a valid capture source
        has_opencv = self._capture is not None and self._capture.isOpened()
        has_picamera2 = self._using_picamera2 and self._picamera2 is not None

        if not has_opencv and not has_picamera2:
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

        # On Linux with V4L2, try MJPEG format for better compatibility
        # Some cameras don't support it, so we don't fail if it doesn't work
        if sys.platform == "linux":
            try:
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                self._capture.set(cv2.CAP_PROP_FOURCC, fourcc)
            except Exception:
                pass  # Camera may not support MJPEG, that's okay

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
        consecutive_failures = 0
        max_failures_before_log = 30  # Only log every 30 failures to avoid spam

        while self._running:
            frame = None

            # Handle picamera2
            if self._using_picamera2 and self._picamera2 is not None:
                try:
                    frame = self._picamera2.capture_array()
                    # picamera2 returns RGB, convert to BGR for OpenCV compatibility
                    if frame is not None:
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                except Exception as e:
                    consecutive_failures += 1
                    if consecutive_failures == 1 or consecutive_failures % max_failures_before_log == 0:
                        logger.warning(f"picamera2 capture failed: {e}")
                    time.sleep(0.01)
                    continue
            # Handle OpenCV capture
            elif self._capture is not None and self._capture.isOpened():
                # Use grab() + retrieve() which works better with V4L2 on Linux
                if not self._capture.grab():
                    consecutive_failures += 1
                    if consecutive_failures == 1 or consecutive_failures % max_failures_before_log == 0:
                        logger.warning(f"Failed to grab frame (attempt {consecutive_failures})")
                    time.sleep(0.01)
                    continue

                ret, frame = self._capture.retrieve()
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures == 1 or consecutive_failures % max_failures_before_log == 0:
                        logger.warning(f"Failed to retrieve frame (attempt {consecutive_failures})")
                    time.sleep(0.01)
                    continue
            else:
                time.sleep(0.1)
                continue

            if frame is None:
                consecutive_failures += 1
                time.sleep(0.01)
                continue

            consecutive_failures = 0  # Reset on success

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
