# File Format Specification

This document describes the `.glider` file format for GLIDER experiments.

## Overview

GLIDER experiment files use JSON format with the `.glider` extension. They contain:

- Experiment metadata
- Hardware configuration (boards, devices)
- Flow graph (nodes, connections)
- Dashboard layout

## File Structure

```json
{
  "schema_version": "1.0.0",
  "metadata": { ... },
  "hardware": { ... },
  "flow": { ... },
  "dashboard": { ... },
  "camera": { ... }
}
```

## Schema Version

```json
{
  "schema_version": "1.0.0"
}
```

Follows semantic versioning (MAJOR.MINOR.PATCH).

| Version | Compatibility |
|---------|---------------|
| 1.0.x | Current, fully supported |
| 0.x.x | Migrated automatically |
| 2.x.x | Rejected (future version) |

## Metadata Section

```json
{
  "metadata": {
    "name": "Blink Experiment",
    "description": "Blinks an LED 5 times",
    "author": "Lab User",
    "created": "2024-01-15T10:30:00",
    "modified": "2024-01-15T11:00:00",
    "tags": ["led", "blink", "tutorial"]
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Experiment name |
| `description` | string | No | Brief description |
| `author` | string | No | Author name/email |
| `created` | string | No | ISO 8601 creation timestamp |
| `modified` | string | No | ISO 8601 modification timestamp |
| `tags` | array | No | List of string tags |

## Hardware Section

### Structure

```json
{
  "hardware": {
    "boards": [ ... ],
    "devices": [ ... ]
  }
}
```

### Board Configuration

```json
{
  "boards": [
    {
      "id": "arduino_1",
      "type": "telemetrix",
      "port": "COM3",
      "settings": {
        "baud_rate": 115200
      }
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique board identifier |
| `type` | string | Yes | Driver type (see below) |
| `port` | string | No | Serial port for Arduino |
| `settings` | object | No | Driver-specific settings |

**Driver Types:**
| Type | Platform |
|------|----------|
| `telemetrix` | Arduino (via Telemetrix) |
| `pigpio` | Raspberry Pi GPIO |

### Device Configuration

```json
{
  "devices": [
    {
      "id": "led_1",
      "type": "digital_output",
      "board_id": "arduino_1",
      "pin": 13,
      "name": "Status LED",
      "settings": {}
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique device identifier |
| `type` | string | Yes | Device type (see below) |
| `board_id` | string | Yes | Parent board ID |
| `pin` | integer | Yes | Primary pin number |
| `name` | string | No | Display name |
| `settings` | object | No | Device-specific settings |

**Device Types:**
| Type | Description |
|------|-------------|
| `digital_output` | Digital output (LED, relay) |
| `digital_input` | Digital input (button, switch) |
| `analog_input` | Analog input (sensor) |
| `pwm_output` | PWM output (motor, dimming) |
| `servo` | Servo motor |

## Flow Section

### Structure

```json
{
  "flow": {
    "nodes": [ ... ],
    "connections": [ ... ]
  }
}
```

### Node Configuration

```json
{
  "nodes": [
    {
      "id": "delay_1",
      "type": "glider.nodes.experiment_nodes.DelayNode",
      "title": "Delay",
      "position": { "x": 200.0, "y": 100.0 },
      "properties": {
        "duration": 1.0,
        "visible_in_runner": false
      },
      "inputs": [
        { "name": "exec", "type": "exec" },
        { "name": "seconds", "type": "data", "data_type": "float" }
      ],
      "outputs": [
        { "name": "next", "type": "exec" }
      ]
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique node identifier |
| `type` | string | Yes | Full Python class path |
| `title` | string | Yes | Display title |
| `position` | object | Yes | Graph position `{x, y}` |
| `properties` | object | No | Node property values |
| `inputs` | array | No | Input port definitions |
| `outputs` | array | No | Output port definitions |

### Port Definition

```json
{
  "name": "value",
  "type": "data",
  "data_type": "float"
}
```

| Field | Type | Values |
|-------|------|--------|
| `name` | string | Port name |
| `type` | string | `"data"` or `"exec"` |
| `data_type` | string | `"int"`, `"float"`, `"bool"`, `"str"`, `"any"` |

### Connection Configuration

```json
{
  "connections": [
    {
      "id": "conn_1",
      "from_node": "start_1",
      "from_port": 0,
      "to_node": "delay_1",
      "to_port": 0,
      "connection_type": "exec"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique connection identifier |
| `from_node` | string | Yes | Source node ID |
| `from_port` | integer | Yes | Source port index |
| `to_node` | string | Yes | Target node ID |
| `to_port` | integer | Yes | Target port index |
| `connection_type` | string | No | `"data"` (default) or `"exec"` |

## Dashboard Section

```json
{
  "dashboard": {
    "layout_mode": "vertical",
    "columns": 2,
    "widgets": [
      {
        "node_id": "display_1",
        "position": 0,
        "size": "normal",
        "visible": true
      }
    ]
  }
}
```

### Dashboard Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `layout_mode` | string | `"vertical"` | Layout type |
| `columns` | integer | 1 | Grid columns (for grid layout) |
| `widgets` | array | [] | Widget configurations |

**Layout Modes:**
- `"vertical"` - Single column, top to bottom
- `"horizontal"` - Single row, left to right
- `"grid"` - Grid layout with specified columns

### Widget Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `node_id` | string | - | Associated node ID |
| `position` | integer | - | Order in layout |
| `size` | string | `"normal"` | Widget size |
| `visible` | boolean | true | Whether visible |

**Widget Sizes:**
- `"small"` - Compact display
- `"normal"` - Standard size
- `"large"` - Expanded display

## Camera Section

```json
{
  "camera": {
    "enabled": true,
    "camera_index": 0,
    "resolution": [640, 480],
    "fps": 30,
    "settings": {
      "exposure": -1,
      "brightness": 128,
      "contrast": 128,
      "saturation": 128,
      "auto_focus": true,
      "auto_exposure": true
    },
    "cv": {
      "enabled": true,
      "backend": "background_subtraction",
      "confidence_threshold": 0.5,
      "min_detection_area": 500,
      "tracking_enabled": true,
      "max_disappeared": 50,
      "draw_overlays": true,
      "show_labels": true
    },
    "recording": {
      "enabled": true,
      "output_directory": null
    }
  }
}
```

### Camera Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | false | Whether camera is enabled |
| `camera_index` | integer | 0 | Camera device index |
| `resolution` | array | [640, 480] | [width, height] in pixels |
| `fps` | integer | 30 | Target frame rate |
| `settings` | object | {} | Camera hardware settings |

### Camera Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `exposure` | integer | -1 | Exposure value (-1 = auto) |
| `brightness` | integer | 128 | Brightness (0-255) |
| `contrast` | integer | 128 | Contrast (0-255) |
| `saturation` | integer | 128 | Saturation (0-255) |
| `auto_focus` | boolean | true | Enable auto-focus |
| `auto_exposure` | boolean | true | Enable auto-exposure |

### CV (Computer Vision) Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | false | Enable CV processing |
| `backend` | string | `"background_subtraction"` | Detection backend |
| `confidence_threshold` | float | 0.5 | Minimum detection confidence |
| `min_detection_area` | integer | 500 | Minimum contour area (pixels) |
| `tracking_enabled` | boolean | true | Enable object tracking |
| `max_disappeared` | integer | 50 | Frames before dropping track |
| `draw_overlays` | boolean | true | Draw bounding boxes |
| `show_labels` | boolean | true | Show class labels |

**Detection Backends:**
| Backend | Description |
|---------|-------------|
| `background_subtraction` | Built-in motion-based detection |
| `motion_only` | Simple motion detection only |
| `yolo_v8` | YOLO v8 AI detection (requires ultralytics) |

### Recording Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | true | Record video during experiments |
| `output_directory` | string | null | Custom output directory (null = default) |

## Complete Example

```json
{
  "schema_version": "1.0.0",
  "metadata": {
    "name": "LED Blink",
    "description": "Blinks an LED 5 times with 500ms intervals",
    "author": "Lab User",
    "created": "2024-01-15T10:30:00",
    "modified": "2024-01-15T10:30:00",
    "tags": ["led", "tutorial"]
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
        "title": "Loop 5x",
        "position": {"x": 250, "y": 100},
        "properties": {"count": 5, "delay": 0},
        "inputs": [{"name": "exec", "type": "exec"}],
        "outputs": [
          {"name": "body", "type": "exec"},
          {"name": "done", "type": "exec"}
        ]
      },
      {
        "id": "on_1",
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
        "title": "Wait 500ms",
        "position": {"x": 550, "y": 50},
        "properties": {"duration": 0.5},
        "inputs": [
          {"name": "exec", "type": "exec"},
          {"name": "seconds", "type": "data", "data_type": "float"}
        ],
        "outputs": [{"name": "next", "type": "exec"}]
      },
      {
        "id": "off_1",
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
        "id": "delay_2",
        "type": "glider.nodes.experiment_nodes.DelayNode",
        "title": "Wait 500ms",
        "position": {"x": 850, "y": 50},
        "properties": {"duration": 0.5},
        "inputs": [
          {"name": "exec", "type": "exec"},
          {"name": "seconds", "type": "data", "data_type": "float"}
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
      {"id": "c2", "from_node": "loop_1", "from_port": 0, "to_node": "on_1", "to_port": 0, "connection_type": "exec"},
      {"id": "c3", "from_node": "on_1", "from_port": 0, "to_node": "delay_1", "to_port": 0, "connection_type": "exec"},
      {"id": "c4", "from_node": "delay_1", "from_port": 0, "to_node": "off_1", "to_port": 0, "connection_type": "exec"},
      {"id": "c5", "from_node": "off_1", "from_port": 0, "to_node": "delay_2", "to_port": 0, "connection_type": "exec"},
      {"id": "c6", "from_node": "loop_1", "from_port": 1, "to_node": "end_1", "to_port": 0, "connection_type": "exec"}
    ]
  },
  "dashboard": {
    "layout_mode": "vertical",
    "columns": 1,
    "widgets": []
  },
  "camera": {
    "enabled": false,
    "camera_index": 0,
    "resolution": [640, 480],
    "fps": 30,
    "cv": {
      "enabled": false,
      "backend": "background_subtraction"
    }
  }
}
```

## Validation

Files are validated on load. Common validation errors:

| Error | Cause |
|-------|-------|
| `Missing required field: name` | Metadata.name is required |
| `Expected dict, got list` | Wrong type for field |
| `Position must have 'x' and 'y' keys` | Invalid node position |
| `Expected int, got str` | Port number is string |

## Migration

Older file versions are automatically migrated:

```
Loading experiment.glider...
Migrating schema from 0.9.0 to 1.0.0
```

## See Also

- [Serialization API](../api-reference/serialization.md) - Programmatic access
- [Creating Experiments](../user-guide/creating-experiments.md) - Building experiments
