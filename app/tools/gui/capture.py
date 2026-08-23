"""
Cross-Platform Screen Capture Tool
"""

from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class CaptureScreenshotTool(BaseTool):
    """Tool to capture full desktop screenshots across Windows & Linux."""

    name = "gui_take_screenshot"
    description = "Capture a screenshot of the primary desktop or display and save it as a PNG file."
    category = "gui"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY
    timeout_seconds = 15

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "output_path": {
                    "type": "string",
                    "description": "Optional custom file path to save the PNG screenshot",
                },
            },
            "additionalProperties": False,
        }

    def _run(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        return SystemProviderFactory.get_gui_provider().capture_screenshot(
            output_path=output_path
        )
