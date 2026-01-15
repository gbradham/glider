"""
GLIDER Vision Module - Video recording and computer vision.

Provides:
- Camera management and webcam capture
- Video recording synchronized with experiments
- Real-time computer vision processing
- Object detection and tracking
- Tracking data logging to CSV
"""

from glider.vision.camera_manager import (
    CameraManager,
    CameraInfo,
    CameraSettings,
    CameraState,
)
from glider.vision.video_recorder import (
    VideoRecorder,
    RecordingState,
    VideoFormat,
)
from glider.vision.multi_camera_manager import MultiCameraManager
from glider.vision.multi_video_recorder import MultiVideoRecorder
from glider.vision.cv_processor import (
    CVProcessor,
    CVSettings,
    Detection,
    TrackedObject,
    MotionResult,
    DetectionBackend,
    ObjectTracker,
)
from glider.vision.tracking_logger import TrackingDataLogger
from glider.vision.calibration import (
    CameraCalibration,
    CalibrationLine,
    LengthUnit,
)

__all__ = [
    # Camera
    "CameraManager",
    "CameraInfo",
    "CameraSettings",
    "CameraState",
    # Multi-Camera
    "MultiCameraManager",
    "MultiVideoRecorder",
    # Video Recording
    "VideoRecorder",
    "RecordingState",
    "VideoFormat",
    # Computer Vision
    "CVProcessor",
    "CVSettings",
    "Detection",
    "TrackedObject",
    "MotionResult",
    "DetectionBackend",
    "ObjectTracker",
    # Tracking Data
    "TrackingDataLogger",
    # Calibration
    "CameraCalibration",
    "CalibrationLine",
    "LengthUnit",
]
