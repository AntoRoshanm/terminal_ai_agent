"""
Installed Software and Application Inventory Tool
"""

from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetInstalledSoftwareTool(BaseTool):
    """Tool to inspect installed software across system application repositories."""

    name = "get_installed_software"
    description = "Search and list installed applications, versions, and publishers."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search string to filter software by name or publisher (e.g. 'Python', 'Git', 'VS Code', 'PostgreSQL', 'Docker')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of applications to return (default: 40)",
                    "default": 40,
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self, query: Optional[str] = None, limit: int = 40
    ) -> List[Dict[str, Any]]:
        return SystemProviderFactory.get_software_provider().get_installed_software(
            query=query, limit=limit
        )
