"""
Windows and Linux Event/System Logs Inspection Tool
"""

from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetEventLogsTool(BaseTool):
    """Tool to query Event Viewer / Journalctl logs for crashes, errors, and warnings."""

    name = "diagnostics_get_event_logs"
    description = "Query system event logs (Windows Event Viewer / Linux journalctl) for errors and warnings."
    category = "diagnostics"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY
    timeout_seconds = 15

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "log_name": {
                    "type": "string",
                    "description": "Log channel: 'Application' or 'System' (default: 'Application')",
                    "enum": ["Application", "System"],
                    "default": "Application",
                },
                "level": {
                    "type": "string",
                    "description": "Severity level: 'Error', 'Warning', or 'Critical' (default: 'Error')",
                    "enum": ["Error", "Warning", "Critical"],
                    "default": "Error",
                },
                "hours": {
                    "type": "integer",
                    "description": "Lookback period in hours (default: 24)",
                    "default": 24,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of events to retrieve (default: 15)",
                    "default": 15,
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        log_name: str = "Application",
        level: str = "Error",
        hours: int = 24,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        return SystemProviderFactory.get_diagnostics_provider().query_event_log(
            channel=log_name, limit=limit, level=level
        )
