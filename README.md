# GLIDER

**General Laboratory Interface for Design, Experimentation, and Recording**

GLIDER is a visual-programming environment for designing, running, and recording behavioral and physiological experiments. It connects directly to Arduino boards, Raspberry Pi GPIO, I²C devices, USB cameras, and the UCLA Miniscope, and produces synchronized CSV logs and video files suitable for downstream scientific analysis.

GLIDER is built for neuroscience labs running behavioral assays, optogenetics protocols, or closed-loop physiology. Experiments are described as node graphs that run unattended for hours; the system is designed to fail safely (outputs driven low on stop, hung devices time out instead of freezing the UI) and to produce reproducible data with embedded provenance.

---

## What GLIDER does

- **Visual flow programming.** Drag-and-drop nodes to describe an experiment. Trial structure, hardware control, vision processing, and data logging all live in one graph.
- **Direct hardware control.** Telemetrix-over-USB for Arduino, gpiozero/lgpio for Raspberry Pi, Adafruit CircuitPython for ADS1115 ADCs, OpenCV / picamera2 / v4l2-ctl for cameras and the UCLA Miniscope V4 (LED + EWL focus).
- **Multi-camera capture with tracking.** Background subtraction or YOLO+ByteTrack, polygon/circle zones with enter/exit events, optional behavior state classification (resting / walking / darting / freezing).
- **Touchscreen runner mode.** Optimised for Raspberry Pi kiosks (480×800 portrait) — large hit targets, simple operator UI for starting, stopping, and intervening in a running experiment.
- **One-file experiments.** A `.glider` file is human-readable JSON containing the flow graph, hardware configuration, camera settings, calibration, and dashboard layout. Open, diff, and version-control it like any other source artifact.
- **Reproducible output.** Per-experiment subdirectory containing the timestamped CSV log, video file(s), zone-tracking CSV, and a copy of the `.glider` file used to produce them.

---

## Supported platforms

| Platform | Python | Boards | Cameras | Notes |
|---|---|---|---|---|
| Linux (x86_64) | 3.11, 3.12, 3.13 | Arduino via USB | USB UVC, Miniscope V4 | Recommended dev platform |
| Windows 10/11 | 3.11, 3.12, 3.13 | Arduino via USB | DirectShow, Miniscope V4 | Codesigning not yet in place |
| macOS 12+ | 3.11, 3.12, 3.13 | Arduino via USB | AVFoundation | Use AVFoundation backend explicitly |
| Raspberry Pi (Pi 4/5, 64-bit OS) | 3.11, 3.12, 3.13 | Pi GPIO, Arduino via USB | Camera Module 3, USB UVC, Miniscope V4 | Touch runner mode optimised here |

---

## Supported hardware

**Microcontrollers**
- Arduino Uno, Mega 2560 (via [telemetrix-aio](https://github.com/MrYsLab/telemetrix-aio))
- Raspberry Pi 4 / 5 GPIO (via [gpiozero](https://gpiozero.readthedocs.io/) + `lgpio` backend)

**I²C devices**
- ADS1115 16-bit ADC (Adafruit CircuitPython driver)

**Output devices**
- Digital output (LEDs, valves, relays)
- PWM (heating elements, motor speed control)
- Servo (positioning)
- Motor governor (relay-based ramp/brake control)

**Input devices**
- Digital input (beam-break sensors, switches)
- Analog input via ADS1115 (loadcells, force transducers, photo sensors)

**Cameras**
- USB UVC cameras (OpenCV backends: V4L2/MSMF/AVFoundation/DirectShow/FFmpeg)
- Raspberry Pi Camera Module 1/2/3 (via `picamera2`)
- UCLA Miniscope V4 (LED + electrowetting lens focus control)

---

## Installation

GLIDER requires Python 3.11, 3.12, or 3.13.

### Windows / macOS

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS:
source venv/bin/activate

pip install ".[pc]"
glider
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y libgl1 libegl1 libxkbcommon-x11-0 libdbus-1-3 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-xinerama0 libxcb-xinput0 libxcb-xfixes0

python3 -m venv venv
source venv/bin/activate
pip install ".[pc]"
glider
```

### Raspberry Pi (Pi OS 64-bit, Bookworm or later)

```bash
sudo apt update
sudo apt install -y python3-pyqt6 python3-venv python3-picamera2 v4l-utils i2c-tools

python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -e ".[rpi]"
glider
```

The `--system-site-packages` flag is required so the venv can see `PyQt6` and `picamera2` from the apt installation.

If using Miniscope V4 on Pi, enable I²C and ensure your user is in the `i2c` group:

```bash
sudo raspi-config  # Interface Options → I2C → Enable
sudo usermod -aG i2c $USER
# Log out and back in
```

---

## Quick start

1. Launch GLIDER: `glider`
2. **Add a board:** `Hardware → Add Board → Arduino` (auto-detect port) or `Raspberry Pi`
3. **Add a device:** Right-click the board → `Add Device → Digital Output → Pin 13`
4. **Build a flow:** Drag a `Start Experiment` node onto the canvas, then `Digital Write` → `Delay (1s)` → `Digital Write (off)` → `End Experiment`. Connect them with the green exec ports.
5. **Save:** `File → Save Experiment As… → my_first_experiment.glider`
6. **Run:** `Experiment → Run`. The LED on pin 13 should blink once.

For multi-camera tracking, zone-based event detection, or behavioral assays, see `docs/GLIDER_Technical_Documentation.pdf`.

---

## Documentation

- **Software design document:** [docs/GLIDER_Technical_Documentation.pdf](docs/GLIDER_Technical_Documentation.pdf)
- **Code review (engineering reference):** [code-review.md](code-review.md) and [code-review-2.md](code-review-2.md)
- **API documentation:** *In progress.* Run `glider --help` for CLI options.

---

## Citing GLIDER

If you use GLIDER in published work, please cite it via [`CITATION.cff`](CITATION.cff). For a `bibtex` snippet, see the same file.

---

## Troubleshooting

**`ImportError: PyQt6.QtCore` on Linux.** You're missing the Qt platform libraries. Run the `apt install` line in the Linux install section above.

**Arduino board not detected.** Make sure your user is in the `dialout` group on Linux (`sudo usermod -aG dialout $USER`, then re-login) or that the COM port is not held by another program (close the Arduino IDE's Serial Monitor).

**Miniscope LED control does nothing.** On Linux, GLIDER uses `v4l2-ctl` for I²C commands. Verify it's installed (`v4l-utils` package) and that your camera shows up as `/dev/video0` or similar. On Windows, the I²C commands go through OpenCV property setters; if that fails, your camera firmware may not support them.

**ADS1115 timeout on initialisation.** Check wiring (SDA/SCL crossed?), check `i2cdetect -y 1` shows the chip at 0x48, check the chip has 3.3 V power, and ensure your user is in the `i2c` group.

**The runner mode UI is blank.** GLIDER detects display size to pick desktop vs. touch mode. Force-set with the environment variable `GLIDER_MODE=runner` before launching.

**Experiment data file is empty after a crash.** If the host OS crashed or was force-rebooted mid-recording, the `.mp4` may be missing its moov atom. Try `ffmpeg -i broken.mp4 -c copy fixed.mp4` for recovery. The CSV log and `.glider` file should be intact (atomic writes; see [code-review-2.md](code-review-2.md)).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short:

- Open an issue before starting non-trivial work so we can align on scope.
- Run `ruff check src tests && black --check src tests && pytest tests/ -v` before sending a PR.
- New hardware drivers go in `src/glider/hal/boards/`; new device classes in `src/glider/hal/base_device.py`; new flow nodes in `src/glider/nodes/`. Each layer has a corresponding test directory.

---

## License

MIT — see [LICENSE](LICENSE).

The bundled YOLO model weights in `models/`, if present, may be subject to additional licence terms from upstream ([Ultralytics YOLO](https://github.com/ultralytics/ultralytics)). Check the upstream licence before redistribution.

---

## Status

GLIDER is preparing **development release 0.3.0**. See [code-review-2.md](code-review-2.md) for the engineering review and known limitations. Treat this as development software: validate protocols and safe-state behavior with your exact hardware before running experiments.
