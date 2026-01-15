"""
Camera Settings Dialog - Configure camera and CV parameters.

Provides tabbed interface for camera settings, computer vision
configuration, and tracking parameters.

Automatically adapts layout for touchscreen (Pi) or desktop environments.
"""

import logging
from typing import Optional, List, Tuple, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QWidget, QGroupBox, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QSlider, QPushButton, QDialogButtonBox, QFileDialog,
    QLineEdit, QScrollArea, QFrame, QSizePolicy, QScroller
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

if TYPE_CHECKING:
    from glider.gui.view_manager import ViewManager

from glider.vision.camera_manager import CameraSettings, CameraManager
from glider.vision.cv_processor import CVSettings, DetectionBackend

logger = logging.getLogger(__name__)


class CameraSettingsDialog(QDialog):
    """Dialog for configuring camera and CV settings."""

    def __init__(
        self,
        camera_settings: Optional[CameraSettings] = None,
        cv_settings: Optional[CVSettings] = None,
        parent=None,
        view_manager: Optional["ViewManager"] = None
    ):
        super().__init__(parent)
        self._camera_settings = camera_settings or CameraSettings()
        self._cv_settings = cv_settings or CVSettings()
        self._view_manager = view_manager
        self._is_touch_mode = view_manager.is_runner_mode if view_manager else False
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        self.setWindowTitle("Camera Settings")

        # Adaptive sizing based on mode
        if self._is_touch_mode:
            # Pi touchscreen: fill most of the screen
            self.setMinimumSize(460, 700)
            self.setMaximumSize(480, 780)
        else:
            self.setMinimumSize(500, 450)

        layout = QVBoxLayout(self)

        # Adjust layout spacing for touch mode
        if self._is_touch_mode:
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)

        # Tab widget with larger tabs for touch
        self._tabs = QTabWidget()
        if self._is_touch_mode:
            self._tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #555;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    padding: 12px 20px;
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 100px;
                }
                QTabBar::tab:selected {
                    background-color: #3a7bd5;
                    color: white;
                }
            """)
        layout.addWidget(self._tabs)

        # Camera tab (wrapped in scroll area)
        self._camera_tab = self._create_scrollable_tab(self._create_camera_tab_content())
        self._tabs.addTab(self._camera_tab, "Camera")

        # Computer Vision tab (wrapped in scroll area)
        self._cv_tab = self._create_scrollable_tab(self._create_cv_tab_content())
        self._tabs.addTab(self._cv_tab, "CV")

        # Tracking tab (wrapped in scroll area)
        self._tracking_tab = self._create_scrollable_tab(self._create_tracking_tab_content())
        self._tabs.addTab(self._tracking_tab, "Tracking")

        # Dialog buttons - larger for touch
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )

        if self._is_touch_mode:
            button_box.setStyleSheet("""
                QPushButton {
                    padding: 14px 24px;
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 90px;
                    min-height: 44px;
                }
            """)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        apply_btn = button_box.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.clicked.connect(self._apply_settings)
        layout.addWidget(button_box)

    def _create_scrollable_tab(self, content_widget: QWidget) -> QScrollArea:
        """Wrap a widget in a scroll area for touch-friendly scrolling."""
        scroll = QScrollArea()
        scroll.setWidget(content_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        if self._is_touch_mode:
            # Wide scrollbar and kinetic scrolling for touch
            scroll.setStyleSheet("""
                QScrollArea {
                    background: transparent;
                }
                QScrollBar:vertical {
                    width: 30px;
                    background: #2a2a2a;
                    border-radius: 15px;
                    margin: 4px;
                }
                QScrollBar::handle:vertical {
                    background: #5a5a5a;
                    border-radius: 13px;
                    min-height: 60px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #6a6a6a;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
            """)
            # Enable kinetic scrolling
            QScroller.grabGesture(scroll.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        return scroll

    def _get_touch_group_style(self) -> str:
        """Get stylesheet for group boxes in touch mode."""
        if not self._is_touch_mode:
            return ""
        return """
            QGroupBox {
                font-size: 15px;
                font-weight: bold;
                padding: 16px 8px 8px 8px;
                margin-top: 12px;
                border: 1px solid #444;
                border-radius: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 8px;
                color: #3a7bd5;
            }
            QLabel {
                font-size: 14px;
            }
            QComboBox {
                padding: 10px;
                font-size: 14px;
                min-height: 36px;
            }
            QComboBox::drop-down {
                width: 30px;
            }
            QSpinBox, QDoubleSpinBox {
                padding: 8px;
                font-size: 14px;
                min-height: 36px;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 30px;
            }
            QCheckBox {
                font-size: 14px;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 28px;
                height: 28px;
            }
            QSlider::groove:horizontal {
                height: 12px;
                background: #3a3a3a;
                border-radius: 6px;
            }
            QSlider::handle:horizontal {
                width: 28px;
                height: 28px;
                margin: -8px 0;
                background: #3a7bd5;
                border-radius: 14px;
            }
        """

    def _create_camera_tab_content(self) -> QWidget:
        """Create the camera settings tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Adjust spacing for touch mode
        if self._is_touch_mode:
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(16)

        touch_style = self._get_touch_group_style()

        # Resolution group
        res_group = QGroupBox("Resolution")
        res_group.setStyleSheet(touch_style)
        res_layout = QFormLayout(res_group)
        if self._is_touch_mode:
            res_layout.setSpacing(12)
            res_layout.setContentsMargins(12, 20, 12, 12)

        self._resolution_combo = QComboBox()
        self._resolution_combo.addItem("320x240", (320, 240))
        self._resolution_combo.addItem("608x608 (Miniscope)", (608, 608))
        self._resolution_combo.addItem("640x480", (640, 480))
        self._resolution_combo.addItem("800x600", (800, 600))
        self._resolution_combo.addItem("1280x720 (HD)", (1280, 720))
        self._resolution_combo.addItem("1920x1080 (Full HD)", (1920, 1080))
        res_layout.addRow("Resolution:", self._resolution_combo)

        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 120)
        self._fps_spin.setValue(30)
        self._fps_spin.setSuffix(" fps")
        res_layout.addRow("Frame Rate:", self._fps_spin)

        layout.addWidget(res_group)

        # Image settings group
        image_group = QGroupBox("Image Settings")
        image_group.setStyleSheet(touch_style)
        image_layout = QFormLayout(image_group)
        if self._is_touch_mode:
            image_layout.setSpacing(12)
            image_layout.setContentsMargins(12, 20, 12, 12)

        # Exposure
        exposure_layout = QHBoxLayout()
        exposure_layout.setSpacing(8 if not self._is_touch_mode else 12)
        self._auto_exposure_cb = QCheckBox("Auto")
        self._auto_exposure_cb.toggled.connect(self._on_auto_exposure_toggle)
        exposure_layout.addWidget(self._auto_exposure_cb)

        self._exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self._exposure_slider.setRange(-10, 0)
        self._exposure_slider.setValue(-5)
        if self._is_touch_mode:
            self._exposure_slider.setMinimumHeight(40)
        exposure_layout.addWidget(self._exposure_slider)

        self._exposure_label = QLabel("-5")
        self._exposure_label.setMinimumWidth(40 if self._is_touch_mode else 30)
        self._exposure_slider.valueChanged.connect(
            lambda v: self._exposure_label.setText(str(v))
        )
        exposure_layout.addWidget(self._exposure_label)

        image_layout.addRow("Exposure:", exposure_layout)

        # Brightness
        brightness_layout = QHBoxLayout()
        brightness_layout.setSpacing(8 if not self._is_touch_mode else 12)
        self._brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self._brightness_slider.setRange(0, 255)
        self._brightness_slider.setValue(128)
        if self._is_touch_mode:
            self._brightness_slider.setMinimumHeight(40)
        brightness_layout.addWidget(self._brightness_slider)

        self._brightness_label = QLabel("128")
        self._brightness_label.setMinimumWidth(40 if self._is_touch_mode else 30)
        self._brightness_slider.valueChanged.connect(
            lambda v: self._brightness_label.setText(str(v))
        )
        brightness_layout.addWidget(self._brightness_label)

        image_layout.addRow("Brightness:", brightness_layout)

        # Contrast
        contrast_layout = QHBoxLayout()
        contrast_layout.setSpacing(8 if not self._is_touch_mode else 12)
        self._contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self._contrast_slider.setRange(0, 255)
        self._contrast_slider.setValue(128)
        if self._is_touch_mode:
            self._contrast_slider.setMinimumHeight(40)
        contrast_layout.addWidget(self._contrast_slider)

        self._contrast_label = QLabel("128")
        self._contrast_label.setMinimumWidth(40 if self._is_touch_mode else 30)
        self._contrast_slider.valueChanged.connect(
            lambda v: self._contrast_label.setText(str(v))
        )
        contrast_layout.addWidget(self._contrast_label)

        image_layout.addRow("Contrast:", contrast_layout)

        layout.addWidget(image_group)

        # Connection settings group (for USB cameras like miniscopes)
        conn_group = QGroupBox("Connection")
        conn_group.setStyleSheet(touch_style)
        conn_layout = QFormLayout(conn_group)
        if self._is_touch_mode:
            conn_layout.setSpacing(12)
            conn_layout.setContentsMargins(12, 20, 12, 12)

        self._backend_camera_combo = QComboBox()
        self._backend_camera_combo.addItem("Auto-detect", None)
        self._backend_camera_combo.addItem("V4L2 (USB)", "v4l2")
        self._backend_camera_combo.addItem("Picamera2", "picamera2")
        self._backend_camera_combo.setToolTip(
            "Force a specific camera backend.\n"
            "Use V4L2 for USB cameras like miniscopes.\n"
            "Use Picamera2 for Raspberry Pi camera modules."
        )
        conn_layout.addRow("Backend:", self._backend_camera_combo)

        self._timeout_spin = QDoubleSpinBox()
        self._timeout_spin.setRange(1.0, 30.0)
        self._timeout_spin.setValue(5.0)
        self._timeout_spin.setSingleStep(1.0)
        self._timeout_spin.setSuffix(" s")
        self._timeout_spin.setToolTip(
            "Connection timeout for camera initialization.\n"
            "Increase this for slow USB cameras like miniscopes (try 10-15s)."
        )
        conn_layout.addRow("Timeout:", self._timeout_spin)

        self._pixel_format_combo = QComboBox()
        self._pixel_format_combo.addItem("Auto-detect", None)
        self._pixel_format_combo.addItem("YUYV (Miniscope)", "YUYV")
        self._pixel_format_combo.addItem("MJPG", "MJPG")
        self._pixel_format_combo.setToolTip(
            "Pixel format for video capture.\n"
            "Use YUYV for miniscopes.\n"
            "Use MJPG for most webcams."
        )
        conn_layout.addRow("Format:", self._pixel_format_combo)

        self._miniscope_mode_cb = QCheckBox("Miniscope Mode")
        self._miniscope_mode_cb.setToolTip(
            "Enable special initialization for UCLA Miniscope cameras.\n"
            "This runs v4l2-ctl commands to wake up the LED and\n"
            "includes a watchdog to re-trigger if image goes dark."
        )
        self._miniscope_mode_cb.toggled.connect(self._on_miniscope_mode_toggle)
        conn_layout.addRow(self._miniscope_mode_cb)

        layout.addWidget(conn_group)
        layout.addStretch()

        return widget

    def _create_cv_tab_content(self) -> QWidget:
        """Create the computer vision settings tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Adjust spacing for touch mode
        if self._is_touch_mode:
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(16)

        touch_style = self._get_touch_group_style()

        # Enable CV - prominent checkbox at top
        self._cv_enabled_cb = QCheckBox("Enable CV Processing")
        if self._is_touch_mode:
            self._cv_enabled_cb.setStyleSheet("""
                QCheckBox {
                    font-size: 16px;
                    font-weight: bold;
                    padding: 8px;
                    spacing: 12px;
                }
                QCheckBox::indicator {
                    width: 32px;
                    height: 32px;
                }
            """)
        self._cv_enabled_cb.toggled.connect(self._on_cv_enabled_toggle)
        layout.addWidget(self._cv_enabled_cb)

        # Detection group
        detection_group = QGroupBox("Detection")
        detection_group.setStyleSheet(touch_style)
        detection_layout = QFormLayout(detection_group)
        if self._is_touch_mode:
            detection_layout.setSpacing(12)
            detection_layout.setContentsMargins(12, 20, 12, 12)

        self._backend_combo = QComboBox()
        self._backend_combo.addItem("Background Sub", DetectionBackend.BACKGROUND_SUBTRACTION)
        self._backend_combo.addItem("Motion Only", DetectionBackend.MOTION_ONLY)
        self._backend_combo.addItem("YOLO v8", DetectionBackend.YOLO_V8)
        self._backend_combo.addItem("YOLO+ByteTrack", DetectionBackend.YOLO_BYTETRACK)
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        detection_layout.addRow("Backend:", self._backend_combo)

        # YOLO model path (only visible for YOLO backend)
        model_layout = QHBoxLayout()
        model_layout.setSpacing(8)
        self._model_path_edit = QLineEdit()
        self._model_path_edit.setPlaceholderText("YOLO model (.pt)")
        model_layout.addWidget(self._model_path_edit)

        self._browse_model_btn = QPushButton("...")
        if self._is_touch_mode:
            self._browse_model_btn.setMinimumSize(50, 40)
        self._browse_model_btn.clicked.connect(self._browse_model)
        model_layout.addWidget(self._browse_model_btn)

        self._model_path_label = QLabel("Model:")
        detection_layout.addRow(self._model_path_label, model_layout)

        # Confidence threshold
        self._confidence_spin = QDoubleSpinBox()
        self._confidence_spin.setRange(0.1, 1.0)
        self._confidence_spin.setSingleStep(0.05)
        self._confidence_spin.setValue(0.5)
        detection_layout.addRow("Confidence:", self._confidence_spin)

        # Min contour area
        self._min_area_spin = QSpinBox()
        self._min_area_spin.setRange(100, 50000)
        self._min_area_spin.setValue(500)
        self._min_area_spin.setSuffix(" px")
        detection_layout.addRow("Min Area:", self._min_area_spin)

        # Frame skip for performance (process every N frames)
        self._frame_skip_spin = QSpinBox()
        self._frame_skip_spin.setRange(1, 10)
        self._frame_skip_spin.setValue(1)
        self._frame_skip_spin.setToolTip(
            "Process CV every N frames. Higher values improve FPS but reduce tracking accuracy.\n"
            "1 = process every frame, 3 = process every 3rd frame (3x faster)"
        )
        detection_layout.addRow("Skip Frames:", self._frame_skip_spin)

        layout.addWidget(detection_group)

        # Overlay group
        overlay_group = QGroupBox("Display")
        overlay_group.setStyleSheet(touch_style)
        overlay_layout = QFormLayout(overlay_group)
        if self._is_touch_mode:
            overlay_layout.setSpacing(12)
            overlay_layout.setContentsMargins(12, 20, 12, 12)

        self._draw_overlays_cb = QCheckBox("Bounding Boxes")
        self._draw_overlays_cb.setChecked(True)
        overlay_layout.addRow(self._draw_overlays_cb)

        self._draw_tracks_cb = QCheckBox("Motion Tracks")
        self._draw_tracks_cb.setChecked(True)
        overlay_layout.addRow(self._draw_tracks_cb)

        self._draw_contours_cb = QCheckBox("Contours")
        self._draw_contours_cb.setChecked(False)
        overlay_layout.addRow(self._draw_contours_cb)

        layout.addWidget(overlay_group)
        layout.addStretch()

        return widget

    def _create_tracking_tab_content(self) -> QWidget:
        """Create the tracking settings tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Adjust spacing for touch mode
        if self._is_touch_mode:
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(16)

        touch_style = self._get_touch_group_style()

        # Enable tracking - prominent checkbox at top
        self._tracking_enabled_cb = QCheckBox("Enable Tracking")
        if self._is_touch_mode:
            self._tracking_enabled_cb.setStyleSheet("""
                QCheckBox {
                    font-size: 16px;
                    font-weight: bold;
                    padding: 8px;
                    spacing: 12px;
                }
                QCheckBox::indicator {
                    width: 32px;
                    height: 32px;
                }
            """)
        self._tracking_enabled_cb.toggled.connect(self._on_tracking_enabled_toggle)
        layout.addWidget(self._tracking_enabled_cb)

        # Tracking parameters
        tracking_group = QGroupBox("Tracking")
        tracking_group.setStyleSheet(touch_style)
        tracking_layout = QFormLayout(tracking_group)
        if self._is_touch_mode:
            tracking_layout.setSpacing(12)
            tracking_layout.setContentsMargins(12, 20, 12, 12)

        self._max_disappeared_spin = QSpinBox()
        self._max_disappeared_spin.setRange(1, 200)
        self._max_disappeared_spin.setValue(50)
        self._max_disappeared_spin.setSuffix(" frames")
        tracking_layout.addRow("Max Lost:", self._max_disappeared_spin)

        # Only show help text in desktop mode (too verbose for touch)
        if not self._is_touch_mode:
            help_label = QLabel(
                "Number of consecutive frames an object can be missing\n"
                "before it is deregistered from tracking."
            )
            help_label.setStyleSheet("color: #888; font-size: 11px;")
            tracking_layout.addRow(help_label)

        self._max_distance_spin = QSpinBox()
        self._max_distance_spin.setRange(10, 500)
        self._max_distance_spin.setValue(100)
        self._max_distance_spin.setSuffix(" px")
        tracking_layout.addRow("Max Distance:", self._max_distance_spin)

        # Only show help text in desktop mode
        if not self._is_touch_mode:
            distance_help = QLabel(
                "Maximum distance (in pixels) an object can move\n"
                "between frames and still be considered the same object."
            )
            distance_help.setStyleSheet("color: #888; font-size: 11px;")
            tracking_layout.addRow(distance_help)

        layout.addWidget(tracking_group)

        # Motion detection
        motion_group = QGroupBox("Motion")
        motion_group.setStyleSheet(touch_style)
        motion_layout = QFormLayout(motion_group)
        if self._is_touch_mode:
            motion_layout.setSpacing(12)
            motion_layout.setContentsMargins(12, 20, 12, 12)

        self._motion_threshold_spin = QSpinBox()
        self._motion_threshold_spin.setRange(1, 100)
        self._motion_threshold_spin.setValue(25)
        motion_layout.addRow("Threshold:", self._motion_threshold_spin)

        self._motion_area_spin = QDoubleSpinBox()
        self._motion_area_spin.setRange(0.1, 50.0)
        self._motion_area_spin.setValue(1.0)
        self._motion_area_spin.setSuffix(" %")
        motion_layout.addRow("Min Area:", self._motion_area_spin)

        layout.addWidget(motion_group)
        layout.addStretch()

        return widget

    def _load_settings(self):
        """Load current settings into the UI."""
        # Camera settings
        res = self._camera_settings.resolution
        for i in range(self._resolution_combo.count()):
            if self._resolution_combo.itemData(i) == res:
                self._resolution_combo.setCurrentIndex(i)
                break

        self._fps_spin.setValue(self._camera_settings.fps)

        if self._camera_settings.exposure == -1:
            self._auto_exposure_cb.setChecked(True)
        else:
            self._auto_exposure_cb.setChecked(False)
            self._exposure_slider.setValue(self._camera_settings.exposure)

        self._brightness_slider.setValue(self._camera_settings.brightness)
        self._contrast_slider.setValue(self._camera_settings.contrast)

        # Connection settings
        self._timeout_spin.setValue(self._camera_settings.connection_timeout)
        for i in range(self._backend_camera_combo.count()):
            if self._backend_camera_combo.itemData(i) == self._camera_settings.force_backend:
                self._backend_camera_combo.setCurrentIndex(i)
                break
        for i in range(self._pixel_format_combo.count()):
            if self._pixel_format_combo.itemData(i) == self._camera_settings.pixel_format:
                self._pixel_format_combo.setCurrentIndex(i)
                break
        self._miniscope_mode_cb.setChecked(self._camera_settings.miniscope_mode)

        # CV settings
        self._cv_enabled_cb.setChecked(self._cv_settings.enabled)

        for i in range(self._backend_combo.count()):
            if self._backend_combo.itemData(i) == self._cv_settings.backend:
                self._backend_combo.setCurrentIndex(i)
                break

        if self._cv_settings.model_path:
            self._model_path_edit.setText(self._cv_settings.model_path)

        self._confidence_spin.setValue(self._cv_settings.confidence_threshold)
        self._min_area_spin.setValue(self._cv_settings.min_detection_area)
        self._frame_skip_spin.setValue(self._cv_settings.process_every_n_frames)
        self._draw_overlays_cb.setChecked(self._cv_settings.draw_overlays)

        # Tracking settings
        self._tracking_enabled_cb.setChecked(self._cv_settings.tracking_enabled)
        self._max_disappeared_spin.setValue(self._cv_settings.max_disappeared)

        # Update UI state
        self._on_cv_enabled_toggle(self._cv_settings.enabled)
        self._on_backend_changed(self._backend_combo.currentIndex())
        self._on_tracking_enabled_toggle(self._cv_settings.tracking_enabled)

    def _on_auto_exposure_toggle(self, checked: bool):
        """Handle auto exposure toggle."""
        self._exposure_slider.setEnabled(not checked)
        self._exposure_label.setEnabled(not checked)

    def _on_cv_enabled_toggle(self, enabled: bool):
        """Handle CV enabled toggle."""
        self._backend_combo.setEnabled(enabled)
        self._confidence_spin.setEnabled(enabled)
        self._min_area_spin.setEnabled(enabled)
        self._frame_skip_spin.setEnabled(enabled)
        self._draw_overlays_cb.setEnabled(enabled)
        self._draw_tracks_cb.setEnabled(enabled)
        self._draw_contours_cb.setEnabled(enabled)
        if enabled:
            self._on_backend_changed(self._backend_combo.currentIndex())

    def _on_backend_changed(self, index: int):
        """Handle backend selection change."""
        backend = self._backend_combo.itemData(index)
        is_yolo = backend in (DetectionBackend.YOLO_V8, DetectionBackend.YOLO_BYTETRACK)
        self._model_path_edit.setVisible(is_yolo)
        self._model_path_label.setVisible(is_yolo)
        self._browse_model_btn.setVisible(is_yolo)

    def _on_tracking_enabled_toggle(self, enabled: bool):
        """Handle tracking enabled toggle."""
        self._max_disappeared_spin.setEnabled(enabled)
        self._max_distance_spin.setEnabled(enabled)

    def _on_miniscope_mode_toggle(self, enabled: bool):
        """Handle miniscope mode toggle - auto-set recommended values."""
        if enabled:
            # Auto-set recommended miniscope settings
            # Set resolution to 608x608
            for i in range(self._resolution_combo.count()):
                if self._resolution_combo.itemData(i) == (608, 608):
                    self._resolution_combo.setCurrentIndex(i)
                    break
            # Set pixel format to YUYV
            for i in range(self._pixel_format_combo.count()):
                if self._pixel_format_combo.itemData(i) == "YUYV":
                    self._pixel_format_combo.setCurrentIndex(i)
                    break
            # Set backend to V4L2
            for i in range(self._backend_camera_combo.count()):
                if self._backend_camera_combo.itemData(i) == "v4l2":
                    self._backend_camera_combo.setCurrentIndex(i)
                    break
            # Increase timeout
            self._timeout_spin.setValue(10.0)

    def _browse_model(self):
        """Browse for YOLO model file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select YOLO Model",
            "",
            "PyTorch Models (*.pt);;All Files (*)"
        )
        if path:
            self._model_path_edit.setText(path)

    def _apply_settings(self):
        """Apply settings without closing dialog."""
        self._save_settings()
        logger.info("Camera settings applied")

    def _save_settings(self):
        """Save UI values to settings objects."""
        # Camera settings
        self._camera_settings.resolution = self._resolution_combo.currentData()
        self._camera_settings.fps = self._fps_spin.value()

        if self._auto_exposure_cb.isChecked():
            self._camera_settings.exposure = -1
        else:
            self._camera_settings.exposure = self._exposure_slider.value()

        self._camera_settings.brightness = self._brightness_slider.value()
        self._camera_settings.contrast = self._contrast_slider.value()
        self._camera_settings.connection_timeout = self._timeout_spin.value()
        self._camera_settings.force_backend = self._backend_camera_combo.currentData()
        self._camera_settings.pixel_format = self._pixel_format_combo.currentData()
        self._camera_settings.miniscope_mode = self._miniscope_mode_cb.isChecked()

        # CV settings
        self._cv_settings.enabled = self._cv_enabled_cb.isChecked()
        self._cv_settings.backend = self._backend_combo.currentData()
        self._cv_settings.model_path = self._model_path_edit.text() or None
        self._cv_settings.confidence_threshold = self._confidence_spin.value()
        self._cv_settings.min_detection_area = self._min_area_spin.value()
        self._cv_settings.process_every_n_frames = self._frame_skip_spin.value()
        self._cv_settings.draw_overlays = self._draw_overlays_cb.isChecked()
        self._cv_settings.tracking_enabled = self._tracking_enabled_cb.isChecked()
        self._cv_settings.max_disappeared = self._max_disappeared_spin.value()

    def accept(self):
        """Handle dialog acceptance."""
        self._save_settings()
        super().accept()

    def get_camera_settings(self) -> CameraSettings:
        """Get the camera settings."""
        return self._camera_settings

    def get_cv_settings(self) -> CVSettings:
        """Get the CV settings."""
        return self._cv_settings
