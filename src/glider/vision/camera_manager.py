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


def _wake_up_miniscope(device_index: int) -> bool:
    """
    Wake up miniscope hardware using v4l2-ctl commands.

    Miniscopes require specific initialization to turn on the LED
    and configure the sensor properly.

    Args:
        device_index: Camera device index (e.g., 2 for /dev/video2)

    Returns:
        True if wake-up commands succeeded
    """
    import subprocess

    device_path = f'/dev/video{device_index}'

    try:
        # Set exposure time
        subprocess.run(
            ['v4l2-ctl', '-d', device_path, '--set-ctrl=exposure_time_absolute=100'],
            capture_output=True, timeout=2
        )
        # Reset saturation to kick the LED
        subprocess.run(
            ['v4l2-ctl', '-d', device_path, '--set-ctrl=saturation=0'],
            capture_output=True, timeout=2
        )
        time.sleep(0.1)
        subprocess.run(
            ['v4l2-ctl', '-d', device_path, '--set-ctrl=saturation=128'],
            capture_output=True, timeout=2
        )
        # Set brightness
        subprocess.run(
            ['v4l2-ctl', '-d', device_path, '--set-ctrl=brightness=50'],
            capture_output=True, timeout=2
        )
        logger.info(f"Miniscope wake-up sequence completed for {device_path}")
        return True
    except FileNotFoundError:
        logger.warning("v4l2-ctl not found - miniscope wake-up skipped")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("Miniscope wake-up timed out")
        return False
    except Exception as e:
        logger.warning(f"Miniscope wake-up failed: {e}")
        return False


def _apply_miniscope_controls(device_index: int, settings: "CameraSettings") -> bool:
    """
    Apply all miniscope camera controls via v4l2-ctl.

    Args:
        device_index: Camera device index (e.g., 2 for /dev/video2)
        settings: Camera settings containing control values

    Returns:
        True if controls were applied successfully
    """
    import subprocess

    device_path = f'/dev/video{device_index}'

    # Map settings to v4l2-ctl control names
    controls = {
        'brightness': settings.brightness,
        'contrast': settings.contrast,
        'saturation': settings.saturation,
        'hue': settings.hue,
        'gamma': settings.gamma,
        'gain': settings.gain,
        'sharpness': settings.sharpness,
        'exposure_time_absolute': settings.exposure_time,
        'focus_absolute': settings.focus,
        'zoom_absolute': settings.zoom,
        'iris_absolute': settings.iris,
    }

    try:
        for ctrl_name, ctrl_value in controls.items():
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, f'--set-ctrl={ctrl_name}={ctrl_value}'],
                capture_output=True, timeout=2, text=True
            )
            if result.returncode != 0 and result.stderr:
                # Some controls may not be supported - log but don't fail
                logger.debug(f"Control {ctrl_name} not applied: {result.stderr.strip()}")

        logger.info(f"Applied miniscope controls to {device_path}")
        return True
    except FileNotFoundError:
        logger.warning("v4l2-ctl not found - miniscope controls not applied")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("Miniscope control application timed out")
        return False
    except Exception as e:
        logger.warning(f"Failed to apply miniscope controls: {e}")
        return False


def _send_miniscope_i2c_command(
    device_index: int,
    contrast: int,
    gamma: int,
    sharpness: int
) -> bool:
    """
    Send an I2C command to Miniscope V4 via UVC control tunnel.

    The Miniscope DAQ uses Contrast/Gamma/Sharpness UVC controls as a tunnel
    to send arbitrary I2C commands to the hardware. The byte layout is:
    - Sharpness: data2 | data1
    - Gamma: data0 | reg0
    - Contrast: packet_length | i2c_address

    Note: Contrast and Gamma values must be divided by 100 due to UVC scaling.

    Args:
        device_index: Camera device index
        contrast: Contrast value (packet_length << 8 | i2c_address)
        gamma: Gamma value (data0 << 8 | reg0)
        sharpness: Sharpness value (data2 << 8 | data1)

    Returns:
        True if command was sent successfully
    """
    import subprocess

    device_path = f'/dev/video{device_index}'

    # UVC controls are scaled by 100 for contrast and gamma
    contrast_scaled = contrast / 100.0
    gamma_scaled = gamma / 100.0

    try:
        # Set sharpness first (no scaling needed)
        subprocess.run(
            ['v4l2-ctl', '-d', device_path, f'--set-ctrl=sharpness={sharpness}'],
            capture_output=True, timeout=2
        )
        # Set gamma (scaled)
        subprocess.run(
            ['v4l2-ctl', '-d', device_path, f'--set-ctrl=gamma={gamma_scaled}'],
            capture_output=True, timeout=2
        )
        # Set contrast last (triggers the I2C transaction)
        subprocess.run(
            ['v4l2-ctl', '-d', device_path, f'--set-ctrl=contrast={contrast_scaled}'],
            capture_output=True, timeout=2
        )
        return True
    except Exception as e:
        logger.debug(f"I2C command failed: {e}")
        return False


def _set_miniscope_led(device_index: int, power_percent: int) -> bool:
    """
    Set Miniscope V4 LED power.

    LED control requires two I2C commands:
    1. MCU (address 0x20): Enable/disable LED driver
    2. Digital potentiometer (address 0x58): Set brightness

    Args:
        device_index: Camera device index
        power_percent: LED power 0-100 (0=off, 100=max brightness)

    Returns:
        True if LED was set successfully
    """
    # Convert percentage to hardware value (0-255, where 255=off, 0=brightest)
    # Clamp to valid range
    power_percent = max(0, min(100, power_percent))

    if power_percent == 0:
        # Turn off LED
        led_value = 255
    else:
        # Map 1-100% to 254-0 (inverted, brighter = lower value)
        led_value = int(255 - (power_percent * 255 / 100))
        led_value = max(0, min(254, led_value))

    logger.debug(f"Setting LED power: {power_percent}% -> hardware value {led_value}")

    # Command 1: MCU (address 0x20)
    # Sets LED enable state - register 0x01
    # Format: contrast=0x0320, gamma=(led_value<<8)|0x01, sharpness=0x0000
    contrast1 = 0x0320  # length=3, address=0x20
    gamma1 = (led_value << 8) | 0x01  # led_value, register 0x01
    sharpness1 = 0x0000

    success1 = _send_miniscope_i2c_command(device_index, contrast1, gamma1, sharpness1)

    # Small delay between commands
    time.sleep(0.05)

    # Command 2: Digital potentiometer (address 0x58)
    # Sets brightness via voltage divider
    # Format: contrast=0x0458, gamma=0x7200, sharpness=led_value
    # The 0x72 (114) is a hardcoded value for the voltage divider reference
    contrast2 = 0x0458  # length=4, address=0x58
    gamma2 = 0x7200  # hardcoded 0x72, register 0x00
    sharpness2 = led_value

    success2 = _send_miniscope_i2c_command(device_index, contrast2, gamma2, sharpness2)

    if success1 and success2:
        logger.info(f"Miniscope LED set to {power_percent}%")
    else:
        logger.warning(f"Failed to set Miniscope LED (cmd1={success1}, cmd2={success2})")

    return success1 and success2


def _set_miniscope_ewl_focus(device_index: int, focus_value: int) -> bool:
    """
    Set Miniscope V4 electrowetting lens (EWL) focus.

    Args:
        device_index: Camera device index
        focus_value: Focus position 0-255

    Returns:
        True if focus was set successfully
    """
    # Clamp to valid range
    focus_value = max(0, min(255, focus_value))

    logger.debug(f"Setting EWL focus to {focus_value}")

    # EWL focus command
    # Address 0xEE, register 0x08
    # Format: contrast=0x04EE, gamma=(focus_value<<8)|0x08, sharpness=0x0002
    contrast = 0x04EE  # length=4, address=0xEE
    gamma = (focus_value << 8) | 0x08  # focus value, register 0x08
    sharpness = 0x0002  # data for EWL

    success = _send_miniscope_i2c_command(device_index, contrast, gamma, sharpness)

    if success:
        logger.info(f"Miniscope EWL focus set to {focus_value}")
    else:
        logger.warning(f"Failed to set Miniscope EWL focus")

    return success


def _apply_miniscope_hardware_controls(device_index: int, settings: "CameraSettings") -> bool:
    """
    Apply Miniscope V4 hardware controls (LED and EWL).

    Args:
        device_index: Camera device index
        settings: Camera settings with led_power and ewl_focus

    Returns:
        True if controls were applied successfully
    """
    success = True

    # Set LED power
    if not _set_miniscope_led(device_index, settings.led_power):
        success = False

    # Small delay between commands
    time.sleep(0.1)

    # Set EWL focus
    if not _set_miniscope_ewl_focus(device_index, settings.ewl_focus):
        success = False

    return success


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
    connection_timeout: float = 5.0  # Seconds to wait for camera connection
    force_backend: Optional[str] = None  # "v4l2", "picamera2", or None for auto
    pixel_format: Optional[str] = None  # "YUYV", "MJPG", or None for auto
    miniscope_mode: bool = False  # Enable miniscope-specific initialization
    buffer_size: int = 1  # Frame buffer size (1 = lowest latency)
    # Miniscope-specific controls (v4l2-ctl)
    hue: int = 0  # -32768 to 32767
    gamma: int = 0  # 0 to 65535
    gain: int = 0  # 0 to 65535
    sharpness: int = 0  # 0 to 65535
    exposure_time: int = 100  # Exposure time absolute
    focus: int = 0  # 0 to 65535
    zoom: int = 0  # 0 to 65535
    iris: int = 0  # 0 to 65535
    # Miniscope V4 hardware controls (sent via UVC I2C tunnel)
    led_power: int = 0  # 0-100 (percentage, 0=off, 100=max brightness)
    ewl_focus: int = 128  # 0-255 (electrowetting lens focus)

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
            "connection_timeout": self.connection_timeout,
            "force_backend": self.force_backend,
            "pixel_format": self.pixel_format,
            "miniscope_mode": self.miniscope_mode,
            "buffer_size": self.buffer_size,
            "hue": self.hue,
            "gamma": self.gamma,
            "gain": self.gain,
            "sharpness": self.sharpness,
            "exposure_time": self.exposure_time,
            "focus": self.focus,
            "zoom": self.zoom,
            "iris": self.iris,
            "led_power": self.led_power,
            "ewl_focus": self.ewl_focus,
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
            connection_timeout=data.get("connection_timeout", 5.0),
            force_backend=data.get("force_backend", None),
            pixel_format=data.get("pixel_format", None),
            miniscope_mode=data.get("miniscope_mode", False),
            buffer_size=data.get("buffer_size", 1),
            hue=data.get("hue", 0),
            gamma=data.get("gamma", 0),
            gain=data.get("gain", 0),
            sharpness=data.get("sharpness", 0),
            exposure_time=data.get("exposure_time", 100),
            focus=data.get("focus", 0),
            zoom=data.get("zoom", 0),
            iris=data.get("iris", 0),
            led_power=data.get("led_power", 0),
            ewl_focus=data.get("ewl_focus", 128),
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

        # Set buffer size (must be set early, before reading frames)
        buffer_size = self._settings.buffer_size
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
        logger.debug(f"Set buffer size to {buffer_size}")

        # Apply settings (format, resolution, etc.)
        self._apply_camera_settings()

        # Calculate timeout based on settings (miniscopes/USB cameras may need longer)
        timeout = self._settings.connection_timeout
        max_attempts = max(10, int(timeout / 0.1))  # At least 10 attempts
        wait_time = timeout / max_attempts

        # Warmup and verify we can actually read frames
        success_count = 0
        for attempt in range(max_attempts):
            if self._capture.grab():
                ret, frame = self._capture.retrieve()
                if ret and frame is not None:
                    success_count += 1
                    if success_count >= 3:
                        logger.debug(f"Camera working with backend {backend} after {attempt + 1} attempts")
                        return True
            time.sleep(wait_time)

        logger.debug(f"Camera opened but failed to read frames with backend {backend} after {max_attempts} attempts")
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
            # Miniscope wake-up sequence (must happen BEFORE opening the camera)
            if self._settings.miniscope_mode:
                logger.info("Miniscope mode enabled - running wake-up sequence")
                _wake_up_miniscope(self._settings.camera_index)

            # Use platform-appropriate backend
            backend = _get_camera_backend()
            force_backend = self._settings.force_backend

            # Check if user forced a specific backend
            if force_backend == "picamera2":
                logger.info("Forcing picamera2 backend")
                if self._try_connect_picamera2():
                    self._state = CameraState.CONNECTED
                    logger.info(f"Connected to Pi camera via picamera2")
                    return True
                self._state = CameraState.ERROR
                return False
            elif force_backend == "v4l2":
                logger.info("Forcing V4L2 backend")
                backend = cv2.CAP_V4L2

            # On Raspberry Pi, only try picamera2 for camera index 0 (Pi Camera module)
            # USB cameras (miniscopes, webcams) should use V4L2 directly
            if _is_raspberry_pi() and force_backend is None:
                if self._settings.camera_index == 0:
                    logger.info("Raspberry Pi detected, trying picamera2 for camera 0")
                    if self._try_connect_picamera2():
                        self._state = CameraState.CONNECTED
                        logger.info(f"Connected to Pi camera via picamera2")
                        return True
                    logger.info("picamera2 failed, falling back to V4L2")
                else:
                    logger.info(f"Camera index {self._settings.camera_index} - using V4L2 (USB camera)")

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

            # Apply miniscope controls after camera is open
            if self._settings.miniscope_mode:
                _apply_miniscope_controls(self._settings.camera_index, self._settings)
                # Apply hardware controls (LED, EWL focus)
                _apply_miniscope_hardware_controls(self._settings.camera_index, self._settings)

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

        # Set pixel format FIRST (before resolution) - important for miniscopes
        if self._settings.pixel_format:
            try:
                fourcc = cv2.VideoWriter_fourcc(*self._settings.pixel_format)
                self._capture.set(cv2.CAP_PROP_FOURCC, fourcc)
                logger.debug(f"Set pixel format to {self._settings.pixel_format}")
            except Exception as e:
                logger.warning(f"Failed to set pixel format {self._settings.pixel_format}: {e}")
        elif sys.platform == "linux":
            # On Linux with V4L2, try MJPEG format for better compatibility
            # Some cameras don't support it, so we don't fail if it doesn't work
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

    def set_led_power(self, power_percent: int) -> bool:
        """
        Set Miniscope LED power (0-100%).

        Can be called while streaming to adjust LED brightness on-the-fly.

        Args:
            power_percent: LED power 0-100 (0=off, 100=max)

        Returns:
            True if LED was set successfully
        """
        if not self._settings.miniscope_mode:
            logger.warning("LED control requires miniscope mode to be enabled")
            return False

        self._settings.led_power = power_percent
        return _set_miniscope_led(self._settings.camera_index, power_percent)

    def set_ewl_focus(self, focus_value: int) -> bool:
        """
        Set Miniscope electrowetting lens focus (0-255).

        Can be called while streaming to adjust focus on-the-fly.

        Args:
            focus_value: Focus position 0-255

        Returns:
            True if focus was set successfully
        """
        if not self._settings.miniscope_mode:
            logger.warning("EWL focus control requires miniscope mode to be enabled")
            return False

        self._settings.ewl_focus = focus_value
        return _set_miniscope_ewl_focus(self._settings.camera_index, focus_value)

    def _capture_loop(self) -> None:
        """Background thread for frame capture."""
        logger.debug("Capture loop started")
        consecutive_failures = 0
        max_failures_before_log = 30  # Only log every 30 failures to avoid spam
        miniscope_check_interval = 30  # Check brightness every N frames
        miniscope_frame_count = 0

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

            # Miniscope watchdog: kick LED if image goes dark
            if self._settings.miniscope_mode:
                miniscope_frame_count += 1
                if miniscope_frame_count % miniscope_check_interval == 0:
                    mean_brightness = np.mean(frame)
                    if mean_brightness < 1.0:
                        logger.warning(f"Miniscope darkness detected ({mean_brightness:.2f}) - kicking LED")
                        _wake_up_miniscope(self._settings.camera_index)

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
