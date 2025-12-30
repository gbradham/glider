"""
Video Recorder - Record video synced with experiment lifecycle.

Records video to file synchronized with experiment start/stop,
generating filenames that match the DataRecorder pattern.
"""

import cv2
import numpy as np
import logging
import threading
from pathlib import Path
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from glider.vision.camera_manager import CameraManager

logger = logging.getLogger(__name__)


class RecordingState(Enum):
    """State of the video recording."""
    IDLE = auto()
    RECORDING = auto()
    PAUSED = auto()
    FINALIZING = auto()


@dataclass
class VideoFormat:
    """Video output format configuration."""
    codec: str = "mp4v"  # OpenCV fourcc code
    extension: str = ".mp4"
    quality: int = 95  # For JPEG-based codecs

    def to_dict(self) -> dict:
        return {
            "codec": self.codec,
            "extension": self.extension,
            "quality": self.quality,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VideoFormat":
        return cls(
            codec=data.get("codec", "mp4v"),
            extension=data.get("extension", ".mp4"),
            quality=data.get("quality", 95),
        )


class VideoRecorder:
    """
    Records video synchronized with experiment lifecycle.

    Integrates with GliderCore to automatically start/stop recording
    when experiments run. Saves video files alongside CSV data files
    with matching timestamps.
    """

    def __init__(self, camera_manager: "CameraManager"):
        """
        Initialize the video recorder.

        Args:
            camera_manager: CameraManager instance to capture frames from
        """
        self._camera = camera_manager
        self._writer: Optional[cv2.VideoWriter] = None
        self._state = RecordingState.IDLE
        self._output_dir: Path = Path.cwd()
        self._file_path: Optional[Path] = None
        self._start_time: Optional[datetime] = None
        self._frame_count = 0
        self._video_format = VideoFormat()
        self._lock = threading.Lock()
        self._frame_callback_registered = False

    @property
    def is_recording(self) -> bool:
        """Whether video is currently being recorded."""
        return self._state == RecordingState.RECORDING

    @property
    def is_paused(self) -> bool:
        """Whether recording is paused."""
        return self._state == RecordingState.PAUSED

    @property
    def state(self) -> RecordingState:
        """Current recording state."""
        return self._state

    @property
    def file_path(self) -> Optional[Path]:
        """Path to the current/last video file."""
        return self._file_path

    @property
    def frame_count(self) -> int:
        """Number of frames recorded."""
        return self._frame_count

    @property
    def duration(self) -> float:
        """Recording duration in seconds."""
        if self._start_time is None:
            return 0.0
        return (datetime.now() - self._start_time).total_seconds()

    def set_output_directory(self, path: Path) -> None:
        """
        Set the output directory for video files.

        Args:
            path: Directory path for video output
        """
        self._output_dir = Path(path)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Video output directory: {self._output_dir}")

    def set_video_format(self, codec: str = "mp4v", extension: str = ".mp4") -> None:
        """
        Set the video codec and file extension.

        Args:
            codec: OpenCV fourcc codec code (e.g., "mp4v", "XVID", "MJPG")
            extension: File extension (e.g., ".mp4", ".avi")
        """
        self._video_format = VideoFormat(codec=codec, extension=extension)
        logger.debug(f"Video format: {codec} ({extension})")

    def _generate_filename(self, experiment_name: str) -> str:
        """
        Generate filename matching DataRecorder pattern.

        Args:
            experiment_name: Name of the experiment

        Returns:
            Formatted filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize name
        safe_name = "".join(
            c if c.isalnum() or c in "._- " else "_"
            for c in experiment_name
        )
        safe_name = safe_name.strip().replace(" ", "_") or "experiment"
        return f"{safe_name}_{timestamp}{self._video_format.extension}"

    async def start(self, experiment_name: str = "experiment") -> Path:
        """
        Start recording video.

        Args:
            experiment_name: Name for the video file

        Returns:
            Path to the video file being created
        """
        if self._state == RecordingState.RECORDING:
            logger.warning("Recording already in progress")
            return self._file_path

        # Generate filename
        filename = self._generate_filename(experiment_name)
        self._file_path = self._output_dir / filename
        self._start_time = datetime.now()
        self._frame_count = 0

        # Get camera settings for video writer
        settings = self._camera.settings
        fourcc = cv2.VideoWriter_fourcc(*self._video_format.codec)

        with self._lock:
            self._writer = cv2.VideoWriter(
                str(self._file_path),
                fourcc,
                settings.fps,
                settings.resolution
            )

            if not self._writer.isOpened():
                logger.error(f"Failed to create video writer: {self._file_path}")
                self._writer = None
                raise RuntimeError(f"Failed to create video file: {self._file_path}")

        # Register frame callback
        if not self._frame_callback_registered:
            self._camera.on_frame(self._on_frame)
            self._frame_callback_registered = True

        self._state = RecordingState.RECORDING
        logger.info(f"Started recording to {self._file_path}")
        return self._file_path

    def _on_frame(self, frame: np.ndarray, timestamp: float) -> None:
        """
        Handle incoming frame for recording.

        Args:
            frame: Frame from camera
            timestamp: Frame timestamp
        """
        if self._state != RecordingState.RECORDING:
            return

        with self._lock:
            if self._writer is not None and self._writer.isOpened():
                self._writer.write(frame)
                self._frame_count += 1

    async def stop(self) -> Optional[Path]:
        """
        Stop recording and finalize video file.

        Returns:
            Path to the saved video file, or None if not recording
        """
        if self._state not in (RecordingState.RECORDING, RecordingState.PAUSED):
            return None

        self._state = RecordingState.FINALIZING

        with self._lock:
            if self._writer is not None:
                self._writer.release()
                self._writer = None

        saved_path = self._file_path
        self._state = RecordingState.IDLE

        duration = self.duration
        logger.info(
            f"Stopped recording. Saved to {saved_path} "
            f"({self._frame_count} frames, {duration:.1f}s)"
        )
        return saved_path

    async def pause(self) -> None:
        """Pause recording (frames will be skipped)."""
        if self._state == RecordingState.RECORDING:
            self._state = RecordingState.PAUSED
            logger.info("Recording paused")

    async def resume(self) -> None:
        """Resume recording after pause."""
        if self._state == RecordingState.PAUSED:
            self._state = RecordingState.RECORDING
            logger.info("Recording resumed")

    def write_frame(self, frame: np.ndarray) -> bool:
        """
        Manually write a frame to the video.

        Useful for writing processed/annotated frames.

        Args:
            frame: Frame to write

        Returns:
            True if frame was written
        """
        if self._state != RecordingState.RECORDING:
            return False

        with self._lock:
            if self._writer is not None and self._writer.isOpened():
                self._writer.write(frame)
                self._frame_count += 1
                return True
        return False

    def get_recording_info(self) -> dict:
        """
        Get information about the current recording.

        Returns:
            Dictionary with recording details
        """
        return {
            "state": self._state.name,
            "file_path": str(self._file_path) if self._file_path else None,
            "frame_count": self._frame_count,
            "duration": self.duration,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "format": self._video_format.to_dict(),
        }
