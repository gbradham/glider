# GLIDER Architecture

**GLIDER** (General Laboratory Interface for Design, Experimentation, and Recording) is a modular experimental orchestration platform for laboratory hardware control through visual flow-based programming.

Built with Python 3.9+ using PyQt6 for the GUI and asyncio for non-blocking hardware operations.

---

## Project Structure

```
glider/
├── src/glider/
│   ├── core/           # Core orchestration logic
│   ├── gui/            # PyQt6 user interface
│   ├── hal/            # Hardware Abstraction Layer
│   ├── nodes/          # Node system (flow graph elements)
│   ├── plugins/        # Plugin system
│   └── serialization/  # Save/load functionality
├── tests/              # Test suite
├── plugins/            # Sample/builtin plugins directory
└── *.glider            # Experiment definition files (JSON)
```

---

## Core Module (`glider/core/`)

The heart of GLIDER - manages the entire system lifecycle.

### GliderCore (`glider_core.py`)
Central orchestrator that:
- Initializes the event loop and plugin system
- Coordinates ExperimentSession, HardwareManager, and FlowEngine
- Manages experiment lifecycle (start, stop, pause, resume, emergency stop)
- Handles callbacks for state changes and errors
- Auto-records experiment data to CSV

### ExperimentSession (`experiment_session.py`)
Single source of truth for experiment state:
- Contains: Metadata, Hardware configs, Flow graph configs, Dashboard layouts
- Serializable to/from JSON
- State machine: `IDLE → INITIALIZING → READY → RUNNING → PAUSED/STOPPING → ERROR`
- Tracks dirty flag for unsaved changes

### FlowEngine (`flow_engine.py`)
Logic graph execution engine:
- Wraps ryvencore for graph state management
- Manages node instances and connections
- Executes data flow (reactive) and execution flow (imperative)
- Handles async node execution with task management

### HardwareManager (`hardware_manager.py`)
Hardware lifecycle management:
- Board driver registration and loading
- Async connection management
- Device initialization
- Pin allocation tracking via PinManager
- Error recovery and reconnection logic

### DataRecorder (`data_recorder.py`)
Experiment data logging:
- Records device states to CSV files with timestamps
- Configurable sampling interval (default 100ms)
- Auto-generates timestamped filenames

---

## GUI Module (`glider/gui/`)

PyQt6-based user interface with dual-mode support.

### MainWindow (`main_window.py`)
Primary application window:
- Menu bar (File, Edit, View, Tools, Help)
- Toolbar with experiment controls
- Stacked widget switching between Builder and Runner views
- Drag-and-drop node creation

### ViewManager (`view_manager.py`)
Responsive design manager:
- Auto-detects screen size and orientation
- Two modes: **DESKTOP** (Builder IDE) vs **RUNNER** (touch dashboard)
- PI_SCREEN detection: 480x800 (portrait)
- Mode-specific styling, fonts, button sizes, scrollbar widths

### Node Graph Editor (`gui/node_graph/`)

| File | Purpose |
|------|---------|
| `graph_view.py` | Main canvas - pan, zoom, node creation, connection drawing |
| `node_item.py` | Visual node representation with color-coded categories |
| `port_item.py` | Port visual elements and connection points |
| `connection_item.py` | Bezier curve connection rendering |

**Node Categories by Color:**
- Green: Hardware nodes
- Blue: Logic nodes
- Orange: Interface nodes
- Purple: Script nodes

### Runner Dashboard (`gui/runner/`)
Touch-optimized control interface:
- `dashboard.py` - Main dashboard view
- `widget_factory.py` - Creates widgets for device controls
- Large touch targets, readable fonts, kinetic scrolling

---

## HAL Module (`glider/hal/`)

Hardware Abstraction Layer - polymorphic interface for hardware.

### BaseBoard (`base_board.py`)
Abstract base class defining:
- `BoardConnectionState`: DISCONNECTED, CONNECTING, CONNECTED, ERROR, RECONNECTING
- `PinType`: DIGITAL, ANALOG, PWM, I2C, SPI, SERVO
- `BoardCapabilities`: pin definitions, resolution, frequency specs
- Abstract methods: `connect()`, `disconnect()`, `get_pin_value()`, `set_pin_value()`

### BaseDevice (`base_device.py`)
Device abstraction:
- Wraps boards into semantic actions (e.g., "DigitalOutput", "DHT22 Sensor")
- Device registry pattern for type discovery
- State management and configuration

### Board Implementations (`hal/boards/`)
- `telemetrix_board.py` - Arduino/Telemetrix driver
- `pi_gpio_board.py` - Raspberry Pi GPIO driver

### PinManager (`pin_manager.py`)
Pin conflict detection and allocation tracking.

---

## Nodes Module (`glider/nodes/`)

Node system for flow-based programming.

### GliderNode (`base_node.py`)
Base node class extending ryvencore.Node:
- `NodeCategory`: HARDWARE, LOGIC, INTERFACE, SCRIPT
- `PortType`: DATA, EXEC
- Async execution support
- Device binding for hardware nodes

### Node Types

**Experiment Nodes** (`experiment_nodes.py`):
- `StartExperimentNode` - Entry point, triggers flow
- `EndExperimentNode` - Exit point, signals completion
- `DelayNode` - Async wait
- `OutputNode` / `InputNode` - Device I/O
- `WaitForInputNode` - Block until input received

**Logic Nodes** (`nodes/logic/`):
- Math: Add, Subtract, Multiply, Divide, MapRange, Clamp
- Comparison: ==, !=, <, >, <=, >=
- Flow: Branch, Merge, Select
- Control: ForLoop, WhileLoop, IfElse

**Hardware Nodes** (`nodes/hardware/`):
- Digital: DigitalRead, DigitalWrite, PWM
- Analog: AnalogRead, AnalogWrite
- Device: Generic device interface nodes

**Interface Nodes** (`nodes/interface/`):
- Input: NumberInput, StringInput, ButtonClick
- Display: NumberDisplay, TextDisplay, Gauge, Graph

---

## Plugin System (`glider/plugins/`)

### PluginManager (`plugin_manager.py`)
Extensibility system:
- Plugin discovery from entry points and local directories
- Async plugin loading with error handling
- Default plugin directory: `~/.glider/plugins`

Plugins can provide:
- Hardware drivers (BaseBoard implementations)
- Devices (BaseDevice implementations)
- Nodes (GliderNode implementations)
- UI components

---

## Serialization (`glider/serialization/`)

### ExperimentSerializer (`serializer.py`)
- `.glider` file format (JSON-based)
- Version migration support
- Node type registry for deserialization

### Schema (`schema.py`)
Data schemas:
- `ExperimentSchema` - Top-level structure
- `MetadataSchema` - Experiment metadata
- `HardwareConfigSchema` - Boards and devices
- `FlowConfigSchema` - Nodes and connections
- `DashboardConfigSchema` - Runner dashboard layout

---

## Class Relationships

```
GliderCore (Main Orchestrator)
├── ExperimentSession (Model/State)
│   ├── SessionMetadata
│   ├── HardwareConfig
│   │   ├── List[BoardConfig]
│   │   └── List[DeviceConfig]
│   ├── FlowConfig
│   │   ├── List[NodeConfig]
│   │   └── List[ConnectionConfig]
│   └── DashboardConfig
├── HardwareManager
│   ├── Dict[board_id, BaseBoard]
│   ├── Dict[device_id, BaseDevice]
│   └── Dict[board_id, PinManager]
├── FlowEngine
│   ├── Dict[node_id, GliderNode]
│   ├── List[Connection]
│   └── Set[asyncio.Task]
├── DataRecorder
└── PluginManager

MainWindow (GUI Root)
├── ViewManager (Mode Detection)
├── NodeGraphView (Desktop Mode)
│   ├── Dict[node_id, NodeItem]
│   ├── Dict[connection_id, ConnectionItem]
│   └── Dict[port_id, PortItem]
└── Dashboard (Runner Mode)
```

---

## Data Flow

### Experiment Load/Save
```
.glider file → ExperimentSerializer → ExperimentSchema → GliderCore
    → ExperimentSession → FlowEngine (nodes) + HardwareManager (devices)
    → GUI renders
```

### Hardware Setup
```
GliderCore.connect_hardware()
    → HardwareManager.create_board() → Board.connect() [async]
    → HardwareManager.create_device() → Device.initialize() [async]
    → Session state: IDLE → INITIALIZING → READY
```

### Experiment Execution
```
Start Experiment
    → DataRecorder.start()
    → FlowEngine.start()
    → StartExperimentNode triggers execution cascade
    → Nodes execute async, propagate through connections
    → EndExperimentNode reached
    → DataRecorder.stop() → saves CSV
    → Session state: RUNNING → READY
```

---

## Design Patterns

### State Machines
- **SessionState**: IDLE → INITIALIZING → READY → RUNNING ↔ PAUSED → STOPPING
- **FlowState**: STOPPED ↔ RUNNING ↔ PAUSED
- **BoardConnectionState**: DISCONNECTED → CONNECTING → CONNECTED (with auto-reconnect)

### Registries
- **Node Registry**: `_node_registry[node_type] = NodeClass`
- **Device Registry**: `DEVICE_REGISTRY[device_type] = DeviceClass`
- **Driver Registry**: `_driver_registry[driver_name] = BoardClass`

### Callback/Observer
All major components use callback lists:
```python
core.on_session_change(callback)
core.on_state_change(callback)
core.on_error(callback)
core.on_node_update(callback)
```

### Async/Await
All I/O is non-blocking using asyncio:
- `qasync` integrates asyncio with Qt event loop
- Tasks tracked to prevent orphaning
- Safe shutdown with cleanup

---

## Key Architectural Features

1. **Dual-Mode GUI** - Same codebase runs as Desktop IDE or Touch Dashboard with auto-detection

2. **Async-First Design** - All hardware operations non-blocking via asyncio + qasync bridge

3. **Hybrid Flow Execution** - Data flow (reactive) + Execution flow (imperative)

4. **Three-Layer Hardware Abstraction** - BaseBoard → BaseDevice → implementations

5. **Plugin Extensibility** - Entry points + local plugin directory for drivers, devices, nodes

6. **Comprehensive Serialization** - Entire experiment state to JSON with version migration

7. **Automatic Data Recording** - CSV logging of all device states during experiments

---

## Example .glider File Structure

```json
{
  "metadata": {
    "name": "My Experiment",
    "author": "User",
    "version": "1.0.0",
    "created_at": "2024-01-01T00:00:00",
    "modified_at": "2024-01-01T00:00:00"
  },
  "hardware": {
    "boards": [
      { "id": "Arduino", "driver_type": "arduino", "port": "COM3" }
    ],
    "devices": [
      { "id": "led_1", "device_type": "DigitalOutput", "board_id": "Arduino", "pins": {"pin": 13} }
    ]
  },
  "flow": {
    "nodes": [
      { "id": "node_1", "node_type": "StartExperiment", "position": [100, 100] },
      { "id": "node_2", "node_type": "Output", "device_id": "led_1", "position": [300, 100] },
      { "id": "node_3", "node_type": "EndExperiment", "position": [500, 100] }
    ],
    "connections": [
      { "from_node": "node_1", "from_output": 0, "to_node": "node_2", "to_input": 0, "connection_type": "exec" },
      { "from_node": "node_2", "from_output": 0, "to_node": "node_3", "to_input": 0, "connection_type": "exec" }
    ]
  },
  "dashboard": {
    "widgets": [],
    "layout": "vertical"
  }
}
```
