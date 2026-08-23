"""
Computer Vision and GUI Automation Tools Subsystem
"""

from app.tools.gui.capture import CaptureScreenshotTool
from app.tools.gui.input import GUISendInputTool, KeyboardTypeTool, MouseClickTool, MouseScrollTool
from app.tools.gui.vision import AnalyzeScreenStateTool
from app.tools.registry import ToolRegistry

__all__ = [
    "CaptureScreenshotTool",
    "AnalyzeScreenStateTool",
    "MouseClickTool",
    "MouseScrollTool",
    "KeyboardTypeTool",
    "GUISendInputTool",
    "register_gui_tools",
]


def register_gui_tools(registry: ToolRegistry) -> None:
    """Register GUI perception and input tools into the registry."""
    registry.register(CaptureScreenshotTool())
    registry.register(AnalyzeScreenStateTool())
    registry.register(MouseClickTool())
    registry.register(MouseScrollTool())
    registry.register(KeyboardTypeTool())
    registry.register(GUISendInputTool())
