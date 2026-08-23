"""
Storage and Disk Volume Information Tool
"""

from typing import Any, Dict, List
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetStorageInfoTool(BaseTool):
    """Tool to inspect logical disk drives, storage capacity, and free space."""

    name = "get_storage_info"
    description = "Inspect storage volumes, drive letters/mounts, total space, used space, and free capacity."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def _run(self) -> List[Dict[str, Any]]:
        return SystemProviderFactory.get_storage_info_provider().get_storage_info()
