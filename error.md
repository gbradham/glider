sudo apt install libgstreamer1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good

  # Make sure OpenCV was built with GStreamer support
  python -c "import cv2; print(cv2.getBuildInformation())" | grep GStreamer

  If GStreamer shows NO, you may need to reinstall opencv-python with GStreamer support:
  pip uninstall opencv-python
  pip install opencv-python-headless  # or build from source with GStreamer