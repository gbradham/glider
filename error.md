 # Check if camera is detected by the system
  lsusb | grep -i cam

  # List video devices
  ls -la /dev/video*

  # Check your user is in video group
  groups

  # Check what formats the camera supports
  v4l2-ctl --list-formats-ext -d /dev/video0

  # Try capturing a single frame with ffmpeg
  ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 test.jpg

  Also, USB webcams with ring lights draw a lot of power. If you're powering the Pi with a weak supply or using an unpowered USB hub, the camera might be browning out. Try:
  - Using a powered USB hub
  - Plugging directly into the Pi (not through a hub)
  - Using a 3A+ power supply for the Pi