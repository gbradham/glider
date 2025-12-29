# Built-in Nodes Reference

This document covers the built-in node types available in GLIDER.

## Overview

GLIDER includes several categories of nodes:

| Category | Color | Purpose |
|----------|-------|---------|
| **Logic** | Blue | Flow control, data processing |
| **Hardware** | Green | Device interaction |
| **Interface** | Orange | User interaction |
| **Script** | Purple | Custom code |

---

## Flow Control Nodes

### StartExperiment

Entry point for the experiment flow.

**Category:** Logic

**Inputs:** None

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `next` | Exec | Triggers the next node |

**Behavior:**
- Automatically triggered when experiment starts
- Initiates the execution flow

**Usage:**
```
Every experiment should have exactly one StartExperiment node.
Connect its "next" output to your first action.
```

---

### EndExperiment

Exit point for the experiment flow.

**Category:** Logic

**Inputs:**
| Port | Type | Description |
|------|------|-------------|
| `exec` | Exec | Execution input |

**Outputs:** None

**Behavior:**
- Signals that the experiment flow is complete
- Triggers flow completion callbacks

**Usage:**
```
Connect the last action in your flow to EndExperiment.
This signals GLIDER to stop the experiment cleanly.
```

---

### Delay

Wait for a specified duration before continuing.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `exec` | Exec | - | Execution input |
| `seconds` | float | 1.0 | Duration in seconds |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `next` | Exec | Triggers after delay |

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `duration` | float | 1.0 | Wait time in seconds |

**Behavior:**
- Pauses execution for the specified duration
- Uses `asyncio.sleep()` (non-blocking)

---

### Loop

Repeat actions multiple times or indefinitely.

**Category:** Logic

**Inputs:**
| Port | Type | Description |
|------|------|-------------|
| `exec` | Exec | Start the loop |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `body` | Exec | Executes each iteration |
| `done` | Exec | Executes when loop completes |

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `count` | int | 0 | Number of iterations (0 = infinite) |
| `delay` | float | 1.0 | Delay between iterations |

**Behavior:**
- If `count > 0`: Loops exactly `count` times
- If `count = 0`: Loops until experiment stops
- Triggers `body` for each iteration
- Triggers `done` when complete

**Example:**
```
Blink LED 5 times:
  StartExperiment -> Loop(count=5) -> Output(HIGH) -> Delay -> Output(LOW) -> Delay
                          |--body------------------------------------------|
                          |--done--> EndExperiment
```

---

### WaitForInput

Pause execution until an input is triggered.

**Category:** Logic

**Inputs:**
| Port | Type | Description |
|------|------|-------------|
| `exec` | Exec | Start waiting |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `triggered` | Exec | Executes when input detected |
| `timeout` | Exec | Executes on timeout |

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `timeout` | float | 0.0 | Timeout in seconds (0 = no timeout) |
| `poll_interval` | float | 0.05 | Polling interval (ms) |

**Device Binding:** Requires a DigitalInput device

**Behavior:**
- Polls bound device for rising edge (LOW → HIGH)
- Triggers `triggered` when input goes HIGH
- Triggers `timeout` if timeout expires
- Uses edge detection to avoid repeated triggers

**Example:**
```
Wait for button press before continuing:
  StartExperiment -> WaitForInput -> DoSomething
                          |--triggered-->|
                          |--timeout--> EndExperiment
```

---

## Hardware Nodes

### Output

Write a digital value to a device.

**Category:** Hardware

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `exec` | Exec | - | Execution input |
| `value` | bool | True | HIGH (true) or LOW (false) |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `next` | Exec | Triggers after write |

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `value` | int | 1 | Output value (1=HIGH, 0=LOW) |

**Device Binding:** Requires DigitalOutput or PWMOutput device

**Behavior:**
- Calls device's `set_state()` or `turn_on()`/`turn_off()`
- Sets error state if device not bound

**Example:**
```
Turn on LED:
  Output (value=HIGH, device=led_1)
```

---

### Input

Read a value from a device.

**Category:** Hardware

**Inputs:**
| Port | Type | Description |
|------|------|-------------|
| `exec` | Exec | Execution input |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `value` | any | Read value |
| `next` | Exec | Triggers after read |

**Device Binding:** Requires DigitalInput or AnalogInput device

**Behavior:**
- Calls device's `read()` or `get_state()`
- Outputs the read value
- Sets error state if read fails

**Example:**
```
Read sensor and display:
  Input (device=sensor_1) --value--> Display
```

---

## Data Processing Nodes

### Math Nodes

*(Coming in future versions)*

Planned nodes for mathematical operations:
- **Add** - Add two numbers
- **Subtract** - Subtract two numbers
- **Multiply** - Multiply two numbers
- **Divide** - Divide two numbers
- **Compare** - Compare two values
- **Clamp** - Limit value to range

---

### Logic Nodes

*(Coming in future versions)*

Planned nodes for logical operations:
- **If** - Branch based on condition
- **And** - Logical AND
- **Or** - Logical OR
- **Not** - Logical NOT
- **Switch** - Multi-way branch

---

## Interface Nodes

*(Coming in future versions)*

Planned nodes for user interaction:
- **Button** - Clickable button
- **Slider** - Value slider
- **Display** - Value display
- **Toggle** - On/off switch
- **Input Field** - Text input

---

## Script Node

Execute custom Python code.

**Category:** Script

**Inputs:**
| Port | Type | Description |
|------|------|-------------|
| `exec` | Exec | Execution input |
| `in0-in3` | any | Custom data inputs |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `next` | Exec | Execution output |
| `out0-out3` | any | Custom data outputs |

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `code` | str | Python code to execute |

**Available in Script:**
```python
# Input values
inputs[0]  # First input value
inputs[1]  # Second input value

# Set outputs
set_output(0, value)  # Set first output
set_output(1, value)  # Set second output

# Access bound device
device.read()
device.set_state(True)

# Async support
await asyncio.sleep(1)
```

**Example:**
```python
# Temperature conversion
celsius = inputs[0]
fahrenheit = celsius * 9/5 + 32
set_output(0, fahrenheit)
```

**Security Note:** Script nodes execute arbitrary Python code. Only use scripts from trusted sources.

---

## Node Registration

### Built-in Registration

GLIDER automatically registers built-in nodes:

```python
# In glider.nodes.experiment_nodes
def register_experiment_nodes(flow_engine):
    flow_engine.register_node("StartExperiment", StartExperimentNode)
    flow_engine.register_node("EndExperiment", EndExperimentNode)
    flow_engine.register_node("Delay", DelayNode)
    flow_engine.register_node("Output", OutputNode)
    flow_engine.register_node("Input", InputNode)

# In glider.nodes.control_nodes
def register_control_nodes(flow_engine):
    flow_engine.register_node("Loop", LoopNode)
    flow_engine.register_node("WaitForInput", WaitForInputNode)
```

### Custom Node Registration

Register custom nodes via plugins:

```python
# In plugin __init__.py
NODE_TYPES = {
    "MyCustomNode": MyCustomNode,
    "AnotherNode": AnotherNode,
}
```

Or manually:

```python
from glider.core.flow_engine import FlowEngine

FlowEngine.register_node("MyNode", MyNodeClass)
```

---

## Creating Custom Nodes

See the [Custom Nodes](../developer-guide/custom-nodes.md) guide for detailed instructions on creating your own nodes.

### Quick Example

```python
from glider.nodes.base_node import GliderNode, NodeDefinition, NodeCategory, PortDefinition, PortType

class DoubleNode(GliderNode):
    """Doubles an input value."""

    definition = NodeDefinition(
        name="Double",
        category=NodeCategory.LOGIC,
        description="Multiplies input by 2",
        inputs=[
            PortDefinition("value", PortType.DATA, float, 0.0),
        ],
        outputs=[
            PortDefinition("result", PortType.DATA),
        ],
    )

    def update_event(self):
        value = self.get_input(0) or 0
        self.set_output(0, value * 2)
```

---

## See Also

- [Flow API](flow.md) - FlowEngine, GliderNode base class
- [Custom Nodes](../developer-guide/custom-nodes.md) - Node development guide
- [Creating Experiments](../user-guide/creating-experiments.md) - Using nodes in the GUI
