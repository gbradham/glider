 To actually fix the picamera2/numpy conflict on your Pi, try:

  # Option 1: Reinstall simplejpeg
  pip install --force-reinstall simplejpeg

  # Option 2: If that fails, reinstall numpy to match
  pip install --force-reinstall numpy

  # Option 3: Use system packages consistently
  sudo apt install --reinstall python3-numpy python3-simplejpeg

  The root cause is that numpy was upgraded but simplejpeg was compiled against an older version.