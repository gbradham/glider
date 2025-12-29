# Command Line Interface Reference

GLIDER provides a command-line interface for running experiments without the GUI.

## Basic Usage

```bash
# Launch the GUI
python -m glider

# Run experiment from file
python -m glider --file experiment.glider --run

# Headless mode (no GUI)
python -m glider --file experiment.glider --run --headless
```

## Commands

### Launch GUI

```bash
python -m glider
```

Opens the GLIDER graphical interface in Builder mode.

**Options:**
```bash
python -m glider [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--file PATH` | Open experiment file on startup |
| `--mode {builder,runner}` | Start in specific mode |
| `--fullscreen` | Start in fullscreen mode |

### Run Experiment

```bash
python -m glider --file experiment.glider --run
```

Run an experiment from a `.glider` file.

**Options:**
| Option | Description |
|--------|-------------|
| `--file PATH` | Path to `.glider` file (required) |
| `--run` | Execute the experiment |
| `--headless` | Run without GUI |
| `--timeout SECONDS` | Maximum runtime (0 = unlimited) |
| `--output-dir PATH` | Directory for data output |

### Hardware Detection

```bash
python -m glider --detect-hardware
```

Detect available hardware (Arduino, Raspberry Pi).

**Output:**
```
Detected Hardware:
  Arduino Uno on COM3
  Arduino Mega on COM4
  Raspberry Pi GPIO available
```

### Version Information

```bash
python -m glider --version
```

Display GLIDER version.

### Help

```bash
python -m glider --help
```

Show help message with all options.

## Complete Options Reference

```
usage: glider [-h] [--version] [--file PATH] [--run] [--headless]
              [--mode {builder,runner}] [--fullscreen]
              [--timeout SECONDS] [--output-dir PATH]
              [--data-dir PATH] [--log-level LEVEL]
              [--detect-hardware] [--list-plugins]
              [--install-plugin-deps PLUGIN]

GLIDER - Visual Flow Programming for Laboratory Hardware

optional arguments:
  -h, --help            Show this help message and exit
  --version             Show version and exit
  --file PATH           Path to experiment file (.glider)
  --run                 Run the experiment immediately
  --headless            Run without GUI
  --mode {builder,runner}
                        Start in specific mode
  --fullscreen          Start in fullscreen mode
  --timeout SECONDS     Maximum runtime in seconds (0 = unlimited)
  --output-dir PATH     Directory for output files
  --data-dir PATH       Directory for recorded data
  --log-level LEVEL     Logging level (DEBUG, INFO, WARNING, ERROR)
  --detect-hardware     Detect available hardware and exit
  --list-plugins        List available plugins and exit
  --install-plugin-deps PLUGIN
                        Install dependencies for a plugin
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GLIDER_DATA_DIR` | Data recording directory | `~/glider_data` |
| `GLIDER_PLUGIN_DIR` | Plugin directory | `~/.glider/plugins` |
| `GLIDER_CONFIG_FILE` | Configuration file | `~/.glider/config.json` |
| `GLIDER_LOG_LEVEL` | Default log level | `INFO` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | File not found |
| 3 | Hardware connection failed |
| 4 | Experiment error |
| 5 | Timeout reached |

## Examples

### Run a Simple Experiment

```bash
python -m glider --file blink.glider --run
```

### Headless Experiment with Data Recording

```bash
python -m glider \
    --file temperature_log.glider \
    --run \
    --headless \
    --output-dir /data/experiments \
    --timeout 3600
```

### Debug Mode

```bash
python -m glider --file experiment.glider --log-level DEBUG
```

### List Available Plugins

```bash
python -m glider --list-plugins
```

**Output:**
```
Available Plugins:
  temperature_sensor v1.0.0 (loaded)
  stepper_motor v2.1.0 (loaded)
  custom_display v0.5.0 (not loaded)
```

### Install Plugin Dependencies

```bash
python -m glider --install-plugin-deps temperature_sensor
```

## Scripting

### Batch Processing

```bash
#!/bin/bash
# Run multiple experiments

for exp in experiments/*.glider; do
    echo "Running: $exp"
    python -m glider --file "$exp" --run --headless --timeout 60
done
```

### Python Integration

```python
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "glider", "--file", "exp.glider", "--run", "--headless"],
    capture_output=True,
    text=True
)

print(f"Exit code: {result.returncode}")
print(f"Output: {result.stdout}")
```

## See Also

- [Configuration](configuration.md) - Configuration options
- [Running Experiments](../user-guide/running-experiments.md) - GUI execution
- [Data Recording](../user-guide/data-recording.md) - Output handling
