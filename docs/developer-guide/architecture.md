# Architecture

This document provides an in-depth look at GLIDER's architecture for developers extending or modifying the system.

## Overview

GLIDER is a modular experimental orchestration platform built with:

- **Python 3.9+** for the core logic
- **PyQt6** for the graphical interface
- **asyncio** for non-blocking hardware operations
- **qasync** for Qt/asyncio integration

## System Architecture

```mermaid
graph TB
    subgraph GUI["GUI Layer"]
        MW[MainWindow]
        VM[ViewManager]
        NG[NodeGraphView]
        DB[Dashboard]
    end

    subgraph Core["Core Layer"]
        GC[GliderCore]
        ES[ExperimentSession]
        FE[FlowEngine]
        HM[HardwareManager]
        DR[DataRecorder]
    end

    subgraph HAL["Hardware Abstraction Layer"]
        BB[BaseBoard]
        BD[BaseDevice]
        PM[PinManager]
        TB[TelemetrixBoard]
        PB[PiGPIOBoard]
    end

    subgraph Plugins["Plugin System"]
        PLM[PluginManager]
        DRV[Custom Drivers]
        DEV[Custom Devices]
        NOD[Custom Nodes]
    end

    MW --> GC
    VM --> MW
    NG --> MW
    DB --> MW

    GC --> ES
    GC --> FE
    GC --> HM
    GC --> DR

    HM --> BB
    HM --> BD
    HM --> PM
    BB --> TB
    BB --> PB

    PLM --> DRV
    PLM --> DEV
    PLM --> NOD
    GC --> PLM
```

## Project Structure

```
glider/
├── src/glider/
│   ├── __init__.py          # Package initialization
│   ├── __main__.py          # CLI entry point
│   ├── core/                # Core orchestration
│   │   ├── glider_core.py   # Main orchestrator
│   │   ├── experiment_session.py  # Session model
│   │   ├── flow_engine.py   # Flow execution
│   │   ├── hardware_manager.py    # Hardware lifecycle
│   │   └── data_recorder.py # Data logging
│   ├── gui/                 # User interface
│   │   ├── main_window.py   # Primary window
│   │   ├── view_manager.py  # Mode detection
│   │   ├── node_graph/      # Visual editor
│   │   └── runner/          # Touch dashboard
│   ├── hal/                 # Hardware abstraction
│   │   ├── base_board.py    # Board interface
│   │   ├── base_device.py   # Device interface
│   │   ├── pin_manager.py   # Pin allocation
│   │   └── boards/          # Board implementations
│   ├── nodes/               # Node system
│   │   ├── base_node.py     # Base node class
│   │   ├── experiment_nodes.py   # Flow control
│   │   ├── hardware/        # Hardware nodes
│   │   ├── logic/           # Logic nodes
│   │   └── interface/       # UI nodes
│   ├── plugins/             # Plugin system
│   │   └── plugin_manager.py
│   └── serialization/       # Save/load
│       ├── schema.py        # Data schemas
│       └── serializer.py    # File operations
├── docs/                    # Documentation
├── tests/                   # Test suite
└── pyproject.toml          # Package config
```

## Core Components

### GliderCore

The central orchestrator managing the entire system lifecycle.

```mermaid
stateDiagram-v2
    [*] --> Created: __init__()
    Created --> Initialized: initialize()
    Initialized --> Ready: setup_hardware()
    Ready --> Running: start_experiment()
    Running --> Paused: pause()
    Paused --> Running: resume()
    Running --> Ready: stop()
    Running --> Ready: flow completes
    Ready --> Shutdown: shutdown()
    Shutdown --> [*]
```

**Responsibilities:**
- Event loop initialization
- Plugin loading and management
- Session lifecycle coordination
- Hardware connection management
- Error handling and callbacks

**Key Methods:**
```python
async def initialize(self) -> None
async def setup_hardware(self) -> None
async def start_experiment(self) -> None
async def stop_experiment(self) -> None
async def pause() -> None
async def resume() -> None
async def emergency_stop() -> None
async def shutdown() -> None
```

### ExperimentSession

The data model representing complete experiment state.

```mermaid
classDiagram
    class ExperimentSession {
        +SessionMetadata metadata
        +HardwareConfig hardware
        +FlowConfig flow
        +DashboardConfig dashboard
        +SessionState state
        +bool is_dirty
        +save(path)
        +load(path)
        +to_dict()
        +from_dict()
    }

    class HardwareConfig {
        +List~BoardConfig~ boards
        +List~DeviceConfig~ devices
    }

    class FlowConfig {
        +List~NodeConfig~ nodes
        +List~ConnectionConfig~ connections
    }

    ExperimentSession *-- HardwareConfig
    ExperimentSession *-- FlowConfig
```

**State Machine:**
```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> INITIALIZING: setup
    INITIALIZING --> READY: connected
    INITIALIZING --> ERROR: failed
    READY --> RUNNING: start
    RUNNING --> PAUSED: pause
    PAUSED --> RUNNING: resume
    RUNNING --> STOPPING: stop
    PAUSED --> STOPPING: stop
    STOPPING --> IDLE: complete
    ERROR --> IDLE: reset
```

### FlowEngine

Executes the visual flow graph with support for both data flow (reactive) and execution flow (imperative).

```mermaid
graph LR
    subgraph "Execution Flow"
        S[Start] -->|exec| A[Action] -->|exec| E[End]
    end

    subgraph "Data Flow"
        I[Input] -->|value| P[Process] -->|result| O[Output]
    end
```

**Execution Model:**
1. **Execution Flow**: White connections control when nodes run
2. **Data Flow**: Colored connections pass values between nodes
3. **Hybrid**: A node can have both exec and data ports

### HardwareManager

Manages the lifecycle of hardware boards and devices.

```mermaid
sequenceDiagram
    participant C as Core
    participant HM as HardwareManager
    participant B as Board
    participant D as Device

    C->>HM: create_board(config)
    HM->>B: __init__(port)
    C->>HM: connect_board(id)
    HM->>B: connect()
    B-->>HM: connected
    C->>HM: create_device(config)
    HM->>D: __init__(board, pins)
    C->>HM: initialize_device(id)
    HM->>D: initialize()
    D->>B: set_pin_mode()
    D-->>HM: ready
```

## Hardware Abstraction Layer

### Board Hierarchy

```mermaid
classDiagram
    class BaseBoard {
        <<abstract>>
        +str id
        +str name
        +BoardConnectionState state
        +BoardCapabilities capabilities
        +connect()* bool
        +disconnect()*
        +set_pin_mode(pin, mode, type)*
        +write_digital(pin, value)*
        +read_digital(pin)* bool
        +write_analog(pin, value)*
        +read_analog(pin)* int
    }

    class TelemetrixBoard {
        +telemetrix_aio instance
        +connect()
        +write_digital()
        +read_analog()
    }

    class PiGPIOBoard {
        +gpiozero devices
        +connect()
        +write_digital()
    }

    BaseBoard <|-- TelemetrixBoard
    BaseBoard <|-- PiGPIOBoard
```

### Device Hierarchy

```mermaid
classDiagram
    class BaseDevice {
        <<abstract>>
        +str id
        +str device_type
        +BaseBoard board
        +DeviceConfig config
        +initialize()*
        +shutdown()*
        +execute_action(name, args)*
    }

    class DigitalOutputDevice {
        +bool state
        +on()
        +off()
        +toggle()
    }

    class DigitalInputDevice {
        +bool last_value
        +read() bool
        +on_change(callback)
    }

    class AnalogInputDevice {
        +int last_value
        +read() int
    }

    BaseDevice <|-- DigitalOutputDevice
    BaseDevice <|-- DigitalInputDevice
    BaseDevice <|-- AnalogInputDevice
```

## Node System

### Node Categories

| Category | Color | Purpose |
|----------|-------|---------|
| Hardware | Green | Device interaction |
| Logic | Blue | Data processing |
| Interface | Orange | User interaction |
| Script | Purple | Custom code |
| Experiment | White | Flow control |

### Node Structure

```mermaid
classDiagram
    class GliderNode {
        +str id
        +str name
        +NodeCategory category
        +List~Port~ inputs
        +List~Port~ outputs
        +execute()
        +update_event()
        +bind_device(device)
        +get_input(index)
        +set_output(index, value)
    }

    class Port {
        +str name
        +PortType type
        +DataType data_type
        +value
    }

    class HardwareNode {
        +BaseDevice device
        +hardware_operation()
    }

    class LogicNode {
        +process()
    }

    GliderNode *-- Port
    GliderNode <|-- HardwareNode
    GliderNode <|-- LogicNode
```

## Data Flow

### Experiment Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant MW as MainWindow
    participant GC as GliderCore
    participant HM as HardwareManager
    participant FE as FlowEngine
    participant DR as DataRecorder

    U->>MW: Click "Run"
    MW->>GC: start_experiment()
    GC->>HM: connect_all()
    HM-->>GC: connected
    GC->>HM: initialize_all_devices()
    HM-->>GC: devices ready
    GC->>DR: start()
    GC->>FE: start()
    FE->>FE: execute Start node
    loop Flow Execution
        FE->>FE: execute next node
        FE->>DR: log state
    end
    FE->>FE: execute End node
    FE-->>GC: flow complete
    GC->>DR: stop()
    GC->>HM: shutdown_all_devices()
    GC-->>MW: experiment complete
```

### File Serialization

```mermaid
graph LR
    subgraph "Save"
        ES[ExperimentSession] --> SER[Serializer]
        SER --> SCH[ExperimentSchema]
        SCH --> JSON[.glider file]
    end

    subgraph "Load"
        JSON2[.glider file] --> SCH2[ExperimentSchema]
        SCH2 --> VAL[Validate/Migrate]
        VAL --> SER2[Serializer]
        SER2 --> ES2[ExperimentSession]
    end
```

## Design Patterns

### State Machines

All major components use state machines for lifecycle management:

- **SessionState**: Experiment lifecycle
- **FlowState**: Flow engine status
- **BoardConnectionState**: Hardware connection

### Registry Pattern

Components are registered and discovered dynamically:

```python
# Node registration
FlowEngine.register_node("DigitalWrite", DigitalWriteNode)

# Driver registration
HardwareManager.register_driver("arduino", TelemetrixBoard)

# Device registration
DEVICE_REGISTRY["DigitalOutput"] = DigitalOutputDevice
```

### Observer/Callback Pattern

All components support callbacks for state changes:

```python
core.on_state_change(lambda state: print(f"State: {state}"))
core.on_error(lambda src, err: log.error(f"{src}: {err}"))
board.register_state_callback(handle_connection_change)
```

### Async/Await Pattern

All I/O operations are non-blocking:

```python
async def connect_hardware(self):
    for board in self.boards.values():
        await board.connect()  # Non-blocking
    for device in self.devices.values():
        await device.initialize()  # Non-blocking
```

## Extension Points

GLIDER is designed for extensibility at multiple levels:

| Extension | Base Class | Registration |
|-----------|------------|--------------|
| Board Drivers | `BaseBoard` | `HardwareManager.register_driver()` |
| Device Types | `BaseDevice` | `DEVICE_REGISTRY[name] = class` |
| Node Types | `GliderNode` | `FlowEngine.register_node()` |
| Plugins | N/A | Entry points or plugin directory |

## Threading Model

GLIDER uses a single-threaded async model:

1. **Main Thread**: Qt event loop + asyncio via qasync
2. **Hardware I/O**: Async operations (no blocking)
3. **Task Tracking**: All async tasks tracked for cleanup

```python
# Task tracking example
self._pending_tasks.add(task)
task.add_done_callback(self._pending_tasks.discard)
```

## See Also

- [Plugin Development](plugin-development.md) - Create plugins
- [Custom Nodes](custom-nodes.md) - Build nodes
- [Custom Drivers](custom-drivers.md) - Hardware drivers
- [API Reference](../api-reference/core.md) - Complete API
