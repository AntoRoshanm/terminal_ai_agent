"""
Windows Native Inspection Tools Subsystem
"""

from app.tools.registry import ToolRegistry
from app.tools.system.datetime_tool import GetCurrentDateTimeTool
from app.tools.windows.env_info import GetEnvInfoTool
from app.tools.windows.hardware_info import GetHardwareInfoTool
from app.tools.windows.installed_software import GetInstalledSoftwareTool
from app.tools.windows.network_info import GetNetworkInfoTool
from app.tools.windows.os_info import GetOSInfoTool
from app.tools.windows.process_info import GetProcessInfoTool
from app.tools.windows.service_info import GetServiceInfoTool, ManageSystemServiceTool
from app.tools.windows.storage_info import GetStorageInfoTool
from app.tools.windows.user_context import GetUserContextTool

__all__ = [
    "GetCurrentDateTimeTool",
    "GetOSInfoTool",
    "GetHardwareInfoTool",
    "GetStorageInfoTool",
    "GetEnvInfoTool",
    "GetProcessInfoTool",
    "GetServiceInfoTool",
    "ManageSystemServiceTool",
    "GetNetworkInfoTool",
    "GetInstalledSoftwareTool",
    "GetUserContextTool",
    "register_windows_tools",
]


def register_windows_tools(registry: ToolRegistry) -> None:
    """Register all Phase 2 Windows inspection and management tools into the registry."""
    registry.register(GetCurrentDateTimeTool())
    registry.register(GetOSInfoTool())
    registry.register(GetHardwareInfoTool())
    registry.register(GetStorageInfoTool())
    registry.register(GetEnvInfoTool())
    registry.register(GetProcessInfoTool())
    registry.register(GetServiceInfoTool())
    registry.register(ManageSystemServiceTool())
    registry.register(GetNetworkInfoTool())
    registry.register(GetInstalledSoftwareTool())
    registry.register(GetUserContextTool())
