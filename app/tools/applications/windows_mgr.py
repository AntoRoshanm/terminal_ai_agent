"""
Desktop Window Enumeration Tool
"""

from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class ListWindowsTool(BaseTool):
    """Tool to enumerate visible desktop windows across Windows & Linux."""

    name = "app_list_windows"
    description = "List visible open application windows on the desktop, including titles, process IDs, and HWNDs."
    category = "applications"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title_filter": {
                    "type": "string",
                    "description": "Optional search string to filter windows by title (e.g. 'Chrome', 'Notepad', 'Visual Studio')",
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Whether to include non-visible background windows (default: false)",
                    "default": False,
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self, title_filter: Optional[str] = None, include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        return SystemProviderFactory.get_gui_provider().list_windows(
            title_filter=title_filter, include_hidden=include_hidden
        )
