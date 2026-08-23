"""
System Health, CPU/RAM Metrics, and Runaway Process Inspector Tool
"""

from typing import Any, Dict
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetSystemHealthTool(BaseTool):
    """Tool to inspect overall system health, resource loads, and runaway processes."""

    name = "diagnostics_get_system_health"
    description = "Inspect real-time CPU utilization, RAM pressure, top consuming processes, and detect hung applications."
    category = "diagnostics"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY
    timeout_seconds = 15

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def _run(self) -> Dict[str, Any]:
        return SystemProviderFactory.get_diagnostics_provider().get_system_health()
