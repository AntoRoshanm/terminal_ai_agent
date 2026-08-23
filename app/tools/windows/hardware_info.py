"""
Hardware Information Inspection Tool
"""

from typing import Any, Dict
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetHardwareInfoTool(BaseTool):
    """Tool to inspect CPU, RAM, and GPU hardware metrics."""

    name = "get_hardware_info"
    description = "Get detailed hardware specifications including RAM usage, CPU architecture/cores, and GPU status."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def _run(self) -> Dict[str, Any]:
        return SystemProviderFactory.get_hardware_info_provider().get_hardware_info()
