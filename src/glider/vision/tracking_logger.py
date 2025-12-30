"""
Tracking Data Logger - Log CV results to CSV.

Logs computer vision tracking data to CSV file synchronized
with experiment timestamps, matching DataRecorder output format.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from glider.vision.cv_processor import TrackedObject, MotionResult

logger = logging.getLogger(__name__)


class TrackingDataLogger:
    """
    Logs computer vision results to CSV file.

    Output format matches DataRecorder pattern with columns:
    frame, timestamp, elapsed_ms, object_id, class, x, y, w, h, confidence
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the tracking logger.

        Args:
            output_dir: Directory for output files, or None for current directory
        """
        self._output_dir = Path(output_dir) if output_dir else Path.cwd()
        self._file = None
        self._writer = None
        self._file_path: Optional[Path] = None
        self._start_time: Optional[datetime] = None
        self._start_timestamp: float = 0.0
        self._frame_count = 0
        self._recording = False

    @property
    def is_recording(self) -> bool:
        """Whether logging is active."""
        return self._recording

    @property
    def file_path(self) -> Optional[Path]:
        """Path to the current/last log file."""
        return self._file_path

    @property
    def frame_count(self) -> int:
        """Number of frames logged."""
        return self._frame_count

    def set_output_directory(self, path: Path) -> None:
        """
        Set the output directory for log files.

        Args:
            path: Directory path
        """
        self._output_dir = Path(path)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, experiment_name: str) -> str:
        """
        Generate filename for tracking data.

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
        return f"{safe_name}_{timestamp}_tracking.csv"

    async def start(self, experiment_name: str = "experiment") -> Path:
        """
        Start logging tracking data.

        Args:
            experiment_name: Name for the log file

        Returns:
            Path to the log file being created
        """
        if self._recording:
            logger.warning("Tracking logger already recording")
            return self._file_path

        # Generate filename
        filename = self._generate_filename(experiment_name)
        self._file_path = self._output_dir / filename
        self._start_time = datetime.now()
        self._start_timestamp = self._start_time.timestamp()
        self._frame_count = 0

        # Open file and create writer
        self._file = open(self._file_path, 'w', newline='', encoding='utf-8')
        self._writer = csv.writer(self._file)

        # Write metadata header
        self._writer.writerow(["# GLIDER Tracking Data"])
        self._writer.writerow(["# Experiment", experiment_name])
        self._writer.writerow(["# Start Time", self._start_time.isoformat()])
        self._writer.writerow([])

        # Write column headers
        self._writer.writerow([
            "frame",
            "timestamp",
            "elapsed_ms",
            "object_id",
            "class",
            "x",
            "y",
            "w",
            "h",
            "confidence"
        ])
        self._file.flush()

        self._recording = True
        logger.info(f"Started tracking log: {self._file_path}")
        return self._file_path

    def log_frame(
        self,
        timestamp: float,
        tracked_objects: List["TrackedObject"],
        motion_detected: bool = False,
        motion_area: float = 0.0
    ) -> None:
        """
        Log tracking data for a single frame.

        Args:
            timestamp: Frame timestamp (Unix time)
            tracked_objects: List of tracked objects
            motion_detected: Whether motion was detected
            motion_area: Area percentage with motion
        """
        if not self._recording or self._writer is None:
            return

        self._frame_count += 1
        elapsed_ms = (timestamp - self._start_timestamp) * 1000
        iso_timestamp = datetime.fromtimestamp(timestamp).isoformat(timespec='milliseconds')

        # Log each tracked object
        for obj in tracked_objects:
            x, y, w, h = obj.bbox
            self._writer.writerow([
                self._frame_count,
                iso_timestamp,
                f"{elapsed_ms:.1f}",
                obj.track_id,
                obj.class_name,
                x,
                y,
                w,
                h,
                f"{obj.confidence:.3f}"
            ])

        # Log motion event if no objects but motion detected
        if not tracked_objects and motion_detected:
            self._writer.writerow([
                self._frame_count,
                iso_timestamp,
                f"{elapsed_ms:.1f}",
                -1,  # No object ID for motion-only
                "motion",
                0, 0, 0, 0,  # No bbox
                f"{motion_area:.3f}"
            ])

        self._file.flush()

    def log_event(self, event_name: str, details: str = "") -> None:
        """
        Log a custom event.

        Args:
            event_name: Name of the event
            details: Optional details
        """
        if not self._recording or self._writer is None:
            return

        timestamp = datetime.now()
        elapsed_ms = (timestamp.timestamp() - self._start_timestamp) * 1000
        iso_timestamp = timestamp.isoformat(timespec='milliseconds')

        self._writer.writerow([
            f"# EVENT: {event_name}",
            iso_timestamp,
            f"{elapsed_ms:.1f}",
            "",
            details,
            "", "", "", "",
            ""
        ])
        self._file.flush()

    async def stop(self) -> Optional[Path]:
        """
        Stop logging and close file.

        Returns:
            Path to the saved log file
        """
        if not self._recording:
            return None

        self._recording = False

        # Write footer
        if self._writer and self._file:
            end_time = datetime.now()
            duration = (end_time - self._start_time).total_seconds() if self._start_time else 0

            self._writer.writerow([])
            self._writer.writerow(["# End Time", end_time.isoformat()])
            self._writer.writerow(["# Duration (s)", f"{duration:.2f}"])
            self._writer.writerow(["# Total Frames", self._frame_count])

        # Close file
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None

        saved_path = self._file_path
        logger.info(f"Stopped tracking log. Saved to {saved_path}")
        return saved_path

    def get_statistics(self) -> dict:
        """
        Get logging statistics.

        Returns:
            Dictionary with logging stats
        """
        duration = 0.0
        if self._start_time and self._recording:
            duration = (datetime.now() - self._start_time).total_seconds()

        return {
            "recording": self._recording,
            "file_path": str(self._file_path) if self._file_path else None,
            "frame_count": self._frame_count,
            "duration": duration,
            "start_time": self._start_time.isoformat() if self._start_time else None,
        }
