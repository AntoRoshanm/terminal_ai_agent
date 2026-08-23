"""
Network Interface and Adapter Information Tool
"""

from typing import Any, Dict
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetNetworkInfoTool(BaseTool):
    """Tool to inspect network adapters, IP addresses, and DNS configuration."""

    name = "get_network_info"
    description = "Get detailed network configuration including active network adapters, IP addresses, gateways, and DNS."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def _run(self) -> Dict[str, Any]:
        return SystemProviderFactory.get_network_info_provider().get_network_info()
