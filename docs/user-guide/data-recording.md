# Data Recording

GLIDER automatically records experiment data to CSV files for analysis. This guide covers configuration and data handling.

## Overview

During experiment execution, GLIDER can record:

- Device states (inputs and outputs)
- Timestamps for each sample
- Custom values from nodes
- Metadata about the experiment
- **Video recordings** from connected cameras
- **Computer vision tracking data** (object positions, IDs, confidence scores)

## Enabling Recording

### Automatic Recording

Recording starts automatically when an experiment runs if enabled:

1. Go to **Tools → Settings → Recording**
2. Check **Enable automatic recording**
3. Set the recording directory
4. Configure sample interval

### Manual Recording

Control recording independently:

```python
# In a Script node
recorder.start("my_experiment")
# ... experiment runs ...
recorder.stop()
```

Or via the **Record** button in the toolbar.

## Configuration Options

### Recording Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Enable Recording** | On | Automatically record all experiments |
| **Directory** | `~/glider_data/` | Where to save CSV files |
| **Sample Interval** | 100ms | Time between samples |
| **Include Metadata** | On | Add experiment info to file |
| **Timestamp Format** | ISO 8601 | Date/time format |

Access via **Tools → Settings → Recording**.

### Sample Interval

Controls how often data is captured:

| Interval | Samples/sec | Best For |
|----------|-------------|----------|
| 10ms | 100 | Fast signals, motor control |
| 100ms | 10 | General purpose |
| 1000ms | 1 | Slow processes, long experiments |

> **Note:** Faster sampling increases file size and CPU usage.

## Output Format

### File Naming

Files are named automatically:
```
{experiment_name}_{timestamp}.csv
```

Example:
```
blink_experiment_2024-01-15_10-30-00.csv
```

### CSV Structure

```csv
timestamp,elapsed_ms,led_state,sensor_value,motor_speed
2024-01-15T10:30:00.000Z,0,0,512,0
2024-01-15T10:30:00.100Z,100,1,515,128
2024-01-15T10:30:00.200Z,200,1,510,128
2024-01-15T10:30:00.300Z,300,0,508,0
```

### Column Types

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | ISO 8601 | Absolute time |
| `elapsed_ms` | Integer | Milliseconds since start |
| `{device_id}` | Varies | Device state value |

### Data Types by Device

| Device Type | Value Format | Example |
|-------------|--------------|---------|
| Digital Output | 0 or 1 | 1 |
| Digital Input | 0 or 1 | 0 |
| Analog Input | 0-1023 | 512 |
| PWM Output | 0-255 | 128 |
| Servo | 0-180 | 90 |

## Metadata Header

When enabled, files include metadata:

```csv
# GLIDER Experiment Data
# Experiment: Blink Experiment
# Author: Lab User
# Date: 2024-01-15T10:30:00Z
# Duration: 60.5 seconds
# Sample Interval: 100ms
# Devices: led, sensor, motor
#
timestamp,elapsed_ms,led_state,sensor_value,motor_speed
...
```

## Recording Specific Data

### Recording Device States

All configured devices are recorded by default. To exclude a device:

1. Select the device in Hardware Panel
2. In Properties, uncheck **Include in Recording**

### Recording Node Outputs

Mark specific node outputs for recording:

1. Select the node
2. In Properties, check **Record Output**
3. Output appears as column in CSV

### Custom Data Points

Use a Script node to record custom values:

```python
# Calculate derived value
temperature_celsius = (inputs[0] - 500) / 10.0
recorder.log("temperature", temperature_celsius)
```

## Managing Data Files

### Storage Location

Default locations:
- **Windows**: `C:\Users\{user}\glider_data\`
- **macOS**: `~/glider_data/`
- **Linux**: `~/glider_data/`

Change in Settings or via:
```bash
glider --data-dir /path/to/data
```

### File Size Estimation

Approximate file sizes:

| Duration | Interval | Devices | Size |
|----------|----------|---------|------|
| 1 minute | 100ms | 5 | ~50 KB |
| 1 hour | 100ms | 5 | ~3 MB |
| 1 hour | 10ms | 10 | ~60 MB |
| 24 hours | 1000ms | 5 | ~7 MB |

### Automatic Cleanup

Configure retention policy:
- **Keep All**: Never delete
- **Days**: Delete after N days
- **Size**: Delete when total exceeds N GB

## Analyzing Data

### Python (Pandas)

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv('experiment_2024-01-15.csv', comment='#')

# Plot sensor values over time
plt.figure(figsize=(10, 6))
plt.plot(df['elapsed_ms'] / 1000, df['sensor_value'])
plt.xlabel('Time (seconds)')
plt.ylabel('Sensor Value')
plt.title('Sensor Reading Over Time')
plt.show()

# Calculate statistics
print(f"Mean: {df['sensor_value'].mean():.2f}")
print(f"Std:  {df['sensor_value'].std():.2f}")
print(f"Min:  {df['sensor_value'].min()}")
print(f"Max:  {df['sensor_value'].max()}")
```

### Excel / Spreadsheet

1. Open the CSV file directly
2. Skip header rows (lines starting with #)
3. Use built-in charting and statistics

### R

```r
library(ggplot2)

# Load data
data <- read.csv('experiment_2024-01-15.csv', comment.char='#')

# Plot
ggplot(data, aes(x=elapsed_ms/1000, y=sensor_value)) +
  geom_line() +
  labs(x="Time (seconds)", y="Sensor Value", title="Sensor Data")
```

### MATLAB

```matlab
% Load data
data = readtable('experiment_2024-01-15.csv', 'CommentStyle', '#');

% Plot
plot(data.elapsed_ms / 1000, data.sensor_value);
xlabel('Time (seconds)');
ylabel('Sensor Value');
title('Sensor Data');
```

## Advanced Features

### Real-Time Streaming

Stream data to external applications:

```bash
# Stream to file (real-time)
glider --file exp.glider --run --stream stdout > live_data.csv

# Stream to network
glider --file exp.glider --run --stream tcp://localhost:5555
```

### Multiple Recording Formats

Export to different formats:

| Format | Extension | Use Case |
|--------|-----------|----------|
| CSV | .csv | Universal, spreadsheets |
| JSON | .json | Web applications |
| HDF5 | .h5 | Large datasets, Python |
| Parquet | .parquet | Big data, columnar |

Configure via **Tools → Settings → Recording → Format**.

## Video Recording

GLIDER can record video from connected webcams synchronized with your experiment.

### Enabling Video Recording

1. Open the **Camera Panel** (View → Camera Panel)
2. Select your camera from the dropdown
3. Click **Start Preview** to verify camera works
4. Video recording starts automatically when experiment runs

### Video Output

Video files are saved alongside sensor data:
```
output_folder/
├── MyExperiment_20250115_103000.csv      # Sensor data
├── MyExperiment_20250115_103000.mp4      # Video recording
└── MyExperiment_20250115_103000_tracking.csv  # CV tracking data
```

### Camera Settings

Access camera settings via the **Settings...** button in the Camera Panel:

| Tab | Settings |
|-----|----------|
| **Camera** | Resolution, FPS, Exposure, Brightness, Contrast |
| **Computer Vision** | Detection backend, Confidence threshold, Min detection area |
| **Tracking** | Enable tracking, Max disappeared frames |

### Supported Resolutions

| Resolution | Aspect Ratio | Use Case |
|------------|--------------|----------|
| 320x240 | 4:3 | Low bandwidth, fast processing |
| 640x480 | 4:3 | General purpose |
| 1280x720 | 16:9 | HD recording |
| 1920x1080 | 16:9 | Full HD (higher CPU usage) |

## Computer Vision Tracking

GLIDER includes real-time computer vision for object detection and tracking.

### Detection Backends

| Backend | Description | Requirements |
|---------|-------------|--------------|
| **Background Subtraction** | Detects moving objects against static background | None (built-in) |
| **Motion Detection** | Detects any movement in frame | None (built-in) |
| **YOLO v8** | AI-powered object detection | `pip install ultralytics` |

### CV Features

- **Bounding Box Detection**: Identifies objects and draws boxes around them
- **Object Tracking**: Assigns persistent IDs to tracked objects across frames
- **Motion Detection**: Detects movement and calculates motion area percentage
- **Overlay Display**: Shows detection boxes and labels on preview

### Tracking Data CSV Format

The tracking CSV contains frame-by-frame detection data:

```csv
# GLIDER Tracking Data
# Experiment: MyExperiment
# Start Time: 2025-01-15T10:30:00

frame,timestamp,elapsed_ms,object_id,class,x,y,w,h,confidence
1,2025-01-15T10:30:00.033,0.0,1,object,120,80,45,30,0.95
2,2025-01-15T10:30:00.066,33.3,1,object,125,82,45,30,0.93
2,2025-01-15T10:30:00.066,33.3,2,object,300,150,40,28,0.87
```

### Tracking CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `frame` | Integer | Frame number |
| `timestamp` | ISO 8601 | Absolute time |
| `elapsed_ms` | Float | Milliseconds since start |
| `object_id` | Integer | Persistent tracking ID (-1 for motion-only) |
| `class` | String | Object class name |
| `x`, `y` | Integer | Bounding box top-left corner |
| `w`, `h` | Integer | Bounding box width and height |
| `confidence` | Float | Detection confidence (0.0-1.0) |

### Analyzing Tracking Data

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load tracking data (skip comment lines)
df = pd.read_csv('experiment_tracking.csv', comment='#')

# Plot object trajectories
for obj_id in df['object_id'].unique():
    if obj_id >= 0:  # Skip motion-only entries
        obj_data = df[df['object_id'] == obj_id]
        # Calculate center position
        cx = obj_data['x'] + obj_data['w'] / 2
        cy = obj_data['y'] + obj_data['h'] / 2
        plt.plot(cx, cy, label=f'Object {obj_id}')

plt.xlabel('X Position')
plt.ylabel('Y Position')
plt.title('Object Trajectories')
plt.legend()
plt.show()
```

### Triggers

Start/stop recording based on conditions:

```
Recording Triggers:
  Start when: sensor_value > 500
  Stop when: elapsed_time > 60 seconds
  Or: button_pressed == true
```

## Troubleshooting

### No Data File Created

1. Check recording is enabled
2. Verify directory exists and is writable
3. Ensure experiment ran (not just started)
4. Check for error messages in log

### Missing Data Points

- Sample interval may be too fast for hardware
- USB/serial communication delays
- CPU overload during processing

### Corrupt Data

- Experiment crashed mid-write
- Disk full during recording
- Check for partial lines at end of file

### Wrong Timestamps

- Verify system clock is correct
- Check timezone settings
- Ensure NTP sync (for networked systems)

## Best Practices

### Before Recording

1. **Configure interval appropriately**: Match experiment needs
2. **Check disk space**: Ensure sufficient storage
3. **Name experiments clearly**: Helps organize data
4. **Test recording**: Run short test first

### During Recording

1. **Monitor file growth**: Watch for unexpected sizes
2. **Check live data**: Verify values are reasonable
3. **Note observations**: Document manual notes

### After Recording

1. **Backup data**: Copy to secondary storage
2. **Validate completeness**: Check start/end times
3. **Document analysis**: Keep processing scripts
4. **Archive or clean**: Follow retention policy

## See Also

- [Running Experiments](running-experiments.md) - Execution guide
- [API Reference: DataRecorder](../api-reference/core.md#datarecorder) - Programming API
- [Configuration](../reference/configuration.md) - All settings
