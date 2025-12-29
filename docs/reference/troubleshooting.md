# Troubleshooting Guide

This guide covers common issues and their solutions.

## Installation Issues

### ModuleNotFoundError: No module named 'glider'

**Problem:** GLIDER is not installed or not in your Python path.

**Solutions:**
```bash
# Install GLIDER
pip install glider

# Or install in development mode
pip install -e .

# Verify installation
python -m glider --version
```

### PyQt6 Installation Fails

**Problem:** PyQt6 fails to install on your system.

**Solutions:**

*Windows:*
```bash
# Ensure Visual C++ Build Tools are installed
pip install pyqt6
```

*macOS:*
```bash
# Install with Homebrew Qt
brew install qt
pip install pyqt6
```

*Linux:*
```bash
# Install Qt dependencies
sudo apt install python3-pyqt6 pyqt6-dev-tools

# Or install via pip
pip install pyqt6
```

### telemetrix-aio Not Found

**Problem:** Arduino support not available.

**Solution:**
```bash
pip install telemetrix-aio pyserial
```

## Hardware Connection Issues

### Arduino Not Detected

**Symptoms:**
- "No Arduino found" message
- Empty COM port list

**Solutions:**

1. **Check USB connection:**
   - Try a different USB cable
   - Try a different USB port
   - Ensure Arduino is powered

2. **Check drivers:**
   - Windows: Install Arduino IDE (includes drivers)
   - macOS: Usually automatic
   - Linux: Add user to dialout group:
     ```bash
     sudo usermod -a -G dialout $USER
     # Log out and back in
     ```

3. **Check firmware:**
   - Upload Telemetrix firmware to Arduino
   - See [Hardware Setup](../user-guide/hardware-setup.md)

### Connection Timeout

**Symptoms:**
- "Connection timed out" error
- Connection hangs indefinitely

**Solutions:**

1. **Check port settings:**
   - Verify correct COM port selected
   - Check baud rate (default: 115200)

2. **Reset Arduino:**
   - Press reset button on Arduino
   - Wait 2 seconds, then connect

3. **Check for conflicts:**
   - Close Arduino IDE Serial Monitor
   - Close other serial terminal applications

### Raspberry Pi GPIO Not Available

**Symptoms:**
- "GPIO not available" error
- Permission denied

**Solutions:**

1. **Check GPIO group:**
   ```bash
   sudo usermod -a -G gpio $USER
   # Log out and back in
   ```

2. **Check SPI/I2C enabled:**
   ```bash
   sudo raspi-config
   # Enable Interface Options → SPI/I2C
   ```

3. **Install gpiozero:**
   ```bash
   pip install gpiozero pigpio
   sudo pigpiod  # Start pigpio daemon
   ```

## Experiment Execution Issues

### Experiment Doesn't Start

**Symptoms:**
- Start button does nothing
- No error messages

**Solutions:**

1. **Check flow graph:**
   - Ensure StartExperiment node exists
   - Verify connections from StartExperiment

2. **Check hardware:**
   - Ensure all boards connected
   - Verify devices initialized

3. **Check logs:**
   ```bash
   python -m glider --log-level DEBUG
   ```

### Nodes Not Executing

**Symptoms:**
- StartExperiment triggers but nothing happens
- Some nodes don't run

**Solutions:**

1. **Check connections:**
   - Verify execution (white) connections
   - Ensure no broken connections

2. **Check device binding:**
   - Hardware nodes need bound devices
   - Check node properties panel

3. **Check errors:**
   - Look for error indicators (red border) on nodes
   - Check node error message in properties

### Loop Runs Forever

**Symptoms:**
- Infinite loop
- Can't stop experiment

**Solutions:**

1. **Check loop count:**
   - Set count > 0 for finite loops
   - count = 0 means infinite

2. **Stop experiment:**
   - Click Stop button
   - Use keyboard shortcut (Shift+F5)
   - Emergency stop: Close application

### Timing Is Inaccurate

**Symptoms:**
- Delays longer than specified
- Inconsistent timing

**Causes:**
- System load affecting timing
- USB communication latency
- Garbage collection pauses

**Solutions:**

1. **Use shorter delays:**
   - Minimum reliable delay: ~10ms

2. **Reduce system load:**
   - Close unnecessary applications
   - Disable animations

3. **For precise timing:**
   - Use Arduino-side timing when possible
   - Consider real-time OS for critical applications

## File Issues

### Can't Open Experiment File

**Symptoms:**
- "Invalid JSON" error
- "Schema validation failed"

**Solutions:**

1. **Check file integrity:**
   - Open in text editor
   - Look for syntax errors

2. **Check version compatibility:**
   - Older files are migrated automatically
   - Very old files may not be supported

3. **Recover from backup:**
   - Check for `.glider.bak` file
   - Restore from version control

### Can't Save Experiment

**Symptoms:**
- "Permission denied" error
- Save silently fails

**Solutions:**

1. **Check permissions:**
   - Ensure write access to directory
   - Try saving to different location

2. **Check disk space:**
   - Ensure sufficient space
   - Clean up old files

### Data Not Recording

**Symptoms:**
- No CSV file created
- Empty data file

**Solutions:**

1. **Check recording settings:**
   - Verify recording enabled
   - Check output directory exists

2. **Check devices:**
   - Ensure devices configured for recording
   - Check device initialization

3. **Check experiment:**
   - Recording only happens during run
   - Ensure experiment ran long enough

## GUI Issues

### Application Won't Start

**Symptoms:**
- Crashes on startup
- Black screen

**Solutions:**

1. **Check Python version:**
   ```bash
   python --version
   # Requires Python 3.9+
   ```

2. **Reinstall PyQt6:**
   ```bash
   pip uninstall pyqt6
   pip install pyqt6
   ```

3. **Check graphics drivers:**
   - Update graphics drivers
   - Try software rendering:
     ```bash
     export QT_QUICK_BACKEND=software
     python -m glider
     ```

### Node Graph Slow/Laggy

**Symptoms:**
- Slow panning/zooming
- Delayed node dragging

**Solutions:**

1. **Reduce node count:**
   - Use subflows for large experiments
   - Remove unused nodes

2. **Disable animations:**
   - Settings → Appearance → Animations

3. **Disable minimap:**
   - Settings → Appearance → Minimap

### Text/Icons Too Small

**Symptoms:**
- Hard to read on high-DPI display

**Solutions:**

1. **Adjust font size:**
   - Settings → Appearance → Font Size

2. **Set scale factor:**
   ```bash
   # Windows/Linux
   export QT_SCALE_FACTOR=1.5
   python -m glider

   # macOS usually handles this automatically
   ```

## Plugin Issues

### Plugin Not Loading

**Symptoms:**
- Plugin not in list
- "Failed to load plugin" error

**Solutions:**

1. **Check plugin structure:**
   ```
   my_plugin/
   ├── __init__.py  # Required
   └── manifest.json  # Recommended
   ```

2. **Check dependencies:**
   ```bash
   python -m glider --install-plugin-deps my_plugin
   ```

3. **Check for syntax errors:**
   ```bash
   python -c "import my_plugin"
   ```

4. **Check logs:**
   - Look for specific error message
   - Common: ImportError, SyntaxError

### Plugin Components Not Registered

**Symptoms:**
- Custom nodes not available
- Custom devices not selectable

**Solutions:**

1. **Check registration:**
   ```python
   # In plugin __init__.py
   NODE_TYPES = {
       "MyNode": MyNodeClass,
   }
   ```

2. **Check setup function:**
   ```python
   def setup():
       # Called when plugin loads
       pass
   ```

## Performance Issues

### High CPU Usage

**Symptoms:**
- Application uses 100% CPU
- System becomes slow

**Causes:**
- Tight polling loops
- Fast sample rates
- Memory leaks

**Solutions:**

1. **Increase sample interval:**
   - Settings → Recording → Sample Interval

2. **Reduce polling:**
   - WaitForInput: increase poll_interval
   - Loop: add delay between iterations

3. **Check for runaway loops:**
   - Ensure loops have exit conditions

### High Memory Usage

**Symptoms:**
- Memory usage grows over time
- Application crashes after long run

**Solutions:**

1. **Limit recording:**
   - Set retention policy
   - Reduce sample rate

2. **Restart application:**
   - Save experiment
   - Close and reopen GLIDER

3. **Check for leaks:**
   - Report issue if memory grows continuously

## Getting Help

### Debug Information

Collect this information when reporting issues:

```bash
# Version info
python --version
python -m glider --version

# System info
python -c "import platform; print(platform.platform())"

# Qt info
python -c "from PyQt6.QtCore import QT_VERSION_STR; print(QT_VERSION_STR)"

# Run with debug logging
python -m glider --log-level DEBUG 2>&1 | tee glider_debug.log
```

### Reporting Issues

Report issues on GitHub:
1. Go to https://github.com/LaingLab/glider/issues
2. Click "New Issue"
3. Include:
   - GLIDER version
   - Operating system
   - Steps to reproduce
   - Error messages
   - Debug log

### Community Support

- GitHub Discussions: Ask questions
- Wiki: User-contributed guides
- Examples: Sample experiments

## See Also

- [Installation](../getting-started/installation.md) - Installation guide
- [Hardware Setup](../user-guide/hardware-setup.md) - Hardware configuration
- [CLI Reference](cli.md) - Command-line options
