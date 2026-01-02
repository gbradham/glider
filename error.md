Traceback (most recent call last):
  File "<frozen runpy>", line 189, in _run_module_as_main
  File "<frozen runpy>", line 148, in _get_module_details
  File "<frozen runpy>", line 112, in _get_module_details
  File "/home/RP3/glider/src/glider/__init__.py", line 11, in <module>
    from glider.core.glider_core import GliderCore
  File "/home/RP3/glider/src/glider/core/__init__.py", line 9, in <module>
    from glider.core.glider_core import GliderCore
  File "/home/RP3/glider/src/glider/core/glider_core.py", line 19, in <module>
    from glider.vision.camera_manager import CameraManager
  File "/home/RP3/glider/src/glider/vision/__init__.py", line 12, in <module>
    from glider.vision.camera_manager import (
  File "/home/RP3/glider/src/glider/vision/camera_manager.py", line 46, in <module>
    from picamera2 import Picamera2
  File "/usr/lib/python3/dist-packages/picamera2/__init__.py", line 11, in <module>
    from .picamera2 import Picamera2, Preview
  File "/usr/lib/python3/dist-packages/picamera2/picamera2.py", line 30, in <module>
    from picamera2.encoders import Encoder, H264Encoder, MJPEGEncoder, Quality
  File "/usr/lib/python3/dist-packages/picamera2/encoders/__init__.py", line 7, in <module>
    from .encoder import Encoder, Quality
  File "/usr/lib/python3/dist-packages/picamera2/encoders/encoder.py", line 13, in <module>
    from ..request import _MappedBuffer
  File "/usr/lib/python3/dist-packages/picamera2/request.py", line 13, in <module>
    import simplejpeg
  File "/usr/lib/python3/dist-packages/simplejpeg/__init__.py", line 1, in <module>
    from ._jpeg import encode_jpeg, encode_jpeg_yuv_planes
  File "simplejpeg/_jpeg.pyx", line 1, in init simplejpeg._jpeg
ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject

