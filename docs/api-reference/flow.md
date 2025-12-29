# Flow API Reference

This document covers the flow graph execution system in GLIDER.

## FlowEngine

Manages the execution of the experiment flow graph.

**Module:** `glider.core.flow_engine`

### Overview

`FlowEngine` executes the visual flow graph with support for:
- **Data Flow**: Reactive propagation when values change
- **Execution Flow**: Imperative sequence of actions

```python
from glider.core.flow_engine import FlowEngine

engine = FlowEngine(hardware_manager)
engine.initialize()
engine.create_node("start", "StartExperiment")
await engine.start()
```

### Constructor

```python
FlowEngine(hardware_manager=None)
```

**Parameters:**
- `hardware_manager`: Optional `HardwareManager` for device access

### Class Methods

##### `register_node(node_type: str, node_class: Type) -> None`

Register a node type globally.

```python
FlowEngine.register_node("MyNode", MyNodeClass)
```

##### `get_available_nodes() -> List[str]`

Get list of available node type names.

```python
nodes = FlowEngine.get_available_nodes()
# ['StartExperiment', 'EndExperiment', 'DigitalWrite', 'Delay', ...]
```

##### `get_node_class(node_type: str) -> Optional[Type]`

Get a node class by type name.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `state` | `FlowState` | Current flow state |
| `is_running` | `bool` | Whether flow is running |
| `nodes` | `Dict[str, Any]` | Dictionary of node instances |

### Methods

#### Initialization

##### `initialize() -> None`

Initialize the flow engine.

```python
engine.initialize()
```

#### Node Management

##### `create_node(node_id: str, node_type: str, position: tuple = (0, 0), state: Optional[Dict] = None, device_id: Optional[str] = None) -> Any`

Create a node instance.

```python
node = engine.create_node(
    node_id="led_write",
    node_type="DigitalWrite",
    position=(100, 200),
    device_id="led_1"
)
```

**Parameters:**
- `node_id`: Unique node ID
- `node_type`: Node type name
- `position`: (x, y) graph position
- `state`: Initial state data
- `device_id`: Associated device ID

**Returns:** Created node instance

##### `remove_node(node_id: str) -> None`

Remove a node from the flow.

##### `get_node(node_id: str) -> Optional[Any]`

Get a node by ID.

#### Connection Management

##### `create_connection(connection_id: str, from_node_id: str, from_output: int, to_node_id: str, to_input: int, connection_type: str = "data") -> None`

Create a connection between nodes.

```python
engine.create_connection(
    connection_id="conn_1",
    from_node_id="start",
    from_output=0,
    to_node_id="delay",
    to_input=0,
    connection_type="exec"
)
```

**Parameters:**
- `connection_id`: Unique connection ID
- `from_node_id`: Source node ID
- `from_output`: Source output index
- `to_node_id`: Target node ID
- `to_input`: Target input index
- `connection_type`: "data" or "exec"

##### `remove_connection(connection_id: str) -> None`

Remove a connection.

#### Data Access

##### `get_node_output(node_id: str, output_index: int) -> Any`

Get current value of a node output.

```python
value = engine.get_node_output("sensor_node", 0)
```

##### `set_node_input(node_id: str, input_index: int, value: Any) -> None`

Set value of a node input.

```python
engine.set_node_input("multiply", 0, 5.0)
```

#### Execution Control

##### `async start() -> None`

Start flow execution.

```python
await engine.start()
```

**Behavior:**
1. Sets state to RUNNING
2. Calls `start()` on all nodes
3. Begins listening for execution triggers

##### `async stop() -> None`

Stop flow execution.

```python
await engine.stop()
```

**Behavior:**
1. Cancels running tasks
2. Calls `stop()` on all nodes
3. Sets state to STOPPED

##### `async pause() -> None`

Pause flow execution.

##### `async resume() -> None`

Resume paused flow.

##### `trigger_exec(node_id: str, exec_output: int = 0) -> None`

Manually trigger an execution output.

```python
engine.trigger_exec("start", 0)
```

#### Session Integration

##### `load_from_session(session: ExperimentSession) -> None`

Load flow from an experiment session.

```python
engine.load_from_session(session)
```

##### `clear() -> None`

Clear all nodes and connections.

##### `shutdown() -> None`

Shutdown the flow engine.

#### Callbacks

##### `on_state_change(callback: Callable[[FlowState], None]) -> None`

Register callback for state changes.

```python
def on_state(state):
    print(f"Flow state: {state.name}")

engine.on_state_change(on_state)
```

##### `on_node_update(callback: Callable[[str, str, Any], None]) -> None`

Register callback for node output updates.

```python
def on_update(node_id, output_name, value):
    print(f"Node {node_id}.{output_name} = {value}")

engine.on_node_update(on_update)
```

##### `on_error(callback: Callable[[str, Exception], None]) -> None`

Register callback for errors.

##### `on_flow_complete(callback: Callable[[], None]) -> None`

Register callback for flow completion (EndExperiment reached).

### FlowState Enum

```python
class FlowState(Enum):
    STOPPED = auto()
    RUNNING = auto()
    PAUSED = auto()
    ERROR = auto()
```

---

## GliderNode

Base class for all GLIDER nodes.

**Module:** `glider.nodes.base_node`

### Overview

`GliderNode` provides common functionality:
- Input/output management
- State serialization
- Device binding
- Async operation support
- Error handling

```python
from glider.nodes.base_node import GliderNode, NodeCategory, NodeDefinition

class MyNode(GliderNode):
    definition = NodeDefinition(
        name="MyNode",
        category=NodeCategory.LOGIC,
        description="Custom node"
    )

    def update_event(self):
        value = self.get_input(0)
        self.set_output(0, value * 2)
```

### Constructor

```python
GliderNode()
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Node ID |
| `name` | `str` | Node type name |
| `category` | `NodeCategory` | Node category |
| `inputs` | `List[Any]` | Current input values |
| `outputs` | `List[Any]` | Current output values |
| `device` | `Optional[BaseDevice]` | Bound device |
| `error` | `Optional[str]` | Current error message |
| `is_enabled` | `bool` | Whether enabled |
| `visible_in_runner` | `bool` | Show in dashboard |

### Class Attribute

##### `definition: NodeDefinition`

Override to define node metadata:

```python
definition = NodeDefinition(
    name="MultiplyNode",
    category=NodeCategory.LOGIC,
    description="Multiplies two numbers",
    inputs=[
        PortDefinition("a", data_type=float, default_value=0.0),
        PortDefinition("b", data_type=float, default_value=1.0),
    ],
    outputs=[
        PortDefinition("result", data_type=float),
    ],
    color="#2d4a5a"
)
```

### Abstract Methods

##### `update_event() -> None`

Called when input values change. Must be implemented.

```python
def update_event(self):
    a = self.get_input(0)
    b = self.get_input(1)
    self.set_output(0, a * b)
```

### Methods

#### Input/Output

##### `get_input(index: int) -> Any`

Get input value by index.

##### `get_input_by_name(name: str) -> Any`

Get input value by name.

##### `set_input(index: int, value: Any) -> None`

Set input value (triggers `update_event`).

##### `get_output(index: int) -> Any`

Get output value by index.

##### `set_output(index: int, value: Any) -> None`

Set output value and notify listeners.

##### `exec_output(index: int = 0) -> None`

Trigger execution flow output (for exec nodes).

#### Device Binding

##### `bind_device(device: BaseDevice) -> None`

Bind a hardware device.

##### `unbind_device() -> None`

Unbind the current device.

#### State Management

##### `enable() -> None`

Enable the node.

##### `disable() -> None`

Disable the node.

##### `set_error(error: Optional[str]) -> None`

Set error state.

##### `clear_error() -> None`

Clear error state.

##### `get_state() -> Dict[str, Any]`

Get serializable state.

##### `set_state(state: Dict[str, Any]) -> None`

Restore state from dictionary.

#### Lifecycle

##### `async start() -> None`

Called when flow execution starts.

##### `async stop() -> None`

Called when flow execution stops.

##### `async pause() -> None`

Called when flow is paused.

##### `async resume() -> None`

Called when flow is resumed.

#### Callbacks

##### `on_output_update(callback: Callable[[str, Any], None]) -> None`

Register callback for output updates.

##### `on_error(callback: Callable[[Exception], None]) -> None`

Register callback for errors.

#### Serialization

##### `to_dict() -> Dict[str, Any]`

Serialize node to dictionary.

---

## Node Base Classes

### DataNode

Base class for data processing nodes.

```python
from glider.nodes.base_node import DataNode

class MultiplyNode(DataNode):
    def process(self):
        a = self.get_input(0) or 0
        b = self.get_input(1) or 1
        self.set_output(0, a * b)
```

**Abstract method:** `process() -> None`

### ExecNode

Base class for execution flow nodes.

```python
from glider.nodes.base_node import ExecNode

class PrintNode(ExecNode):
    async def execute(self):
        message = self.get_input(0)
        print(message)
        self.exec_output(0)  # Trigger next node
```

**Abstract method:** `async execute() -> None`

**Additional methods:**
- `on_exec(callback)` - Register exec callback
- `exec_output(index)` - Trigger execution output

### HardwareNode

Base class for hardware interaction nodes.

```python
from glider.nodes.base_node import HardwareNode

class DigitalWriteNode(HardwareNode):
    async def hardware_operation(self):
        value = self.get_input(0)
        await self.device.set_state(value)
```

**Abstract method:** `async hardware_operation() -> None`

Automatically handles:
- Device validation
- Error handling
- Disabled state

### LogicNode

Base class for logic/math nodes.

Same as `DataNode` but with `LOGIC` category preset.

### InterfaceNode

Base class for UI interface nodes.

```python
from glider.nodes.base_node import InterfaceNode

class DisplayNode(InterfaceNode):
    def update_event(self):
        value = self.get_input(0)
        self.notify_widget(value)
```

**Additional methods:**
- `on_widget_update(callback)` - Register widget callback
- `notify_widget(value)` - Notify widget of value change

**Note:** `visible_in_runner` defaults to `True`.

### ScriptNode

Base class for custom script nodes.

```python
from glider.nodes.base_node import ScriptNode

node = ScriptNode()
node.code = """
result = inputs[0] * 2
set_output(0, result)
"""
await node.execute()
```

**Properties:**
- `code: str` - Script code

**Methods:**
- `compile() -> bool` - Compile the script

---

## Enums and Data Classes

### NodeCategory

```python
class NodeCategory(Enum):
    HARDWARE = "hardware"   # Green border
    LOGIC = "logic"         # Blue border
    INTERFACE = "interface" # Orange border
    SCRIPT = "script"       # Purple border
```

### PortType

```python
class PortType(Enum):
    DATA = auto()      # Data flow
    EXEC = auto()      # Execution flow
```

### PortDefinition

```python
@dataclass
class PortDefinition:
    name: str
    port_type: PortType = PortType.DATA
    data_type: type = object
    default_value: Any = None
    description: str = ""
```

### NodeDefinition

```python
@dataclass
class NodeDefinition:
    name: str
    category: NodeCategory
    description: str = ""
    inputs: List[PortDefinition] = []
    outputs: List[PortDefinition] = []
    color: str = "#444444"
```

---

## Example: Complete Custom Node

```python
from glider.nodes.base_node import (
    ExecNode,
    NodeCategory,
    NodeDefinition,
    PortDefinition,
    PortType
)

class ThresholdNode(ExecNode):
    """Checks if value exceeds threshold and branches."""

    definition = NodeDefinition(
        name="Threshold",
        category=NodeCategory.LOGIC,
        description="Branches based on value vs threshold",
        inputs=[
            PortDefinition("exec", PortType.EXEC, description="Execute"),
            PortDefinition("value", data_type=float, default_value=0.0),
            PortDefinition("threshold", data_type=float, default_value=50.0),
        ],
        outputs=[
            PortDefinition("above", PortType.EXEC, description="Value >= threshold"),
            PortDefinition("below", PortType.EXEC, description="Value < threshold"),
            PortDefinition("difference", data_type=float),
        ],
        color="#2d4a5a"
    )

    async def execute(self):
        value = self.get_input(1) or 0.0
        threshold = self.get_input(2) or 50.0

        # Set difference output
        diff = value - threshold
        self.set_output(2, diff)

        # Branch execution
        if value >= threshold:
            self.exec_output(0)  # above
        else:
            self.exec_output(1)  # below
```

---

## See Also

- [Core API](core.md) - GliderCore, FlowEngine integration
- [Nodes Reference](nodes.md) - Built-in node types
- [Custom Nodes](../developer-guide/custom-nodes.md) - Node development guide
