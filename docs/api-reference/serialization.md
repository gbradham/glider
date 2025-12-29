# Serialization API Reference

This document covers the serialization system for saving and loading GLIDER experiments.

## Overview

GLIDER experiments are saved as `.glider` files in JSON format. The serialization system provides:

- **Schema validation** - Ensures file integrity
- **Version migration** - Handles older file formats
- **Type safety** - Validates all fields

**Module:** `glider.serialization`

---

## ExperimentSerializer

Main class for saving and loading experiment files.

**Module:** `glider.serialization.serializer`

### Constructor

```python
ExperimentSerializer()
```

### Methods

#### `save(path, session, flow_engine=None, hardware_manager=None) -> None`

Save an experiment session to a file.

```python
from glider.serialization.serializer import get_serializer
from pathlib import Path

serializer = get_serializer()
serializer.save(
    path=Path("experiment.glider"),
    session=session,
    flow_engine=flow_engine,
    hardware_manager=hardware_manager
)
```

**Parameters:**
- `path`: File path to save to (`.glider` extension added if missing)
- `session`: ExperimentSession to save
- `flow_engine`: Optional FlowEngine for node/connection data
- `hardware_manager`: Optional HardwareManager for device config

#### `load(path) -> ExperimentSchema`

Load an experiment schema from a file.

```python
schema = serializer.load(Path("experiment.glider"))
```

**Parameters:**
- `path`: File path to load from

**Returns:** `ExperimentSchema` object

**Raises:**
- `FileNotFoundError`: File doesn't exist
- `PermissionError`: Cannot read file
- `SchemaValidationError`: Invalid or malformed file

#### `apply_to_session(schema, session, flow_engine=None, hardware_manager=None) -> None`

Apply a loaded schema to a session.

```python
serializer.apply_to_session(
    schema=schema,
    session=session,
    flow_engine=flow_engine,
    hardware_manager=hardware_manager
)
```

#### `register_node_type(node_type, node_class) -> None`

Register a node type for deserialization.

```python
serializer.register_node_type("glider.nodes.MyNode", MyNode)
```

### Global Instance

```python
from glider.serialization.serializer import get_serializer

serializer = get_serializer()  # Returns global instance
```

---

## Schema Classes

**Module:** `glider.serialization.schema`

### ExperimentSchema

Root schema for `.glider` files.

```python
@dataclass
class ExperimentSchema:
    schema_version: str = "1.0.0"
    metadata: MetadataSchema
    hardware: HardwareConfigSchema
    flow: FlowConfigSchema
    dashboard: DashboardConfigSchema
```

**Methods:**

```python
# Serialization
schema.to_dict() -> Dict[str, Any]
schema.to_json(indent=2) -> str

# Deserialization
ExperimentSchema.from_dict(data) -> ExperimentSchema
ExperimentSchema.from_json(json_str) -> ExperimentSchema

# Utility
schema.update_modified()  # Updates modified timestamp
```

---

### MetadataSchema

Experiment metadata.

```python
@dataclass
class MetadataSchema:
    name: str                    # Required
    description: str = ""
    author: str = ""
    created: str = ""            # ISO 8601 timestamp
    modified: str = ""           # ISO 8601 timestamp
    tags: List[str] = []
```

**Example:**
```json
{
  "name": "Blink Experiment",
  "description": "Blinks an LED",
  "author": "Lab User",
  "created": "2024-01-15T10:30:00",
  "modified": "2024-01-15T11:00:00",
  "tags": ["led", "blink", "tutorial"]
}
```

---

### HardwareConfigSchema

Hardware configuration container.

```python
@dataclass
class HardwareConfigSchema:
    boards: List[BoardConfigSchema] = []
    devices: List[DeviceConfigSchema] = []
```

---

### BoardConfigSchema

Board configuration.

```python
@dataclass
class BoardConfigSchema:
    id: str                      # Required
    type: str                    # Required (e.g., "telemetrix")
    port: Optional[str] = None   # Serial port
    settings: Dict[str, Any] = {}
```

**Example:**
```json
{
  "id": "arduino_1",
  "type": "telemetrix",
  "port": "COM3",
  "settings": {
    "baud_rate": 115200
  }
}
```

---

### DeviceConfigSchema

Device configuration.

```python
@dataclass
class DeviceConfigSchema:
    id: str                      # Required
    type: str                    # Required (e.g., "digital_output")
    board_id: str                # Required
    pin: int                     # Required
    name: Optional[str] = None
    settings: Dict[str, Any] = {}
```

**Example:**
```json
{
  "id": "led_1",
  "type": "digital_output",
  "board_id": "arduino_1",
  "pin": 13,
  "name": "Status LED",
  "settings": {}
}
```

---

### FlowConfigSchema

Flow graph configuration.

```python
@dataclass
class FlowConfigSchema:
    nodes: List[NodeSchema] = []
    connections: List[ConnectionSchema] = []
```

---

### NodeSchema

Node configuration.

```python
@dataclass
class NodeSchema:
    id: str                      # Required
    type: str                    # Required (full path)
    title: str                   # Required
    position: Dict[str, float]   # Required {"x": float, "y": float}
    properties: Dict[str, Any] = {}
    inputs: List[PortSchema] = []
    outputs: List[PortSchema] = []
```

**Example:**
```json
{
  "id": "delay_1",
  "type": "glider.nodes.experiment_nodes.DelayNode",
  "title": "Delay",
  "position": {"x": 200, "y": 100},
  "properties": {
    "duration": 1.0,
    "visible_in_runner": false
  },
  "inputs": [
    {"name": "exec", "type": "exec"},
    {"name": "seconds", "type": "data", "data_type": "float"}
  ],
  "outputs": [
    {"name": "next", "type": "exec"}
  ]
}
```

---

### ConnectionSchema

Connection between nodes.

```python
@dataclass
class ConnectionSchema:
    id: str                      # Required
    from_node: str               # Required
    from_port: int               # Required
    to_node: str                 # Required
    to_port: int                 # Required
    connection_type: str = "data"  # "data" or "exec"
```

**Example:**
```json
{
  "id": "conn_1",
  "from_node": "start_1",
  "from_port": 0,
  "to_node": "delay_1",
  "to_port": 0,
  "connection_type": "exec"
}
```

---

### PortSchema

Port definition.

```python
@dataclass
class PortSchema:
    name: str
    type: str                    # "data" or "exec"
    data_type: Optional[str] = None
```

---

### DashboardConfigSchema

Dashboard layout configuration.

```python
@dataclass
class DashboardConfigSchema:
    layout_mode: str = "vertical"  # "vertical", "horizontal", "grid"
    columns: int = 1
    widgets: List[DashboardWidgetSchema] = []
```

---

### DashboardWidgetSchema

Dashboard widget configuration.

```python
@dataclass
class DashboardWidgetSchema:
    node_id: str
    position: int                # Order in dashboard
    size: str = "normal"         # "small", "normal", "large"
    visible: bool = True
```

---

## File Format

### Complete Example

```json
{
  "schema_version": "1.0.0",
  "metadata": {
    "name": "Blink Experiment",
    "description": "Blinks an LED on pin 13",
    "author": "Lab User",
    "created": "2024-01-15T10:30:00",
    "modified": "2024-01-15T11:00:00",
    "tags": ["led", "blink"]
  },
  "hardware": {
    "boards": [
      {
        "id": "arduino_1",
        "type": "telemetrix",
        "port": "COM3",
        "settings": {}
      }
    ],
    "devices": [
      {
        "id": "led_1",
        "type": "digital_output",
        "board_id": "arduino_1",
        "pin": 13,
        "name": "LED",
        "settings": {}
      }
    ]
  },
  "flow": {
    "nodes": [
      {
        "id": "start_1",
        "type": "glider.nodes.experiment_nodes.StartExperimentNode",
        "title": "Start",
        "position": {"x": 100, "y": 100},
        "properties": {},
        "inputs": [],
        "outputs": [{"name": "next", "type": "exec"}]
      },
      {
        "id": "loop_1",
        "type": "glider.nodes.control_nodes.LoopNode",
        "title": "Loop",
        "position": {"x": 250, "y": 100},
        "properties": {"count": 5, "delay": 1.0},
        "inputs": [{"name": "exec", "type": "exec"}],
        "outputs": [
          {"name": "body", "type": "exec"},
          {"name": "done", "type": "exec"}
        ]
      },
      {
        "id": "output_on",
        "type": "glider.nodes.experiment_nodes.OutputNode",
        "title": "LED On",
        "position": {"x": 400, "y": 50},
        "properties": {"value": 1, "device_id": "led_1"},
        "inputs": [
          {"name": "exec", "type": "exec"},
          {"name": "value", "type": "data", "data_type": "bool"}
        ],
        "outputs": [{"name": "next", "type": "exec"}]
      },
      {
        "id": "delay_1",
        "type": "glider.nodes.experiment_nodes.DelayNode",
        "title": "Delay",
        "position": {"x": 550, "y": 50},
        "properties": {"duration": 0.5},
        "inputs": [
          {"name": "exec", "type": "exec"},
          {"name": "seconds", "type": "data", "data_type": "float"}
        ],
        "outputs": [{"name": "next", "type": "exec"}]
      },
      {
        "id": "output_off",
        "type": "glider.nodes.experiment_nodes.OutputNode",
        "title": "LED Off",
        "position": {"x": 700, "y": 50},
        "properties": {"value": 0, "device_id": "led_1"},
        "inputs": [
          {"name": "exec", "type": "exec"},
          {"name": "value", "type": "data", "data_type": "bool"}
        ],
        "outputs": [{"name": "next", "type": "exec"}]
      },
      {
        "id": "end_1",
        "type": "glider.nodes.experiment_nodes.EndExperimentNode",
        "title": "End",
        "position": {"x": 400, "y": 200},
        "properties": {},
        "inputs": [{"name": "exec", "type": "exec"}],
        "outputs": []
      }
    ],
    "connections": [
      {"id": "c1", "from_node": "start_1", "from_port": 0, "to_node": "loop_1", "to_port": 0, "connection_type": "exec"},
      {"id": "c2", "from_node": "loop_1", "from_port": 0, "to_node": "output_on", "to_port": 0, "connection_type": "exec"},
      {"id": "c3", "from_node": "output_on", "from_port": 0, "to_node": "delay_1", "to_port": 0, "connection_type": "exec"},
      {"id": "c4", "from_node": "delay_1", "from_port": 0, "to_node": "output_off", "to_port": 0, "connection_type": "exec"},
      {"id": "c5", "from_node": "loop_1", "from_port": 1, "to_node": "end_1", "to_port": 0, "connection_type": "exec"}
    ]
  },
  "dashboard": {
    "layout_mode": "vertical",
    "columns": 1,
    "widgets": []
  }
}
```

---

## Validation

### SchemaValidationError

Exception raised when validation fails.

```python
class SchemaValidationError(Exception):
    path: str                    # JSON path to error
    details: Dict[str, Any]      # Additional details
```

**Example:**
```python
try:
    schema = ExperimentSchema.from_json(content)
except SchemaValidationError as e:
    print(f"Validation error at {e.path}: {e}")
```

### Validation Rules

| Field | Rule |
|-------|------|
| `schema_version` | Must be string, semantic version |
| `metadata.name` | Required, non-empty string |
| `node.id` | Required, unique string |
| `node.position` | Must have `x` and `y` keys |
| `connection.from_port` | Must be integer |
| `connection.to_port` | Must be integer |
| `device.pin` | Must be integer |

---

## Version Migration

The serializer handles older file formats automatically:

```python
def _validate_and_migrate(self, schema):
    version = schema.schema_version
    if version < SCHEMA_VERSION:
        schema = self._migrate_schema(schema, version, SCHEMA_VERSION)
    return schema
```

### Version Compatibility

| File Version | Support |
|--------------|---------|
| 1.0.x | Full support |
| 0.x.x | Migration available |
| 2.x.x | Rejected (future version) |

---

## Constants

```python
from glider.serialization.schema import SCHEMA_VERSION

SCHEMA_VERSION  # "1.0.0"
```

```python
from glider.serialization.serializer import ExperimentSerializer

ExperimentSerializer.FILE_EXTENSION  # ".glider"
```

---

## See Also

- [Core API](core.md) - ExperimentSession
- [File Format Reference](../reference/file-format.md) - Detailed specification
- [Custom Nodes](../developer-guide/custom-nodes.md) - Node serialization
