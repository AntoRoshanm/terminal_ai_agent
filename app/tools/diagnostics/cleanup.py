"""
Safe Temporary Cache and Junk File Cleanup Tool
"""

from typing import Any, Dict
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class SafeCleanupTool(BaseTool):
    """Tool to safely scan and clean user temporary cache directories."""

    name = "diagnostics_safe_cleanup"
    description = (
        "Scan or clean user temporary directories to free up disk space. "
        "Supports dry_run preview. Deletion requires user approval."
    )
    category = "diagnostics"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, only calculates reclaimable space without deleting files (default: true)",
                    "default": True,
                },
                "older_than_days": {
                    "type": "integer",
                    "description": "Only clean files older than N days (default: 1)",
                    "default": 1,
                },
            },
            "additionalProperties": False,
        }

    def _run(self, dry_run: bool = True, older_than_days: int = 1) -> Dict[str, Any]:
        return SystemProviderFactory.get_diagnostics_provider().clean_temp(dry_run=dry_run)
