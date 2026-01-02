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

#### Add

Add two numbers together.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `A` | float | 0.0 | First number |
| `B` | float | 0.0 | Second number |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Result` | float | A + B |

---

#### Subtract

Subtract two numbers.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `A` | float | 0.0 | First number |
| `B` | float | 0.0 | Number to subtract |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Result` | float | A - B |

---

#### Multiply

Multiply two numbers.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `A` | float | 0.0 | First number |
| `B` | float | 1.0 | Second number |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Result` | float | A * B |

---

#### Divide

Divide two numbers.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `A` | float | 0.0 | Numerator |
| `B` | float | 1.0 | Denominator |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Result` | float | A / B |

**Behavior:**
- Returns 0.0 and sets error if B is 0 (division by zero)

---

#### Map Range

Map a value from one range to another.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `Value` | float | 0.0 | Input value |
| `In Min` | float | 0.0 | Input range minimum |
| `In Max` | float | 1023.0 | Input range maximum |
| `Out Min` | float | 0.0 | Output range minimum |
| `Out Max` | float | 255.0 | Output range maximum |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Result` | float | Mapped value |

**Example:**
```
Map analog sensor (0-1023) to PWM output (0-255):
  AnalogRead -> MapRange -> PWMWrite
```

---

#### Clamp

Clamp a value to a specified range.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `Value` | float | 0.0 | Input value |
| `Min` | float | 0.0 | Minimum allowed |
| `Max` | float | 100.0 | Maximum allowed |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Result` | float | Clamped value |

---

### Comparison Nodes

#### Threshold

Check if a value exceeds a threshold with optional hysteresis.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `Value` | float | 0.0 | Input value |
| `Threshold` | float | 50.0 | Threshold level |
| `Hysteresis` | float | 0.0 | Hysteresis band |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Above` | bool | True if value > threshold |
| `Below` | bool | True if value <= threshold |

**Behavior:**
- With hysteresis > 0, prevents rapid toggling near threshold
- Rising: triggers when value > (threshold + hysteresis)
- Falling: triggers when value < (threshold - hysteresis)

---

#### In Range

Check if a value is within a specified range.

**Category:** Logic

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `Value` | float | 0.0 | Input value |
| `Min` | float | 0.0 | Range minimum |
| `Max` | float | 100.0 | Range maximum |

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `In Range` | bool | True if min <= value <= max |
| `Out of Range` | bool | True if value outside range |

---

## Interface Nodes

### Input Nodes

#### Button

A clickable button that triggers execution when pressed.

**Category:** Interface

**Inputs:** None

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Pressed` | Exec | Triggers when button clicked |

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | str | "Button" | Button label text |

**Note:** Always visible in Runner mode.

---

#### Toggle Switch

An on/off toggle switch.

**Category:** Interface

**Inputs:** None

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `State` | bool | Current switch state |
| `Changed` | Exec | Triggers when toggled |

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | str | "Switch" | Switch label text |

---

#### Slider

A slider for continuous value input.

**Category:** Interface

**Inputs:** None

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Value` | float | Current slider value |
| `Changed` | Exec | Triggers when value changes |

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | str | "Slider" | Slider label text |
| `min_value` | float | 0.0 | Minimum value |
| `max_value` | float | 100.0 | Maximum value |
| `step` | float | 1.0 | Value step increment |

---

#### Numeric Input

A numeric input field with optional virtual keypad.

**Category:** Interface

**Inputs:** None

**Outputs:**
| Port | Type | Description |
|------|------|-------------|
| `Value` | float | Current input value |
| `Submitted` | Exec | Triggers on Enter/submit |

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | str | "Input" | Input label text |
| `min_value` | float | None | Optional minimum |
| `max_value` | float | None | Optional maximum |
| `decimal_places` | int | 2 | Decimal precision |

---

### Display Nodes

#### Label

Display a value as formatted text.

**Category:** Interface

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `Value` | any | - | Value to display |
| `Format` | str | "{}" | Python format string |

**Outputs:** None

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | str | "Value" | Label text |

**Example:**
```
Format examples:
  "{:.2f}" - Two decimal places
  "{:.0f}%" - Percentage without decimals
  "Temp: {}C" - With prefix/suffix
```

---

#### Gauge

Display a value as a gauge/meter widget.

**Category:** Interface

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `Value` | float | 0.0 | Current value |
| `Min` | float | 0.0 | Gauge minimum |
| `Max` | float | 100.0 | Gauge maximum |

**Outputs:** None

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | str | "Value" | Gauge label |
| `unit` | str | "" | Unit suffix (e.g., "%" or "C") |
| `warning_threshold` | float | None | Yellow zone threshold |
| `danger_threshold` | float | None | Red zone threshold |

---

#### Chart

Display a real-time chart/graph of values over time.

**Category:** Interface

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `Value` | float | 0.0 | Value to plot |

**Outputs:** None

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | str | "Chart" | Chart title |
| `max_points` | int | 100 | Maximum data points |
| `y_min` | float | None | Fixed Y-axis minimum |
| `y_max` | float | None | Fixed Y-axis maximum |

**Behavior:**
- Automatically scrolls as new data arrives
- Call `clear_data()` to reset the chart

---

#### LED Indicator

Display an on/off LED indicator.

**Category:** Interface

**Inputs:**
| Port | Type | Default | Description |
|------|------|---------|-------------|
| `State` | bool | False | LED state |

**Outputs:** None

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | str | "LED" | Indicator label |
| `on_color` | str | "#00ff00" | Color when on (green) |
| `off_color` | str | "#333333" | Color when off (dark gray) |

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
