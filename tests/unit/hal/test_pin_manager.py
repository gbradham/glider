"""
Tests for glider.hal.pin_manager module.

Tests pin allocation, conflict detection, and validation.
"""

import pytest

from glider.hal.base_board import PinType
from glider.hal.pin_manager import InvalidPinError, PinConflictError, PinManager


class TestPinManager:
    """Tests for PinManager class."""

    @pytest.fixture
    def pin_manager(self):
        """Provide a fresh PinManager instance."""
        return PinManager()

    def test_init(self, pin_manager):
        """Test PinManager initialization."""
        assert len(pin_manager.allocated_pins) == 0

    def test_allocate_pin(self, pin_manager):
        """Test allocating a pin."""
        pin_manager.allocate(pin=13, device_id="led_1", pin_type=PinType.DIGITAL)

        assert 13 in pin_manager.allocated_pins
        assert pin_manager.allocated_pins[13] == "led_1"

    def test_allocate_multiple_pins(self, pin_manager):
        """Test allocating multiple pins."""
        pin_manager.allocate(pin=13, device_id="led_1", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=12, device_id="led_2", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=11, device_id="led_3", pin_type=PinType.DIGITAL)

        assert len(pin_manager.allocated_pins) == 3
        assert pin_manager.allocated_pins[13] == "led_1"
        assert pin_manager.allocated_pins[12] == "led_2"
        assert pin_manager.allocated_pins[11] == "led_3"

    def test_allocate_duplicate_raises_conflict(self, pin_manager):
        """Test that allocating an already-allocated pin raises PinConflictError."""
        pin_manager.allocate(pin=13, device_id="led_1", pin_type=PinType.DIGITAL)

        with pytest.raises(PinConflictError) as exc_info:
            pin_manager.allocate(pin=13, device_id="led_2", pin_type=PinType.DIGITAL)

        assert "13" in str(exc_info.value)
        assert "led_1" in str(exc_info.value)

    def test_deallocate_pin(self, pin_manager):
        """Test deallocating a pin."""
        pin_manager.allocate(pin=13, device_id="led_1", pin_type=PinType.DIGITAL)
        assert 13 in pin_manager.allocated_pins

        pin_manager.deallocate(pin=13)
        assert 13 not in pin_manager.allocated_pins

    def test_deallocate_nonexistent_pin(self, pin_manager):
        """Test deallocating a pin that isn't allocated (should not raise)."""
        # Should not raise
        pin_manager.deallocate(pin=99)

    def test_is_pin_available(self, pin_manager):
        """Test checking pin availability."""
        assert pin_manager.is_pin_available(13) is True

        pin_manager.allocate(pin=13, device_id="led_1", pin_type=PinType.DIGITAL)
        assert pin_manager.is_pin_available(13) is False

        pin_manager.deallocate(13)
        assert pin_manager.is_pin_available(13) is True

    def test_get_device_for_pin(self, pin_manager):
        """Test getting the device ID for an allocated pin."""
        pin_manager.allocate(pin=13, device_id="led_1", pin_type=PinType.DIGITAL)

        assert pin_manager.get_device_for_pin(13) == "led_1"
        assert pin_manager.get_device_for_pin(12) is None

    def test_get_pins_for_device(self, pin_manager):
        """Test getting all pins allocated to a device."""
        pin_manager.allocate(pin=13, device_id="stepper_1", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=12, device_id="stepper_1", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=11, device_id="stepper_1", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=10, device_id="led_1", pin_type=PinType.DIGITAL)

        stepper_pins = pin_manager.get_pins_for_device("stepper_1")
        assert len(stepper_pins) == 3
        assert 13 in stepper_pins
        assert 12 in stepper_pins
        assert 11 in stepper_pins

        led_pins = pin_manager.get_pins_for_device("led_1")
        assert len(led_pins) == 1
        assert 10 in led_pins

    def test_deallocate_all_for_device(self, pin_manager):
        """Test deallocating all pins for a device."""
        pin_manager.allocate(pin=13, device_id="stepper_1", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=12, device_id="stepper_1", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=10, device_id="led_1", pin_type=PinType.DIGITAL)

        pin_manager.deallocate_all_for_device("stepper_1")

        assert 13 not in pin_manager.allocated_pins
        assert 12 not in pin_manager.allocated_pins
        assert 10 in pin_manager.allocated_pins  # led_1 should remain

    def test_clear_all(self, pin_manager):
        """Test clearing all pin allocations."""
        pin_manager.allocate(pin=13, device_id="led_1", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=12, device_id="led_2", pin_type=PinType.DIGITAL)

        pin_manager.clear_all()

        assert len(pin_manager.allocated_pins) == 0

    def test_validate_pin_type_digital(self, pin_manager):
        """Test validating digital pin type."""
        # Digital pins should accept digital type
        pin_manager.set_available_pins(
            digital=[0, 1, 2, 13],
            analog=[],
            pwm=[]
        )

        # Should not raise
        pin_manager.validate_pin_type(13, PinType.DIGITAL)

    def test_validate_pin_type_analog(self, pin_manager):
        """Test validating analog pin type."""
        pin_manager.set_available_pins(
            digital=[],
            analog=[0, 1, 2, 3, 4, 5],
            pwm=[]
        )

        # Should not raise
        pin_manager.validate_pin_type(0, PinType.ANALOG)

    def test_validate_pin_type_pwm(self, pin_manager):
        """Test validating PWM pin type."""
        pin_manager.set_available_pins(
            digital=[],
            analog=[],
            pwm=[3, 5, 6, 9, 10, 11]
        )

        # Should not raise
        pin_manager.validate_pin_type(9, PinType.PWM)

    def test_validate_invalid_pin_type_raises(self, pin_manager):
        """Test that validating an invalid pin type raises InvalidPinError."""
        pin_manager.set_available_pins(
            digital=[0, 1, 2, 13],
            analog=[],
            pwm=[]
        )

        with pytest.raises(InvalidPinError):
            pin_manager.validate_pin_type(13, PinType.ANALOG)

    def test_available_pins_property(self, pin_manager):
        """Test available_pins property."""
        pin_manager.set_available_pins(
            digital=[0, 1, 2, 13],
            analog=[0, 1, 2],
            pwm=[3, 5, 6]
        )

        # Allocate some pins
        pin_manager.allocate(pin=13, device_id="led_1", pin_type=PinType.DIGITAL)
        pin_manager.allocate(pin=0, device_id="sensor_1", pin_type=PinType.ANALOG)

        available = pin_manager.available_pins
        assert 13 not in available["digital"]
        assert 0 in available["digital"]  # Different namespace
        assert 0 not in available["analog"]


class TestPinConflictError:
    """Tests for PinConflictError exception."""

    def test_error_message(self):
        """Test PinConflictError message format."""
        error = PinConflictError(pin=13, existing_device="led_1")

        assert "13" in str(error)
        assert "led_1" in str(error)

    def test_error_attributes(self):
        """Test PinConflictError attributes."""
        error = PinConflictError(pin=13, existing_device="led_1")

        assert error.pin == 13
        assert error.existing_device == "led_1"


class TestInvalidPinError:
    """Tests for InvalidPinError exception."""

    def test_error_message(self):
        """Test InvalidPinError message format."""
        error = InvalidPinError(pin=99, reason="Pin not available")

        assert "99" in str(error)
        assert "not available" in str(error)

    def test_error_attributes(self):
        """Test InvalidPinError attributes."""
        error = InvalidPinError(pin=99, reason="Invalid")

        assert error.pin == 99
        assert error.reason == "Invalid"
