"""
System Diagnostics and Troubleshooting Tools Subsystem
"""

from app.tools.diagnostics.cleanup import SafeCleanupTool
from app.tools.diagnostics.event_log import GetEventLogsTool
from app.tools.diagnostics.health import GetSystemHealthTool
from app.tools.diagnostics.updates import GetUpdateStatusTool
from app.tools.registry import ToolRegistry

__all__ = [
    "GetEventLogsTool",
    "GetSystemHealthTool",
    "SafeCleanupTool",
    "GetUpdateStatusTool",
    "register_diagnostics_tools",
]


def register_diagnostics_tools(registry: ToolRegistry) -> None:
    """Register system diagnostics tools into the registry."""
    registry.register(GetEventLogsTool())
    registry.register(GetSystemHealthTool())
    registry.register(SafeCleanupTool())
    registry.register(GetUpdateStatusTool())
