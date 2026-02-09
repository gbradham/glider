"""Real-time miniscope streaming using OpenCV with LED control."""

import cv2
import threading


class FrameGrabber(threading.Thread):
    """Threaded frame grabber for lower latency."""

    def __init__(self, cap):
        super().__init__(daemon=True)
        self.cap = cap
        self.frame = None
        self.running = True
        self.lock = threading.Lock()

    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False


def create_miniscope_command(i2c_addr, *data_bytes):
    """
    Create a 64-bit command for miniscope firmware.
    Format matches Bonsai.Miniscope Helpers.CreateCommand() exactly.
    """
    command = i2c_addr

    if len(data_bytes) == 5:
        # Full 6-byte package: set address LSB to 1
        command |= 0x01
        for i, byte in enumerate(data_bytes):
            command |= (byte & 0xFF) << (8 * (i + 1))
    else:
        # Partial package: encode (length + 1) in second byte
        command |= ((len(data_bytes) + 1) << 8)
        for i, byte in enumerate(data_bytes):
            command |= (byte & 0xFF) << (8 * (i + 2))

    return command


def send_miniscope_config(cap, command, debug=False):
    """
    Send command to miniscope by splitting across Contrast/Gamma/Sharpness.
    This matches the Bonsai.Miniscope SendConfig implementation exactly.
    """
    # Split 64-bit command into three 16-bit values
    # Bonsai order: Contrast (bits 0-15), Gamma (bits 16-31), Sharpness (bits 32-47)
    contrast_val = command & 0xFFFF
    gamma_val = (command >> 16) & 0xFFFF
    sharpness_val = (command >> 32) & 0xFFFF

    # Send via camera properties in correct order (Contrast, Gamma, Sharpness)
    r1 = cap.set(cv2.CAP_PROP_CONTRAST, contrast_val)
    r2 = cap.set(cv2.CAP_PROP_GAMMA, gamma_val)
    r3 = cap.set(cv2.CAP_PROP_SHARPNESS, sharpness_val)

    if debug:
        print(f"    Contrast={contrast_val} ({r1}), Gamma={gamma_val} ({r2}), Sharp={sharpness_val} ({r3})")


def set_led(cap, brightness, debug=True):
    """
    Set miniscope LED brightness (0-100).
    Uses I2C commands sent via camera properties.
    """
    brightness = max(0, min(100, brightness))

    # Convert to 0-255 and invert (miniscope uses inverted scale)
    value = int(255 - (brightness * 2.55))

    if debug:
        print(f"  LED value (inverted): {value}")

    # Send to ATTINY MCU (I2C address 32 = 0x20)
    cmd1 = create_miniscope_command(32, 1, value)
    if debug:
        print(f"  CMD1 (addr 32): 0x{cmd1:012X}")
    send_miniscope_config(cap, cmd1, debug)

    # Also send to digital pot (I2C address 88 = 0x58)
    cmd2 = create_miniscope_command(88, 0, 114, value)
    if debug:
        print(f"  CMD2 (addr 88): 0x{cmd2:012X}")
    send_miniscope_config(cap, cmd2, debug)

    return True


def init_ewl(cap, debug=True):
    """
    Initialize the EWL (Electrowetting Lens) driver.
    Must be called before set_ewl().
    """
    # Initialize MAX14574 EWL driver (I2C address 238 = 0xEE)
    cmd = create_miniscope_command(238, 3, 3)
    if debug:
        print(f"  EWL init: 0x{cmd:012X}")
    send_miniscope_config(cap, cmd, debug)
    return True


def set_ewl(cap, focus, debug=True):
    """
    Set EWL focus (-127 to +127).
    0 is neutral, negative values focus closer, positive focus farther.
    """
    focus = max(-127, min(127, focus))

    # Convert to byte value (127 + focus gives 0-254 range)
    value = 127 + focus

    if debug:
        print(f"  EWL focus: {focus} (value: {value})")

    # Send to MAX14574 EWL driver (I2C address 238 = 0xEE)
    cmd = create_miniscope_command(238, 8, value, 2)
    if debug:
        print(f"  EWL cmd: 0x{cmd:012X}")
    send_miniscope_config(cap, cmd, debug)

    return True


def list_cameras():
    """List all available cameras with their info."""
    print("Scanning cameras...")
    cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cameras.append((i, w, h))
            print(f"  Camera {i}: {w}x{h}")
            cap.release()
    return cameras


def print_controls():
    """Print available keyboard controls."""
    print("\nControls:")
    print("  q      - Quit")
    print("  l/k    - Increase/decrease LED brightness (0-100)")
    print("  w/s    - Increase/decrease EWL focus (-127 to +127)")
    print("  r      - Reset to defaults")
    print("  i      - Show current settings")
    print("  0-9    - Switch camera")
    print()


def show_settings(cap, led=0, ewl=0):
    """Display current camera settings."""
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)])
    print("\nCurrent settings:")
    print(f"  Format:     {fourcc_str}")
    print(f"  LED:        {led}%")
    print(f"  EWL:        {ewl}")
    print(f"  Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")


def open_camera(index, backend=cv2.CAP_DSHOW):
    """Open camera with optimized settings."""
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        return None

    # Set YUY2 format (required for miniscope)
    fourcc = cv2.VideoWriter_fourcc(*"YUY2")
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)

    # Set resolution to 608x608
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 608)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 608)

    # Reduce buffer for lower latency
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    return cap


def try_backends(index):
    """Try different backends to open camera."""
    backends = [
        (cv2.CAP_DSHOW, "DirectShow"),
        (cv2.CAP_MSMF, "Media Foundation"),
        (cv2.CAP_ANY, "Auto"),
    ]
    for backend, name in backends:
        print(f"Trying {name} backend...")
        cap = open_camera(index, backend)
        if cap is not None:
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"  {name} works! Got frame.")
                return cap, name
            cap.release()
            print(f"  {name} opened but can't read frames")
        else:
            print(f"  {name} failed to open")
    return None, None


def main():
    cameras = list_cameras()
    if not cameras:
        print("No cameras found")
        return

    # Find miniscope (not 1920x1080 webcam)
    camera_index = cameras[0][0]
    for idx, w, h in cameras:
        if w != 1920 and h != 1080:
            camera_index = idx
            print(f"\nSelected camera {idx} ({w}x{h}) - likely miniscope")
            break

    cap, backend_name = try_backends(camera_index)
    if cap is None:
        print("Failed to open camera")
        return
    print(f"Using {backend_name} backend")

    led = 0
    ewl = 0

    # Initialize EWL driver
    print("\nInitializing EWL...")
    init_ewl(cap)
    set_ewl(cap, ewl, debug=False)

    print_controls()
    show_settings(cap, led, ewl)
    print(f"\nStreaming camera {camera_index}... Press 'q' to quit")

    # Start threaded grabber
    grabber = FrameGrabber(cap)
    grabber.start()

    frame_count = 0
    while True:
        frame = grabber.get_frame()
        if frame is not None:
            frame_count += 1
            if frame_count == 1:
                print(f"First frame! Shape: {frame.shape}")
            cv2.imshow("Miniscope", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("l"):
            led = min(led + 5, 100)
            print(f"LED: {led}%")
            set_led(cap, led)
        elif key == ord("k"):
            led = max(led - 5, 0)
            print(f"LED: {led}%")
            set_led(cap, led)
        elif key == ord("w"):
            ewl = min(ewl + 10, 127)
            print(f"EWL: {ewl}")
            set_ewl(cap, ewl)
        elif key == ord("s"):
            ewl = max(ewl - 10, -127)
            print(f"EWL: {ewl}")
            set_ewl(cap, ewl)
        elif key == ord("r"):
            led = 0
            ewl = 0
            set_led(cap, led)
            set_ewl(cap, ewl)
            print("Reset")
        elif key == ord("i"):
            show_settings(cap, led, ewl)
        elif ord("0") <= key <= ord("9"):
            new_idx = key - ord("0")
            grabber.stop()
            cap.release()
            new_cap, new_backend = try_backends(new_idx)
            if new_cap:
                cap = new_cap
                camera_index = new_idx
                grabber = FrameGrabber(cap)
                grabber.start()
                frame_count = 0
                print(f"Switched to camera {new_idx}")
            else:
                print(f"Camera {new_idx} unavailable")
                cap, _ = try_backends(camera_index)
                grabber = FrameGrabber(cap)
                grabber.start()

    grabber.stop()
    set_led(cap, 0, debug=False)
    set_ewl(cap, 0, debug=False)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
