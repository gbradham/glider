# Core API Reference

This document covers the core orchestration classes in GLIDER.

## GliderCore

The central orchestrator that manages the entire GLIDER system.

**Module:** `glider.core.glider_core`

### Overview

`GliderCore` coordinates all GLIDER components:
- Initializes and manages the event loop
- Loads and manages plugins
- Coordinates ExperimentSession, HardwareManager, and FlowEngine
- Handles system signals and emergency shutdown

```python
from glider.core.glider_core import GliderCore, create_core

# Create and initialize
core = await create_core()

# Or manually
core = GliderCore()
await core.initialize()
```

### Constructor

```python
GliderCore()
```

Creates a new GliderCore instance. Does not perform initialization; call `initialize()` before use.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `session` | `Optional[ExperimentSession]` | Current experiment session |
| `hardware_manager` | `HardwareManager` | Hardware manager instance |
| `flow_engine` | `FlowEngine` | Flow engine instance |
| `data_recorder` | `DataRecorder` | Data recorder instance |
| `is_initialized` | `bool` | Whether the core is initialized |
| `state` | `SessionState` | Current session state |
| `recording_enabled` | `bool` | Whether automatic recording is enabled |

### Methods

#### Lifecycle Methods

##### `async initialize() -> None`

Initialize the GLIDER core. Must be called before any other operations.

```python
await core.initialize()
```

**Operations performed:**
1. Initialize flow engine
2. Register built-in nodes
3. Load plugins
4. Create initial session

##### `async shutdown() -> None`

Shutdown the GLIDER core cleanly.

```python
await core.shutdown()
```

**Operations performed:**
1. Stop running experiment
2. Shutdown flow engine
3. Shutdown hardware
4. Unload plugins

#### Session Management

##### `new_session() -> ExperimentSession`

Create a new empty experiment session.

```python
session = core.new_session()
```

**Returns:** New `ExperimentSession` instance

**Note:** Discards any unsaved changes in the current session.

##### `load_session(file_path: str) -> ExperimentSession`

Load an experiment session from a JSON file.

```python
session = core.load_session("/path/to/experiment.json")
```

**Parameters:**
- `file_path`: Path to the session file

**Returns:** Loaded `ExperimentSession`

##### `save_session(file_path: Optional[str] = None) -> str`

Save the current session to file.

```python
path = core.save_session("/path/to/experiment.json")
# Or use existing path
path = core.save_session()
```

**Parameters:**
- `file_path`: Path to save to (uses existing path if None)

**Returns:** Path to saved file

**Raises:** `RuntimeError` if no session exists

##### `async load_experiment(file_path: Path) -> None`

Load an experiment from a `.glider` file using the serialization layer.

```python
await core.load_experiment(Path("experiment.glider"))
```

**Parameters:**
- `file_path`: Path to the `.glider` file

##### `async save_experiment(file_path: Path) -> None`

Save the current experiment to a `.glider` file.

```python
await core.save_experiment(Path("experiment.glider"))
```

**Parameters:**
- `file_path`: Path for the `.glider` file

**Raises:** `RuntimeError` if no session exists

#### Hardware Methods

##### `async setup_hardware() -> bool`

Set up hardware from the current session configuration.

```python
success = await core.setup_hardware()
```

**Returns:** `True` if all hardware set up successfully

**Raises:** `RuntimeError` if no session is loaded

##### `async connect_hardware() -> Dict[str, bool]`

Connect to all configured hardware boards.

```python
results = await core.connect_hardware()
# {'board_1': True, 'device:led': True, ...}
```

**Returns:** Dictionary mapping board/device IDs to connection success

**Raises:** `RuntimeError` if no session is loaded

##### `get_available_board_types() -> List[Dict[str, Any]]`

Get list of available board drivers.

```python
board_types = core.get_available_board_types()
# [{'driver': 'arduino', 'name': 'TelemetrixBoard', 'subtypes': ['uno', 'mega']}, ...]
```

##### `get_available_device_types() -> List[str]`

Get list of available device types.

```python
device_types = core.get_available_device_types()
# ['DigitalOutput', 'DigitalInput', 'AnalogInput', 'PWMOutput', 'Servo']
```

##### `get_available_node_types() -> List[str]`

Get list of available node types.

```python
node_types = core.get_available_node_types()
# ['StartExperiment', 'EndExperiment', 'DigitalWrite', 'Delay', ...]
```

#### Experiment Control

##### `async start_experiment() -> None`

Start running the experiment.

```python
await core.start_experiment()
```

**Behavior:**
- If in IDLE state, connects hardware first
- Sets up flow from session
- Starts data recording if enabled
- Begins flow execution

**Raises:** `RuntimeError` if state is invalid or no session

##### `async stop_experiment() -> None`

Stop the running experiment.

```python
await core.stop_experiment()
```

**Behavior:**
- Stops flow execution
- Stops data recording
- Sets all devices to safe state
- Transitions to READY state

##### `async pause_experiment() -> None`

Pause the running experiment.

```python
await core.pause_experiment()
```

##### `async resume_experiment() -> None`

Resume a paused experiment.

```python
await core.resume_experiment()
```

##### `async emergency_stop() -> None`

Trigger emergency stop - immediately stops all hardware and flow.

```python
await core.emergency_stop()
```

**Warning:** This is for emergency use only. Sets session to ERROR state.

#### Recording Configuration

##### `set_recording_directory(path: Path) -> None`

Set the directory for data recording output.

```python
core.set_recording_directory(Path("/data/experiments"))
```

##### `set_recording_interval(interval: float) -> None`

Set the sampling interval for recording.

```python
core.set_recording_interval(0.05)  # 50ms = 20 samples/second
```

**Parameters:**
- `interval`: Time between samples in seconds

#### Callbacks

##### `on_session_change(callback: Callable[[ExperimentSession], None]) -> None`

Register callback for session changes.

```python
def handle_session(session):
    print(f"Session: {session.name}")

core.on_session_change(handle_session)
```

##### `on_state_change(callback: Callable[[SessionState], None]) -> None`

Register callback for state changes.

```python
def handle_state(state):
    print(f"State: {state.name}")

core.on_state_change(handle_state)
```

##### `on_error(callback: Callable[[str, Exception], None]) -> None`

Register callback for errors.

```python
def handle_error(source, error):
    print(f"Error from {source}: {error}")

core.on_error(handle_error)
```

---

## ExperimentSession

The data model representing complete experiment state.

**Module:** `glider.core.experiment_session`

### Overview

`ExperimentSession` is the single source of truth for experiment configuration:
- Metadata (name, author, timestamps)
- Hardware configuration (boards, devices)
- Flow configuration (nodes, connections)
- Dashboard configuration

```python
from glider.core.experiment_session import ExperimentSession

session = ExperimentSession()
session.name = "My Experiment"
```

### Constructor

```python
ExperimentSession()
```

Creates a new empty experiment session.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `metadata` | `SessionMetadata` | Experiment metadata |
| `hardware` | `HardwareConfig` | Hardware configuration |
| `flow` | `FlowConfig` | Flow graph configuration |
| `dashboard` | `DashboardConfig` | Dashboard layout |
| `state` | `SessionState` | Current session state |
| `is_dirty` | `bool` | Has unsaved changes |
| `file_path` | `Optional[str]` | Path to saved file |
| `name` | `str` | Experiment name (shortcut to metadata.name) |

### SessionState Enum

```python
class SessionState(Enum):
    IDLE = auto()          # Not running
    INITIALIZING = auto()  # Connecting to hardware
    READY = auto()         # Hardware connected, ready to run
    RUNNING = auto()       # Experiment in progress
    PAUSED = auto()        # Experiment paused
    STOPPING = auto()      # Shutting down
    ERROR = auto()         # Error state
```

### Methods

#### Board Management

##### `add_board(config: BoardConfig) -> None`

Add a board to the hardware configuration.

```python
from glider.core.experiment_session import BoardConfig

config = BoardConfig(
    id="arduino_1",
    driver_type="arduino",
    port="COM3",
    board_type="uno"
)
session.add_board(config)
```

##### `remove_board(board_id: str) -> None`

Remove a board and its associated devices.

```python
session.remove_board("arduino_1")
```

##### `get_board(board_id: str) -> Optional[BoardConfig]`

Get a board by ID.

```python
board = session.get_board("arduino_1")
```

#### Device Management

##### `add_device(config: DeviceConfig) -> None`

Add a device to the hardware configuration.

```python
from glider.core.experiment_session import DeviceConfig

config = DeviceConfig(
    id="led_1",
    device_type="DigitalOutput",
    name="Status LED",
    board_id="arduino_1",
    pins={"signal": 13}
)
session.add_device(config)
```

##### `remove_device(device_id: str) -> None`

Remove a device and its associated nodes.

```python
session.remove_device("led_1")
```

##### `get_device(device_id: str) -> Optional[DeviceConfig]`

Get a device by ID.

```python
device = session.get_device("led_1")
```

#### Node Management

##### `add_node(config: NodeConfig) -> None`

Add a node to the flow graph.

```python
from glider.core.experiment_session import NodeConfig

config = NodeConfig(
    id="node_1",
    node_type="DigitalWrite",
    position=(100, 200),
    device_id="led_1"
)
session.add_node(config)
```

##### `remove_node(node_id: str) -> None`

Remove a node and its connections.

```python
session.remove_node("node_1")
```

##### `get_node(node_id: str) -> Optional[NodeConfig]`

Get a node by ID.

```python
node = session.get_node("node_1")
```

##### `update_node_position(node_id: str, x: float, y: float) -> None`

Update a node's position.

```python
session.update_node_position("node_1", 150, 250)
```

##### `update_node_state(node_id: str, state: Dict[str, Any]) -> None`

Update a node's internal state.

```python
session.update_node_state("node_1", {"value": True})
```

#### Connection Management

##### `add_connection(config: ConnectionConfig) -> None`

Add a connection between nodes.

```python
from glider.core.experiment_session import ConnectionConfig

config = ConnectionConfig(
    id="conn_1",
    from_node="node_1",
    from_output=0,
    to_node="node_2",
    to_input=0,
    connection_type="exec"
)
session.add_connection(config)
```

##### `remove_connection(connection_id: str) -> None`

Remove a connection.

```python
session.remove_connection("conn_1")
```

##### `get_connection(connection_id: str) -> Optional[ConnectionConfig]`

Get a connection by ID.

```python
conn = session.get_connection("conn_1")
```

#### Serialization

##### `to_dict() -> Dict[str, Any]`

Serialize session to dictionary.

```python
data = session.to_dict()
```

##### `from_dict(data: Dict[str, Any]) -> ExperimentSession` (classmethod)

Create session from dictionary.

```python
session = ExperimentSession.from_dict(data)
```

##### `to_json(indent: int = 2) -> str`

Serialize session to JSON string.

```python
json_str = session.to_json()
```

##### `from_json(json_str: str) -> ExperimentSession` (classmethod)

Create session from JSON string.

```python
session = ExperimentSession.from_json(json_str)
```

##### `save(file_path: Optional[str] = None) -> str`

Save session to file.

```python
path = session.save("/path/to/experiment.json")
```

##### `load(file_path: str) -> ExperimentSession` (classmethod)

Load session from file.

```python
session = ExperimentSession.load("/path/to/experiment.json")
```

##### `clear() -> None`

Reset session to empty state.

```python
session.clear()
```

#### Callbacks

##### `on_state_change(callback: Callable[[SessionState], None]) -> None`

Register callback for state changes.

##### `on_change(callback: Callable[[], None]) -> None`

Register callback for any changes (marks session dirty).

---

## DataRecorder

Records experiment data to CSV files.

**Module:** `glider.core.data_recorder`

### Overview

`DataRecorder` provides timestamped logging of device states during experiments.

```python
from glider.core.data_recorder import DataRecorder

recorder = DataRecorder(hardware_manager)
await recorder.start("my_experiment")
# ... experiment runs ...
file_path = await recorder.stop()
```

### Constructor

```python
DataRecorder(
    hardware_manager: HardwareManager,
    output_dir: Optional[Path] = None,
    sample_interval: float = 0.1
)
```

**Parameters:**
- `hardware_manager`: Hardware manager to read device states from
- `output_dir`: Directory for CSV files (defaults to current directory)
- `sample_interval`: Time between samples in seconds (default 0.1 = 100ms)

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_recording` | `bool` | Whether recording is active |
| `file_path` | `Optional[Path]` | Path to current recording file |
| `sample_interval` | `float` | Current sample interval in seconds |

### Methods

##### `async start(experiment_name: str = "experiment", session: Optional[ExperimentSession] = None) -> Path`

Start recording data.

```python
file_path = await recorder.start("temperature_test", session)
print(f"Recording to: {file_path}")
```

**Parameters:**
- `experiment_name`: Name for the filename
- `session`: Optional session for additional metadata

**Returns:** Path to the created CSV file

**Behavior:**
1. Creates timestamped filename
2. Writes metadata header
3. Starts sampling loop

##### `async stop() -> Optional[Path]`

Stop recording and close the file.

```python
file_path = await recorder.stop()
if file_path:
    print(f"Data saved to: {file_path}")
```

**Returns:** Path to completed file, or None if not recording

**Behavior:**
1. Stops sampling loop
2. Records final sample
3. Writes footer with duration
4. Closes file

##### `async record_event(event_name: str, details: str = "") -> None`

Record a custom event in the data file.

```python
await recorder.record_event("button_pressed", "User triggered action")
```

**Parameters:**
- `event_name`: Name of the event
- `details`: Additional details

**Output format:** `# EVENT: {name}, {elapsed_ms}ms, {details}`

### Output Format

CSV files include:

1. **Metadata header:**
```csv
# GLIDER Experiment Data
# Experiment Name,temperature_test
# Start Time,2024-01-15T10:30:00
# Sample Interval (s),0.1

# Boards
#,arduino_1,TelemetrixBoard,Connected

# Devices
#,sensor_1,AnalogInput,board=arduino_1,signal=0

timestamp,elapsed_ms,sensor_1:AnalogInput
```

2. **Data rows:**
```csv
2024-01-15T10:30:00.100,100.0,512
2024-01-15T10:30:00.200,200.0,515
```

3. **Footer:**
```csv
# End Time,2024-01-15T10:35:00
# Duration (s),300.00
```

---

## Configuration Classes

### SessionMetadata

```python
@dataclass
class SessionMetadata:
    id: str                    # Unique identifier (UUID)
    name: str = "Untitled"     # Experiment name
    description: str = ""      # Description
    author: str = ""           # Author name
    version: str = "1.0.0"     # Experiment version
    created_at: str            # ISO timestamp
    modified_at: str           # ISO timestamp
    glider_version: str        # GLIDER version
```

### BoardConfig

```python
@dataclass
class BoardConfig:
    id: str                    # Unique identifier
    driver_type: str           # Driver name (e.g., "arduino")
    port: Optional[str]        # Connection port
    board_type: Optional[str]  # Board variant (e.g., "uno")
    auto_reconnect: bool       # Auto-reconnect on disconnect
    settings: Dict[str, Any]   # Driver-specific settings
```

### DeviceConfig

```python
@dataclass
class DeviceConfig:
    id: str                    # Unique identifier
    device_type: str           # Device class name
    name: str                  # Human-readable name
    board_id: str              # Parent board ID
    pins: Dict[str, int]       # Pin assignments
    settings: Dict[str, Any]   # Device-specific settings
```

### NodeConfig

```python
@dataclass
class NodeConfig:
    id: str                    # Unique identifier
    node_type: str             # Node class name
    position: tuple            # (x, y) position
    state: Dict[str, Any]      # Node state
    device_id: Optional[str]   # Bound device ID
    visible_in_runner: bool    # Show in dashboard
```

### ConnectionConfig

```python
@dataclass
class ConnectionConfig:
    id: str                    # Unique identifier
    from_node: str             # Source node ID
    from_output: int           # Output port index
    to_node: str               # Target node ID
    to_input: int              # Input port index
    connection_type: str       # "data" or "exec"
```

### HardwareConfig

```python
@dataclass
class HardwareConfig:
    boards: List[BoardConfig]
    devices: List[DeviceConfig]
```

### FlowConfig

```python
@dataclass
class FlowConfig:
    nodes: List[NodeConfig]
    connections: List[ConnectionConfig]
```

### DashboardConfig

```python
@dataclass
class DashboardConfig:
    widgets: List[Dict[str, Any]]  # Widget configurations
    layout: str = "vertical"        # Layout type
    columns: int = 1                # Grid columns
```

---

## Convenience Functions

### create_core

```python
async def create_core() -> GliderCore:
    """Create and initialize a GliderCore instance."""
```

**Usage:**
```python
core = await create_core()
# Equivalent to:
core = GliderCore()
await core.initialize()
```

---

## See Also

- [Hardware API](hardware.md) - HardwareManager, BaseBoard, BaseDevice
- [Flow API](flow.md) - FlowEngine, GliderNode
- [Serialization API](serialization.md) - File format handling
