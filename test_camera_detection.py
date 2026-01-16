"""
Camera Detection Diagnostic Script

Run this to test which backends and formats can detect your camera.
Includes specialized tests for grayscale cameras like ANYMAZE.
"""

import cv2
import sys
import time

print("=" * 60)
print("Camera Detection Diagnostic")
print("=" * 60)
print(f"OpenCV version: {cv2.__version__}")
print(f"Platform: {sys.platform}")
print(f"OpenCV build info backends: {cv2.getBuildInformation().split('Video I/O:')[1].split('Parallel framework:')[0] if 'Video I/O:' in cv2.getBuildInformation() else 'N/A'}")
print()

# Backends to try
backends = [
    (cv2.CAP_DSHOW, "DirectShow"),
    (cv2.CAP_MSMF, "MediaFoundation"),
    (cv2.CAP_ANY, "Auto"),
]

# Pixel formats to try (Y800 first since ANYMAZE uses it)
formats = [
    ("Y800", "Y800 (grayscale)"),
    ("GREY", "GREY (grayscale)"),
    ("Y8  ", "Y8 (grayscale)"),
    (None, "Default"),
    ("MJPG", "MJPG"),
    ("YUY2", "YUY2"),
]

print("Testing camera indices 0-4...")
print("This may take a minute...")
print()

found_any = False
working_configs = []


def try_grayscale_mode(cam_idx, backend_id, backend_name):
    """
    Try connecting with grayscale-specific settings.
    This mimics what GLIDER does for Y800 cameras.
    """
    try:
        cap = cv2.VideoCapture(cam_idx, backend_id)

        if not cap.isOpened():
            return None

        # Critical: disable RGB conversion FIRST
        cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Try setting Y800 format
        for fourcc_str in ["Y800", "GREY", "Y8  "]:
            try:
                fourcc = cv2.VideoWriter_fourcc(*fourcc_str[:4])
                cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            except:
                pass

        # Try grab/retrieve instead of read()
        success_count = 0
        for _ in range(5):
            if cap.grab():
                ret, frame = cap.retrieve()
                if ret and frame is not None:
                    success_count += 1
                    if success_count >= 2:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        result = {
                            'index': cam_idx,
                            'backend': backend_name,
                            'format': "Grayscale (special)",
                            'resolution': f"{w}x{h}",
                            'frame_shape': frame.shape,
                            'frame_dtype': str(frame.dtype),
                        }
                        cap.release()
                        return result
            time.sleep(0.1)

        cap.release()
        return None
    except Exception as e:
        return None


def try_mode_setting(cam_idx, backend_id, backend_name):
    """Try using CAP_PROP_MODE for format selection."""
    try:
        cap = cv2.VideoCapture(cam_idx, backend_id)
        if not cap.isOpened():
            return None

        for mode in [0, 1, 2]:
            cap.set(cv2.CAP_PROP_MODE, mode)
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)

            ret, frame = cap.read()
            if ret and frame is not None:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                result = {
                    'index': cam_idx,
                    'backend': backend_name,
                    'format': f"MODE={mode}",
                    'resolution': f"{w}x{h}",
                    'frame_shape': frame.shape,
                    'frame_dtype': str(frame.dtype),
                }
                cap.release()
                return result

        cap.release()
        return None
    except:
        return None


for cam_idx in range(5):
    print(f"=== Testing Camera Index {cam_idx} ===")
    cam_found = False

    for backend_id, backend_name in backends:
        # First: try grayscale-specific mode (most important for ANYMAZE)
        result = try_grayscale_mode(cam_idx, backend_id, backend_name)
        if result:
            print(f"  SUCCESS (Grayscale): {backend_name}")
            print(f"           Resolution: {result['resolution']}")
            print(f"           Frame shape: {result['frame_shape']}, dtype: {result['frame_dtype']}")
            working_configs.append(result)
            found_any = True
            cam_found = True
            continue

        # Second: try MODE setting
        result = try_mode_setting(cam_idx, backend_id, backend_name)
        if result:
            print(f"  SUCCESS (MODE): {backend_name} + {result['format']}")
            print(f"           Resolution: {result['resolution']}")
            print(f"           Frame shape: {result['frame_shape']}, dtype: {result['frame_dtype']}")
            working_configs.append(result)
            found_any = True
            cam_found = True
            continue

        # Third: try standard formats
        for fourcc_code, fourcc_name in formats:
            try:
                cap = cv2.VideoCapture(cam_idx, backend_id)

                if cap.isOpened():
                    # Set format if specified
                    if fourcc_code:
                        fourcc = cv2.VideoWriter_fourcc(*fourcc_code[:4])
                        cap.set(cv2.CAP_PROP_FOURCC, fourcc)

                    # Try disabling RGB conversion for grayscale cameras
                    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)

                    # Try to read a frame
                    ret, frame = cap.read()

                    if ret and frame is not None:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)

                        # Get actual fourcc
                        actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                        fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])

                        print(f"  SUCCESS: {backend_name} + {fourcc_name}")
                        print(f"           Resolution: {w}x{h}, FPS: {fps}, Format: {fourcc_str}")
                        print(f"           Frame shape: {frame.shape}, dtype: {frame.dtype}")

                        working_configs.append({
                            'index': cam_idx,
                            'backend': backend_name,
                            'format': fourcc_name,
                            'resolution': f"{w}x{h}",
                            'frame_shape': frame.shape,
                            'frame_dtype': str(frame.dtype),
                        })
                        found_any = True
                        cam_found = True

                    cap.release()

            except Exception as e:
                pass  # Silently ignore errors

    if not cam_found:
        print(f"  No working configuration found for camera {cam_idx}")

    print()

print("=" * 60)
print("SUMMARY")
print("=" * 60)

if working_configs:
    print(f"\nFound {len(working_configs)} working configuration(s):\n")
    for cfg in working_configs:
        shape_info = f", shape={cfg.get('frame_shape', 'N/A')}" if 'frame_shape' in cfg else ""
        print(f"  Camera {cfg['index']}: {cfg['backend']} + {cfg['format']} @ {cfg['resolution']}{shape_info}")

    print("\nGLIDER should be able to connect to these cameras automatically.")
    print("If you still have issues, try selecting the specific backend in Camera Settings.")
else:
    print("\nNo working configurations found!")
    print()
    print("This could mean:")
    print()
    print("1. The camera driver doesn't support standard Windows video interfaces")
    print("   - Check if the camera has a specific SDK or driver that needs to be installed")
    print("   - Some scientific cameras require their vendor's drivers")
    print()
    print("2. The camera uses a format that OpenCV doesn't support")
    print("   - Try installing a newer OpenCV: pip install opencv-python --upgrade")
    print("   - Try opencv-contrib-python for additional codec support")
    print()
    print("3. The camera might be in use by another application")
    print("   - Close any other video applications and try again")

print()
print("=" * 60)
input("Press Enter to exit...")
