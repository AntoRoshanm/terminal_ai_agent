"""
Operating System Information Inspection Tool
"""

from typing import Any, Dict
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetOSInfoTool(BaseTool):
    """Tool to inspect Operating System version, build, architecture, and user."""

    name = "get_os_info"
    description = "Get detailed Operating System information including name, version, build number, and architecture."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def _run(self) -> Dict[str, Any]:
        return SystemProviderFactory.get_system_info_provider().get_os_info()
