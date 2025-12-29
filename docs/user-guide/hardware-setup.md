# Hardware Setup

This guide covers configuring Arduino and Raspberry Pi boards for use with GLIDER.

## Supported Hardware

### Arduino Boards

| Board | Support | Notes |
|-------|---------|-------|
| Arduino Uno | Full | Most common, recommended |
| Arduino Nano | Full | Compact, same pins as Uno |
| Arduino Mega | Full | More pins, more memory |
| Arduino Leonardo | Partial | USB differences |
| Arduino Due | Partial | 3.3V logic |

### Raspberry Pi

| Model | Support | Notes |
|-------|---------|-------|
| Pi 3 Model B+ | Full | Recommended minimum |
| Pi 4 Model B | Full | Best performance |
| Pi Zero W | Partial | Limited resources |
| Pi 5 | Full | Latest hardware |

## Arduino Setup

### Step 1: Install Arduino IDE

Download from [arduino.cc](https://www.arduino.cc/en/software) and install.

### Step 2: Install Telemetrix Firmware

GLIDER uses Telemetrix for Arduino communication.

1. Open Arduino IDE
2. Go to **Sketch → Include Library → Manage Libraries**
3. Search for "Telemetrix4Arduino"
4. Click **Install**

### Step 3: Upload Firmware

1. Connect Arduino via USB
2. Select board: **Tools → Board → Arduino Uno** (or your board)
3. Select port: **Tools → Port → COM3** (or your port)
4. Open example: **File → Examples → Telemetrix4Arduino → Telemetrix4Arduino**
5. Click **Upload** (→ button)
6. Wait for "Done uploading" message

### Step 4: Verify in GLIDER

```bash
glider --builder
```

1. Go to **Hardware → Add Board**
2. Select **Arduino**
3. Choose the COM port
4. Click **Connect**

Status should show green "Connected".

## Raspberry Pi Setup

### GPIO Libraries

GLIDER supports multiple GPIO libraries:

**gpiozero (Recommended)**
```bash
pip install gpiozero
```

**lgpio (Alternative)**
```bash
pip install lgpio
```

### Permission Setup

Add your user to the gpio group:

```bash
sudo usermod -a -G gpio $USER
# Log out and back in
```

### Pin Numbering

GLIDER uses **BCM numbering** (GPIO numbers, not physical pins):

```
                    3V3  (1) (2)  5V
          GPIO2/SDA (3) (4)  5V
          GPIO3/SCL (5) (6)  GND
              GPIO4 (7) (8)  GPIO14/TXD
                GND (9) (10) GPIO15/RXD
             GPIO17 (11)(12) GPIO18/PWM0
             GPIO27 (13)(14) GND
             GPIO22 (15)(16) GPIO23
                3V3 (17)(18) GPIO24
    GPIO10/SPI_MOSI (19)(20) GND
     GPIO9/SPI_MISO (21)(22) GPIO25
    GPIO11/SPI_SCLK (23)(24) GPIO8/CE0
                GND (25)(26) GPIO7/CE1
              GPIO0 (27)(28) GPIO1
              GPIO5 (29)(30) GND
              GPIO6 (31)(32) GPIO12/PWM0
        GPIO13/PWM1 (33)(34) GND
        GPIO19/PWM1 (35)(36) GPIO16
             GPIO26 (37)(38) GPIO20
                GND (39)(40) GPIO21
```

### Adding Raspberry Pi in GLIDER

1. Launch GLIDER on the Pi: `glider --builder`
2. Go to **Hardware → Add Board**
3. Select **Raspberry Pi**
4. Click **Add** (no port needed)
5. Connection is automatic

## Adding Devices

### Digital Output (LED, Relay)

**Wiring an LED:**
```
GPIO Pin ──[330Ω]──[LED]── GND
```

**In GLIDER:**
1. Right-click board → **Add Device**
2. Select **Digital Output**
3. Name: "LED"
4. Pin: 17 (or your GPIO)
5. Click **Create**

### Digital Input (Button)

**Wiring a button with pull-up:**
```
GPIO Pin ──┬── Button ── GND
           │
         [10kΩ]
           │
          3.3V
```

Or use internal pull-up (no external resistor needed).

**In GLIDER:**
1. Right-click board → **Add Device**
2. Select **Digital Input**
3. Name: "Button"
4. Pin: 18
5. Pull-up: **Enabled**
6. Click **Create**

### Analog Input (Potentiometer, Sensor)

> **Note:** Raspberry Pi has no built-in ADC. Use an external ADC (MCP3008) or Arduino for analog.

**Arduino Analog Wiring:**
```
Sensor VCC ── 5V
Sensor GND ── GND
Sensor OUT ── A0
```

**In GLIDER:**
1. Right-click Arduino board → **Add Device**
2. Select **Analog Input**
3. Name: "Sensor"
4. Pin: 0 (A0)
5. Click **Create**

### PWM Output (Motor Speed, LED Dimming)

**Wiring a motor with driver:**
```
GPIO PWM Pin ── Motor Driver IN
Motor Driver OUT ── Motor
Motor Driver VCC ── 5V
Motor Driver GND ── GND
```

**PWM-Capable Pins:**
- Arduino: 3, 5, 6, 9, 10, 11
- Raspberry Pi: 12, 13, 18, 19

**In GLIDER:**
1. Right-click board → **Add Device**
2. Select **PWM Output**
3. Name: "Motor"
4. Pin: 9 (Arduino) or 18 (Pi)
5. Click **Create**

### Servo Motor

**Wiring:**
```
Servo Red (VCC) ── 5V
Servo Brown (GND) ── GND
Servo Orange (Signal) ── GPIO Pin
```

**In GLIDER:**
1. Right-click board → **Add Device**
2. Select **Servo**
3. Name: "Servo1"
4. Pin: 9
5. Click **Create**

## Pin Capabilities

### Arduino Uno Pin Map

| Pin | Digital | Analog In | PWM | Notes |
|-----|---------|-----------|-----|-------|
| 0 | ✓ | - | - | RX (serial) |
| 1 | ✓ | - | - | TX (serial) |
| 2 | ✓ | - | - | Interrupt |
| 3 | ✓ | - | ✓ | Interrupt |
| 4 | ✓ | - | - | |
| 5 | ✓ | - | ✓ | |
| 6 | ✓ | - | ✓ | |
| 7 | ✓ | - | - | |
| 8 | ✓ | - | - | |
| 9 | ✓ | - | ✓ | |
| 10 | ✓ | - | ✓ | SPI SS |
| 11 | ✓ | - | ✓ | SPI MOSI |
| 12 | ✓ | - | - | SPI MISO |
| 13 | ✓ | - | - | Built-in LED |
| A0-A5 | ✓ | ✓ | - | Analog inputs |

### Raspberry Pi GPIO Capabilities

| GPIO | Digital | PWM | Special |
|------|---------|-----|---------|
| 2, 3 | ✓ | - | I2C |
| 4-11 | ✓ | - | Various |
| 12, 13 | ✓ | ✓ | Hardware PWM |
| 14, 15 | ✓ | - | UART |
| 16-27 | ✓ | - | General IO |
| 18, 19 | ✓ | ✓ | Hardware PWM |

## Troubleshooting

### Arduino Not Detected

1. Check USB cable (use data cable, not charge-only)
2. Install drivers if needed (Windows may need CH340 driver)
3. Verify Telemetrix firmware is uploaded
4. Try different USB port
5. Check **Tools → Port** in Arduino IDE

### Raspberry Pi GPIO Errors

**Permission denied:**
```bash
sudo usermod -a -G gpio $USER
# Log out and back in
```

**Pin busy:**
- Another process may be using the pin
- Reboot or kill conflicting processes
- Check for leftover `/sys/class/gpio` exports

### Connection Drops

**Arduino:**
- Check USB cable quality
- Reduce baud rate in settings
- Avoid pins 0, 1 (serial)

**Raspberry Pi:**
- Reduce GPIO switching frequency
- Check for power supply issues
- Monitor CPU temperature

### Servo Jitter

- Use dedicated servo power supply
- Add capacitor across servo power (100µF)
- Use hardware PWM pins

## Best Practices

### Power

- Use adequate power supply (especially for motors)
- Don't power high-current devices from GPIO
- Add decoupling capacitors near noisy loads

### Wiring

- Keep wires short for high-speed signals
- Use pull-up/pull-down resistors for inputs
- Add current-limiting resistors for LEDs

### Safety

- Always disconnect power when rewiring
- Start with low current/voltage for testing
- Use optocouplers for high-voltage isolation

## See Also

- [Creating Experiments](creating-experiments.md) - Use configured hardware
- [Custom Drivers](../developer-guide/custom-drivers.md) - Add new board types
- [Custom Devices](../developer-guide/custom-devices.md) - Add new device types
