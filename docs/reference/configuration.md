# Configuration Reference

This document covers all configuration options available in GLIDER.

## Configuration File

GLIDER stores settings in `~/.glider/config.json`:

```json
{
  "general": {
    "last_file": "/path/to/experiment.glider",
    "recent_files": [],
    "check_updates": true
  },
  "appearance": {
    "theme": "dark",
    "font_size": 12,
    "grid_size": 20
  },
  "hardware": {
    "auto_detect": true,
    "auto_connect": false,
    "reconnect_timeout": 5000
  },
  "recording": {
    "enabled": true,
    "directory": "~/glider_data",
    "sample_interval": 100,
    "format": "csv"
  },
  "plugins": {
    "enabled": true,
    "directory": "~/.glider/plugins"
  }
}
```

## General Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `last_file` | string | null | Last opened experiment file |
| `recent_files` | array | [] | List of recently opened files |
| `recent_files_max` | int | 10 | Maximum recent files to remember |
| `check_updates` | bool | true | Check for updates on startup |
| `confirm_exit` | bool | true | Confirm before closing with unsaved changes |

## Appearance Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `theme` | string | "dark" | Color theme ("dark", "light") |
| `font_family` | string | "system" | Font family name |
| `font_size` | int | 12 | Base font size (pt) |
| `grid_size` | int | 20 | Node graph grid size (px) |
| `grid_visible` | bool | true | Show grid in node graph |
| `snap_to_grid` | bool | true | Snap nodes to grid |
| `zoom_level` | float | 1.0 | Default zoom level |
| `minimap_visible` | bool | true | Show minimap in node graph |
| `animation_enabled` | bool | true | Enable UI animations |

## Hardware Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `auto_detect` | bool | true | Auto-detect hardware on startup |
| `auto_connect` | bool | false | Auto-connect to detected hardware |
| `reconnect_timeout` | int | 5000 | Reconnection timeout (ms) |
| `reconnect_attempts` | int | 3 | Maximum reconnection attempts |
| `default_board_type` | string | "arduino" | Default board type for new boards |

### Arduino Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `arduino.baud_rate` | int | 115200 | Serial baud rate |
| `arduino.timeout` | float | 1.0 | Serial timeout (seconds) |
| `arduino.firmware_check` | bool | true | Check Telemetrix firmware on connect |

### Raspberry Pi Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `raspberry_pi.gpio_mode` | string | "BCM" | GPIO pin numbering mode |
| `raspberry_pi.pwm_frequency` | int | 1000 | Default PWM frequency (Hz) |

## Recording Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable automatic recording |
| `directory` | string | "~/glider_data" | Recording output directory |
| `sample_interval` | int | 100 | Sample interval (ms) |
| `format` | string | "csv" | Output format ("csv", "json") |
| `include_metadata` | bool | true | Include metadata header |
| `timestamp_format` | string | "iso" | Timestamp format ("iso", "unix") |
| `retention_days` | int | 0 | Auto-delete after days (0 = never) |
| `max_size_gb` | float | 0 | Max total size in GB (0 = unlimited) |

## Plugin Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable plugin loading |
| `directory` | string | "~/.glider/plugins" | Plugin directory |
| `auto_install_deps` | bool | false | Auto-install plugin dependencies |
| `disabled_plugins` | array | [] | List of disabled plugin names |

## Editor Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `undo_limit` | int | 100 | Maximum undo history size |
| `auto_save` | bool | false | Enable auto-save |
| `auto_save_interval` | int | 300 | Auto-save interval (seconds) |
| `confirm_delete` | bool | true | Confirm before deleting nodes |
| `connection_style` | string | "curved" | Connection line style ("curved", "straight", "step") |
| `connection_thickness` | int | 2 | Connection line thickness (px) |

## Runner Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `default_layout` | string | "vertical" | Default dashboard layout |
| `widget_spacing` | int | 10 | Spacing between widgets (px) |
| `touch_mode` | bool | false | Enable touch-friendly controls |
| `button_size` | string | "normal" | Button size ("small", "normal", "large") |

## Keyboard Shortcuts

Customize shortcuts in the config file:

```json
{
  "shortcuts": {
    "new_file": "Ctrl+N",
    "open_file": "Ctrl+O",
    "save_file": "Ctrl+S",
    "save_as": "Ctrl+Shift+S",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Y",
    "copy": "Ctrl+C",
    "paste": "Ctrl+V",
    "delete": "Delete",
    "select_all": "Ctrl+A",
    "run_experiment": "F5",
    "stop_experiment": "Shift+F5",
    "toggle_mode": "F6",
    "zoom_in": "Ctrl++",
    "zoom_out": "Ctrl+-",
    "zoom_fit": "Ctrl+0",
    "toggle_fullscreen": "F11"
  }
}
```

## Environment Variables

Override settings with environment variables:

| Variable | Setting | Example |
|----------|---------|---------|
| `GLIDER_DATA_DIR` | recording.directory | `/data/glider` |
| `GLIDER_PLUGIN_DIR` | plugins.directory | `/opt/glider/plugins` |
| `GLIDER_CONFIG_FILE` | Config file path | `/etc/glider.json` |
| `GLIDER_LOG_LEVEL` | Logging level | `DEBUG` |
| `GLIDER_THEME` | appearance.theme | `light` |

## Command Line Overrides

Override settings via command line:

```bash
# Override data directory
python -m glider --data-dir /custom/path

# Override log level
python -m glider --log-level DEBUG

# Override theme
python -m glider --theme light
```

## Platform-Specific Paths

### Windows

```
Config: %APPDATA%\glider\config.json
Data: %USERPROFILE%\glider_data
Plugins: %APPDATA%\glider\plugins
```

### macOS

```
Config: ~/Library/Application Support/glider/config.json
Data: ~/glider_data
Plugins: ~/Library/Application Support/glider/plugins
```

### Linux

```
Config: ~/.config/glider/config.json
Data: ~/glider_data
Plugins: ~/.local/share/glider/plugins
```

## Accessing Settings Programmatically

```python
from glider.core.config import get_config, save_config

# Get current configuration
config = get_config()

# Read a setting
theme = config.get("appearance", {}).get("theme", "dark")

# Modify settings
config["appearance"]["theme"] = "light"
save_config(config)
```

## Resetting to Defaults

Delete the config file to reset all settings:

```bash
# Windows
del %APPDATA%\glider\config.json

# macOS/Linux
rm ~/.glider/config.json
```

Or use the GUI: **Tools → Settings → Reset to Defaults**

## See Also

- [CLI Reference](cli.md) - Command-line options
- [Keyboard Shortcuts](../user-guide/builder-mode.md#keyboard-shortcuts) - Default shortcuts
- [Plugin Development](../developer-guide/plugin-development.md) - Plugin configuration
