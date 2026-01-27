"""
Tests for glider.vision.calibration module.

Tests camera calibration and pixel-to-real-world conversion.
"""

import math

from glider.vision.calibration import (
    CalibrationLine,
    CameraCalibration,
    LengthUnit,
)


class TestLengthUnit:
    """Tests for LengthUnit enum."""

    def test_unit_values(self):
        """Test LengthUnit enum values."""
        assert LengthUnit.MM.value == "mm"
        assert LengthUnit.CM.value == "cm"
        assert LengthUnit.M.value == "m"
        assert LengthUnit.IN.value == "in"
        assert LengthUnit.FT.value == "ft"

    def test_all_units_exist(self):
        """Test that all expected units exist."""
        units = [LengthUnit.MM, LengthUnit.CM, LengthUnit.M, LengthUnit.IN, LengthUnit.FT]
        assert len(units) == 5


class TestCalibrationLine:
    """Tests for CalibrationLine dataclass."""

    def test_creation(self):
        """Test CalibrationLine creation."""
        line = CalibrationLine(
            start_x=0.1,
            start_y=0.5,
            end_x=0.9,
            end_y=0.5,
            length=100.0,
            unit=LengthUnit.MM
        )

        assert line.start_x == 0.1
        assert line.start_y == 0.5
        assert line.end_x == 0.9
        assert line.end_y == 0.5
        assert line.length == 100.0
        assert line.unit == LengthUnit.MM

    def test_default_color(self):
        """Test CalibrationLine default color."""
        line = CalibrationLine(
            start_x=0.0, start_y=0.0, end_x=1.0, end_y=1.0,
            length=100.0, unit=LengthUnit.MM
        )

        assert line.color == (0, 255, 0)  # Default green

    def test_custom_color(self):
        """Test CalibrationLine with custom color."""
        line = CalibrationLine(
            start_x=0.0, start_y=0.0, end_x=1.0, end_y=1.0,
            length=100.0, unit=LengthUnit.MM,
            color=(255, 0, 0)  # Red
        )

        assert line.color == (255, 0, 0)

    def test_get_pixel_coords(self):
        """Test converting normalized coords to pixel coords."""
        line = CalibrationLine(
            start_x=0.1, start_y=0.2,
            end_x=0.9, end_y=0.8,
            length=100.0, unit=LengthUnit.MM
        )

        # For a 640x480 frame
        x1, y1, x2, y2 = line.get_pixel_coords(640, 480)

        assert x1 == int(0.1 * 640)  # 64
        assert y1 == int(0.2 * 480)  # 96
        assert x2 == int(0.9 * 640)  # 576
        assert y2 == int(0.8 * 480)  # 384

    def test_get_pixel_length(self):
        """Test calculating pixel length of line."""
        line = CalibrationLine(
            start_x=0.0, start_y=0.0,
            end_x=1.0, end_y=0.0,  # Horizontal line
            length=100.0, unit=LengthUnit.MM
        )

        pixel_length = line.get_pixel_length(640, 480)
        assert pixel_length == 640  # Full width

    def test_get_pixel_length_diagonal(self):
        """Test calculating pixel length of diagonal line."""
        line = CalibrationLine(
            start_x=0.0, start_y=0.0,
            end_x=1.0, end_y=1.0,  # Diagonal
            length=100.0, unit=LengthUnit.MM
        )

        pixel_length = line.get_pixel_length(640, 480)
        expected = math.sqrt(640**2 + 480**2)
        assert abs(pixel_length - expected) < 0.01

    def test_to_dict(self):
        """Test CalibrationLine serialization."""
        line = CalibrationLine(
            start_x=0.1, start_y=0.2,
            end_x=0.9, end_y=0.8,
            length=150.0, unit=LengthUnit.CM,
            color=(255, 128, 0)
        )

        data = line.to_dict()

        assert data["start_x"] == 0.1
        assert data["start_y"] == 0.2
        assert data["end_x"] == 0.9
        assert data["end_y"] == 0.8
        assert data["length"] == 150.0
        assert data["unit"] == "cm"
        assert data["color"] == [255, 128, 0]

    def test_from_dict(self):
        """Test CalibrationLine deserialization."""
        data = {
            "start_x": 0.25,
            "start_y": 0.25,
            "end_x": 0.75,
            "end_y": 0.75,
            "length": 50.0,
            "unit": "in",
            "color": [0, 0, 255]
        }

        line = CalibrationLine.from_dict(data)

        assert line.start_x == 0.25
        assert line.end_x == 0.75
        assert line.length == 50.0
        assert line.unit == LengthUnit.IN
        assert line.color == (0, 0, 255)

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = CalibrationLine(
            start_x=0.33, start_y=0.44,
            end_x=0.55, end_y=0.66,
            length=77.7, unit=LengthUnit.FT,
            color=(100, 150, 200)
        )

        restored = CalibrationLine.from_dict(original.to_dict())

        assert restored.start_x == original.start_x
        assert restored.start_y == original.start_y
        assert restored.end_x == original.end_x
        assert restored.end_y == original.end_y
        assert restored.length == original.length
        assert restored.unit == original.unit
        assert restored.color == original.color


class TestCameraCalibration:
    """Tests for CameraCalibration class."""

    def test_creation(self):
        """Test CameraCalibration creation."""
        calibration = CameraCalibration()

        assert calibration.lines == []
        assert calibration.pixels_per_unit is None

    def test_add_line(self):
        """Test adding a calibration line."""
        calibration = CameraCalibration()
        line = CalibrationLine(
            start_x=0.0, start_y=0.5,
            end_x=1.0, end_y=0.5,
            length=100.0, unit=LengthUnit.MM
        )

        calibration.add_line(line)

        assert len(calibration.lines) == 1
        assert calibration.lines[0] == line

    def test_remove_line(self):
        """Test removing a calibration line."""
        calibration = CameraCalibration()
        line = CalibrationLine(
            start_x=0.0, start_y=0.5,
            end_x=1.0, end_y=0.5,
            length=100.0, unit=LengthUnit.MM
        )

        calibration.add_line(line)
        calibration.remove_line(0)

        assert len(calibration.lines) == 0

    def test_clear(self):
        """Test clearing all calibration lines."""
        calibration = CameraCalibration()

        for i in range(3):
            calibration.add_line(CalibrationLine(
                start_x=0.0, start_y=0.1 * i,
                end_x=1.0, end_y=0.1 * i,
                length=100.0, unit=LengthUnit.MM
            ))

        assert len(calibration.lines) == 3

        calibration.clear()

        assert len(calibration.lines) == 0

    def test_calculate_pixels_per_unit(self):
        """Test calculating pixels per unit from calibration line."""
        calibration = CameraCalibration()

        # Horizontal line spanning full width
        line = CalibrationLine(
            start_x=0.0, start_y=0.5,
            end_x=1.0, end_y=0.5,
            length=100.0, unit=LengthUnit.MM
        )
        calibration.add_line(line)

        # Calculate for 640 pixel width
        ppu = calibration.calculate_pixels_per_unit(640, 480)

        # 640 pixels / 100 mm = 6.4 pixels per mm
        assert abs(ppu - 6.4) < 0.01

    def test_pixels_to_real_world(self):
        """Test converting pixel distance to real-world units."""
        calibration = CameraCalibration()

        # Set up calibration: 640 pixels = 100mm
        line = CalibrationLine(
            start_x=0.0, start_y=0.5,
            end_x=1.0, end_y=0.5,
            length=100.0, unit=LengthUnit.MM
        )
        calibration.add_line(line)
        calibration.calculate_pixels_per_unit(640, 480)

        # 64 pixels should be 10mm
        distance = calibration.pixels_to_real_world(64)
        assert abs(distance - 10.0) < 0.1

    def test_real_world_to_pixels(self):
        """Test converting real-world distance to pixels."""
        calibration = CameraCalibration()

        line = CalibrationLine(
            start_x=0.0, start_y=0.5,
            end_x=1.0, end_y=0.5,
            length=100.0, unit=LengthUnit.MM
        )
        calibration.add_line(line)
        calibration.calculate_pixels_per_unit(640, 480)

        # 10mm should be 64 pixels
        pixels = calibration.real_world_to_pixels(10.0)
        assert abs(pixels - 64) < 1

    def test_to_dict(self):
        """Test CameraCalibration serialization."""
        calibration = CameraCalibration()
        calibration.add_line(CalibrationLine(
            start_x=0.0, start_y=0.5,
            end_x=1.0, end_y=0.5,
            length=100.0, unit=LengthUnit.MM
        ))
        calibration.calculate_pixels_per_unit(640, 480)

        data = calibration.to_dict()

        assert "lines" in data
        assert len(data["lines"]) == 1
        assert "pixels_per_unit" in data

    def test_from_dict(self):
        """Test CameraCalibration deserialization."""
        data = {
            "lines": [
                {
                    "start_x": 0.0, "start_y": 0.5,
                    "end_x": 1.0, "end_y": 0.5,
                    "length": 200.0, "unit": "cm",
                    "color": [0, 255, 0]
                }
            ],
            "pixels_per_unit": 3.2
        }

        calibration = CameraCalibration.from_dict(data)

        assert len(calibration.lines) == 1
        assert calibration.lines[0].length == 200.0
        assert calibration.lines[0].unit == LengthUnit.CM
        assert calibration.pixels_per_unit == 3.2

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = CameraCalibration()
        original.add_line(CalibrationLine(
            start_x=0.1, start_y=0.2,
            end_x=0.8, end_y=0.9,
            length=50.0, unit=LengthUnit.IN,
            color=(255, 0, 0)
        ))
        original.calculate_pixels_per_unit(1920, 1080)

        restored = CameraCalibration.from_dict(original.to_dict())

        assert len(restored.lines) == len(original.lines)
        assert restored.lines[0].length == original.lines[0].length
        assert restored.pixels_per_unit == original.pixels_per_unit

    def test_no_calibration_returns_none(self):
        """Test that conversion returns None when not calibrated."""
        calibration = CameraCalibration()

        # No lines added, no calibration calculated
        assert calibration.pixels_per_unit is None
        assert calibration.pixels_to_real_world(100) is None

    def test_multiple_lines_average(self):
        """Test that multiple calibration lines are averaged."""
        calibration = CameraCalibration()

        # Two lines with different calibrations
        calibration.add_line(CalibrationLine(
            start_x=0.0, start_y=0.25,
            end_x=0.5, end_y=0.25,  # Half width
            length=50.0, unit=LengthUnit.MM
        ))
        calibration.add_line(CalibrationLine(
            start_x=0.0, start_y=0.75,
            end_x=1.0, end_y=0.75,  # Full width
            length=100.0, unit=LengthUnit.MM
        ))

        ppu = calibration.calculate_pixels_per_unit(640, 480)

        # Both should give 6.4 pixels/mm (640/100 or 320/50)
        # Average should be 6.4
        assert abs(ppu - 6.4) < 0.01
