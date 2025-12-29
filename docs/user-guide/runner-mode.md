# Runner Mode

Runner Mode is GLIDER's touch-optimized interface for experiment execution. It's designed for use on small displays like the Raspberry Pi's official 7" touchscreen (800x480).

## Launching Runner Mode

```bash
# Auto-detect (uses Runner on small/touch screens)
glider

# Force Runner mode
glider --runner

# Open an experiment file directly in Runner
glider --runner --file experiment.glider
```

## When to Use Runner Mode

Runner Mode is ideal for:

- **Touchscreen displays**: Raspberry Pi official display, tablets
- **Dedicated experiment stations**: Minimal UI for operators
- **Live monitoring**: Focus on real-time data
- **Production use**: No accidental editing of experiments

## Interface Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    My Experiment                             │
│                    ════════════                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│    ┌──────────────┐    ┌──────────────┐                     │
│    │     LED      │    │   Sensor     │                     │
│    │              │    │              │                     │
│    │    ● ON      │    │    512       │                     │
│    │              │    │              │                     │
│    └──────────────┘    └──────────────┘                     │
│                                                              │
│    ┌──────────────┐    ┌──────────────┐                     │
│    │   Motor      │    │   Button     │                     │
│    │              │    │              │                     │
│    │ ████████░░   │    │   [PRESS]    │                     │
│    │     80%      │    │              │                     │
│    └──────────────┘    └──────────────┘                     │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   [  ▶ START  ]    [  ⏸ PAUSE  ]    [  ⏹ STOP  ]           │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  ● READY                                    00:00:00         │
└─────────────────────────────────────────────────────────────┘
```

## Interface Components

### Header Bar

Displays:
- **Experiment name**: Current loaded experiment
- **Recording indicator**: Red dot when recording data
- **Settings button**: Access Runner settings

### Device Dashboard

Large, touch-friendly cards showing:

- **Device name**: Identifier from experiment
- **Current state**: Real-time value display
- **Visual indicator**: State-appropriate graphics
  - Digital: ON/OFF indicator
  - Analog: Value with bar graph
  - PWM: Percentage bar
  - Servo: Angle indicator

### Control Buttons

Large buttons for experiment control:

| Button | Action | Available When |
|--------|--------|----------------|
| **START** | Begin experiment | READY, IDLE |
| **PAUSE** | Pause execution | RUNNING |
| **RESUME** | Continue from pause | PAUSED |
| **STOP** | End experiment | RUNNING, PAUSED |

### Status Bar

Shows:
- **State indicator**: IDLE, READY, RUNNING, PAUSED, ERROR
- **Elapsed time**: Duration since start
- **Connection status**: Hardware connection state

## Dashboard Widgets

### Output Widgets

**Digital Output (LED, Relay)**
```
┌──────────────────┐
│      LED         │
│                  │
│     ● ON         │
│                  │
└──────────────────┘
```
- Shows ON/OFF state
- Color changes with state

**PWM Output (Motor, Dimmer)**
```
┌──────────────────┐
│     Motor        │
│                  │
│  ████████░░ 80%  │
│                  │
└──────────────────┘
```
- Progress bar shows duty cycle
- Percentage value displayed

**Servo**
```
┌──────────────────┐
│     Servo        │
│                  │
│     ◐ 90°       │
│                  │
└──────────────────┘
```
- Angle displayed
- Visual position indicator

### Input Widgets

**Digital Input (Button, Switch)**
```
┌──────────────────┐
│    Button        │
│                  │
│   ○ Released     │
│                  │
└──────────────────┘
```
- Shows current state
- Updates in real-time

**Analog Input (Sensor)**
```
┌──────────────────┐
│    Sensor        │
│                  │
│      512         │
│  ▁▂▃▄▅▆▇█        │
└──────────────────┘
```
- Numeric value
- Mini graph of recent values

### Interactive Widgets

Some nodes expose interactive controls in Runner mode:

**Slider Control**
```
┌──────────────────┐
│    Speed         │
│                  │
│  ◀═══════●═▶    │
│       75%        │
└──────────────────┘
```
- Drag to adjust value
- Affects connected nodes

**Button Control**
```
┌──────────────────┐
│                  │
│   [  TRIGGER  ]  │
│                  │
└──────────────────┘
```
- Tap to trigger action
- Momentary or toggle mode

## Configuring Runner Dashboard

### In Builder Mode

Mark nodes as "Visible in Runner":

1. Select a node in Builder mode
2. In Properties panel, check **Visible in Runner**
3. Optionally set widget size: Small, Normal, Large

### Dashboard Layout

Configure in **View → Dashboard Settings**:

- **Layout Mode**: Vertical, Horizontal, or Grid
- **Columns**: Number of columns (grid mode)
- **Widget Size**: Default size for widgets

## Touch Gestures

| Gesture | Action |
|---------|--------|
| **Tap** | Select/activate |
| **Long press** | Context menu |
| **Swipe down** | Refresh display |
| **Pinch** | Zoom dashboard (if enabled) |

## Switching Between Modes

### From Runner to Builder

1. Tap the **Settings** icon (gear)
2. Select **Switch to Builder**
3. Or use keyboard: Press F11

### From Builder to Runner

1. Menu: **View → Runner Mode**
2. Or press F11
3. Or click the **Runner** button in toolbar

## Running Experiments

### Starting an Experiment

1. Load an experiment (from Builder or command line)
2. Verify hardware is connected (green indicators)
3. Tap **START**
4. Monitor device states on dashboard

### During Execution

- Watch real-time device states
- Use interactive widgets if available
- Tap **PAUSE** to temporarily stop
- Tap **STOP** to end experiment

### Handling Errors

If an error occurs:
- Status shows **ERROR** (red)
- Error message displayed
- Tap **STOP** to reset
- Check hardware connections
- Review experiment in Builder mode

## Settings

Access via gear icon or long-press on empty area:

| Setting | Description |
|---------|-------------|
| **Auto-start** | Start experiment on load |
| **Keep awake** | Prevent screen sleep |
| **Show clock** | Display current time |
| **Full screen** | Hide system UI |
| **Dark mode** | Reduce brightness |
| **Font size** | Adjust text size |

## Raspberry Pi Deployment

For dedicated experiment stations:

### Auto-Start on Boot

Add to `/etc/rc.local` or create a systemd service:

```bash
#!/bin/bash
# /home/pi/start-glider.sh
cd /home/pi/glider
source venv/bin/activate
glider --runner --file /home/pi/experiments/current.glider
```

### Disable Screen Blanking

```bash
# In /etc/xdg/lxsession/LXDE-pi/autostart
@xset s off
@xset -dpms
@xset s noblank
```

### Rotate Display (if needed)

Add to `/boot/config.txt`:
```
display_rotate=1  # 90 degrees
```

## Troubleshooting

### Widgets Not Showing

- Ensure nodes are marked "Visible in Runner"
- Check that devices are properly configured
- Verify hardware is connected

### Touch Not Responding

- Check touchscreen drivers installed
- Calibrate touchscreen if needed
- Verify Qt has touch support

### Performance Issues

- Reduce widget refresh rate
- Disable graphing for analog inputs
- Use simpler widget styles

## See Also

- [Builder Mode](builder-mode.md) - Design experiments
- [Running Experiments](running-experiments.md) - Execution details
- [Hardware Setup](hardware-setup.md) - Configure hardware
