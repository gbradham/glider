# Installation

This guide covers installing GLIDER and its dependencies on various platforms.

## System Requirements

### Minimum Requirements

- **Python**: 3.9 or higher
- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 20.04+)
- **RAM**: 4 GB minimum, 8 GB recommended
- **Display**: 1024x768 minimum (480x800 for Runner mode)

### Hardware Requirements

For hardware control, you'll need one or more of:

- **Arduino**: Uno, Nano, Mega, or compatible board
- **Raspberry Pi**: Model 3B+ or newer with GPIO access
- **Custom Hardware**: Via plugin drivers

## Installation Methods

### From Source (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/LaingLab/glider.git
cd glider

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
```

### With Optional Dependencies

```bash
# With Raspberry Pi GPIO support
pip install -e ".[rpi]"

# With development tools (testing, linting)
pip install -e ".[dev]"

# With all optional dependencies
pip install -e ".[dev,rpi]"
```

## Platform-Specific Setup

### Windows

1. Install Python 3.9+ from [python.org](https://www.python.org/downloads/)
2. Ensure Python is added to PATH during installation
3. Install GLIDER:

```powershell
pip install -e .
```

4. For Arduino support, install the [Arduino IDE](https://www.arduino.cc/en/software) to get USB drivers

### macOS

1. Install Python via Homebrew:

```bash
brew install python@3.11
```

2. Install GLIDER:

```bash
pip3 install -e .
```

3. Grant terminal access to USB devices in System Preferences > Security & Privacy

### Linux (Ubuntu/Debian)

1. Install system dependencies:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
sudo apt install libxcb-xinerama0  # Required for PyQt6
```

2. Install GLIDER:

```bash
pip3 install -e .
```

3. Add user to dialout group for serial port access:

```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

### Raspberry Pi

1. Update system packages:

```bash
sudo apt update && sudo apt upgrade -y
```

2. Install dependencies:

```bash
sudo apt install python3-pip python3-venv libxcb-xinerama0
```

3. Install with Raspberry Pi support:

```bash
pip3 install -e ".[rpi]"
```

4. Enable GPIO access (no sudo required):

```bash
sudo usermod -a -G gpio $USER
```

## Arduino Firmware Setup

GLIDER communicates with Arduino via the Telemetrix protocol. You must upload the Telemetrix firmware to your Arduino:

1. Install Arduino IDE
2. Open the Arduino IDE and install the Telemetrix4Arduino library:
   - Go to **Sketch > Include Library > Manage Libraries**
   - Search for "Telemetrix4Arduino"
   - Click Install

3. Upload the Telemetrix sketch:
   - Go to **File > Examples > Telemetrix4Arduino > Telemetrix4Arduino**
   - Select your board type in **Tools > Board**
   - Select the correct port in **Tools > Port**
   - Click **Upload**

4. Verify the upload was successful (LED may blink)

## Verifying Installation

Run GLIDER to verify everything is working:

```bash
# Start GLIDER
glider

# Or with debug output
glider --debug
```

You should see the GLIDER window appear. Check the status bar for any connection warnings.

### Testing Hardware Connection

1. Connect your Arduino via USB
2. Launch GLIDER: `glider --builder`
3. Go to **Hardware > Scan for Devices**
4. Your Arduino should appear in the Hardware panel

## Troubleshooting

### PyQt6 Import Errors

If you see errors about missing Qt libraries:

```bash
# Linux
sudo apt install libxcb-xinerama0 libxcb-cursor0

# macOS - reinstall PyQt6
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip
pip install PyQt6
```

### Serial Port Access Denied

On Linux, add yourself to the `dialout` group:

```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

### Arduino Not Detected

1. Verify Arduino is connected and LED is on
2. Check that Telemetrix firmware is uploaded
3. Try a different USB cable (data cable, not charge-only)
4. Check the port in Arduino IDE to confirm it's recognized

## Next Steps

- [Quick Start Guide](quickstart.md) - Create your first experiment
- [Core Concepts](concepts.md) - Understand GLIDER's architecture
- [Hardware Setup](../user-guide/hardware-setup.md) - Configure your hardware
