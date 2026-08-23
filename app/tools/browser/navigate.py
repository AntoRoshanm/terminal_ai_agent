"""
Default Desktop Browser Navigation Tool
"""

from typing import Any, Dict
import webbrowser
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class OpenBrowserTool(BaseTool):
    """Tool to open a URL in the user's default Windows web browser."""

    name = "browser_open"
    description = "Open a URL in the user's default desktop web browser (e.g. Edge, Chrome, Firefox)."
    category = "browser"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to open in the browser",
                },
                "new_tab": {
                    "type": "boolean",
                    "description": "Whether to open in a new tab/window (default: true)",
                    "default": True,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        }

    def _run(self, url: str, new_tab: bool = True) -> Dict[str, Any]:
        target_url = url.strip()
        if not target_url.startswith(("http://", "https://", "file://")):
            target_url = "https://" + target_url

        try:
            opened = webbrowser.open(target_url, new=2 if new_tab else 0)
            return {
                "url": target_url,
                "opened": opened,
                "status": "opened" if opened else "browser_invoked",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to open browser for '{target_url}': {str(e)}")
