"""
Main Window - The primary PyQt6 window for GLIDER.

Manages the high-level layout and view switching between
Desktop (Builder) and Runner modes.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QStatusBar,
    QMenuBar,
    QMenu,
    QFileDialog,
    QMessageBox,
    QDockWidget,
    QLabel,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QComboBox,
    QGroupBox,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QScrollArea,
    QFrame,
    QPlainTextEdit,
    QCheckBox,
)
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QDrag
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QMimeData, QTimer

from glider.gui.view_manager import ViewManager, ViewMode
from glider.gui.node_graph.graph_view import NodeGraphView
from glider.hal.base_board import BoardConnectionState

if TYPE_CHECKING:
    from glider.core.glider_core import GliderCore

logger = logging.getLogger(__name__)


# =============================================================================
# Undo/Redo Command Pattern Implementation
# =============================================================================

class Command:
    """Base class for undoable commands."""

    def execute(self) -> None:
        """Execute the command."""
        raise NotImplementedError

    def undo(self) -> None:
        """Undo the command."""
        raise NotImplementedError

    def description(self) -> str:
        """Human-readable description."""
        return "Unknown command"


class CreateNodeCommand(Command):
    """Command for creating a node."""

    def __init__(self, main_window: "MainWindow", node_id: str, node_type: str, x: float, y: float):
        self._main_window = main_window
        self._node_id = node_id
        self._node_type = node_type
        self._x = x
        self._y = y

    def execute(self) -> None:
        """Create the node."""
        # Node is already created when command is recorded
        pass

    def undo(self) -> None:
        """Delete the node."""
        self._main_window._graph_view.remove_node(self._node_id)
        if self._main_window._core.session:
            self._main_window._core.session.remove_node(self._node_id)

    def description(self) -> str:
        return f"Create {self._node_type}"


class DeleteNodeCommand(Command):
    """Command for deleting a node."""

    def __init__(self, main_window: "MainWindow", node_id: str, node_data: dict):
        self._main_window = main_window
        self._node_id = node_id
        self._node_data = node_data  # Saved node state for restoration

    def execute(self) -> None:
        """Delete is already done when command is recorded."""
        pass

    def undo(self) -> None:
        """Restore the node."""
        data = self._node_data
        node_item = self._main_window._graph_view.add_node(
            data["id"], data["node_type"], data["x"], data["y"]
        )
        self._main_window._setup_node_ports(node_item, data["node_type"])
        self._main_window._graph_view._connect_port_signals(node_item)

        if self._main_window._core.session:
            from glider.core.experiment_session import NodeConfig
            node_config = NodeConfig(
                id=data["id"],
                node_type=data["node_type"],
                position=(data["x"], data["y"]),
                state=data.get("state", {}),
                device_id=data.get("device_id"),
                visible_in_runner=data.get("visible_in_runner", False),
            )
            self._main_window._core.session.add_node(node_config)

    def description(self) -> str:
        return f"Delete {self._node_data.get('node_type', 'node')}"


class MoveNodeCommand(Command):
    """Command for moving a node."""

    def __init__(self, main_window: "MainWindow", node_id: str, old_x: float, old_y: float, new_x: float, new_y: float):
        self._main_window = main_window
        self._node_id = node_id
        self._old_x = old_x
        self._old_y = old_y
        self._new_x = new_x
        self._new_y = new_y

    def execute(self) -> None:
        """Move is already done when command is recorded."""
        pass

    def undo(self) -> None:
        """Move node back to original position."""
        node_item = self._main_window._graph_view.nodes.get(self._node_id)
        if node_item:
            node_item.setPos(self._old_x, self._old_y)
        if self._main_window._core.session:
            self._main_window._core.session.update_node_position(self._node_id, self._old_x, self._old_y)

    def description(self) -> str:
        return "Move node"


class CreateConnectionCommand(Command):
    """Command for creating a connection."""

    def __init__(self, main_window: "MainWindow", conn_id: str, from_node: str, from_port: int, to_node: str, to_port: int, conn_type: str):
        self._main_window = main_window
        self._conn_id = conn_id
        self._from_node = from_node
        self._from_port = from_port
        self._to_node = to_node
        self._to_port = to_port
        self._conn_type = conn_type

    def execute(self) -> None:
        """Connection is already created when command is recorded."""
        pass

    def undo(self) -> None:
        """Remove the connection."""
        self._main_window._graph_view.remove_connection(self._conn_id)
        if self._main_window._core.session:
            self._main_window._core.session.remove_connection(self._conn_id)

    def description(self) -> str:
        return "Create connection"


class DeleteConnectionCommand(Command):
    """Command for deleting a connection."""

    def __init__(self, main_window: "MainWindow", conn_id: str, conn_data: dict):
        self._main_window = main_window
        self._conn_id = conn_id
        self._conn_data = conn_data

    def execute(self) -> None:
        """Deletion is already done when command is recorded."""
        pass

    def undo(self) -> None:
        """Restore the connection."""
        data = self._conn_data
        self._main_window._graph_view.add_connection(
            data["id"], data["from_node"], data["from_port"], data["to_node"], data["to_port"]
        )
        if self._main_window._core.session:
            from glider.core.experiment_session import ConnectionConfig
            conn_config = ConnectionConfig(
                id=data["id"],
                from_node=data["from_node"],
                from_output=data["from_port"],
                to_node=data["to_node"],
                to_input=data["to_port"],
                connection_type=data.get("conn_type", "data"),
            )
            self._main_window._core.session.add_connection(conn_config)

    def description(self) -> str:
        return "Delete connection"


class PropertyChangeCommand(Command):
    """Command for changing a node property."""

    def __init__(self, main_window: "MainWindow", node_id: str, prop_name: str, old_value, new_value):
        self._main_window = main_window
        self._node_id = node_id
        self._prop_name = prop_name
        self._old_value = old_value
        self._new_value = new_value

    def execute(self) -> None:
        """Property is already changed when command is recorded."""
        pass

    def undo(self) -> None:
        """Restore old property value."""
        if self._main_window._core.session:
            self._main_window._core.session.update_node_state(self._node_id, {self._prop_name: self._old_value})

    def description(self) -> str:
        return f"Change {self._prop_name}"


class UndoStack:
    """Manages undo/redo history."""

    def __init__(self, max_size: int = 100):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_size = max_size

    def push(self, command: Command) -> None:
        """Add a command to the undo stack."""
        self._undo_stack.append(command)
        # Clear redo stack when new command is added
        self._redo_stack.clear()
        # Limit stack size
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)

    def undo(self) -> Optional[Command]:
        """Undo the last command."""
        if not self._undo_stack:
            return None
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        return command

    def redo(self) -> Optional[Command]:
        """Redo the last undone command."""
        if not self._redo_stack:
            return None
        command = self._redo_stack.pop()
        # Re-execute by undoing the undo (for property changes, we need to swap values)
        # For most commands, we need to re-apply the action
        self._undo_stack.append(command)
        return command

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self) -> None:
        """Clear both stacks."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    def undo_description(self) -> str:
        """Get description of next undo action."""
        if self._undo_stack:
            return self._undo_stack[-1].description()
        return ""

    def redo_description(self) -> str:
        """Get description of next redo action."""
        if self._redo_stack:
            return self._redo_stack[-1].description()
        return ""


class DraggableNodeButton(QPushButton):
    """A button that can be dragged to create nodes in the graph."""

    def __init__(self, node_type: str, display_name: str, category: str, parent=None):
        super().__init__(display_name, parent)
        self._node_type = node_type
        self._category = category

        # Use Qt properties for styling (defined in desktop.qss)
        self.setProperty("nodeCategory", category)
        self.setProperty("nodeButton", True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        """Handle mouse press for drag initiation."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for drag operation."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        if not hasattr(self, '_drag_start_pos'):
            return

        # Check if we've moved enough to start a drag
        if (event.pos() - self._drag_start_pos).manhattanLength() < 10:
            return

        # Create drag
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(f"node:{self._node_type}")
        drag.setMimeData(mime_data)

        # Execute drag
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class MainWindow(QMainWindow):
    """
    Main application window for GLIDER.

    Uses a QStackedWidget to switch between:
    - Index 0: Builder view (Desktop mode with node graph)
    - Index 1: Runner view (Touch-optimized dashboard)
    """

    # Signals
    session_changed = pyqtSignal()
    state_changed = pyqtSignal(str)  # Session state name
    error_occurred = pyqtSignal(str, str)  # source, message

    def __init__(self, core: "GliderCore", view_mode: ViewMode = ViewMode.AUTO):
        """
        Initialize the main window.

        Args:
            core: GliderCore instance
            view_mode: Initial view mode
        """
        super().__init__()

        self._core = core
        self._view_manager = ViewManager(None)
        self._view_manager.mode = view_mode

        # Undo/Redo stack
        self._undo_stack = UndoStack()

        # Async task tracking to prevent garbage collection
        self._pending_tasks: set = set()

        # UI components
        self._stack: Optional[QStackedWidget] = None
        self._builder_view: Optional[QWidget] = None
        self._runner_view: Optional[QWidget] = None
        self._node_library_dock: Optional[QDockWidget] = None
        self._properties_dock: Optional[QDockWidget] = None

        # Setup UI
        self._setup_window()
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_status_bar()
        self._connect_signals()

        # Apply stylesheet
        self._view_manager.apply_stylesheet(self)

        logger.info(f"MainWindow initialized in {self._view_manager.mode.name} mode")

    @property
    def core(self) -> "GliderCore":
        """Get the GliderCore instance."""
        return self._core

    @property
    def view_manager(self) -> ViewManager:
        """Get the view manager."""
        return self._view_manager

    @property
    def is_runner_mode(self) -> bool:
        """Whether in runner mode."""
        return self._view_manager.is_runner_mode

    def _setup_window(self) -> None:
        """Configure the main window properties."""
        self.setWindowTitle("GLIDER - General Laboratory Interface")

        if self._view_manager.is_runner_mode:
            # Runner mode: fullscreen, no frame
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.showFullScreen()
        else:
            # Desktop mode: standard window
            self.setMinimumSize(1024, 768)
            self.resize(1400, 900)

    def _setup_ui(self) -> None:
        """Set up the main UI components."""
        # Central stacked widget
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Create views
        self._create_builder_view()
        self._create_runner_view()

        # Add to stack
        self._stack.addWidget(self._builder_view)  # Index 0
        self._stack.addWidget(self._runner_view)   # Index 1

        # Set initial view based on mode
        if self._view_manager.is_runner_mode:
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)
            self._setup_dock_widgets()

    def _create_builder_view(self) -> None:
        """Create the builder (desktop) view."""
        self._builder_view = QWidget()
        layout = QVBoxLayout(self._builder_view)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main splitter for graph and properties
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Node graph view (actual graph editor)
        self._graph_view = NodeGraphView()
        self._graph_view.setMinimumSize(400, 300)

        # Connect graph view signals
        self._graph_view.node_created.connect(self._on_node_created)
        self._graph_view.node_deleted.connect(self._on_node_deleted)
        self._graph_view.node_selected.connect(self._on_node_selected)
        self._graph_view.node_moved.connect(self._on_node_moved)
        self._graph_view.connection_created.connect(self._on_connection_created)
        self._graph_view.connection_deleted.connect(self._on_connection_deleted)

        splitter.addWidget(self._graph_view)
        layout.addWidget(splitter)

    def _create_runner_view(self) -> None:
        """Create the runner (dashboard) view optimized for 480x800 portrait."""
        self._runner_view = QWidget()
        self._runner_view.setObjectName("runnerView")
        layout = QVBoxLayout(self._runner_view)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # === Header Bar ===
        header = QWidget()
        header.setFixedHeight(50)
        header.setProperty("runnerHeader", True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 4)

        # Experiment name
        self._runner_exp_name = QLabel("No Experiment")
        self._runner_exp_name.setProperty("title", True)
        header_layout.addWidget(self._runner_exp_name)

        header_layout.addStretch()

        # Status indicator - uses properties for styling
        self._status_label = QLabel("IDLE")
        self._status_label.setProperty("runnerStatus", True)
        self._status_label.setProperty("statusState", "IDLE")
        header_layout.addWidget(self._status_label)

        layout.addWidget(header)

        # === Recording Indicator ===
        self._runner_recording = QLabel("● REC")
        self._runner_recording.setProperty("recording", True)
        self._runner_recording.setFixedHeight(28)
        self._runner_recording.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._runner_recording.hide()  # Hidden until recording starts
        layout.addWidget(self._runner_recording)

        # === Device Status Area (Scrollable) ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent;")

        # Enable kinetic scrolling
        from PyQt6.QtWidgets import QScroller
        QScroller.grabGesture(scroll.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        # Content widget for device cards
        self._runner_devices_widget = QWidget()
        self._runner_devices_layout = QVBoxLayout(self._runner_devices_widget)
        self._runner_devices_layout.setContentsMargins(0, 0, 0, 0)
        self._runner_devices_layout.setSpacing(8)

        # Placeholder for devices
        self._runner_no_devices = QLabel("Connect hardware to see devices")
        self._runner_no_devices.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._runner_no_devices.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 14px;
                padding: 40px;
            }
        """)
        self._runner_devices_layout.addWidget(self._runner_no_devices)
        self._runner_devices_layout.addStretch()

        scroll.setWidget(self._runner_devices_widget)
        layout.addWidget(scroll, 1)

        # === Control Buttons ===
        controls = QWidget()
        controls.setFixedHeight(160)
        controls.setProperty("runnerControls", True)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(8)

        # Top row: START and STOP
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._start_btn = QPushButton("▶  START")
        self._start_btn.setFixedHeight(60)
        self._start_btn.setProperty("runnerAction", "start")
        self._start_btn.clicked.connect(self._on_start_clicked)
        top_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("■  STOP")
        self._stop_btn.setFixedHeight(60)
        self._stop_btn.setProperty("runnerAction", "stop")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        top_row.addWidget(self._stop_btn)

        controls_layout.addLayout(top_row)

        # Bottom row: E-STOP (full width)
        self._emergency_btn = QPushButton("⚠  EMERGENCY STOP")
        self._emergency_btn.setFixedHeight(60)
        self._emergency_btn.setProperty("runnerAction", "emergency")
        self._emergency_btn.clicked.connect(self._on_emergency_stop)
        controls_layout.addWidget(self._emergency_btn)

        layout.addWidget(controls)

        # Store device widgets for updates
        self._runner_device_cards: Dict[str, QWidget] = {}

        # Timer for periodic device state updates in runner view
        self._device_refresh_timer = QTimer()
        self._device_refresh_timer.setInterval(250)  # 250ms refresh rate
        self._device_refresh_timer.timeout.connect(self._update_runner_device_states)

    def _setup_dock_widgets(self) -> None:
        """Set up dock widgets for desktop mode."""
        if self._view_manager.is_runner_mode:
            return

        # Node Library dock
        self._node_library_dock = QDockWidget("Node Library", self)
        self._node_library_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        library_widget = self._create_node_library()
        self._node_library_dock.setWidget(library_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._node_library_dock)

        # Properties dock
        self._properties_dock = QDockWidget("Properties", self)
        self._properties_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        properties_widget = QWidget()
        properties_layout = QVBoxLayout(properties_widget)
        properties_layout.addWidget(QLabel("Select a node to view properties"))
        properties_layout.addStretch()
        self._properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._properties_dock)

        # Hardware Panel dock
        self._hardware_dock = QDockWidget("Hardware", self)
        self._hardware_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        hardware_widget = QWidget()
        hardware_layout = QVBoxLayout(hardware_widget)
        hardware_layout.setContentsMargins(4, 4, 4, 4)

        # Hardware tree
        self._hardware_tree = QTreeWidget()
        self._hardware_tree.setHeaderLabels(["Name", "Type", "Status"])
        self._hardware_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._hardware_tree.customContextMenuRequested.connect(self._on_hardware_context_menu)
        hardware_layout.addWidget(self._hardware_tree)

        # Hardware buttons
        hw_btn_layout = QHBoxLayout()
        add_board_btn = QPushButton("+ Board")
        add_board_btn.clicked.connect(self._on_add_board)
        hw_btn_layout.addWidget(add_board_btn)

        add_device_btn = QPushButton("+ Device")
        add_device_btn.clicked.connect(self._on_add_device)
        hw_btn_layout.addWidget(add_device_btn)

        hardware_layout.addLayout(hw_btn_layout)

        self._hardware_dock.setWidget(hardware_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._hardware_dock)

        # Device Control Panel dock
        self._control_dock = QDockWidget("Device Control", self)
        self._control_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        control_widget = QWidget()
        self._control_layout = QVBoxLayout(control_widget)
        self._control_layout.setContentsMargins(4, 4, 4, 4)

        # Device selector
        device_group = QGroupBox("Select Device")
        device_group_layout = QVBoxLayout(device_group)

        self._device_combo = QComboBox()
        self._device_combo.currentTextChanged.connect(self._on_device_selected)
        device_group_layout.addWidget(self._device_combo)

        self._control_layout.addWidget(device_group)

        # Control buttons group
        self._control_group = QGroupBox("Controls")
        self._control_group_layout = QVBoxLayout(self._control_group)

        # Digital output controls
        digital_layout = QHBoxLayout()
        self._on_btn = QPushButton("ON (HIGH)")
        self._on_btn.clicked.connect(lambda: self._set_digital_output(True))
        self._off_btn = QPushButton("OFF (LOW)")
        self._off_btn.clicked.connect(lambda: self._set_digital_output(False))
        self._toggle_btn = QPushButton("Toggle")
        self._toggle_btn.clicked.connect(self._toggle_digital_output)
        digital_layout.addWidget(self._on_btn)
        digital_layout.addWidget(self._off_btn)
        digital_layout.addWidget(self._toggle_btn)
        self._control_group_layout.addLayout(digital_layout)

        # PWM/Analog control
        pwm_layout = QHBoxLayout()
        pwm_label = QLabel("PWM Value:")
        self._pwm_slider = QSlider(Qt.Orientation.Horizontal)
        self._pwm_slider.setRange(0, 255)
        self._pwm_slider.valueChanged.connect(self._on_pwm_changed)
        self._pwm_spinbox = QSpinBox()
        self._pwm_spinbox.setRange(0, 255)
        self._pwm_spinbox.valueChanged.connect(self._pwm_slider.setValue)
        self._pwm_slider.valueChanged.connect(self._pwm_spinbox.setValue)
        pwm_layout.addWidget(pwm_label)
        pwm_layout.addWidget(self._pwm_slider)
        pwm_layout.addWidget(self._pwm_spinbox)
        self._control_group_layout.addLayout(pwm_layout)

        # Servo control
        servo_layout = QHBoxLayout()
        servo_label = QLabel("Servo Angle:")
        self._servo_slider = QSlider(Qt.Orientation.Horizontal)
        self._servo_slider.setRange(0, 180)
        self._servo_slider.setValue(90)
        self._servo_slider.valueChanged.connect(self._on_servo_changed)
        self._servo_spinbox = QSpinBox()
        self._servo_spinbox.setRange(0, 180)
        self._servo_spinbox.setValue(90)
        self._servo_spinbox.valueChanged.connect(self._servo_slider.setValue)
        self._servo_slider.valueChanged.connect(self._servo_spinbox.setValue)
        servo_layout.addWidget(servo_label)
        servo_layout.addWidget(self._servo_slider)
        servo_layout.addWidget(self._servo_spinbox)
        self._control_group_layout.addLayout(servo_layout)

        # Status display
        self._device_status_label = QLabel("Status: Not connected")
        self._control_group_layout.addWidget(self._device_status_label)

        self._control_layout.addWidget(self._control_group)
        self._control_layout.addStretch()

        self._control_dock.setWidget(control_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._control_dock)

        # Stack the control dock below the hardware dock
        self.tabifyDockWidget(self._hardware_dock, self._control_dock)
        self._hardware_dock.raise_()

        # Refresh hardware tree (which also refreshes the device combo)
        self._refresh_hardware_tree()

    def _setup_menu(self) -> None:
        """Set up the menu bar."""
        if self._view_manager.is_runner_mode:
            return  # No menu in runner mode

        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new)
        file_menu.addAction(new_action)

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self._undo_action = QAction("&Undo", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._on_undo)
        self._undo_action.setEnabled(False)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("&Redo", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self._on_redo)
        self._redo_action.setEnabled(False)
        edit_menu.addAction(self._redo_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        switch_view_action = QAction("Switch to &Runner View", self)
        switch_view_action.setShortcut(QKeySequence("F11"))
        switch_view_action.triggered.connect(self._toggle_view)
        view_menu.addAction(switch_view_action)

        view_menu.addSeparator()

        # Window size presets
        pi_view_action = QAction("&Pi Display (480x800)", self)
        pi_view_action.triggered.connect(lambda: self._set_window_size(480, 800))
        view_menu.addAction(pi_view_action)

        compact_view_action = QAction("&Compact (1024x768)", self)
        compact_view_action.triggered.connect(lambda: self._set_window_size(1024, 768))
        view_menu.addAction(compact_view_action)

        default_view_action = QAction("&Default (1400x900)", self)
        default_view_action.triggered.connect(lambda: self._set_window_size(1400, 900))
        view_menu.addAction(default_view_action)

        # Hardware menu
        hardware_menu = menubar.addMenu("&Hardware")

        add_board_action = QAction("Add &Board...", self)
        add_board_action.triggered.connect(self._on_add_board)
        hardware_menu.addAction(add_board_action)

        add_device_action = QAction("Add &Device...", self)
        add_device_action.triggered.connect(self._on_add_device)
        hardware_menu.addAction(add_device_action)

        hardware_menu.addSeparator()

        connect_action = QAction("&Connect All", self)
        connect_action.triggered.connect(self._on_connect_hardware)
        hardware_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect All", self)
        disconnect_action.triggered.connect(self._on_disconnect_hardware)
        hardware_menu.addAction(disconnect_action)

        # Run menu
        run_menu = menubar.addMenu("&Run")

        start_action = QAction("&Start", self)
        start_action.setShortcut(QKeySequence("F5"))
        start_action.triggered.connect(self._on_start_clicked)
        run_menu.addAction(start_action)

        stop_action = QAction("S&top", self)
        stop_action.setShortcut(QKeySequence("Shift+F5"))
        stop_action.triggered.connect(self._on_stop_clicked)
        run_menu.addAction(stop_action)

        run_menu.addSeparator()

        emergency_action = QAction("&Emergency Stop", self)
        emergency_action.setShortcut(QKeySequence("Ctrl+Shift+Escape"))
        emergency_action.triggered.connect(self._on_emergency_stop)
        run_menu.addAction(emergency_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About GLIDER", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self) -> None:
        """Set up the toolbar."""
        if self._view_manager.is_runner_mode:
            return

        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Add toolbar actions with proper connections
        new_action = toolbar.addAction("New")
        new_action.triggered.connect(self._on_new)

        open_action = toolbar.addAction("Open")
        open_action.triggered.connect(self._on_open)

        save_action = toolbar.addAction("Save")
        save_action.triggered.connect(self._on_save)

        toolbar.addSeparator()

        connect_action = toolbar.addAction("Connect")
        connect_action.triggered.connect(self._on_connect_hardware)

        toolbar.addSeparator()

        start_action = toolbar.addAction("Start")
        start_action.triggered.connect(self._on_start_clicked)

        stop_action = toolbar.addAction("Stop")
        stop_action.triggered.connect(self._on_stop_clicked)

        # Add spacer to push status to the right
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        from PyQt6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Persistent status indicator - uses properties for styling
        self._toolbar_status = QLabel("IDLE")
        self._toolbar_status.setProperty("statusIndicator", True)
        self._toolbar_status.setProperty("statusState", "IDLE")
        toolbar.addWidget(self._toolbar_status)

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        if self._view_manager.is_runner_mode:
            return

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Ready")

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Connect core callbacks
        self._core.on_state_change(self._on_core_state_change)
        self._core.on_error(self._on_core_error)

        # Connect hardware connection change callback for disconnect handling
        self._core.hardware_manager.on_connection_change(self._on_hardware_connection_change)

        # Connect session changed to update runner view
        self.session_changed.connect(self._update_runner_experiment_name)

    def _on_core_state_change(self, state) -> None:
        """Handle core state changes."""
        state_name = state.name
        self.state_changed.emit(state_name)

        # Update runner view status label - uses property for color (defined in QSS)
        if hasattr(self, '_status_label'):
            self._status_label.setText(state_name)
            self._status_label.setProperty("statusState", state_name)
            self._status_label.style().unpolish(self._status_label)
            self._status_label.style().polish(self._status_label)

        # Update toolbar status indicator - uses property for color (defined in QSS)
        if hasattr(self, '_toolbar_status'):
            self._toolbar_status.setText(state_name)
            self._toolbar_status.setProperty("statusState", state_name)
            self._toolbar_status.style().unpolish(self._toolbar_status)
            self._toolbar_status.style().polish(self._toolbar_status)

        if hasattr(self, 'statusBar') and self.statusBar():
            self.statusBar().showMessage(f"State: {state_name}")

        # Update runner view recording indicator
        if hasattr(self, '_runner_recording'):
            if state_name == "RUNNING" and self._core.data_recorder.is_recording:
                self._runner_recording.show()
            else:
                self._runner_recording.hide()

        # Start/stop device refresh timer based on state
        if hasattr(self, '_device_refresh_timer'):
            if state_name == "RUNNING":
                self._device_refresh_timer.start()
            else:
                self._device_refresh_timer.stop()
                # Do one final refresh when stopping
                self._update_runner_device_states()

    def _refresh_runner_devices(self) -> None:
        """Refresh the device cards in runner view."""
        if not hasattr(self, '_runner_devices_layout'):
            return

        # Clear existing device cards
        for card in self._runner_device_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._runner_device_cards.clear()

        # Get devices from hardware manager
        devices = self._core.hardware_manager.devices

        if not devices:
            self._runner_no_devices.show()
            return

        self._runner_no_devices.hide()

        # Create a card for each device
        for device_id, device in devices.items():
            card = self._create_device_card(device_id, device)
            # Insert before the stretch
            self._runner_devices_layout.insertWidget(
                self._runner_devices_layout.count() - 1, card
            )
            self._runner_device_cards[device_id] = card

    def _create_device_card(self, device_id: str, device) -> QWidget:
        """Create a device status card for the runner view."""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                border: 2px solid #2d2d44;
                border-radius: 12px;
            }
        """)
        card.setFixedHeight(80)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Device info (left side)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_label = QLabel(device_id)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff; background: transparent; border: none;")
        info_layout.addWidget(name_label)

        device_type = getattr(device, 'device_type', 'Unknown')
        type_label = QLabel(device_type)
        type_label.setStyleSheet("font-size: 12px; color: #888; background: transparent; border: none;")
        info_layout.addWidget(type_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Status indicator (right side)
        initialized = getattr(device, '_initialized', False)
        state = getattr(device, '_state', None)

        status_widget = QWidget()
        status_widget.setFixedSize(60, 50)
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(2)

        # State value
        if state is not None:
            if isinstance(state, bool):
                state_text = "HIGH" if state else "LOW"
                state_color = "#27ae60" if state else "#7f8c8d"
            else:
                state_text = str(state)[:6]
                state_color = "#3498db"
        else:
            state_text = "---"
            state_color = "#444"

        state_label = QLabel(state_text)
        state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state_label.setStyleSheet(f"""
            QLabel {{
                background-color: {state_color};
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                padding: 4px 8px;
                border: none;
            }}
        """)
        status_layout.addWidget(state_label)

        # Ready indicator
        ready_label = QLabel("Ready" if initialized else "---")
        ready_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ready_label.setStyleSheet(f"font-size: 10px; color: {'#27ae60' if initialized else '#666'}; background: transparent; border: none;")
        status_layout.addWidget(ready_label)

        layout.addWidget(status_widget)

        # Store references for updates
        card._state_label = state_label
        card._ready_label = ready_label

        return card

    def _update_runner_experiment_name(self) -> None:
        """Update the experiment name in runner view."""
        if not hasattr(self, '_runner_exp_name'):
            return

        if self._core.session and self._core.session.metadata.name:
            self._runner_exp_name.setText(self._core.session.metadata.name)
        else:
            self._runner_exp_name.setText("Untitled Experiment")

    def _update_runner_device_states(self) -> None:
        """Update the device state displays in runner view."""
        if not hasattr(self, '_runner_device_cards'):
            return

        for device_id, card in self._runner_device_cards.items():
            device = self._core.hardware_manager.get_device(device_id)
            if device is None:
                continue

            # Get current state
            state = getattr(device, '_state', None)
            initialized = getattr(device, '_initialized', False)

            # Update state label
            if hasattr(card, '_state_label'):
                if state is not None:
                    if isinstance(state, bool):
                        state_text = "HIGH" if state else "LOW"
                        state_color = "#27ae60" if state else "#7f8c8d"
                    else:
                        state_text = str(state)[:6]
                        state_color = "#3498db"
                else:
                    state_text = "---"
                    state_color = "#444"

                card._state_label.setText(state_text)
                card._state_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: {state_color};
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        border-radius: 8px;
                        padding: 4px 8px;
                        border: none;
                    }}
                """)

            # Update ready label
            if hasattr(card, '_ready_label'):
                card._ready_label.setText("Ready" if initialized else "---")
                card._ready_label.setStyleSheet(
                    f"font-size: 10px; color: {'#27ae60' if initialized else '#666'}; background: transparent; border: none;"
                )

    def _on_core_error(self, source: str, error: Exception) -> None:
        """Handle core errors."""
        self.error_occurred.emit(source, str(error))
        logger.error(f"Error from {source}: {error}")

    def _on_hardware_connection_change(self, board_id: str, state: BoardConnectionState) -> None:
        """
        Handle hardware connection state changes.

        If a board disconnects while running, pause and prompt the user.
        """
        # Only handle disconnection during active experiment
        if state not in (BoardConnectionState.DISCONNECTED, BoardConnectionState.ERROR):
            return

        # Check if we're running an experiment
        if not hasattr(self._core, 'state'):
            return

        from glider.core.glider_core import SessionState
        if self._core.state != SessionState.RUNNING:
            # Not running, just log it
            logger.warning(f"Board {board_id} disconnected (state: {state.name})")
            return

        # We're running and a board disconnected - pause and prompt
        logger.warning(f"Board {board_id} disconnected during experiment! Pausing...")

        # Pause the experiment
        self._run_async(self._core.pause())

        # Show the disconnection dialog
        self._show_hardware_disconnection_dialog(board_id, state)

    def _show_hardware_disconnection_dialog(self, board_id: str, state: BoardConnectionState) -> None:
        """Show a dialog when hardware disconnects during an experiment."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Hardware Disconnected")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)

        # Warning icon and message
        header_layout = QHBoxLayout()
        warning_label = QLabel("⚠️")
        warning_label.setStyleSheet("font-size: 48px;")
        header_layout.addWidget(warning_label)

        message = QLabel(
            f"<b>Board '{board_id}' has disconnected.</b><br><br>"
            f"The experiment has been paused. What would you like to do?"
        )
        message.setWordWrap(True)
        header_layout.addWidget(message, 1)
        layout.addLayout(header_layout)

        # Status info
        status_label = QLabel(f"Connection state: {state.name}")
        status_label.setStyleSheet("color: #888;")
        layout.addWidget(status_label)

        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)

        retry_btn = QPushButton("🔄 Retry Connection")
        retry_btn.setMinimumHeight(40)
        retry_btn.clicked.connect(lambda: self._handle_disconnection_retry(dialog, board_id))
        button_layout.addWidget(retry_btn)

        continue_btn = QPushButton("▶️ Continue Without Hardware")
        continue_btn.setMinimumHeight(40)
        continue_btn.setToolTip("Resume the experiment without this board (may cause errors)")
        continue_btn.clicked.connect(lambda: self._handle_disconnection_continue(dialog))
        button_layout.addWidget(continue_btn)

        stop_btn = QPushButton("⏹️ Stop Experiment")
        stop_btn.setMinimumHeight(40)
        stop_btn.clicked.connect(lambda: self._handle_disconnection_stop(dialog))
        button_layout.addWidget(stop_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def _handle_disconnection_retry(self, dialog: QDialog, board_id: str) -> None:
        """Attempt to reconnect to the disconnected board."""
        dialog.accept()

        # Show progress
        self.statusBar().showMessage(f"Reconnecting to {board_id}...")

        async def retry_connection():
            try:
                success = await self._core.hardware_manager.connect_board(board_id)
                if success:
                    logger.info(f"Reconnected to board {board_id}")
                    self.statusBar().showMessage(f"Reconnected to {board_id}. Resuming...", 3000)
                    # Resume the experiment
                    await self._core.resume()
                else:
                    logger.warning(f"Failed to reconnect to board {board_id}")
                    self.statusBar().showMessage(f"Failed to reconnect to {board_id}", 5000)
                    # Show dialog again
                    self._show_hardware_disconnection_dialog(
                        board_id, BoardConnectionState.DISCONNECTED
                    )
            except Exception as e:
                logger.error(f"Error reconnecting to {board_id}: {e}")
                self.statusBar().showMessage(f"Error: {e}", 5000)
                self._show_hardware_disconnection_dialog(
                    board_id, BoardConnectionState.ERROR
                )

        self._run_async(retry_connection())

    def _handle_disconnection_continue(self, dialog: QDialog) -> None:
        """Continue the experiment without the disconnected hardware."""
        dialog.accept()

        reply = QMessageBox.warning(
            self,
            "Continue Without Hardware",
            "Continuing without the disconnected hardware may cause errors "
            "or unexpected behavior. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.warning("User chose to continue experiment without disconnected hardware")
            self._run_async(self._core.resume())

    def _handle_disconnection_stop(self, dialog: QDialog) -> None:
        """Stop the experiment due to hardware disconnection."""
        dialog.accept()
        logger.info("User stopped experiment due to hardware disconnection")
        self._run_async(self._core.stop())
        self.statusBar().showMessage("Experiment stopped", 3000)

    def _toggle_view(self) -> None:
        """Toggle between builder and runner views."""
        current = self._stack.currentIndex()
        self._stack.setCurrentIndex(1 if current == 0 else 0)

    def switch_to_builder(self) -> None:
        """Switch to builder view."""
        self._stack.setCurrentIndex(0)

    def switch_to_runner(self) -> None:
        """Switch to runner view."""
        self._stack.setCurrentIndex(1)

    def _set_window_size(self, width: int, height: int) -> None:
        """Set the window to a specific size."""
        # Adjust minimum size to allow smaller dimensions (e.g., Pi display)
        self.setMinimumSize(min(width, 480), min(height, 480))
        self.resize(width, height)
        self.statusBar().showMessage(f"Window resized to {width}x{height}", 2000)

    # File operations
    def _on_new(self) -> None:
        """Create new experiment."""
        if self._check_save():
            self._core.hardware_manager.clear()
            self._core.new_session()
            self._graph_view.clear_graph()
            self.session_changed.emit()
            self._refresh_hardware_tree()

    def _on_open(self) -> None:
        """Open experiment file."""
        if not self._check_save():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Experiment",
            "",
            "GLIDER Experiments (*.glider);;JSON Files (*.json);;All Files (*)",
        )

        if file_path:
            try:
                self._core.load_session(file_path)
                # Populate hardware manager from session
                self._populate_hardware_from_session()
                # Populate graph view from session
                self._populate_graph_from_session()
                self.session_changed.emit()
                self._refresh_hardware_tree()
                self.statusBar().showMessage(f"Opened: {file_path}")
            except Exception as e:
                logger.exception(f"Failed to open file: {e}")
                QMessageBox.critical(self, "Error", f"Failed to open file: {e}")

    def _populate_hardware_from_session(self) -> None:
        """Populate hardware manager from session configuration."""
        if not self._core.session:
            return

        # Clear existing hardware
        self._core.hardware_manager.clear()

        # Add boards from session
        for board_config in self._core.session.hardware.boards:
            try:
                # Map driver type to the type expected by add_board
                board_type = "telemetrix" if board_config.driver_type == "arduino" else "pigpio"
                self._core.hardware_manager.add_board(
                    board_config.id,
                    board_type,
                    port=board_config.port,
                )
            except Exception as e:
                logger.warning(f"Failed to add board {board_config.id}: {e}")

        # Add devices from session
        for device_config in self._core.session.hardware.devices:
            try:
                # Get the pin name and value from the pins dict
                # Pins dict is like {"output": 13} or {"input": 2}
                if device_config.pins:
                    pin_name = list(device_config.pins.keys())[0]
                    pin = device_config.pins[pin_name]
                else:
                    pin_name = "pin"
                    pin = 0

                self._core.hardware_manager.add_device(
                    device_config.id,
                    device_config.device_type,
                    device_config.board_id,
                    pin,
                    name=device_config.name,
                    pin_name=pin_name,
                )
            except Exception as e:
                logger.warning(f"Failed to add device {device_config.id}: {e}")

    def _populate_graph_from_session(self) -> None:
        """Populate graph view from session flow configuration."""
        if not self._core.session:
            return

        # Clear existing graph
        self._graph_view.clear_graph()

        # Create visual nodes from session
        for node_config in self._core.session.flow.nodes:
            try:
                x, y = node_config.position
                node_type = node_config.node_type

                # Determine category from node type
                category = "default"
                flow_nodes = ["StartExperiment", "EndExperiment", "Delay"]
                control_nodes = ["Loop", "WaitForInput"]
                io_nodes = ["Output", "Input"]

                node_type_normalized = node_type.replace(" ", "")
                if node_type_normalized in flow_nodes:
                    category = "logic"
                elif node_type_normalized in control_nodes:
                    category = "interface"  # Orange color for control nodes
                elif node_type_normalized in io_nodes:
                    category = "hardware"

                # Add visual node to graph
                node_item = self._graph_view.add_node(node_config.id, node_type, x, y)
                node_item._category = category
                node_item._header_color = node_item.CATEGORY_COLORS.get(category, node_item.CATEGORY_COLORS["default"])

                # Add ports based on node type
                self._setup_node_ports(node_item, node_type)

                # Connect port signals
                self._graph_view._connect_port_signals(node_item)

                logger.debug(f"Loaded node: {node_config.id} at ({x}, {y})")

            except Exception as e:
                logger.error(f"Failed to load node {node_config.id}: {e}")

        # Create visual connections from session
        for conn_config in self._core.session.flow.connections:
            try:
                self._graph_view.add_connection(
                    conn_config.id,
                    conn_config.from_node,
                    conn_config.from_output,
                    conn_config.to_node,
                    conn_config.to_input,
                )
                logger.debug(f"Loaded connection: {conn_config.id}")

            except Exception as e:
                logger.error(f"Failed to load connection {conn_config.id}: {e}")

        logger.info(f"Loaded {len(self._core.session.flow.nodes)} nodes and {len(self._core.session.flow.connections)} connections from session")

    def _on_save(self) -> None:
        """Save experiment."""
        if self._core.session and self._core.session.file_path:
            try:
                self._core.save_session()
                self.statusBar().showMessage("Saved")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")
        else:
            self._on_save_as()

    def _on_save_as(self) -> None:
        """Save experiment as new file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Experiment",
            "",
            "GLIDER Experiments (*.glider);;JSON Files (*.json)",
        )

        if file_path:
            try:
                self._core.save_session(file_path)
                self.statusBar().showMessage(f"Saved: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _check_save(self) -> bool:
        """Check if current session should be saved. Returns True to proceed."""
        if self._core.session and self._core.session.is_dirty:
            result = QMessageBox.question(
                self,
                "Save Changes?",
                "The current experiment has unsaved changes. Save before continuing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )

            if result == QMessageBox.StandardButton.Save:
                self._on_save()
                return True
            elif result == QMessageBox.StandardButton.Cancel:
                return False

        return True

    # Hardware operations
    def _on_add_board(self) -> None:
        """Show dialog to add a new board."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Board")
        dialog.setMinimumWidth(350)

        layout = QFormLayout(dialog)

        # Board type selection
        type_combo = QComboBox()
        type_combo.addItems(["telemetrix", "pigpio"])
        layout.addRow("Board Type:", type_combo)

        # Board ID
        id_edit = QLineEdit()
        id_edit.setPlaceholderText("e.g., arduino_1")
        layout.addRow("Board ID:", id_edit)

        # Port selection with refresh button
        port_layout = QHBoxLayout()
        port_combo = QComboBox()
        port_combo.setMinimumWidth(200)

        def refresh_ports():
            port_combo.clear()
            port_combo.addItem("Auto-detect", None)
            try:
                import serial.tools.list_ports
                ports = serial.tools.list_ports.comports()
                for port in ports:
                    # Show port with description
                    label = f"{port.device}"
                    if port.description and port.description != "n/a":
                        label += f" - {port.description}"
                    port_combo.addItem(label, port.device)
            except ImportError:
                pass

        refresh_ports()
        port_layout.addWidget(port_combo)

        refresh_btn = QPushButton("↻")
        refresh_btn.setMaximumWidth(30)
        refresh_btn.clicked.connect(refresh_ports)
        port_layout.addWidget(refresh_btn)

        layout.addRow("Serial Port:", port_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            from glider.core.experiment_session import BoardConfig

            board_id = id_edit.text().strip() or f"board_{len(self._core.hardware_manager.boards)}"
            board_type = type_combo.currentText()
            port = port_combo.currentData()  # Get the actual port device path

            # Map UI type to driver type
            driver_type = "arduino" if board_type == "telemetrix" else "raspberry_pi"

            try:
                # Add to hardware manager for runtime use
                self._core.hardware_manager.add_board(board_id, board_type, port=port)

                # Add to session for persistence
                if self._core.session:
                    board_config = BoardConfig(
                        id=board_id,
                        driver_type=driver_type,
                        port=port,
                        board_type="uno",  # Default board type
                    )
                    self._core.session.add_board(board_config)

                self._refresh_hardware_tree()
                QMessageBox.information(self, "Success", f"Added board: {board_id}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add board: {e}")

    def _on_add_device(self) -> None:
        """Show dialog to add a new device."""
        if not self._core.hardware_manager.boards:
            QMessageBox.warning(self, "No Boards", "Please add a board first.")
            return

        # Map UI names to registry types and pin names
        device_type_map = {
            "Digital Output (LED, Relay)": ("DigitalOutput", "output"),
            "Digital Input (Button, Sensor)": ("DigitalInput", "input"),
            "Analog Input (Potentiometer)": ("AnalogInput", "input"),
            "PWM Output (Dimmable LED, Motor)": ("PWMOutput", "output"),
            "Servo Motor": ("Servo", "signal"),
        }

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Device")
        dialog.setMinimumWidth(350)

        layout = QFormLayout(dialog)

        # Device type
        type_combo = QComboBox()
        type_combo.addItems(list(device_type_map.keys()))
        layout.addRow("Device Type:", type_combo)

        # Device ID
        id_edit = QLineEdit()
        id_edit.setPlaceholderText("e.g., led_1")
        layout.addRow("Device ID:", id_edit)

        # Board selection
        board_combo = QComboBox()
        board_combo.addItems(list(self._core.hardware_manager.boards.keys()))
        layout.addRow("Board:", board_combo)

        # Pin number
        pin_spin = QSpinBox()
        pin_spin.setRange(0, 53)
        layout.addRow("Pin:", pin_spin)

        # Name
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g., Status LED")
        layout.addRow("Name:", name_edit)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            from glider.core.experiment_session import DeviceConfig

            device_id = id_edit.text().strip() or f"device_{len(self._core.hardware_manager.devices)}"
            ui_device_type = type_combo.currentText()
            board_id = board_combo.currentText()
            pin = pin_spin.value()
            name = name_edit.text().strip() or device_id

            # Get the actual device type and pin name from the map
            device_type, pin_name = device_type_map[ui_device_type]

            try:
                # Add to hardware manager for runtime use
                self._core.hardware_manager.add_device(
                    device_id, device_type, board_id, pin, name=name, pin_name=pin_name
                )

                # Add to session for persistence
                if self._core.session:
                    device_config = DeviceConfig(
                        id=device_id,
                        device_type=device_type,
                        name=name,
                        board_id=board_id,
                        pins={pin_name: pin},
                    )
                    self._core.session.add_device(device_config)

                self._refresh_hardware_tree()
                QMessageBox.information(self, "Success", f"Added device: {device_id}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add device: {e}")

    def _refresh_hardware_tree(self) -> None:
        """Refresh the hardware tree widget."""
        if not hasattr(self, '_hardware_tree'):
            return

        self._hardware_tree.clear()

        # Add boards
        for board_id, board in self._core.hardware_manager.boards.items():
            board_item = QTreeWidgetItem([
                board_id,
                getattr(board, 'name', type(board).__name__),
                board.state.name if hasattr(board, 'state') else "Unknown"
            ])
            board_item.setData(0, Qt.ItemDataRole.UserRole, ("board", board_id))

            # Add devices under this board
            for device_id, device in self._core.hardware_manager.devices.items():
                if hasattr(device, 'board') and device.board is board:
                    pins = getattr(device, '_pins', [])
                    pin_str = f"Pin {pins[0]}" if pins else ""
                    device_item = QTreeWidgetItem([
                        getattr(device, 'name', device_id),
                        f"{getattr(device, 'device_type', 'unknown')} ({pin_str})",
                        "Ready" if getattr(device, '_initialized', False) else "Not initialized"
                    ])
                    device_item.setData(0, Qt.ItemDataRole.UserRole, ("device", device_id))
                    board_item.addChild(device_item)

            self._hardware_tree.addTopLevelItem(board_item)
            board_item.setExpanded(True)

        self._hardware_tree.resizeColumnToContents(0)
        self._hardware_tree.resizeColumnToContents(1)

        # Also refresh the device combo for the control panel
        self._refresh_device_combo()

        # Also refresh runner view devices
        self._refresh_runner_devices()

    def _on_hardware_context_menu(self, position) -> None:
        """Show context menu for hardware tree."""
        item = self._hardware_tree.itemAt(position)
        if item is None:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return

        item_type, item_id = data

        menu = QMenu(self)

        if item_type == "board":
            connect_action = menu.addAction("Connect")
            connect_action.triggered.connect(lambda: self._connect_board(item_id))

            disconnect_action = menu.addAction("Disconnect")
            disconnect_action.triggered.connect(lambda: self._disconnect_board(item_id))

            menu.addSeparator()

            remove_action = menu.addAction("Remove Board")
            remove_action.triggered.connect(lambda: self._remove_board(item_id))

        elif item_type == "device":
            remove_action = menu.addAction("Remove Device")
            remove_action.triggered.connect(lambda: self._remove_device(item_id))

        menu.exec(self._hardware_tree.viewport().mapToGlobal(position))

    def _connect_board(self, board_id: str) -> None:
        """Connect to a specific board and initialize its devices."""
        async def connect():
            try:
                success = await self._core.hardware_manager.connect_board(board_id)
                if success:
                    # Initialize devices for this board
                    for device_id, device in self._core.hardware_manager.devices.items():
                        if hasattr(device, 'board') and device.board is not None:
                            if device.board.id == board_id:
                                try:
                                    await self._core.hardware_manager.initialize_device(device_id)
                                except Exception as e:
                                    logger.warning(f"Failed to initialize device {device_id}: {e}")
                    self.statusBar().showMessage(f"Connected to {board_id}", 3000)
                else:
                    QMessageBox.warning(self, "Connection Failed", f"Could not connect to {board_id}")
                self._refresh_hardware_tree()
            except Exception as e:
                QMessageBox.critical(self, "Connection Error", str(e))
        self._run_async(connect())

    def _disconnect_board(self, board_id: str) -> None:
        """Disconnect from a specific board."""
        async def disconnect():
            try:
                await self._core.hardware_manager.disconnect_board(board_id)
                self._refresh_hardware_tree()
            except Exception as e:
                QMessageBox.critical(self, "Disconnect Error", str(e))
        self._run_async(disconnect())

    def _remove_board(self, board_id: str) -> None:
        """Remove a board."""
        reply = QMessageBox.question(
            self, "Remove Board",
            f"Remove board '{board_id}' and all its devices?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            async def remove():
                await self._core.hardware_manager.remove_board(board_id)
                # Also remove from session for persistence
                if self._core.session:
                    self._core.session.remove_board(board_id)
                self._refresh_hardware_tree()
            self._run_async(remove())

    def _remove_device(self, device_id: str) -> None:
        """Remove a device."""
        reply = QMessageBox.question(
            self, "Remove Device",
            f"Remove device '{device_id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            async def remove():
                await self._core.hardware_manager.remove_device(device_id)
                # Also remove from session for persistence
                if self._core.session:
                    self._core.session.remove_device(device_id)
                self._refresh_hardware_tree()
            self._run_async(remove())

    def _on_connect_hardware(self) -> None:
        """Connect to all hardware."""
        self._run_async(self._connect_hardware_async())

    async def _connect_hardware_async(self) -> None:
        """Async hardware connection."""
        try:
            await self._core.setup_hardware()
            results = await self._core.connect_hardware()
            self._refresh_hardware_tree()
            failed = [k for k, v in results.items() if not v]
            if failed:
                QMessageBox.warning(
                    self, "Connection Warning",
                    f"Failed to connect: {', '.join(failed)}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def _on_disconnect_hardware(self) -> None:
        """Disconnect all hardware."""
        self._run_async(self._core.hardware_manager.disconnect_all())

    # Run operations
    @pyqtSlot()
    def _on_start_clicked(self) -> None:
        """Start experiment."""
        # Check for Script nodes and warn user
        if self._core.session:
            script_nodes = [
                node for node in self._core.session.flow.nodes
                if node.node_type.replace(" ", "") == "Script"
            ]
            if script_nodes:
                result = QMessageBox.warning(
                    self,
                    "Script Nodes Detected",
                    f"This experiment contains {len(script_nodes)} Script node(s).\n\n"
                    "Script nodes execute arbitrary Python code which could:\n"
                    "- Access and modify files on your system\n"
                    "- Make network connections\n"
                    "- Control connected hardware unexpectedly\n\n"
                    "Only run experiments with Script nodes from trusted sources.\n\n"
                    "Do you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if result != QMessageBox.StandardButton.Yes:
                    return

        self._run_async(self._start_async())

    async def _start_async(self) -> None:
        """Async start."""
        try:
            await self._core.start_experiment()
        except Exception as e:
            QMessageBox.critical(self, "Start Error", str(e))

    @pyqtSlot()
    def _on_stop_clicked(self) -> None:
        """Stop experiment."""
        self._run_async(self._stop_async())

    async def _stop_async(self) -> None:
        """Async stop."""
        try:
            await self._core.stop_experiment()
        except Exception as e:
            QMessageBox.critical(self, "Stop Error", str(e))

    @pyqtSlot()
    def _on_emergency_stop(self) -> None:
        """Trigger emergency stop."""
        self._run_async(self._core.emergency_stop())

    def _on_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About GLIDER",
            "GLIDER - General Laboratory Interface for Design, "
            "Experimentation, and Recording\n\n"
            "Version 1.0.0\n\n"
            "A modular experimental orchestration platform."
        )

    # Node Library methods
    def _create_node_library(self) -> QWidget:
        """Create the node library widget with draggable node items."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Define available nodes by category
        node_categories = {
            "Flow": [
                ("StartExperiment", "Start Experiment", "Entry point - begins the experiment flow"),
                ("EndExperiment", "End Experiment", "Exit point - ends the experiment"),
                ("Delay", "Delay", "Wait for a specified duration"),
            ],
            "Control": [
                ("Loop", "Loop", "Repeat actions N times (0 = infinite)"),
                ("WaitForInput", "Wait For Input", "Wait for input trigger before continuing"),
            ],
            "I/O": [
                ("Output", "Output", "Write to a device (digital or PWM)"),
                ("Input", "Input", "Read from a device (digital or analog)"),
            ],
            "Script": [
                ("Script", "Python Script", "Execute custom Python code (SECURITY WARNING: runs arbitrary code)"),
            ],
        }

        # Category colors
        category_colors = {
            "Flow": "#2d4a5a",  # Blue
            "Control": "#5a4a2d",  # Orange/Brown
            "I/O": "#2d5a2d",   # Green
            "Script": "#4a2d5a",  # Purple
        }

        for category, nodes in node_categories.items():
            # Category header - uses Qt properties for styling (defined in desktop.qss)
            header = QLabel(category)
            header.setProperty("categoryHeader", category)
            layout.addWidget(header)

            # Node items
            for node_type, node_name, tooltip in nodes:
                node_btn = DraggableNodeButton(node_type, node_name, category)
                node_btn.setToolTip(tooltip)
                node_btn.clicked.connect(lambda checked, nt=node_type: self._add_node_to_center(nt))
                layout.addWidget(node_btn)

        layout.addStretch()
        scroll_area.setWidget(container)
        return scroll_area

    def _add_node_to_center(self, node_type: str) -> None:
        """Add a node to the center of the graph view."""
        if hasattr(self, '_graph_view'):
            # Get center of current view
            center = self._graph_view.mapToScene(
                self._graph_view.viewport().rect().center()
            )
            self._graph_view.node_created.emit(node_type, center.x(), center.y())

    # Node graph event handlers
    def _on_node_created(self, node_type: str, x: float, y: float) -> None:
        """Handle node creation from graph view."""
        import uuid
        from glider.core.experiment_session import NodeConfig

        node_type_normalized = node_type.replace(" ", "")

        # Show security warning for Script nodes
        if node_type_normalized == "Script":
            result = QMessageBox.warning(
                self,
                "Security Warning",
                "Script nodes execute arbitrary Python code.\n\n"
                "This is a potential security risk as the code has full access to:\n"
                "- The file system\n"
                "- Network connections\n"
                "- Connected hardware\n"
                "- System resources\n\n"
                "Only use Script nodes with code you trust.\n\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return

        node_id = f"{node_type.lower()}_{uuid.uuid4().hex[:8]}"

        # Determine category from node type
        category = "default"
        flow_nodes = ["StartExperiment", "EndExperiment", "Delay"]
        control_nodes = ["Loop", "WaitForInput"]
        io_nodes = ["Output", "Input"]
        script_nodes = ["Script"]

        if node_type_normalized in flow_nodes:
            category = "logic"  # Use blue color
        elif node_type_normalized in control_nodes:
            category = "interface"  # Use orange color for control nodes
        elif node_type_normalized in io_nodes:
            category = "hardware"  # Use green color
        elif node_type_normalized in script_nodes:
            category = "script"  # Use purple color

        # Add visual node to graph
        node_item = self._graph_view.add_node(node_id, node_type, x, y)
        node_item._category = category
        node_item._header_color = node_item.CATEGORY_COLORS.get(category, node_item.CATEGORY_COLORS["default"])

        # Add default ports based on node type
        self._setup_node_ports(node_item, node_type)

        # Connect port signals for connection creation (after ports are added)
        self._graph_view._connect_port_signals(node_item)

        # Add to session for persistence
        if self._core.session:
            node_config = NodeConfig(
                id=node_id,
                node_type=node_type,
                position=(x, y),
                state={},
                device_id=None,
                visible_in_runner=category == "interface",
            )
            self._core.session.add_node(node_config)

        # Add to undo stack
        command = CreateNodeCommand(self, node_id, node_type, x, y)
        self._undo_stack.push(command)
        self._update_undo_redo_actions()

        self.statusBar().showMessage(f"Created node: {node_type}", 2000)

    def _setup_node_ports(self, node_item, node_type: str) -> None:
        """Set up input/output ports for a node based on its type."""
        from glider.gui.node_graph.port_item import PortType

        # Normalize node type (handle spaces)
        nt = node_type.replace(" ", "")

        # Define ports for each node type
        # Format: (input_ports, output_ports)
        # Port names starting with ">" are EXEC type, others are DATA type
        port_configs = {
            # Flow nodes
            "StartExperiment": ([], [">next"]),  # No inputs, one exec output
            "EndExperiment": ([">exec"], []),     # One exec input, no outputs
            "Delay": ([">exec", "seconds"], [">next"]),  # Exec in, duration, exec out
            # Control nodes (properties controlled via panel, not ports)
            "Loop": ([">exec"], [">body", ">done"]),  # Exec in, body and done exec outputs
            "WaitForInput": ([">exec"], [">triggered", ">timeout"]),  # Exec in, triggered and timeout exec outputs
            # I/O nodes
            "Output": ([">exec", "value"], [">next"]),  # Exec in, value to write, exec out
            "Input": ([">exec"], ["value", ">next"]),   # Exec in, outputs value and exec
            # Script nodes
            "Script": ([">exec", "input"], ["output", ">next"]),  # Exec in, data input, data output, exec out
        }

        inputs, outputs = port_configs.get(nt, ([">in"], [">out"]))

        for port_name in inputs:
            if port_name.startswith(">"):
                node_item.add_input_port(port_name[1:], PortType.EXEC)
            else:
                node_item.add_input_port(port_name, PortType.DATA)

        for port_name in outputs:
            if port_name.startswith(">"):
                node_item.add_output_port(port_name[1:], PortType.EXEC)
            else:
                node_item.add_output_port(port_name, PortType.DATA)

    def _on_node_deleted(self, node_id: str) -> None:
        """Handle node deletion from graph view."""
        # Save node data for undo before deletion
        node_data = {}
        node_item = self._graph_view.nodes.get(node_id)
        if node_item:
            node_data = {
                "id": node_id,
                "node_type": node_item.node_type,
                "x": node_item.pos().x(),
                "y": node_item.pos().y(),
            }

        # Get additional data from session
        if self._core.session:
            node_config = self._core.session.get_node(node_id)
            if node_config:
                node_data["state"] = node_config.state
                node_data["device_id"] = node_config.device_id
                node_data["visible_in_runner"] = node_config.visible_in_runner

            # Remove from session
            self._core.session.remove_node(node_id)

        # Add to undo stack
        command = DeleteNodeCommand(self, node_id, node_data)
        self._undo_stack.push(command)
        self._update_undo_redo_actions()

        self.statusBar().showMessage(f"Deleted node: {node_id}", 2000)

    def _on_node_selected(self, node_id: str) -> None:
        """Handle node selection from graph view."""
        self._update_properties_panel(node_id)
        self.statusBar().showMessage(f"Selected: {node_id}", 1000)

    def _on_node_moved(self, node_id: str, x: float, y: float) -> None:
        """Handle node movement from graph view."""
        if self._core.session:
            self._core.session.update_node_position(node_id, x, y)

    def _on_connection_created(self, from_node: str, from_port: int, to_node: str, to_port: int, conn_type: str = "data") -> None:
        """Handle connection creation from graph view."""
        import uuid
        from glider.core.experiment_session import ConnectionConfig

        connection_id = f"conn_{uuid.uuid4().hex[:8]}"

        # Add visual connection
        self._graph_view.add_connection(connection_id, from_node, from_port, to_node, to_port)

        # Add to session for persistence
        if self._core.session:
            conn_config = ConnectionConfig(
                id=connection_id,
                from_node=from_node,
                from_output=from_port,
                to_node=to_node,
                to_input=to_port,
                connection_type=conn_type,
            )
            self._core.session.add_connection(conn_config)
            logger.info(f"Saved connection: {from_node}:{from_port} -> {to_node}:{to_port} (type: {conn_type})")

        # Add to undo stack
        command = CreateConnectionCommand(self, connection_id, from_node, from_port, to_node, to_port, conn_type)
        self._undo_stack.push(command)
        self._update_undo_redo_actions()

        self.statusBar().showMessage(f"Connected: {from_node} -> {to_node}", 2000)

    def _on_connection_deleted(self, connection_id: str) -> None:
        """Handle connection deletion from graph view."""
        # Save connection data for undo
        conn_data = {"id": connection_id}

        # Get connection data from session before deletion
        if self._core.session:
            conn_config = self._core.session.get_connection(connection_id)
            if conn_config:
                conn_data["from_node"] = conn_config.from_node
                conn_data["from_port"] = conn_config.from_output
                conn_data["to_node"] = conn_config.to_node
                conn_data["to_port"] = conn_config.to_input
                conn_data["conn_type"] = conn_config.connection_type

            self._core.session.remove_connection(connection_id)

        # Add to undo stack
        command = DeleteConnectionCommand(self, connection_id, conn_data)
        self._undo_stack.push(command)
        self._update_undo_redo_actions()

        self.statusBar().showMessage(f"Deleted connection: {connection_id}", 2000)

    def _update_properties_panel(self, node_id: str) -> None:
        """Update the properties panel for the selected node."""
        if not hasattr(self, '_properties_dock'):
            return

        # Get node from graph view
        node_item = self._graph_view.nodes.get(node_id)
        if node_item is None:
            return

        # Get node config from session to load saved values
        node_config = None
        if self._core.session:
            node_config = self._core.session.get_node(node_id)

        # Create properties widget
        props_widget = QWidget()
        props_layout = QFormLayout(props_widget)
        props_layout.setContentsMargins(8, 8, 8, 8)

        # Node info
        props_layout.addRow("ID:", QLabel(node_id))
        props_layout.addRow("Type:", QLabel(node_item.node_type))

        node_type = node_item.node_type.replace(" ", "")

        # Add device selector for I/O nodes and WaitForInput
        if node_type in ["Output", "Input", "WaitForInput"]:
            device_combo = QComboBox()
            device_combo.addItem("-- Select Device --", None)
            current_device_id = node_config.device_id if node_config else None
            current_index = 0

            for i, (dev_id, device) in enumerate(self._core.hardware_manager.devices.items()):
                device_name = getattr(device, 'name', dev_id)
                device_type = getattr(device, 'device_type', '')
                device_combo.addItem(f"{device_name} ({device_type})", dev_id)
                if dev_id == current_device_id:
                    current_index = i + 1  # +1 because of "-- Select Device --" item

            device_combo.setCurrentIndex(current_index)
            device_combo.currentIndexChanged.connect(
                lambda idx, nid=node_id, combo=device_combo: self._on_node_device_changed(nid, combo.currentData())
            )
            props_layout.addRow("Device:", device_combo)

        # Add duration input for Delay node
        elif node_type == "Delay":
            duration_spin = QSpinBox()
            duration_spin.setRange(0, 3600)
            # Load saved duration from session
            saved_duration = 1
            if node_config and node_config.state:
                saved_duration = node_config.state.get("duration", 1)
            duration_spin.setValue(saved_duration)
            duration_spin.setSuffix(" sec")
            duration_spin.valueChanged.connect(
                lambda val, nid=node_id: self._on_node_property_changed(nid, "duration", val)
            )
            props_layout.addRow("Duration:", duration_spin)

        # Add HIGH/LOW selector for Output node
        if node_type == "Output":
            from PyQt6.QtWidgets import QButtonGroup, QRadioButton, QHBoxLayout
            value_layout = QHBoxLayout()
            high_radio = QRadioButton("HIGH")
            low_radio = QRadioButton("LOW")

            # Load saved value from session (1=HIGH, 0=LOW)
            saved_value = 1  # Default to HIGH
            if node_config and node_config.state:
                saved_value = node_config.state.get("value", 1)

            if saved_value:
                high_radio.setChecked(True)
            else:
                low_radio.setChecked(True)

            value_layout.addWidget(high_radio)
            value_layout.addWidget(low_radio)
            high_radio.toggled.connect(
                lambda checked, nid=node_id: self._on_node_property_changed(nid, "value", 1 if checked else 0)
            )
            value_widget = QWidget()
            value_widget.setLayout(value_layout)
            props_layout.addRow("Value:", value_widget)

        # Add properties for Loop node
        elif node_type == "Loop":
            # Loop count (0 = infinite)
            count_spin = QSpinBox()
            count_spin.setRange(0, 10000)
            count_spin.setSpecialValueText("Infinite")
            saved_count = 0
            if node_config and node_config.state:
                saved_count = node_config.state.get("count", 0)
            count_spin.setValue(saved_count)
            count_spin.valueChanged.connect(
                lambda val, nid=node_id: self._on_node_property_changed(nid, "count", val)
            )
            props_layout.addRow("Iterations:", count_spin)

            # Loop delay
            delay_spin = QDoubleSpinBox()
            delay_spin.setRange(0.0, 3600.0)
            delay_spin.setDecimals(2)
            delay_spin.setSingleStep(0.1)
            saved_delay = 1.0
            if node_config and node_config.state:
                saved_delay = node_config.state.get("delay", 1.0)
            delay_spin.setValue(saved_delay)
            delay_spin.setSuffix(" sec")
            delay_spin.valueChanged.connect(
                lambda val, nid=node_id: self._on_node_property_changed(nid, "delay", val)
            )
            props_layout.addRow("Delay:", delay_spin)

        # Add properties for WaitForInput node
        elif node_type == "WaitForInput":
            # Timeout (0 = no timeout)
            timeout_spin = QDoubleSpinBox()
            timeout_spin.setRange(0.0, 3600.0)
            timeout_spin.setDecimals(1)
            timeout_spin.setSpecialValueText("No timeout")
            saved_timeout = 0.0
            if node_config and node_config.state:
                saved_timeout = node_config.state.get("timeout", 0.0)
            timeout_spin.setValue(saved_timeout)
            timeout_spin.setSuffix(" sec")
            timeout_spin.valueChanged.connect(
                lambda val, nid=node_id: self._on_node_property_changed(nid, "timeout", val)
            )
            props_layout.addRow("Timeout:", timeout_spin)

        # Add properties for Script node
        elif node_type == "Script":
            # Security warning banner - uses property for styling (defined in QSS)
            warning_label = QLabel("WARNING: Executes arbitrary Python code")
            warning_label.setProperty("securityWarning", True)
            props_layout.addRow(warning_label)

            # Code editor
            code_label = QLabel("Python Code:")
            props_layout.addRow(code_label)

            code_edit = QPlainTextEdit()
            code_edit.setMinimumHeight(200)
            code_edit.setProperty("codeEditor", True)
            code_edit.setPlaceholderText(
                "# Available variables:\n"
                "# - inputs: list of input values\n"
                "# - outputs: list for output values\n"
                "# - set_output(index, value): set output\n"
                "# - device: bound hardware device\n"
                "# - asyncio: asyncio module\n\n"
                "# Example:\n"
                "value = inputs[0] * 2\n"
                "set_output(0, value)"
            )

            # Load saved code
            saved_code = ""
            if node_config and node_config.state:
                saved_code = node_config.state.get("code", "")
            code_edit.setPlainText(saved_code)

            # Save code on change (with debounce)
            def on_code_changed(nid=node_id, editor=code_edit):
                self._on_node_property_changed(nid, "code", editor.toPlainText())

            code_edit.textChanged.connect(on_code_changed)
            props_layout.addRow(code_edit)

            # Validate button
            validate_btn = QPushButton("Validate Syntax")
            validate_btn.clicked.connect(lambda: self._validate_script_syntax(code_edit.toPlainText()))
            props_layout.addRow(validate_btn)

        self._properties_dock.setWidget(props_widget)

    def _on_node_device_changed(self, node_id: str, device_id: str) -> None:
        """Handle device selection change for a node."""
        if self._core.session:
            node_config = self._core.session.get_node(node_id)
            if node_config:
                # Update session config for persistence
                node_config.device_id = device_id
                self._core.session._mark_dirty()
                logger.info(f"Node {node_id} device changed to: {device_id}")

                # Also bind device to the runtime node in flow engine
                if device_id and hasattr(self._core, 'flow_engine') and self._core.flow_engine:
                    runtime_node = self._core.flow_engine.get_node(node_id)
                    if runtime_node and hasattr(runtime_node, 'bind_device'):
                        device = self._core.hardware_manager.get_device(device_id)
                        if device:
                            runtime_node.bind_device(device)
                            logger.info(f"Bound device '{device_id}' to runtime node {node_id}")

    def _on_node_property_changed(self, node_id: str, prop_name: str, value) -> None:
        """Handle property change for a node."""
        if self._core.session:
            self._core.session.update_node_state(node_id, {prop_name: value})
            logger.info(f"Node {node_id} property '{prop_name}' changed to: {value}")

    def _validate_script_syntax(self, code: str) -> None:
        """Validate Python script syntax and show result."""
        if not code.strip():
            QMessageBox.information(self, "Validation", "No code to validate.")
            return

        try:
            compile(code, "<script>", "exec")
            QMessageBox.information(
                self, "Validation Passed",
                "Script syntax is valid.\n\n"
                "Note: This only checks syntax, not runtime errors."
            )
        except SyntaxError as e:
            QMessageBox.warning(
                self, "Syntax Error",
                f"Line {e.lineno}: {e.msg}\n\n{e.text}"
            )

    def _run_async(self, coro) -> asyncio.Task:
        """
        Run an async coroutine with proper task tracking.

        This prevents garbage collection of the task before completion
        and ensures proper cleanup on application exit.
        """
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        return task

    # Undo/Redo methods
    def _on_undo(self) -> None:
        """Handle undo action."""
        command = self._undo_stack.undo()
        if command:
            self.statusBar().showMessage(f"Undo: {command.description()}", 2000)
            self._update_undo_redo_actions()

    def _on_redo(self) -> None:
        """Handle redo action."""
        command = self._undo_stack.redo()
        if command:
            # For redo, we need to re-apply the action
            # Most commands just need to be re-created
            self._redo_command(command)
            self.statusBar().showMessage(f"Redo: {command.description()}", 2000)
            self._update_undo_redo_actions()

    def _redo_command(self, command: Command) -> None:
        """Re-apply a command for redo."""
        if isinstance(command, CreateNodeCommand):
            # Re-create the node
            self._on_node_created(command._node_type, command._x, command._y)
            # Remove the duplicate undo entry that was just added
            if self._undo_stack._undo_stack:
                self._undo_stack._undo_stack.pop()
        elif isinstance(command, DeleteNodeCommand):
            # Re-delete the node
            node_id = command._node_id
            self._graph_view.remove_node(node_id)
            if self._core.session:
                self._core.session.remove_node(node_id)
        elif isinstance(command, MoveNodeCommand):
            # Re-apply the move
            node_item = self._graph_view.nodes.get(command._node_id)
            if node_item:
                node_item.setPos(command._new_x, command._new_y)
            if self._core.session:
                self._core.session.update_node_position(command._node_id, command._new_x, command._new_y)
        elif isinstance(command, CreateConnectionCommand):
            # Re-create the connection
            self._graph_view.add_connection(
                command._conn_id, command._from_node, command._from_port,
                command._to_node, command._to_port
            )
            if self._core.session:
                from glider.core.experiment_session import ConnectionConfig
                conn_config = ConnectionConfig(
                    id=command._conn_id,
                    from_node=command._from_node,
                    from_output=command._from_port,
                    to_node=command._to_node,
                    to_input=command._to_port,
                    connection_type=command._conn_type,
                )
                self._core.session.add_connection(conn_config)
        elif isinstance(command, DeleteConnectionCommand):
            # Re-delete the connection
            self._graph_view.remove_connection(command._conn_id)
            if self._core.session:
                self._core.session.remove_connection(command._conn_id)
        elif isinstance(command, PropertyChangeCommand):
            # Re-apply the property change
            if self._core.session:
                self._core.session.update_node_state(command._node_id, {command._prop_name: command._new_value})

    def _update_undo_redo_actions(self) -> None:
        """Update the enabled state of undo/redo menu actions."""
        if hasattr(self, '_undo_action'):
            can_undo = self._undo_stack.can_undo()
            self._undo_action.setEnabled(can_undo)
            if can_undo:
                self._undo_action.setText(f"&Undo {self._undo_stack.undo_description()}")
            else:
                self._undo_action.setText("&Undo")

        if hasattr(self, '_redo_action'):
            can_redo = self._undo_stack.can_redo()
            self._redo_action.setEnabled(can_redo)
            if can_redo:
                self._redo_action.setText(f"&Redo {self._undo_stack.redo_description()}")
            else:
                self._redo_action.setText("&Redo")

    # Device Control Panel methods
    def _refresh_device_combo(self) -> None:
        """Refresh the device selector combo box."""
        if not hasattr(self, '_device_combo'):
            return

        self._device_combo.clear()
        self._device_combo.addItem("-- Select Device --", None)

        for device_id, device in self._core.hardware_manager.devices.items():
            device_name = getattr(device, 'name', device_id)
            device_type = getattr(device, 'device_type', 'unknown')
            self._device_combo.addItem(f"{device_name} ({device_type})", device_id)

    def _on_device_selected(self, text: str) -> None:
        """Handle device selection change."""
        device_id = self._device_combo.currentData()
        if device_id is None:
            self._device_status_label.setText("Status: No device selected")
            return

        device = self._core.hardware_manager.get_device(device_id)
        if device is None:
            self._device_status_label.setText("Status: Device not found")
            return

        device_type = getattr(device, 'device_type', 'unknown')
        board = getattr(device, 'board', None)
        connected = board.is_connected if board else False
        initialized = getattr(device, '_initialized', False)

        status = "Connected" if connected else "Disconnected"
        if connected and initialized:
            status = "Ready"
        elif connected and not initialized:
            status = "Not initialized"

        self._device_status_label.setText(f"Status: {status} | Type: {device_type}")

    def _get_selected_device(self):
        """Get the currently selected device."""
        device_id = self._device_combo.currentData()
        if device_id is None:
            return None
        return self._core.hardware_manager.get_device(device_id)

    def _set_digital_output(self, value: bool) -> None:
        """Set digital output to HIGH or LOW."""
        device = self._get_selected_device()
        if device is None:
            QMessageBox.warning(self, "No Device", "Please select a device first.")
            return

        async def set_output():
            try:
                if hasattr(device, 'set_state'):
                    await device.set_state(value)
                elif hasattr(device, 'turn_on') and hasattr(device, 'turn_off'):
                    if value:
                        await device.turn_on()
                    else:
                        await device.turn_off()
                else:
                    # Direct pin write
                    pin = list(device.pins.values())[0] if device.pins else 0
                    await device.board.write_digital(pin, value)

                state = "ON" if value else "OFF"
                self._device_status_label.setText(f"Status: Output set to {state}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to set output: {e}")

        self._run_async(set_output())

    def _toggle_digital_output(self) -> None:
        """Toggle digital output."""
        device = self._get_selected_device()
        if device is None:
            QMessageBox.warning(self, "No Device", "Please select a device first.")
            return

        async def toggle():
            try:
                if hasattr(device, 'toggle'):
                    await device.toggle()
                elif hasattr(device, 'state'):
                    new_state = not device.state
                    if hasattr(device, 'set_state'):
                        await device.set_state(new_state)
                self._device_status_label.setText("Status: Output toggled")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to toggle: {e}")

        self._run_async(toggle())

    def _on_pwm_changed(self, value: int) -> None:
        """Handle PWM slider change."""
        device = self._get_selected_device()
        if device is None:
            return

        async def set_pwm():
            try:
                if hasattr(device, 'set_value'):
                    await device.set_value(value)
                elif hasattr(device, 'board'):
                    pin = list(device.pins.values())[0] if device.pins else 0
                    await device.board.write_analog(pin, value)
                self._device_status_label.setText(f"Status: PWM set to {value}")
            except Exception as e:
                logger.error(f"PWM error: {e}")

        self._run_async(set_pwm())

    def _on_servo_changed(self, angle: int) -> None:
        """Handle servo slider change."""
        device = self._get_selected_device()
        if device is None:
            return

        async def set_servo():
            try:
                if hasattr(device, 'set_angle'):
                    await device.set_angle(angle)
                elif hasattr(device, 'board'):
                    pin = list(device.pins.values())[0] if device.pins else 0
                    await device.board.write_servo(pin, angle)
                self._device_status_label.setText(f"Status: Servo set to {angle}°")
            except Exception as e:
                logger.error(f"Servo error: {e}")

        self._run_async(set_servo())

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Stop device refresh timer
        if hasattr(self, '_device_refresh_timer'):
            self._device_refresh_timer.stop()

        if self._check_save():
            # Cancel any pending async tasks
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
            self._pending_tasks.clear()

            # Shutdown core - must complete before closing to ensure devices are LOW
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    # Loop not running, can use run_until_complete
                    loop.run_until_complete(self._core.shutdown())
                else:
                    # Loop is running (qasync) - schedule and wait with processEvents
                    future = asyncio.ensure_future(self._core.shutdown())
                    from PyQt6.QtWidgets import QApplication
                    import time
                    # Process events until shutdown completes (max 10 seconds)
                    timeout = time.time() + 10
                    while not future.done() and time.time() < timeout:
                        QApplication.processEvents()
                        time.sleep(0.01)  # Small sleep to prevent busy loop
                    if not future.done():
                        logger.warning("Shutdown timed out")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            event.accept()
        else:
            event.ignore()
