# Builder Mode

Builder Mode is GLIDER's desktop IDE for designing and testing experiments. This guide covers the interface and workflow.

## Launching Builder Mode

```bash
# Auto-detect (uses Builder on desktop screens)
glider

# Force Builder mode
glider --builder

# Open an experiment file
glider --builder --file experiment.glider
```

## Interface Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  File  Edit  View  Hardware  Flow  Tools  Help            [Builder Mode]│
├─────────────────────────────────────────────────────────────────────────┤
│  [New] [Open] [Save] | [Run] [Stop] [Pause] | [Undo] [Redo]             │
├──────────────┬──────────────────────────────────┬───────────────────────┤
│              │                                  │                       │
│   Hardware   │                                  │    Node Library       │
│    Panel     │       Node Graph Canvas          │                       │
│              │                                  │    [Experiment]       │
│  ┌─Arduino   │                                  │      Start            │
│  │  └─LED    │     ┌─────┐    ┌─────┐          │      End              │
│  │  └─Button │     │Start│───▶│Write│          │      Delay            │
│  └─Pi        │     └─────┘    └─────┘          │                       │
│              │                                  │    [Hardware]         │
│              │                                  │      Digital Write    │
│              │                                  │      Analog Read      │
├──────────────┴──────────────────────────────────┴───────────────────────┤
│  Properties Panel                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┤
│  │ Node: Digital Write                                                   │
│  │ Device: [LED          ▼]                                             │
│  │ Value:  [✓] HIGH                                                     │
│  └──────────────────────────────────────────────────────────────────────┤
├─────────────────────────────────────────────────────────────────────────┤
│  Ready                                              State: IDLE          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Main Panels

### Hardware Panel (Left)

Displays connected boards and configured devices in a tree view:

- **Boards**: Hardware platforms (Arduino, Raspberry Pi)
  - Connection status indicator (green=connected)
  - Port information
- **Devices**: Configured I/O devices
  - Device type and pin assignment
  - Current state (when running)

**Actions:**
- Right-click board → Add Device, Disconnect, Remove
- Right-click device → Configure, Remove
- Double-click → Open properties

### Node Graph Canvas (Center)

The main workspace for visual programming:

- **Nodes**: Drag from Node Library or double-click to add
- **Connections**: Drag from output port to input port
- **Pan**: Middle-mouse drag or Ctrl+drag
- **Zoom**: Mouse wheel or Ctrl+/Ctrl-
- **Select**: Click node or drag selection box
- **Multi-select**: Shift+click or Ctrl+click
- **Delete**: Select and press Delete

**Grid:**
- Nodes snap to grid for alignment
- Toggle grid: View → Show Grid

### Node Library (Right)

Organized palette of available nodes:

- **Experiment**: Start, End, Delay
- **Hardware**: Digital/Analog Read/Write
- **Logic**: Math, Comparison, Flow Control
- **Interface**: Buttons, Sliders, Displays
- **Script**: Custom Python code

**Adding Nodes:**
1. Drag node from library to canvas
2. Or double-click in library to add at center
3. Or right-click canvas → Add Node

### Properties Panel (Bottom)

Configure the selected node or device:

- **Node Properties**: Type-specific settings
- **Device Properties**: Pin assignments, settings
- **Connection Properties**: Data type information

## Working with Nodes

### Adding Nodes

**Method 1: Drag and Drop**
1. Find the node in the Node Library
2. Drag it onto the canvas
3. Release at desired position

**Method 2: Context Menu**
1. Right-click on the canvas
2. Select **Add Node**
3. Choose from the submenu

**Method 3: Quick Add**
1. Double-click on empty canvas area
2. Type to search for node
3. Press Enter to add

### Connecting Nodes

1. Hover over an output port (right side of node)
2. Click and drag toward an input port
3. Release on a compatible port
4. Connection appears as a curved line

**Connection Rules:**
- Execution ports (white) only connect to execution ports
- Data ports connect to matching or compatible types
- One output can connect to multiple inputs
- Each input accepts only one connection

### Configuring Nodes

1. Click a node to select it
2. View/edit properties in the Properties Panel
3. Changes apply immediately

**Common Properties:**
- **Device**: Which hardware device to use
- **Value**: Output value or threshold
- **Duration**: Time for delay nodes
- **Condition**: For logic nodes

### Deleting Elements

- **Single Node**: Select → Delete key
- **Multiple Nodes**: Select all → Delete key
- **Connection**: Click connection → Delete key
- **With Context Menu**: Right-click → Delete

## Working with Hardware

### Adding a Board

1. Go to **Hardware → Add Board**
2. Select board type (Arduino, Raspberry Pi)
3. Configure connection:
   - **Arduino**: Select COM port
   - **Raspberry Pi**: No port needed (local GPIO)
4. Click **Add**

### Connecting to Hardware

1. Select a board in the Hardware Panel
2. Click **Connect** button or right-click → Connect
3. Wait for connection (status turns green)

> **Note:** Arduino requires Telemetrix firmware. See [Hardware Setup](hardware-setup.md).

### Adding Devices

1. Right-click a board in Hardware Panel
2. Select **Add Device**
3. Choose device type:
   - Digital Output (LED, Relay)
   - Digital Input (Button, Switch)
   - Analog Input (Sensor)
   - PWM Output (Motor, Dimmable LED)
   - Servo
4. Configure:
   - **Name**: Friendly identifier
   - **Pin**: GPIO pin number
   - **Settings**: Device-specific options
5. Click **Create**

## Menu Reference

### File Menu

| Action | Shortcut | Description |
|--------|----------|-------------|
| New | Ctrl+N | Create new experiment |
| Open | Ctrl+O | Open .glider file |
| Save | Ctrl+S | Save current experiment |
| Save As | Ctrl+Shift+S | Save with new name |
| Export | - | Export to other formats |
| Exit | Alt+F4 | Close GLIDER |

### Edit Menu

| Action | Shortcut | Description |
|--------|----------|-------------|
| Undo | Ctrl+Z | Undo last action |
| Redo | Ctrl+Y | Redo undone action |
| Cut | Ctrl+X | Cut selected nodes |
| Copy | Ctrl+C | Copy selected nodes |
| Paste | Ctrl+V | Paste nodes |
| Delete | Delete | Delete selection |
| Select All | Ctrl+A | Select all nodes |

### View Menu

| Action | Shortcut | Description |
|--------|----------|-------------|
| Zoom In | Ctrl++ | Zoom in on canvas |
| Zoom Out | Ctrl+- | Zoom out on canvas |
| Fit to Window | Ctrl+0 | Fit all nodes in view |
| Show Grid | Ctrl+G | Toggle grid display |
| Runner Mode | F11 | Switch to Runner Mode |

### Hardware Menu

| Action | Description |
|--------|-------------|
| Add Board | Add new hardware board |
| Scan Ports | Refresh available COM ports |
| Connect All | Connect all boards |
| Disconnect All | Disconnect all boards |
| Emergency Stop | Immediately stop all outputs |

### Flow Menu

| Action | Shortcut | Description |
|--------|----------|-------------|
| Run | F5 | Start experiment |
| Stop | Shift+F5 | Stop experiment |
| Pause | F6 | Pause experiment |
| Resume | F6 | Resume paused experiment |
| Validate | F7 | Check for errors |

## Keyboard Shortcuts

| Category | Shortcut | Action |
|----------|----------|--------|
| **File** | Ctrl+N | New |
| | Ctrl+O | Open |
| | Ctrl+S | Save |
| **Edit** | Ctrl+Z | Undo |
| | Ctrl+Y | Redo |
| | Delete | Delete selection |
| **View** | Ctrl++ | Zoom in |
| | Ctrl+- | Zoom out |
| | Ctrl+0 | Fit to window |
| **Flow** | F5 | Run |
| | Shift+F5 | Stop |
| | F6 | Pause/Resume |
| **Navigation** | Middle-drag | Pan canvas |
| | Scroll | Zoom |

## Tips and Best Practices

### Organization

- **Name your nodes**: Double-click title to rename
- **Use comments**: Add Comment nodes to document flow
- **Align nodes**: Use grid snapping for neat layouts
- **Group related nodes**: Keep logical sections together

### Performance

- **Minimize connections**: Shorter paths execute faster
- **Use appropriate sample rates**: Don't poll faster than needed
- **Batch operations**: Combine related writes when possible

### Debugging

- **Watch values**: Enable data display on connections
- **Use breakpoints**: Pause at specific nodes (coming soon)
- **Check logs**: View → Show Log for detailed output
- **Validate first**: Run Flow → Validate before execution

## See Also

- [Runner Mode](runner-mode.md) - Execution interface
- [Creating Experiments](creating-experiments.md) - Detailed workflow
- [Hardware Setup](hardware-setup.md) - Board configuration
