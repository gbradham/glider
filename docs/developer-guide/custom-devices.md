# Custom Devices

This guide covers creating custom device types to abstract hardware functionality in GLIDER.

## Overview

A device represents a logical hardware component (sensor, actuator, etc.) that uses one or more pins on a board. Devices provide high-level operations while the driver handles low-level communication.

## Built-in Device Types

| Device Type | Purpose | Pins |
|-------------|---------|------|
| `DigitalOutput` | On/off control (LEDs, relays) | 1 digital |
| `DigitalInput` | Binary sensing (buttons, switches) | 1 digital |
| `AnalogInput` | Voltage sensing (sensors) | 1 analog |
| `PWMOutput` | Variable output (motors, dimming) | 1 PWM |
| `Servo` | Angle control | 1 PWM |

## BaseDevice Interface

All devices implement the `BaseDevice` abstract class:

```python
from abc import abstractmethod
from typing import Dict, Any, Optional, List
from glider.hal.base_device import BaseDevice, DeviceConfig

class MyDevice(BaseDevice):
    """Custom device implementation."""

    # Class attributes
    device_type: str = "MyDevice"
    required_pins: List[str] = ["signal"]  # Named pin requirements

    @abstractmethod
    async def initialize(self) -> None:
        """Configure pins and prepare device."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Release resources and set safe state."""
        ...

    @abstractmethod
    async def execute_action(self, action: str, *args, **kwargs) -> Any:
        """Execute a named action."""
        ...
```

## Creating a Device

### Step 1: Define the Device Class

```python
import asyncio
import logging
from typing import Dict, Any, Optional, List

from glider.hal.base_device import BaseDevice, DeviceConfig
from glider.hal.base_board import BaseBoard, PinMode, PinType

logger = logging.getLogger(__name__)

class TemperatureSensor(BaseDevice):
    """DHT22 temperature and humidity sensor."""

    device_type = "TemperatureSensor"
    required_pins = ["data"]  # Single data pin

    def __init__(
        self,
        board: BaseBoard,
        config: DeviceConfig,
    ):
        super().__init__(board, config)
        self._last_temperature: float = 0.0
        self._last_humidity: float = 0.0
        self._last_read_time: float = 0.0

    async def initialize(self) -> None:
        """Configure the sensor pin."""
        data_pin = self.config.pins.get("data")
        if data_pin is None:
            raise ValueError("TemperatureSensor requires 'data' pin")

        # Configure pin for digital input
        await self.board.set_pin_mode(
            data_pin,
            PinMode.INPUT,
            PinType.DIGITAL
        )

        self._initialized = True
        logger.info(f"TemperatureSensor initialized on pin {data_pin}")

    async def shutdown(self) -> None:
        """Release sensor resources."""
        self._initialized = False
        logger.info("TemperatureSensor shutdown")

    async def execute_action(self, action: str, *args, **kwargs) -> Any:
        """Execute sensor actions."""
        if action == "read_temperature":
            return await self.read_temperature()
        elif action == "read_humidity":
            return await self.read_humidity()
        elif action == "read_all":
            return await self.read_all()
        else:
            raise ValueError(f"Unknown action: {action}")

    async def read_temperature(self) -> float:
        """Read temperature in Celsius."""
        await self._update_readings()
        return self._last_temperature

    async def read_humidity(self) -> float:
        """Read relative humidity percentage."""
        await self._update_readings()
        return self._last_humidity

    async def read_all(self) -> Dict[str, float]:
        """Read both temperature and humidity."""
        await self._update_readings()
        return {
            "temperature": self._last_temperature,
            "humidity": self._last_humidity,
        }

    async def _update_readings(self) -> None:
        """Update sensor readings (with debounce)."""
        current_time = asyncio.get_event_loop().time()

        # DHT22 needs 2 seconds between reads
        if current_time - self._last_read_time < 2.0:
            return

        data_pin = self.config.pins["data"]

        # Read raw data from sensor
        # (Implementation depends on protocol)
        raw_data = await self._read_dht22(data_pin)

        if raw_data:
            self._last_humidity = raw_data[0]
            self._last_temperature = raw_data[1]
            self._last_read_time = current_time

    async def _read_dht22(self, pin: int) -> Optional[tuple]:
        """Read DHT22 protocol (simplified)."""
        # Real implementation would handle the 1-wire protocol
        # This is a placeholder
        return (50.0, 25.0)  # humidity, temperature
```

### Step 2: Multi-Pin Devices

Devices that use multiple pins:

```python
class StepperMotor(BaseDevice):
    """4-wire stepper motor driver."""

    device_type = "StepperMotor"
    required_pins = ["step", "direction", "enable", "ms1"]

    def __init__(self, board: BaseBoard, config: DeviceConfig):
        super().__init__(board, config)
        self._position: int = 0
        self._enabled: bool = False

    async def initialize(self) -> None:
        """Configure all stepper pins as outputs."""
        for pin_name in self.required_pins:
            pin = self.config.pins.get(pin_name)
            if pin is None:
                raise ValueError(f"StepperMotor requires '{pin_name}' pin")

            await self.board.set_pin_mode(pin, PinMode.OUTPUT, PinType.DIGITAL)
            await self.board.write_digital(pin, False)

        self._initialized = True

    async def shutdown(self) -> None:
        """Disable motor and release pins."""
        await self.disable()
        self._initialized = False

    async def execute_action(self, action: str, *args, **kwargs) -> Any:
        """Execute motor actions."""
        actions = {
            "enable": self.enable,
            "disable": self.disable,
            "step": lambda: self.step(kwargs.get("direction", 1)),
            "move": lambda: self.move(kwargs.get("steps", 0)),
            "set_position": lambda: self.set_position(kwargs.get("position", 0)),
        }

        if action in actions:
            return await actions[action]()
        raise ValueError(f"Unknown action: {action}")

    async def enable(self) -> None:
        """Enable the motor driver."""
        enable_pin = self.config.pins["enable"]
        await self.board.write_digital(enable_pin, True)
        self._enabled = True

    async def disable(self) -> None:
        """Disable the motor driver."""
        enable_pin = self.config.pins["enable"]
        await self.board.write_digital(enable_pin, False)
        self._enabled = False

    async def step(self, direction: int = 1) -> None:
        """Execute a single step."""
        if not self._enabled:
            await self.enable()

        dir_pin = self.config.pins["direction"]
        step_pin = self.config.pins["step"]

        # Set direction
        await self.board.write_digital(dir_pin, direction > 0)

        # Pulse step pin
        await self.board.write_digital(step_pin, True)
        await asyncio.sleep(0.001)  # 1ms pulse
        await self.board.write_digital(step_pin, False)

        # Update position
        self._position += 1 if direction > 0 else -1

    async def move(self, steps: int) -> None:
        """Move specified number of steps."""
        direction = 1 if steps > 0 else -1
        for _ in range(abs(steps)):
            await self.step(direction)
            await asyncio.sleep(0.001)  # Step delay

    async def set_position(self, position: int) -> None:
        """Move to absolute position."""
        delta = position - self._position
        await self.move(delta)

    @property
    def position(self) -> int:
        """Current position in steps."""
        return self._position
```

## Device Configuration

### DeviceConfig Structure

```python
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class DeviceConfig:
    """Configuration for a device instance."""

    id: str                          # Unique identifier
    device_type: str                 # Device class name
    name: str                        # Human-readable name
    board_id: str                    # Parent board ID
    pins: Dict[str, int]             # Pin assignments
    settings: Dict[str, Any] = None  # Device-specific settings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_type": self.device_type,
            "name": self.name,
            "board_id": self.board_id,
            "pins": self.pins,
            "settings": self.settings or {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceConfig":
        return cls(
            id=data["id"],
            device_type=data["device_type"],
            name=data["name"],
            board_id=data["board_id"],
            pins=data["pins"],
            settings=data.get("settings", {}),
        )
```

### Device-Specific Settings

```python
class ConfigurableSensor(BaseDevice):
    """Sensor with configurable settings."""

    device_type = "ConfigurableSensor"
    required_pins = ["signal"]

    # Default settings
    DEFAULT_SETTINGS = {
        "sample_rate": 10,      # Hz
        "averaging": 1,         # Number of samples to average
        "calibration_offset": 0.0,
        "calibration_scale": 1.0,
    }

    def __init__(self, board: BaseBoard, config: DeviceConfig):
        super().__init__(board, config)

        # Merge defaults with provided settings
        self.settings = {**self.DEFAULT_SETTINGS, **(config.settings or {})}

    async def read(self) -> float:
        """Read calibrated value."""
        pin = self.config.pins["signal"]
        samples = []

        # Collect samples for averaging
        for _ in range(self.settings["averaging"]):
            raw = await self.board.read_analog(pin)
            samples.append(raw)
            await asyncio.sleep(1.0 / self.settings["sample_rate"])

        # Average and calibrate
        avg = sum(samples) / len(samples)
        calibrated = (avg * self.settings["calibration_scale"]
                     + self.settings["calibration_offset"])

        return calibrated
```

## Callback Support

### Value Change Callbacks

```python
from typing import Callable, List

class CallbackDevice(BaseDevice):
    """Device with value change callbacks."""

    def __init__(self, board: BaseBoard, config: DeviceConfig):
        super().__init__(board, config)
        self._callbacks: List[Callable[[Any], None]] = []
        self._last_value: Any = None

    def register_callback(self, callback: Callable[[Any], None]) -> None:
        """Register a callback for value changes."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[Any], None]) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, value: Any) -> None:
        """Notify all callbacks of a value change."""
        if value != self._last_value:
            self._last_value = value
            for callback in self._callbacks:
                try:
                    callback(value)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
```

### Event-Based Input

```python
class ButtonDevice(BaseDevice):
    """Button with press/release events."""

    device_type = "Button"
    required_pins = ["signal"]

    def __init__(self, board: BaseBoard, config: DeviceConfig):
        super().__init__(board, config)
        self._pressed = False
        self._on_press: List[Callable[[], None]] = []
        self._on_release: List[Callable[[], None]] = []

    async def initialize(self) -> None:
        pin = self.config.pins["signal"]

        # Configure with pull-up
        await self.board.set_pin_mode(pin, PinMode.INPUT_PULLUP, PinType.DIGITAL)

        # Register for pin change notifications if board supports it
        if hasattr(self.board, 'register_pin_callback'):
            self.board.register_pin_callback(pin, self._on_pin_change)

        self._initialized = True

    def on_press(self, callback: Callable[[], None]) -> None:
        """Register press callback."""
        self._on_press.append(callback)

    def on_release(self, callback: Callable[[], None]) -> None:
        """Register release callback."""
        self._on_release.append(callback)

    def _on_pin_change(self, pin: int, value: bool) -> None:
        """Handle pin state change."""
        # Invert for pull-up (pressed = LOW)
        pressed = not value

        if pressed and not self._pressed:
            self._pressed = True
            for cb in self._on_press:
                cb()
        elif not pressed and self._pressed:
            self._pressed = False
            for cb in self._on_release:
                cb()

    @property
    def is_pressed(self) -> bool:
        return self._pressed
```

## Composite Devices

Devices that combine multiple components:

```python
class RGBLed(BaseDevice):
    """RGB LED with color control."""

    device_type = "RGBLed"
    required_pins = ["red", "green", "blue"]

    def __init__(self, board: BaseBoard, config: DeviceConfig):
        super().__init__(board, config)
        self._color = (0, 0, 0)

    async def initialize(self) -> None:
        """Configure all color pins as PWM outputs."""
        for color in ["red", "green", "blue"]:
            pin = self.config.pins[color]
            await self.board.set_pin_mode(pin, PinMode.OUTPUT, PinType.PWM)
            await self.board.write_analog(pin, 0)

        self._initialized = True

    async def shutdown(self) -> None:
        """Turn off LED."""
        await self.set_color(0, 0, 0)
        self._initialized = False

    async def execute_action(self, action: str, *args, **kwargs) -> Any:
        if action == "set_color":
            r = kwargs.get("red", 0)
            g = kwargs.get("green", 0)
            b = kwargs.get("blue", 0)
            await self.set_color(r, g, b)
        elif action == "off":
            await self.set_color(0, 0, 0)
        elif action == "get_color":
            return self._color
        else:
            raise ValueError(f"Unknown action: {action}")

    async def set_color(self, red: int, green: int, blue: int) -> None:
        """Set RGB color (0-255 each)."""
        self._color = (red, green, blue)

        await self.board.write_analog(self.config.pins["red"], red)
        await self.board.write_analog(self.config.pins["green"], green)
        await self.board.write_analog(self.config.pins["blue"], blue)

    async def set_hex(self, hex_color: str) -> None:
        """Set color from hex string (#RRGGBB)."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        await self.set_color(r, g, b)

    @property
    def color(self) -> tuple:
        return self._color
```

## Serialization

Support saving and loading device state:

```python
class StatefulDevice(BaseDevice):
    """Device that persists state."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize device for saving."""
        return {
            "id": self._id,
            "device_type": self.device_type,
            "config": self.config.to_dict(),
            "state": self.get_state(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], board: BaseBoard) -> "StatefulDevice":
        """Deserialize device."""
        config = DeviceConfig.from_dict(data["config"])
        instance = cls(board, config)
        instance._id = data.get("id", instance._id)
        if "state" in data:
            instance.set_state(data["state"])
        return instance

    def get_state(self) -> Dict[str, Any]:
        """Get current device state."""
        return {
            "initialized": self._initialized,
            # Add device-specific state
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        """Restore device state."""
        # Restore device-specific state
        pass
```

## Registration

Register devices for use in GLIDER:

```python
# In plugin __init__.py
from glider.hal.base_device import DEVICE_REGISTRY

# Automatic registration
DEVICE_TYPES = {
    "TemperatureSensor": TemperatureSensor,
    "StepperMotor": StepperMotor,
    "RGBLed": RGBLed,
}

# Or manual registration
def setup():
    DEVICE_REGISTRY["TemperatureSensor"] = TemperatureSensor
    DEVICE_REGISTRY["StepperMotor"] = StepperMotor
    DEVICE_REGISTRY["RGBLed"] = RGBLed
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_board():
    board = MagicMock()
    board.set_pin_mode = AsyncMock()
    board.write_digital = AsyncMock()
    board.write_analog = AsyncMock()
    board.read_analog = AsyncMock(return_value=512)
    return board

@pytest.fixture
def device_config():
    return DeviceConfig(
        id="test_device",
        device_type="TemperatureSensor",
        name="Test Sensor",
        board_id="board_1",
        pins={"data": 2},
    )

@pytest.mark.asyncio
async def test_device_initialize(mock_board, device_config):
    device = TemperatureSensor(mock_board, device_config)

    await device.initialize()

    assert device._initialized
    mock_board.set_pin_mode.assert_called_once()

@pytest.mark.asyncio
async def test_device_read(mock_board, device_config):
    device = TemperatureSensor(mock_board, device_config)
    await device.initialize()

    temp = await device.read_temperature()

    assert isinstance(temp, float)
```

### Integration Tests

```python
@pytest.mark.hardware
@pytest.mark.asyncio
async def test_real_device():
    """Test with real hardware."""
    from glider.hal.boards.telemetrix_board import TelemetrixBoard

    board = TelemetrixBoard(port="COM3")
    try:
        await board.connect()

        config = DeviceConfig(
            id="temp_1",
            device_type="TemperatureSensor",
            name="Room Temp",
            board_id=board._id,
            pins={"data": 4},
        )

        device = TemperatureSensor(board, config)
        await device.initialize()

        temp = await device.read_temperature()
        assert 0 < temp < 50  # Reasonable room temperature

    finally:
        await board.disconnect()
```

## Best Practices

1. **Pin Validation**: Always validate required pins in `initialize()`
2. **Safe Shutdown**: Implement `shutdown()` to leave hardware in safe state
3. **Error Handling**: Catch and report errors without crashing
4. **Async I/O**: Use `async/await` for all hardware operations
5. **State Tracking**: Keep track of device state for debugging
6. **Documentation**: Document actions and their parameters
7. **Debouncing**: Implement appropriate delays for physical sensors

## Example: Complete Sensor Device

```python
"""Ultrasonic distance sensor for GLIDER."""

import asyncio
import logging
from typing import Dict, Any, Optional

from glider.hal.base_device import BaseDevice, DeviceConfig
from glider.hal.base_board import BaseBoard, PinMode, PinType

logger = logging.getLogger(__name__)

class UltrasonicSensor(BaseDevice):
    """HC-SR04 ultrasonic distance sensor."""

    device_type = "UltrasonicSensor"
    required_pins = ["trigger", "echo"]

    # Speed of sound in cm/us
    SPEED_OF_SOUND = 0.0343

    def __init__(self, board: BaseBoard, config: DeviceConfig):
        super().__init__(board, config)
        self._last_distance: float = 0.0
        self._max_distance: float = config.settings.get("max_distance", 400.0)
        self._timeout: float = (self._max_distance * 2) / (self.SPEED_OF_SOUND * 1000000)

    async def initialize(self) -> None:
        """Configure trigger and echo pins."""
        trigger_pin = self.config.pins.get("trigger")
        echo_pin = self.config.pins.get("echo")

        if trigger_pin is None or echo_pin is None:
            raise ValueError("UltrasonicSensor requires 'trigger' and 'echo' pins")

        # Trigger is output, echo is input
        await self.board.set_pin_mode(trigger_pin, PinMode.OUTPUT, PinType.DIGITAL)
        await self.board.set_pin_mode(echo_pin, PinMode.INPUT, PinType.DIGITAL)

        # Ensure trigger starts low
        await self.board.write_digital(trigger_pin, False)

        self._initialized = True
        logger.info(f"UltrasonicSensor initialized (trigger={trigger_pin}, echo={echo_pin})")

    async def shutdown(self) -> None:
        """Release sensor resources."""
        self._initialized = False
        logger.info("UltrasonicSensor shutdown")

    async def execute_action(self, action: str, *args, **kwargs) -> Any:
        """Execute sensor actions."""
        if action == "read" or action == "measure":
            return await self.read_distance()
        elif action == "get_last":
            return self._last_distance
        else:
            raise ValueError(f"Unknown action: {action}")

    async def read_distance(self) -> float:
        """Measure distance in centimeters."""
        if not self._initialized:
            raise RuntimeError("Sensor not initialized")

        trigger_pin = self.config.pins["trigger"]
        echo_pin = self.config.pins["echo"]

        # Send 10us trigger pulse
        await self.board.write_digital(trigger_pin, True)
        await asyncio.sleep(0.00001)  # 10 microseconds
        await self.board.write_digital(trigger_pin, False)

        # Measure echo pulse duration
        # Note: Actual implementation depends on board capabilities
        # This is simplified; real implementation needs precise timing

        start_time = asyncio.get_event_loop().time()
        timeout_time = start_time + self._timeout

        # Wait for echo to go high
        while not await self.board.read_digital(echo_pin):
            if asyncio.get_event_loop().time() > timeout_time:
                return self._max_distance

        pulse_start = asyncio.get_event_loop().time()

        # Wait for echo to go low
        while await self.board.read_digital(echo_pin):
            if asyncio.get_event_loop().time() > timeout_time:
                return self._max_distance

        pulse_end = asyncio.get_event_loop().time()

        # Calculate distance
        pulse_duration = pulse_end - pulse_start
        distance = (pulse_duration * 1000000 * self.SPEED_OF_SOUND) / 2

        # Clamp to valid range
        distance = min(distance, self._max_distance)
        distance = max(distance, 0.0)

        self._last_distance = distance
        return distance

    @property
    def last_distance(self) -> float:
        """Last measured distance."""
        return self._last_distance

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for saving."""
        return {
            "id": self._id,
            "device_type": self.device_type,
            "config": self.config.to_dict(),
        }
```

## See Also

- [Custom Drivers](custom-drivers.md) - Board driver development
- [Custom Nodes](custom-nodes.md) - Build nodes that use devices
- [Plugin Development](plugin-development.md) - Package as plugin
- [API Reference: Hardware](../api-reference/hardware.md) - Complete API
