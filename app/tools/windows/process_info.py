"""
Process Information and Resource Usage Tool
"""

from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetProcessInfoTool(BaseTool):
    """Tool to inspect running processes and resource utilization."""

    name = "get_process_info"
    description = "List running processes sorted by memory or CPU usage, with optional name filtering."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional process name filter (e.g. 'python', 'chrome', 'postgres', 'docker')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of processes to return (default: 20)",
                    "default": 20,
                },
                "sort_by": {
                    "type": "string",
                    "description": "Metric to sort by: 'memory' or 'cpu' (default: 'memory')",
                    "enum": ["memory", "cpu"],
                    "default": "memory",
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self, query: Optional[str] = None, limit: int = 20, sort_by: str = "memory"
    ) -> List[Dict[str, Any]]:
        return SystemProviderFactory.get_process_provider().get_process_info(
            query=query, limit=limit, sort_by=sort_by
        )
