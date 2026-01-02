 # Test with ffmpeg using MJPG
  ffmpeg -f v4l2 -input_format mjpeg -i /dev/video0 -frames:v 1 test.jpg

  If that works, try this Python test:

  import cv2

  cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

  # Force MJPG format
  fourcc = cv2.VideoWriter_fourcc(*'MJPG')
  cap.set(cv2.CAP_PROP_FOURCC, fourcc)
  cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
  cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

  # Try to read
  for i in range(10):
      ret, frame = cap.read()
      print(f"Attempt {i}: ret={ret}, frame shape={frame.shape if ret else None}")
      if ret:
          cv2.imwrite("test_frame.jpg", frame)
          print("Success! Saved test_frame.jpg")
          break

  cap.release()