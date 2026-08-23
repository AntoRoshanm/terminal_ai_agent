"""
System Background Services Information Tool
"""

from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetServiceInfoTool(BaseTool):
    """Tool to inspect system background services and statuses."""

    name = "get_service_info"
    description = "List system background services, display names, execution statuses, and startup types."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search string to filter services by name or display name",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of services to return (default: 30)",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self, query: Optional[str] = None, limit: int = 30
    ) -> List[Dict[str, Any]]:
        return SystemProviderFactory.get_service_provider().get_service_info(
            query=query, limit=limit
        )


class ManageSystemServiceTool(BaseTool):
    """Tool to manage system background services (start, stop, restart, enable, disable)."""

    name = "manage_service"
    description = "Manage system background services: start, stop, restart, enable, or disable Windows/system services."
    category = "system"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the system service (e.g. 'Spooler', 'wuauserv')",
                },
                "service_name": {
                    "type": "string",
                    "description": "Alternative service name parameter",
                },
                "action": {
                    "type": "string",
                    "description": "Action to perform: 'start', 'stop', 'restart', 'enable', 'disable' (default: 'restart')",
                    "enum": ["start", "stop", "restart", "enable", "disable"],
                    "default": "restart",
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        name: Optional[str] = None,
        service_name: Optional[str] = None,
        action: str = "restart",
    ) -> Dict[str, Any]:
        target = name or service_name or "Spooler"
        return SystemProviderFactory.get_service_provider().manage_service(
            name=target, action=action
        )
