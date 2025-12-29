# Hardware API Reference

This document covers the Hardware Abstraction Layer (HAL) classes in GLIDER.

## HardwareManager

Manages the lifecycle of hardware boards and devices.

**Module:** `glider.core.hardware_manager`

### Overview

`HardwareManager` handles:
- Board driver registration and loading
- Connection management
- Device creation and initialization
- Pin allocation tracking
- Error recovery and reconnection

```python
from glider.core.hardware_manager import HardwareManager

manager = HardwareManager()
manager.add_board("arduino_1", "arduino", port="COM3")
await manager.connect_board("arduino_1")
```

### Class Methods

##### `register_driver(name: str, driver_class: Type[BaseBoard]) -> None`

Register a board driver globally.

```python
from glider.hal.base_board import BaseBoard

class MyBoard(BaseBoard):
    # Implementation
    pass

HardwareManager.register_driver("my_board", MyBoard)
```

##### `get_available_drivers() -> List[str]`

Get list of registered driver names.

```python
drivers = HardwareManager.get_available_drivers()
# ['arduino', 'raspberry_pi']
```

##### `get_driver_class(name: str) -> Optional[Type[BaseBoard]]`

Get a driver class by name.

```python
driver = HardwareManager.get_driver_class("arduino")
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `boards` | `Dict[str, BaseBoard]` | Active board instances |
| `devices` | `Dict[str, BaseDevice]` | Active device instances |

### Methods

#### Board Management

##### `add_board(board_id: str, driver_type: str, port: Optional[str] = None, **kwargs) -> None`

Add a board using simplified API.

```python
manager.add_board("arduino_1", "arduino", port="COM3")
manager.add_board("pi_1", "raspberry_pi")
```

**Parameters:**
- `board_id`: Unique identifier
- `driver_type`: Driver name ("arduino", "raspberry_pi")
- `port`: Serial port (for Arduino)
- `**kwargs`: Additional driver settings

##### `async create_board(config: BoardConfig) -> BaseBoard`

Create a board from configuration.

```python
from glider.core.experiment_session import BoardConfig

config = BoardConfig(
    id="arduino_1",
    driver_type="arduino",
    port="COM3",
    board_type="uno"
)
board = await manager.create_board(config)
```

##### `get_board(board_id: str) -> Optional[BaseBoard]`

Get a board by ID.

##### `async connect_board(board_id: str) -> bool`

Connect to a specific board.

```python
success = await manager.connect_board("arduino_1")
```

##### `async disconnect_board(board_id: str) -> None`

Disconnect from a board.

##### `async remove_board(board_id: str) -> None`

Remove a board and its devices.

##### `async connect_all() -> Dict[str, bool]`

Connect to all registered boards.

```python
results = await manager.connect_all()
# {'arduino_1': True, 'pi_1': False}
```

#### Device Management

##### `add_device(device_id: str, device_type: str, board_id: str, pin: int, name: Optional[str] = None, **kwargs) -> None`

Add a device using simplified API.

```python
manager.add_device("led_1", "DigitalOutput", "arduino_1", pin=13, name="Status LED")
manager.add_device("sensor_1", "AnalogInput", "arduino_1", pin=0)
```

##### `async create_device(config: DeviceConfig) -> BaseDevice`

Create a device from configuration.

```python
from glider.core.experiment_session import DeviceConfig

config = DeviceConfig(
    id="led_1",
    device_type="DigitalOutput",
    name="Status LED",
    board_id="arduino_1",
    pins={"output": 13}
)
device = await manager.create_device(config)
```

##### `get_device(device_id: str) -> Optional[BaseDevice]`

Get a device by ID.

##### `async initialize_device(device_id: str) -> None`

Initialize a device (configure pins).

##### `async shutdown_device(device_id: str) -> None`

Shutdown a device safely.

##### `async remove_device(device_id: str) -> None`

Remove a device.

##### `async initialize_all_devices() -> Dict[str, bool]`

Initialize all devices.

```python
results = await manager.initialize_all_devices()
# {'led_1': True, 'sensor_1': True}
```

#### Pin Management

##### `get_pin_manager(board_id: str) -> Optional[PinManager]`

Get the pin manager for a board.

```python
pm = manager.get_pin_manager("arduino_1")
available = pm.get_available_pins(PinType.DIGITAL)
```

#### Lifecycle

##### `async emergency_stop() -> None`

Emergency stop all hardware.

```python
await manager.emergency_stop()
```

##### `async disconnect_all() -> None`

Disconnect from all boards.

##### `async shutdown() -> None`

Shutdown the hardware manager.

##### `clear() -> None`

Clear all boards and devices.

#### Callbacks

##### `on_error(callback: Callable[[str, Exception], None]) -> None`

Register callback for hardware errors.

```python
def handle_error(source, error):
    print(f"Error from {source}: {error}")

manager.on_error(handle_error)
```

##### `on_connection_change(callback: Callable[[str, BoardConnectionState], None]) -> None`

Register callback for connection state changes.

### Exceptions

| Exception | Description |
|-----------|-------------|
| `HardwareError` | Base exception for hardware errors |
| `BoardNotFoundError` | Referenced board not found |
| `DeviceNotFoundError` | Referenced device not found |

---

## BaseBoard

Abstract base class for hardware board drivers.

**Module:** `glider.hal.base_board`

### Overview

`BaseBoard` defines the contract for all hardware drivers. Implementations must provide methods for pin I/O operations.

```python
from glider.hal.base_board import BaseBoard, BoardCapabilities

class MyBoard(BaseBoard):
    @property
    def name(self) -> str:
        return "My Board"

    @property
    def capabilities(self) -> BoardCapabilities:
        return BoardCapabilities(name=self.name)

    async def connect(self) -> bool:
        # Connection logic
        return True
```

### Constructor

```python
BaseBoard(port: Optional[str] = None, auto_reconnect: bool = False)
```

**Parameters:**
- `port`: Connection port (e.g., "COM3", "/dev/ttyUSB0")
- `auto_reconnect`: Enable automatic reconnection

### Abstract Properties (Must Override)

##### `name -> str`

Human-readable board name.

##### `capabilities -> BoardCapabilities`

Board capabilities map.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Unique board ID |
| `port` | `Optional[str]` | Connection port |
| `state` | `BoardConnectionState` | Current connection state |
| `is_connected` | `bool` | Whether connected |

### Abstract Methods (Must Override)

##### `async connect() -> bool`

Establish connection to the board.

##### `async disconnect() -> None`

Close the connection.

##### `async set_pin_mode(pin: int, mode: PinMode, pin_type: PinType = PinType.DIGITAL) -> None`

Configure a pin's mode.

##### `async write_digital(pin: int, value: bool) -> None`

Write a digital value.

##### `async read_digital(pin: int) -> bool`

Read a digital value.

##### `async write_analog(pin: int, value: int) -> None`

Write an analog (PWM) value.

##### `async read_analog(pin: int) -> int`

Read an analog value.

### Helper Methods

##### `async write_pin(pin: int, pin_type: PinType, value: Any) -> None`

Generic write that dispatches to specific methods.

##### `async read_pin(pin: int, pin_type: PinType) -> Any`

Generic read that dispatches to specific methods.

##### `async write_servo(pin: int, angle: int) -> None`

Write servo angle (override if supported).

##### `async emergency_stop() -> None`

Set all outputs to safe state.

### Callbacks

##### `register_callback(pin: int, callback: Callable[[int, Any], None]) -> None`

Register callback for pin value changes.

##### `register_error_callback(callback: Callable[[Exception], None]) -> None`

Register callback for errors.

##### `register_state_callback(callback: Callable[[BoardConnectionState], None]) -> None`

Register callback for state changes.

### Auto-Reconnection

##### `start_reconnect() -> None`

Start automatic reconnection process.

##### `stop_reconnect() -> None`

Stop automatic reconnection.

### Serialization

##### `to_dict() -> Dict[str, Any]`

Serialize board configuration.

##### `from_dict(data: Dict[str, Any]) -> BaseBoard` (classmethod)

Create board from configuration.

---

## BaseDevice

Abstract base class for hardware devices.

**Module:** `glider.hal.base_device`

### Overview

Devices represent logical hardware components attached to boards. They wrap pin operations into semantic actions.

```python
from glider.hal.base_device import BaseDevice, DeviceConfig

class MySensor(BaseDevice):
    @property
    def device_type(self) -> str:
        return "MySensor"

    @property
    def actions(self) -> Dict[str, Callable]:
        return {"read": self.read}

    async def initialize(self) -> None:
        await self.board.set_pin_mode(self.pins["signal"], PinMode.INPUT)
```

### Constructor

```python
BaseDevice(board: BaseBoard, config: DeviceConfig, name: Optional[str] = None)
```

**Parameters:**
- `board`: Parent board instance
- `config`: Device configuration (pins, settings)
- `name`: Human-readable name

### Abstract Properties (Must Override)

##### `device_type -> str`

Type identifier (e.g., "LED", "DHT22").

##### `actions -> Dict[str, Callable]`

Map of action names to methods.

```python
@property
def actions(self) -> Dict[str, Callable]:
    return {
        "on": self.turn_on,
        "off": self.turn_off,
        "toggle": self.toggle,
    }
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Unique device ID |
| `name` | `str` | Human-readable name |
| `board` | `BaseBoard` | Parent board |
| `config` | `DeviceConfig` | Configuration |
| `pins` | `Dict[str, int]` | Pin assignments |
| `is_initialized` | `bool` | Whether initialized |
| `is_enabled` | `bool` | Whether enabled |
| `required_pins` | `List[str]` | Required pin names |

### Abstract Methods (Must Override)

##### `async initialize() -> None`

Initialize the device (configure pins).

##### `async shutdown() -> None`

Shutdown device safely.

### Methods

##### `async execute_action(action_name: str, *args, **kwargs) -> Any`

Execute a named action.

```python
await device.execute_action("on")
await device.execute_action("set", value=True)
```

##### `async enable() -> None`

Enable the device.

##### `async disable() -> None`

Disable the device.

##### `validate_config() -> List[str]`

Validate configuration, return list of errors.

##### `to_dict() -> Dict[str, Any]`

Serialize device configuration.

---

## Built-in Device Types

### DigitalOutputDevice

Digital output (LED, relay).

**Actions:** `on`, `off`, `toggle`, `set`

```python
device = DigitalOutputDevice(board, DeviceConfig(pins={"output": 13}))
await device.turn_on()
await device.toggle()
```

**Properties:**
- `state: bool` - Current output state

### DigitalInputDevice

Digital input (button, switch).

**Actions:** `read`

```python
device = DigitalInputDevice(board, DeviceConfig(
    pins={"input": 2},
    settings={"pullup": True}
))
value = await device.read()
```

**Properties:**
- `last_value: Optional[bool]` - Last read value

**Methods:**
- `on_change(callback)` - Register value change callback

### AnalogInputDevice

Analog input (sensor).

**Actions:** `read`, `read_voltage`

```python
device = AnalogInputDevice(board, DeviceConfig(
    pins={"input": 0},
    settings={"reference_voltage": 5.0}
))
raw = await device.read()         # 0-1023
voltage = await device.read_voltage()  # 0.0-5.0
```

### PWMOutputDevice

PWM output (motor, LED brightness).

**Actions:** `set`, `set_percent`, `off`

```python
device = PWMOutputDevice(board, DeviceConfig(pins={"output": 9}))
await device.set_value(128)       # 0-255
await device.set_percent(50.0)    # 0-100%
```

**Properties:**
- `value: int` - Current PWM value

### ServoDevice

Servo motor.

**Actions:** `set_angle`, `center`

```python
device = ServoDevice(board, DeviceConfig(
    pins={"signal": 9},
    settings={"min_angle": 0, "max_angle": 180}
))
await device.set_angle(90)
await device.center()
```

**Properties:**
- `angle: int` - Current angle

---

## Enums

### PinType

```python
class PinType(Enum):
    DIGITAL = auto()
    ANALOG = auto()
    PWM = auto()
    I2C = auto()
    SPI = auto()
    SERVO = auto()
```

### PinMode

```python
class PinMode(Enum):
    INPUT = auto()
    OUTPUT = auto()
    INPUT_PULLUP = auto()
    INPUT_PULLDOWN = auto()
```

### BoardConnectionState

```python
class BoardConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()
    RECONNECTING = auto()
```

---

## Data Classes

### BoardCapabilities

```python
@dataclass
class BoardCapabilities:
    name: str
    pins: Dict[int, PinCapability] = {}
    supports_analog: bool = False
    analog_resolution: int = 10      # bits
    pwm_resolution: int = 8          # bits
    pwm_frequency: int = 490         # Hz
    i2c_buses: List[int] = []
    spi_buses: List[int] = []
```

### PinCapability

```python
@dataclass
class PinCapability:
    pin: int
    supported_types: Set[PinType] = set()
    max_value: int = 1
    description: str = ""
```

### DeviceConfig

```python
@dataclass
class DeviceConfig:
    pins: Dict[str, int] = {}        # Pin assignments
    settings: Dict[str, Any] = {}    # Device settings
```

---

## PinManager

Tracks pin allocation to prevent conflicts.

**Module:** `glider.hal.pin_manager`

### Overview

```python
from glider.hal.pin_manager import PinManager

pm = PinManager(board)
available = pm.get_available_pins(PinType.DIGITAL)
pm.allocate_pin(13, "led_1", PinType.DIGITAL)
```

### Methods

##### `allocate_pin(pin: int, device_id: str, pin_type: PinType) -> None`

Allocate a pin to a device.

**Raises:** `PinConflictError` if pin already allocated.

##### `release_pin(pin: int) -> None`

Release an allocated pin.

##### `allocate_device_pins(device: BaseDevice) -> None`

Allocate all pins for a device.

##### `release_device_pins(device_id: str) -> None`

Release all pins for a device.

##### `get_available_pins(pin_type: PinType) -> List[int]`

Get list of available pins of a type.

##### `is_pin_available(pin: int) -> bool`

Check if a pin is available.

##### `get_allocation(pin: int) -> Optional[str]`

Get device ID that owns a pin.

---

## Device Registry

Global registry for device types.

**Module:** `glider.hal.base_device`

```python
from glider.hal.base_device import DEVICE_REGISTRY, create_device_from_dict

# Built-in types
DEVICE_REGISTRY = {
    "DigitalOutput": DigitalOutputDevice,
    "DigitalInput": DigitalInputDevice,
    "AnalogInput": AnalogInputDevice,
    "PWMOutput": PWMOutputDevice,
    "Servo": ServoDevice,
}

# Add custom type
DEVICE_REGISTRY["MySensor"] = MySensorDevice

# Create from dictionary
device = create_device_from_dict(data, board)
```

---

## See Also

- [Core API](core.md) - GliderCore, HardwareManager integration
- [Flow API](flow.md) - FlowEngine, hardware nodes
- [Custom Drivers](../developer-guide/custom-drivers.md) - Driver development
- [Custom Devices](../developer-guide/custom-devices.md) - Device development
