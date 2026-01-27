"""
GLIDER Dialog Components.

Contains dialog windows for:
- Custom Device Editor
- Flow Function Editor
- Camera Settings
"""

from glider.gui.dialogs.camera_settings_dialog import CameraSettingsDialog
from glider.gui.dialogs.custom_device_dialog import CustomDeviceDialog
from glider.gui.dialogs.flow_function_dialog import FlowFunctionDialog

__all__ = [
    "CustomDeviceDialog",
    "FlowFunctionDialog",
    "CameraSettingsDialog",
]
