"""
Tests for glider.core.config module.

Tests configuration dataclasses and their serialization.
"""

import json
from pathlib import Path

from glider.core.config import (
    GliderConfig,
    HardwareConfig,
    PathConfig,
    TimingConfig,
    UIConfig,
)


class TestTimingConfig:
    """Tests for TimingConfig dataclass."""

    def test_default_values(self):
        """Test TimingConfig default values."""
        config = TimingConfig()
        assert config.default_sample_interval == 0.1
        assert config.min_sample_interval == 0.001
        assert config.flow_tick_rate == 60
        assert config.hardware_poll_interval == 0.01

    def test_custom_values(self):
        """Test TimingConfig with custom values."""
        config = TimingConfig(
            default_sample_interval=0.5,
            min_sample_interval=0.01,
            flow_tick_rate=30,
            hardware_poll_interval=0.05
        )
        assert config.default_sample_interval == 0.5
        assert config.min_sample_interval == 0.01
        assert config.flow_tick_rate == 30
        assert config.hardware_poll_interval == 0.05

    def test_to_dict(self):
        """Test TimingConfig serialization to dict."""
        config = TimingConfig()
        data = config.to_dict()

        assert isinstance(data, dict)
        assert "default_sample_interval" in data
        assert "min_sample_interval" in data
        assert "flow_tick_rate" in data
        assert "hardware_poll_interval" in data

    def test_from_dict(self):
        """Test TimingConfig deserialization from dict."""
        data = {
            "default_sample_interval": 0.2,
            "min_sample_interval": 0.005,
            "flow_tick_rate": 120,
            "hardware_poll_interval": 0.02
        }
        config = TimingConfig.from_dict(data)

        assert config.default_sample_interval == 0.2
        assert config.min_sample_interval == 0.005
        assert config.flow_tick_rate == 120
        assert config.hardware_poll_interval == 0.02

    def test_from_dict_with_missing_keys(self):
        """Test TimingConfig from_dict uses defaults for missing keys."""
        data = {"default_sample_interval": 0.5}
        config = TimingConfig.from_dict(data)

        assert config.default_sample_interval == 0.5
        # Other values should be defaults
        assert config.flow_tick_rate == 60

    def test_roundtrip(self):
        """Test TimingConfig serialization roundtrip."""
        original = TimingConfig(
            default_sample_interval=0.25,
            flow_tick_rate=90
        )
        restored = TimingConfig.from_dict(original.to_dict())

        assert original.default_sample_interval == restored.default_sample_interval
        assert original.flow_tick_rate == restored.flow_tick_rate


class TestUIConfig:
    """Tests for UIConfig dataclass."""

    def test_default_values(self):
        """Test UIConfig default values."""
        config = UIConfig()
        assert config.theme == "dark"
        assert config.show_grid is True
        assert config.grid_size == 20
        assert config.snap_to_grid is True

    def test_to_dict(self):
        """Test UIConfig serialization."""
        config = UIConfig(theme="light", show_grid=False)
        data = config.to_dict()

        assert data["theme"] == "light"
        assert data["show_grid"] is False

    def test_from_dict(self):
        """Test UIConfig deserialization."""
        data = {
            "theme": "light",
            "show_grid": False,
            "grid_size": 25,
            "snap_to_grid": False
        }
        config = UIConfig.from_dict(data)

        assert config.theme == "light"
        assert config.show_grid is False
        assert config.grid_size == 25
        assert config.snap_to_grid is False


class TestHardwareConfig:
    """Tests for HardwareConfig dataclass."""

    def test_default_values(self):
        """Test HardwareConfig default values."""
        config = HardwareConfig()
        assert config.auto_connect is False
        assert config.connection_timeout == 5.0
        assert config.retry_attempts == 3

    def test_to_dict(self):
        """Test HardwareConfig serialization."""
        config = HardwareConfig(
            auto_connect=True,
            connection_timeout=10.0
        )
        data = config.to_dict()

        assert data["auto_connect"] is True
        assert data["connection_timeout"] == 10.0

    def test_from_dict(self):
        """Test HardwareConfig deserialization."""
        data = {
            "auto_connect": True,
            "connection_timeout": 15.0,
            "retry_attempts": 5
        }
        config = HardwareConfig.from_dict(data)

        assert config.auto_connect is True
        assert config.connection_timeout == 15.0
        assert config.retry_attempts == 5


class TestPathConfig:
    """Tests for PathConfig dataclass."""

    def test_default_values(self):
        """Test PathConfig default values are Path objects."""
        config = PathConfig()
        assert isinstance(config.data_dir, Path)
        assert isinstance(config.experiments_dir, Path)
        assert isinstance(config.plugins_dir, Path)

    def test_to_dict_converts_to_strings(self):
        """Test PathConfig serialization converts Paths to strings."""
        config = PathConfig(
            data_dir=Path("/custom/data"),
            experiments_dir=Path("/custom/experiments")
        )
        data = config.to_dict()

        assert isinstance(data["data_dir"], str)
        assert data["data_dir"] == "/custom/data"

    def test_from_dict_converts_to_paths(self):
        """Test PathConfig deserialization converts strings to Paths."""
        data = {
            "data_dir": "/test/data",
            "experiments_dir": "/test/experiments",
            "plugins_dir": "/test/plugins"
        }
        config = PathConfig.from_dict(data)

        assert isinstance(config.data_dir, Path)
        assert str(config.data_dir) == "/test/data"


class TestGliderConfig:
    """Tests for GliderConfig main configuration class."""

    def test_default_values(self):
        """Test GliderConfig default values."""
        config = GliderConfig()

        assert isinstance(config.timing, TimingConfig)
        assert isinstance(config.ui, UIConfig)
        assert isinstance(config.hardware, HardwareConfig)
        assert isinstance(config.paths, PathConfig)

    def test_to_dict(self):
        """Test GliderConfig serialization."""
        config = GliderConfig()
        data = config.to_dict()

        assert "timing" in data
        assert "ui" in data
        assert "hardware" in data
        assert "paths" in data
        assert isinstance(data["timing"], dict)

    def test_from_dict(self):
        """Test GliderConfig deserialization."""
        data = {
            "timing": {"default_sample_interval": 0.5},
            "ui": {"theme": "light"},
            "hardware": {"auto_connect": True},
            "paths": {"data_dir": "/custom/path"}
        }
        config = GliderConfig.from_dict(data)

        assert config.timing.default_sample_interval == 0.5
        assert config.ui.theme == "light"
        assert config.hardware.auto_connect is True

    def test_from_dict_with_missing_sections(self):
        """Test GliderConfig from_dict handles missing sections."""
        data = {"timing": {"flow_tick_rate": 30}}
        config = GliderConfig.from_dict(data)

        assert config.timing.flow_tick_rate == 30
        # Other sections should use defaults
        assert config.ui.theme == "dark"

    def test_save_and_load(self, temp_dir):
        """Test GliderConfig save and load to/from file."""
        config = GliderConfig()
        config.timing.default_sample_interval = 0.25
        config.ui.theme = "light"

        file_path = temp_dir / "config.json"
        config.save(file_path)

        assert file_path.exists()

        loaded = GliderConfig.load(file_path)
        assert loaded.timing.default_sample_interval == 0.25
        assert loaded.ui.theme == "light"

    def test_load_nonexistent_file(self, temp_dir):
        """Test GliderConfig load returns defaults for nonexistent file."""
        file_path = temp_dir / "nonexistent.json"
        config = GliderConfig.load(file_path)

        # Should return default config
        assert config.timing.default_sample_interval == 0.1
        assert config.ui.theme == "dark"

    def test_save_creates_parent_directories(self, temp_dir):
        """Test that save creates parent directories if needed."""
        file_path = temp_dir / "nested" / "dir" / "config.json"
        config = GliderConfig()
        config.save(file_path)

        assert file_path.exists()

    def test_roundtrip_preserves_all_values(self, temp_dir):
        """Test complete roundtrip preserves all configuration values."""
        original = GliderConfig()
        original.timing.default_sample_interval = 0.3
        original.timing.flow_tick_rate = 45
        original.ui.theme = "light"
        original.ui.grid_size = 30
        original.hardware.auto_connect = True
        original.hardware.connection_timeout = 20.0

        file_path = temp_dir / "roundtrip.json"
        original.save(file_path)
        loaded = GliderConfig.load(file_path)

        assert loaded.timing.default_sample_interval == original.timing.default_sample_interval
        assert loaded.timing.flow_tick_rate == original.timing.flow_tick_rate
        assert loaded.ui.theme == original.ui.theme
        assert loaded.ui.grid_size == original.ui.grid_size
        assert loaded.hardware.auto_connect == original.hardware.auto_connect
        assert loaded.hardware.connection_timeout == original.hardware.connection_timeout

    def test_json_format(self, temp_dir):
        """Test that saved config is valid JSON."""
        config = GliderConfig()
        file_path = temp_dir / "config.json"
        config.save(file_path)

        # Should be valid JSON
        content = file_path.read_text()
        parsed = json.loads(content)

        assert isinstance(parsed, dict)
        assert "timing" in parsed
