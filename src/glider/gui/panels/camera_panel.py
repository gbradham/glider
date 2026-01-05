"""
Camera Panel - Dock widget for camera preview and controls.

Provides live camera preview with CV overlays, recording status,
and quick access to camera settings.
"""

import cv2
import numpy as np
import logging
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QComboBox, QFrame,
    QSizePolicy, QScrollArea
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

if TYPE_CHECKING:
    from glider.vision.camera_manager import CameraManager
    from glider.vision.cv_processor import CVProcessor
    from glider.vision.video_recorder import VideoRecorder
    from glider.vision.tracking_logger import TrackingDataLogger
    from glider.vision.calibration import CameraCalibration

logger = logging.getLogger(__name__)


class CameraPreviewWidget(QLabel):
    """Widget displaying live camera feed."""

    frame_clicked = pyqtSignal(int, int)  # x, y click position

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #0d0d1a;
                border: 1px solid #2d2d44;
                border-radius: 8px;
            }
        """)
        self._placeholder = True
        self._calibration = None
        self._show_calibration = True
        self.setText("No Camera")
        # Prevent the widget from resizing based on pixmap content
        self.setScaledContents(False)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored
        )

    def set_calibration(self, calibration) -> None:
        """Set calibration to display on preview."""
        self._calibration = calibration

    def set_show_calibration(self, show: bool) -> None:
        """Toggle calibration line display."""
        self._show_calibration = show

    def update_frame(self, frame: np.ndarray) -> None:
        """Update display with new frame."""
        self._placeholder = False

        # Draw calibration lines if enabled
        display_frame = frame
        if self._show_calibration and self._calibration and self._calibration.lines:
            display_frame = frame.copy()
            h, w = display_frame.shape[:2]
            for line in self._calibration.lines:
                x1, y1, x2, y2 = line.get_pixel_coords(w, h)
                cv2.line(display_frame, (x1, y1), (x2, y2), line.color, 2)
                cv2.circle(display_frame, (x1, y1), 4, line.color, -1)
                cv2.circle(display_frame, (x2, y2), 4, line.color, -1)
                # Draw label
                mid_x = (x1 + x2) // 2
                mid_y = (y1 + y2) // 2
                label = f"{line.length:.1f}{line.unit.value}"
                cv2.putText(
                    display_frame, label,
                    (mid_x + 5, mid_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, line.color, 1
                )

        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w

        q_image = QImage(
            rgb_frame.data, w, h, bytes_per_line,
            QImage.Format.Format_RGB888
        )

        # Scale to fit widget while maintaining aspect ratio
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)

    def show_placeholder(self, text: str = "No Camera") -> None:
        """Show placeholder text."""
        self._placeholder = True
        self.clear()
        self.setText(text)
        self.setStyleSheet("""
            QLabel {
                background-color: #0d0d1a;
                border: 1px solid #2d2d44;
                border-radius: 8px;
                color: #666;
                font-size: 14px;
            }
        """)

    def mousePressEvent(self, event):
        """Handle mouse clicks on the preview."""
        if not self._placeholder:
            self.frame_clicked.emit(event.pos().x(), event.pos().y())
        super().mousePressEvent(event)


class CameraPanel(QWidget):
    """
    Camera control panel as dock widget content.

    Layout:
    - Camera preview (top, expandable)
    - Status bar (recording indicator, FPS)
    - Control buttons (Settings, Start/Stop Preview)
    - CV toggle checkbox
    """

    settings_requested = pyqtSignal()
    calibration_requested = pyqtSignal()

    def __init__(
        self,
        camera_manager: "CameraManager",
        cv_processor: "CVProcessor",
        parent=None
    ):
        super().__init__(parent)
        self._camera = camera_manager
        self._cv_processor = cv_processor
        self._video_recorder: Optional["VideoRecorder"] = None
        self._tracking_logger: Optional["TrackingDataLogger"] = None
        self._calibration: Optional["CameraCalibration"] = None
        self._preview_active = False
        self._last_frame = None
        self._frame_count = 0

        self._setup_ui()
        self._connect_signals()

        # Timer for FPS updates
        self._fps_timer = QTimer()
        self._fps_timer.timeout.connect(self._update_fps_display)
        self._fps_timer.start(1000)

    def _setup_ui(self) -> None:
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for the entire panel
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        # Content widget inside scroll area
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Camera preview
        self._preview = CameraPreviewWidget()
        layout.addWidget(self._preview, 1)  # Stretch factor 1

        # Status bar
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 4, 8, 4)

        self._recording_indicator = QLabel("REC")
        self._recording_indicator.setStyleSheet("""
            QLabel {
                background-color: #c0392b;
                color: white;
                padding: 2px 8px;
                border-radius: 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self._recording_indicator.hide()
        status_layout.addWidget(self._recording_indicator)

        self._fps_label = QLabel("-- FPS")
        self._fps_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self._fps_label)

        status_layout.addStretch()

        self._resolution_label = QLabel("---")
        self._resolution_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self._resolution_label)

        layout.addWidget(status_frame)

        # Camera selector
        camera_layout = QHBoxLayout()
        camera_label = QLabel("Camera:")
        camera_label.setStyleSheet("font-size: 12px;")
        camera_layout.addWidget(camera_label)

        self._camera_combo = QComboBox()
        self._camera_combo.setMinimumWidth(150)
        camera_layout.addWidget(self._camera_combo, 1)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedWidth(80)
        self._refresh_btn.clicked.connect(self._refresh_cameras)
        camera_layout.addWidget(self._refresh_btn)

        layout.addLayout(camera_layout)

        # Control buttons
        control_layout = QHBoxLayout()

        self._preview_btn = QPushButton("Start Preview")
        self._preview_btn.clicked.connect(self._toggle_preview)
        control_layout.addWidget(self._preview_btn)

        self._settings_btn = QPushButton("Settings...")
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        control_layout.addWidget(self._settings_btn)

        self._calibrate_btn = QPushButton("Calibrate...")
        self._calibrate_btn.clicked.connect(self.calibration_requested.emit)
        control_layout.addWidget(self._calibrate_btn)

        layout.addLayout(control_layout)

        # CV options
        cv_layout = QHBoxLayout()

        self._cv_enabled_cb = QCheckBox("Enable CV")
        self._cv_enabled_cb.setChecked(True)
        self._cv_enabled_cb.toggled.connect(self._on_cv_toggle)
        cv_layout.addWidget(self._cv_enabled_cb)

        self._overlay_cb = QCheckBox("Show Overlays")
        self._overlay_cb.setChecked(True)
        self._overlay_cb.toggled.connect(self._on_overlay_toggle)
        cv_layout.addWidget(self._overlay_cb)

        cv_layout.addStretch()
        layout.addLayout(cv_layout)

        # Set up scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Initial camera list
        self._refresh_cameras()

    def _connect_signals(self) -> None:
        """Connect camera callbacks."""
        self._camera.on_frame(self._on_frame)

    def _refresh_cameras(self) -> None:
        """Refresh available camera list."""
        self._camera_combo.clear()
        cameras = self._camera.enumerate_cameras()
        for cam in cameras:
            self._camera_combo.addItem(cam.name, cam.index)
        if not cameras:
            self._camera_combo.addItem("No cameras found", -1)
            self._preview_btn.setEnabled(False)
        else:
            self._preview_btn.setEnabled(True)

    def _toggle_preview(self) -> None:
        """Start/stop camera preview."""
        if self._preview_active:
            self._stop_preview()
        else:
            self._start_preview()

    def _start_preview(self) -> None:
        """Start camera preview."""
        camera_idx = self._camera_combo.currentData()
        if camera_idx is None or camera_idx < 0:
            return

        from glider.vision.camera_manager import CameraSettings
        settings = CameraSettings(camera_index=camera_idx)

        if self._camera.connect(settings):
            self._camera.start_streaming()
            self._preview_btn.setText("Stop Preview")
            self._preview_active = True

            # Update resolution display
            res = settings.resolution
            self._resolution_label.setText(f"{res[0]}x{res[1]}")

            # Initialize CV processor
            if self._cv_enabled_cb.isChecked():
                self._cv_processor.initialize()

            logger.info(f"Started camera preview: {camera_idx}")
        else:
            self._preview.show_placeholder("Failed to connect")

    def _stop_preview(self) -> None:
        """Stop camera preview."""
        self._camera.stop_streaming()
        self._camera.disconnect()
        self._preview_btn.setText("Start Preview")
        self._preview.show_placeholder("No Camera")
        self._preview_active = False
        self._resolution_label.setText("---")
        self._fps_label.setText("-- FPS")
        logger.info("Stopped camera preview")

    def _on_frame(self, frame: np.ndarray, timestamp: float) -> None:
        """Handle incoming camera frame."""
        if not self._preview_active:
            return

        self._frame_count += 1
        display_frame = frame
        annotated_frame = None
        tracked_objects = []
        motion_result = None

        # Process with CV if enabled
        if self._cv_enabled_cb.isChecked() and self._cv_processor.is_initialized:
            detections, tracked, motion = self._cv_processor.process_frame(
                frame, timestamp
            )
            tracked_objects = tracked
            motion_result = motion
            if self._overlay_cb.isChecked():
                display_frame = self._cv_processor.draw_overlays(
                    frame, detections, tracked, motion
                )
                annotated_frame = display_frame

        self._last_frame = display_frame
        self._preview.update_frame(display_frame)

        # Write annotated frame to video recorder if recording
        if annotated_frame is not None and self._video_recorder is not None:
            # Draw calibration lines on the annotated frame for the video
            if self._calibration and self._calibration.lines:
                annotated_frame = self._draw_calibration_lines(annotated_frame)
            self._video_recorder.write_annotated_frame(annotated_frame)

        # Log tracking data if tracking logger is active
        if self._tracking_logger is not None and self._tracking_logger.is_recording:
            # Set frame size and calibration for distance calculations
            h, w = frame.shape[:2]
            self._tracking_logger.set_frame_size(w, h)
            if self._calibration:
                self._tracking_logger.set_calibration(self._calibration)

            motion_detected = motion_result.motion_detected if motion_result else False
            motion_area = motion_result.motion_area if motion_result else 0.0

            # Debug: Log every 100 frames to avoid log spam
            if self._frame_count % 100 == 0:
                logger.debug(
                    f"Tracking frame {self._frame_count}: "
                    f"objects={len(tracked_objects)}, motion={motion_detected}, "
                    f"cv_enabled={self._cv_enabled_cb.isChecked()}, "
                    f"cv_initialized={self._cv_processor.is_initialized}"
                )

            self._tracking_logger.log_frame(
                timestamp, tracked_objects, motion_detected, motion_area
            )
        elif self._tracking_logger is not None and self._frame_count % 500 == 0:
            # Debug: Log when tracking logger exists but isn't recording
            logger.debug(
                f"Tracking logger exists but is_recording={self._tracking_logger.is_recording}"
            )

    def _draw_calibration_lines(self, frame: np.ndarray) -> np.ndarray:
        """Draw calibration lines on a frame for video recording."""
        if not self._calibration or not self._calibration.lines:
            return frame

        output = frame.copy()
        h, w = output.shape[:2]

        for line in self._calibration.lines:
            x1, y1, x2, y2 = line.get_pixel_coords(w, h)
            # Draw the line
            cv2.line(output, (x1, y1), (x2, y2), line.color, 2)
            # Draw endpoint circles
            cv2.circle(output, (x1, y1), 4, line.color, -1)
            cv2.circle(output, (x2, y2), 4, line.color, -1)
            # Draw measurement label at midpoint
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            label = f"{line.length:.1f}{line.unit.value}"
            cv2.putText(
                output, label,
                (mid_x + 5, mid_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, line.color, 1
            )

        return output

    def _update_fps_display(self) -> None:
        """Update FPS display."""
        if self._preview_active:
            fps = self._camera.current_fps
            self._fps_label.setText(f"{fps:.1f} FPS")

    def _on_cv_toggle(self, enabled: bool) -> None:
        """Handle CV processing toggle."""
        self._cv_processor.settings.enabled = enabled
        self._overlay_cb.setEnabled(enabled)
        if enabled and self._preview_active:
            self._cv_processor.initialize()

    def _on_overlay_toggle(self, enabled: bool) -> None:
        """Handle overlay display toggle."""
        self._cv_processor.settings.draw_overlays = enabled

    def set_video_recorder(self, recorder: "VideoRecorder") -> None:
        """Set the video recorder for annotated frame writing."""
        self._video_recorder = recorder

    def set_tracking_logger(self, logger: "TrackingDataLogger") -> None:
        """Set the tracking logger for logging CV results."""
        self._tracking_logger = logger

    def set_calibration(self, calibration: "CameraCalibration") -> None:
        """Set the camera calibration for real-world measurements."""
        self._calibration = calibration

    def set_recording(self, recording: bool) -> None:
        """Update recording indicator."""
        if recording:
            self._recording_indicator.show()
        else:
            self._recording_indicator.hide()

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current frame (for snapshots)."""
        return self._last_frame.copy() if self._last_frame is not None else None

    def closeEvent(self, event):
        """Clean up on close."""
        if self._preview_active:
            self._stop_preview()
        self._fps_timer.stop()
        super().closeEvent(event)
