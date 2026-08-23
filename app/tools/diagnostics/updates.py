"""
Windows and Linux System Updates Inspection Tool
"""

from typing import Any, Dict, List
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetUpdateStatusTool(BaseTool):
    """Tool to inspect installed OS updates, Hotfixes, and security patches."""

    name = "diagnostics_get_update_status"
    description = "Query installed Hotfixes/patches or available package updates on Windows and Linux."
    category = "diagnostics"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY
    timeout_seconds = 15

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of updates to return (default: 10)",
                    "default": 10,
                },
            },
            "additionalProperties": False,
        }

    def _run(self, limit: int = 10) -> Any:
        provider = SystemProviderFactory.get_diagnostics_provider()
        res = provider.check_updates()
        if isinstance(res, dict) and "updates" in res:
            return res["updates"][:limit]
        return res
