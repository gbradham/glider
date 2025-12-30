# Vision API Reference

The vision module provides video recording and computer vision capabilities for GLIDER experiments.

## Module: `glider.vision`

```python
from glider.vision import (
    CameraManager, CameraInfo, CameraSettings, CameraState,
    VideoRecorder, RecordingState, VideoFormat,
    CVProcessor, CVSettings, Detection, TrackedObject, MotionResult,
    DetectionBackend, ObjectTracker,
    TrackingDataLogger
)
```

---

## CameraManager

Thread-safe webcam capture manager.

### Class: `CameraManager`

```python
class CameraManager:
    """Manages camera devices for video capture."""
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `state` | `CameraState` | Current connection state |
| `is_connected` | `bool` | Whether camera is connected |
| `is_streaming` | `bool` | Whether actively capturing frames |
| `settings` | `CameraSettings` | Current camera settings |
| `current_fps` | `float` | Measured frames per second |

#### Methods

##### `enumerate_cameras`

```python
@staticmethod
def enumerate_cameras(max_cameras: int = 10) -> List[CameraInfo]
```

Enumerate all available camera devices.

**Parameters:**
- `max_cameras`: Maximum number of camera indices to check

**Returns:** List of `CameraInfo` for available cameras

##### `connect`

```python
def connect(settings: Optional[CameraSettings] = None) -> bool
```

Connect to a camera with given settings.

**Parameters:**
- `settings`: Camera settings to apply, or None for defaults

**Returns:** True if connection successful

##### `disconnect`

```python
def disconnect() -> None
```

Disconnect from the current camera.

##### `start_streaming`

```python
def start_streaming() -> None
```

Start the capture thread and begin frame callbacks.

##### `stop_streaming`

```python
def stop_streaming() -> None
```

Stop the capture thread.

##### `on_frame`

```python
def on_frame(callback: Callable[[np.ndarray, float], None]) -> None
```

Register a callback for new frames.

**Parameters:**
- `callback`: Function receiving (frame, timestamp)

##### `get_frame`

```python
def get_frame() -> Optional[np.ndarray]
```

Get the most recent frame (non-blocking).

**Returns:** Frame as numpy array or None

##### `apply_settings`

```python
def apply_settings(settings: CameraSettings) -> None
```

Apply new camera settings.

---

### Dataclass: `CameraInfo`

```python
@dataclass
class CameraInfo:
    index: int                          # Camera index
    name: str                           # Display name
    resolutions: List[Tuple[int, int]]  # Supported resolutions
    max_fps: float                      # Maximum frame rate
    is_available: bool                  # Currently available
```

### Dataclass: `CameraSettings`

```python
@dataclass
class CameraSettings:
    camera_index: int = 0
    resolution: Tuple[int, int] = (640, 480)
    fps: int = 30
    exposure: int = -1          # -1 = auto
    brightness: int = 128       # 0-255
    contrast: int = 128         # 0-255
    saturation: int = 128       # 0-255
    auto_focus: bool = True
    auto_exposure: bool = True
```

### Enum: `CameraState`

```python
class CameraState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    STREAMING = auto()
    ERROR = auto()
```

---

## VideoRecorder

Records video synchronized with experiments.

### Class: `VideoRecorder`

```python
class VideoRecorder:
    """Records video from camera frames."""
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_recording` | `bool` | Whether actively recording |
| `is_paused` | `bool` | Whether recording is paused |
| `file_path` | `Optional[Path]` | Current/last recording path |
| `frame_count` | `int` | Frames recorded |
| `duration` | `float` | Recording duration in seconds |

#### Methods

##### `start`

```python
async def start(experiment_name: str = "experiment") -> Path
```

Start recording video.

**Parameters:**
- `experiment_name`: Name for the video file

**Returns:** Path to the video file being created

##### `stop`

```python
async def stop() -> Optional[Path]
```

Stop recording and finalize the video file.

**Returns:** Path to the saved video file

##### `pause` / `resume`

```python
def pause() -> None
def resume() -> None
```

Pause or resume recording.

##### `set_output_directory`

```python
def set_output_directory(path: Path) -> None
```

Set the output directory for recordings.

---

## CVProcessor

Real-time computer vision processing.

### Class: `CVProcessor`

```python
class CVProcessor:
    """Processes video frames for object detection and tracking."""
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_initialized` | `bool` | Whether processor is ready |
| `settings` | `CVSettings` | Current CV settings |

#### Methods

##### `initialize`

```python
def initialize() -> bool
```

Initialize the CV processor with current settings.

**Returns:** True if initialization successful

##### `process_frame`

```python
def process_frame(
    frame: np.ndarray,
    timestamp: float
) -> Tuple[List[Detection], List[TrackedObject], MotionResult]
```

Process a video frame.

**Parameters:**
- `frame`: BGR image as numpy array
- `timestamp`: Frame timestamp

**Returns:** Tuple of (detections, tracked_objects, motion_result)

##### `draw_overlays`

```python
def draw_overlays(
    frame: np.ndarray,
    detections: List[Detection],
    tracked: List[TrackedObject],
    motion: MotionResult
) -> np.ndarray
```

Draw detection overlays on a frame.

**Returns:** Frame with overlays drawn

##### `update_settings`

```python
def update_settings(settings: CVSettings) -> None
```

Update CV settings (may trigger reinitialization).

---

### Dataclass: `CVSettings`

```python
@dataclass
class CVSettings:
    enabled: bool = True
    backend: DetectionBackend = DetectionBackend.BACKGROUND_SUBTRACTION
    model_path: Optional[str] = None      # For YOLO
    confidence_threshold: float = 0.5
    min_detection_area: int = 500         # Minimum contour area
    motion_threshold: float = 25.0
    motion_area_threshold: float = 0.01   # 1% of frame
    tracking_enabled: bool = True
    max_disappeared: int = 50             # Frames before dropping track
    draw_overlays: bool = True
    overlay_color: Tuple[int, int, int] = (0, 255, 0)  # BGR
    overlay_thickness: int = 2
    show_labels: bool = True
    show_trails: bool = False
```

### Enum: `DetectionBackend`

```python
class DetectionBackend(Enum):
    BACKGROUND_SUBTRACTION = auto()  # Built-in, no dependencies
    MOTION_ONLY = auto()             # Simple motion detection
    YOLO_V8 = auto()                 # Requires ultralytics
```

### Dataclass: `Detection`

```python
@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, width, height
```

### Dataclass: `TrackedObject`

```python
@dataclass
class TrackedObject:
    track_id: int                        # Persistent ID
    class_name: str
    bbox: Tuple[int, int, int, int]
    confidence: float
    centroid: Tuple[int, int]
    age: int                             # Frames tracked
```

### Dataclass: `MotionResult`

```python
@dataclass
class MotionResult:
    motion_detected: bool
    motion_area: float                   # Percentage of frame
    motion_contours: List[np.ndarray]
```

---

## ObjectTracker

Centroid-based multi-object tracker.

### Class: `ObjectTracker`

```python
class ObjectTracker:
    """Tracks objects across frames using centroid matching."""
```

#### Methods

##### `update`

```python
def update(detections: List[Detection]) -> List[TrackedObject]
```

Update tracker with new detections.

**Parameters:**
- `detections`: List of detections from current frame

**Returns:** List of tracked objects with persistent IDs

##### `reset`

```python
def reset() -> None
```

Clear all tracked objects.

---

## TrackingDataLogger

Logs CV tracking results to CSV.

### Class: `TrackingDataLogger`

```python
class TrackingDataLogger:
    """Logs computer vision results to CSV file."""
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_recording` | `bool` | Whether logging is active |
| `file_path` | `Optional[Path]` | Current/last log file path |
| `frame_count` | `int` | Frames logged |

#### Methods

##### `start`

```python
async def start(experiment_name: str = "experiment") -> Path
```

Start logging tracking data.

**Returns:** Path to the log file being created

##### `stop`

```python
async def stop() -> Optional[Path]
```

Stop logging and close file.

**Returns:** Path to the saved log file

##### `log_frame`

```python
def log_frame(
    timestamp: float,
    tracked_objects: List[TrackedObject],
    motion_detected: bool = False,
    motion_area: float = 0.0
) -> None
```

Log tracking data for a single frame.

##### `log_event`

```python
def log_event(event_name: str, details: str = "") -> None
```

Log a custom event.

##### `set_output_directory`

```python
def set_output_directory(path: Path) -> None
```

Set the output directory for log files.

---

## Usage Examples

### Basic Camera Capture

```python
from glider.vision import CameraManager, CameraSettings

# Create manager
camera = CameraManager()

# List available cameras
cameras = CameraManager.enumerate_cameras()
for cam in cameras:
    print(f"{cam.index}: {cam.name} ({cam.resolutions})")

# Connect
settings = CameraSettings(camera_index=0, resolution=(1280, 720))
if camera.connect(settings):
    camera.start_streaming()

    # Process frames
    def on_frame(frame, timestamp):
        print(f"Frame at {timestamp}: {frame.shape}")

    camera.on_frame(on_frame)
```

### Computer Vision Processing

```python
from glider.vision import CVProcessor, CVSettings, DetectionBackend

# Configure CV
settings = CVSettings(
    backend=DetectionBackend.BACKGROUND_SUBTRACTION,
    confidence_threshold=0.5,
    tracking_enabled=True
)

# Create processor
cv = CVProcessor(settings)
cv.initialize()

# Process frame
def on_frame(frame, timestamp):
    detections, tracked, motion = cv.process_frame(frame, timestamp)

    for obj in tracked:
        print(f"Object {obj.track_id}: {obj.class_name} at {obj.centroid}")

    if motion.motion_detected:
        print(f"Motion: {motion.motion_area:.1%} of frame")

    # Draw overlays
    display = cv.draw_overlays(frame, detections, tracked, motion)
```

### Recording with Tracking

```python
from glider.vision import VideoRecorder, TrackingDataLogger

recorder = VideoRecorder(camera_manager)
tracker = TrackingDataLogger()

# Start recording
await recorder.start("my_experiment")
await tracker.start("my_experiment")

# ... experiment runs, frames are captured ...

# Stop recording
video_path = await recorder.stop()
tracking_path = await tracker.stop()

print(f"Video: {video_path}")
print(f"Tracking: {tracking_path}")
```

---

## See Also

- [Data Recording Guide](../user-guide/data-recording.md) - User guide for video/tracking
- [Architecture](../developer-guide/architecture.md) - Vision layer architecture
- [Builder Mode](../user-guide/builder-mode.md) - Camera panel usage
