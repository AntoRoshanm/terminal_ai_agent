"""
Application Management Tools Subsystem
"""

from app.tools.applications.focus import FocusWindowTool, GetApplicationStatusTool
from app.tools.applications.lifecycle import CloseApplicationTool, LaunchApplicationTool
from app.tools.applications.windows_mgr import ListWindowsTool
from app.tools.registry import ToolRegistry

__all__ = [
    "ListWindowsTool",
    "LaunchApplicationTool",
    "CloseApplicationTool",
    "FocusWindowTool",
    "GetApplicationStatusTool",
    "register_application_tools",
]


def register_application_tools(registry: ToolRegistry) -> None:
    """Register application management tools into the registry."""
    registry.register(ListWindowsTool())
    registry.register(LaunchApplicationTool())
    registry.register(CloseApplicationTool())
    registry.register(FocusWindowTool())
    registry.register(GetApplicationStatusTool())
