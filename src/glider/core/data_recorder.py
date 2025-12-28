"""
Data Recorder - Records experiment data to CSV files.

Provides timestamped logging of all device states during experiment execution.
"""

import asyncio
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from glider.core.hardware_manager import HardwareManager
    from glider.core.experiment_session import ExperimentSession

logger = logging.getLogger(__name__)


class DataRecorder:
    """
    Records experiment data to CSV files.

    Creates timestamped CSV files with device states sampled at regular intervals.
    """

    DEFAULT_SAMPLE_INTERVAL = 0.1  # 100ms default sampling

    def __init__(
        self,
        hardware_manager: "HardwareManager",
        output_dir: Optional[Path] = None,
        sample_interval: float = DEFAULT_SAMPLE_INTERVAL,
    ):
        """
        Initialize the data recorder.

        Args:
            hardware_manager: The hardware manager to read device states from
            output_dir: Directory to save CSV files (defaults to current directory)
            sample_interval: Time between samples in seconds
        """
        self._hardware_manager = hardware_manager
        self._output_dir = output_dir or Path.cwd()
        self._sample_interval = sample_interval

        self._recording = False
        self._file: Optional[Any] = None
        self._writer: Optional[csv.writer] = None
        self._file_path: Optional[Path] = None
        self._start_time: Optional[datetime] = None
        self._sample_task: Optional[asyncio.Task] = None
        self._device_columns: List[str] = []

    @property
    def is_recording(self) -> bool:
        """Whether recording is currently active."""
        return self._recording

    @property
    def file_path(self) -> Optional[Path]:
        """Path to the current recording file."""
        return self._file_path

    @property
    def sample_interval(self) -> float:
        """Current sample interval in seconds."""
        return self._sample_interval

    @sample_interval.setter
    def sample_interval(self, value: float) -> None:
        """Set the sample interval (minimum 0.01 seconds)."""
        self._sample_interval = max(0.01, value)

    def _generate_filename(self, experiment_name: str) -> str:
        """Generate a filename with experiment name, date, and time."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize experiment name for filename
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in experiment_name)
        safe_name = safe_name.strip().replace(" ", "_")
        if not safe_name:
            safe_name = "experiment"
        return f"{safe_name}_{timestamp}.csv"

    def _get_device_columns(self) -> List[str]:
        """Get list of device column names."""
        columns = []
        for device_id, device in self._hardware_manager.devices.items():
            device_type = getattr(device, 'device_type', 'unknown')
            columns.append(f"{device_id}:{device_type}")
        return columns

    async def _read_device_state(self, device) -> Any:
        """Read the current state of a device."""
        try:
            # Try different methods to get device state
            if hasattr(device, '_state'):
                return device._state
            if hasattr(device, 'get_state'):
                return await device.get_state()
            if hasattr(device, 'read'):
                return await device.read()
            if hasattr(device, '_value'):
                return device._value
            return None
        except Exception as e:
            logger.debug(f"Could not read state for device: {e}")
            return None

    async def _sample_devices(self) -> Dict[str, Any]:
        """Sample all device states."""
        states = {}
        for device_id, device in self._hardware_manager.devices.items():
            state = await self._read_device_state(device)
            states[device_id] = state
        return states

    def _write_metadata(self, experiment_name: str, session: Optional["ExperimentSession"] = None) -> None:
        """Write metadata header to the CSV file."""
        if self._writer is None:
            return

        # Write metadata section
        self._writer.writerow(["# GLIDER Experiment Data"])
        self._writer.writerow(["# Experiment Name", experiment_name])
        self._writer.writerow(["# Start Time", self._start_time.isoformat() if self._start_time else ""])
        self._writer.writerow(["# Sample Interval (s)", self._sample_interval])
        self._writer.writerow([])

        # Write board info
        self._writer.writerow(["# Boards"])
        for board_id, board in self._hardware_manager.boards.items():
            board_type = getattr(board, 'board_type', 'unknown')
            connected = getattr(board, 'is_connected', False)
            self._writer.writerow(["#", board_id, board_type, "Connected" if connected else "Disconnected"])
        self._writer.writerow([])

        # Write device info
        self._writer.writerow(["# Devices"])
        for device_id, device in self._hardware_manager.devices.items():
            device_type = getattr(device, 'device_type', 'unknown')
            board = getattr(device, 'board', None)
            board_id = board.id if board else "none"
            config = getattr(device, '_config', None)
            pins = config.pins if config else {}
            pin_str = ", ".join(f"{k}={v}" for k, v in pins.items())
            self._writer.writerow(["#", device_id, device_type, f"board={board_id}", pin_str])
        self._writer.writerow([])

        # Write column headers
        self._device_columns = self._get_device_columns()
        headers = ["timestamp", "elapsed_ms"] + self._device_columns
        self._writer.writerow(headers)

    async def start(
        self,
        experiment_name: str = "experiment",
        session: Optional["ExperimentSession"] = None,
    ) -> Path:
        """
        Start recording data.

        Args:
            experiment_name: Name of the experiment for the filename
            session: Optional experiment session for additional metadata

        Returns:
            Path to the created CSV file
        """
        if self._recording:
            logger.warning("Recording already in progress")
            return self._file_path

        # Generate filename and create file
        filename = self._generate_filename(experiment_name)
        self._file_path = self._output_dir / filename
        self._start_time = datetime.now()

        # Open file and create CSV writer
        self._file = open(self._file_path, 'w', newline='', encoding='utf-8')
        self._writer = csv.writer(self._file)

        # Write metadata and headers
        self._write_metadata(experiment_name, session)
        self._file.flush()

        # Start sampling task
        self._recording = True
        self._sample_task = asyncio.create_task(self._sampling_loop())

        logger.info(f"Started recording to {self._file_path}")
        return self._file_path

    async def _sampling_loop(self) -> None:
        """Main sampling loop."""
        while self._recording:
            try:
                await self._record_sample()
            except Exception as e:
                logger.error(f"Error recording sample: {e}")

            await asyncio.sleep(self._sample_interval)

    async def _record_sample(self) -> None:
        """Record a single sample of all device states."""
        if not self._recording or self._writer is None:
            return

        # Get current timestamp
        now = datetime.now()
        elapsed_ms = (now - self._start_time).total_seconds() * 1000 if self._start_time else 0

        # Sample all devices
        states = await self._sample_devices()

        # Build row
        row = [now.isoformat(timespec='milliseconds'), f"{elapsed_ms:.1f}"]

        # Add device states in column order
        for col in self._device_columns:
            device_id = col.split(":")[0]
            state = states.get(device_id)
            # Format state value
            if state is None:
                row.append("")
            elif isinstance(state, bool):
                row.append("1" if state else "0")
            elif isinstance(state, float):
                row.append(f"{state:.4f}")
            else:
                row.append(str(state))

        self._writer.writerow(row)
        self._file.flush()

    async def stop(self) -> Optional[Path]:
        """
        Stop recording and close the file.

        Returns:
            Path to the completed CSV file, or None if not recording
        """
        if not self._recording:
            return None

        self._recording = False

        # Cancel sampling task
        if self._sample_task:
            self._sample_task.cancel()
            try:
                await self._sample_task
            except asyncio.CancelledError:
                pass
            self._sample_task = None

        # Write final sample
        try:
            await self._record_sample()
        except Exception:
            pass

        # Write footer
        if self._writer:
            end_time = datetime.now()
            duration = (end_time - self._start_time).total_seconds() if self._start_time else 0
            self._writer.writerow([])
            self._writer.writerow(["# End Time", end_time.isoformat()])
            self._writer.writerow(["# Duration (s)", f"{duration:.2f}"])

        # Close file
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None

        file_path = self._file_path
        logger.info(f"Stopped recording. Data saved to {file_path}")

        return file_path

    async def record_event(self, event_name: str, details: str = "") -> None:
        """
        Record a custom event in the data file.

        Args:
            event_name: Name of the event
            details: Additional details
        """
        if not self._recording or self._writer is None:
            return

        now = datetime.now()
        elapsed_ms = (now - self._start_time).total_seconds() * 1000 if self._start_time else 0

        # Write event as a comment row
        self._writer.writerow([f"# EVENT: {event_name}", f"{elapsed_ms:.1f}ms", details])
        self._file.flush()
