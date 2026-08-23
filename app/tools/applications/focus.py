"""
Window Focus and Application Status Tools
"""

from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class FocusWindowTool(BaseTool):
    """Tool to bring an application window to the foreground."""

    name = "app_focus_window"
    description = "Restore and bring a specific desktop application window to the front by HWND or title."
    category = "applications"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hwnd": {
                    "type": "integer",
                    "description": "The HWND/window handle to bring to the foreground",
                },
                "window_title": {
                    "type": "string",
                    "description": "Optional title search string to find window if handle is not known",
                },
            },
            "additionalProperties": False,
        }

    def _run(self, hwnd: Optional[int] = None, window_title: Optional[str] = None) -> Dict[str, Any]:
        return SystemProviderFactory.get_gui_provider().focus_window(
            title=window_title, hwnd=hwnd
        )


class GetApplicationStatusTool(BaseTool):
    """Tool to inspect runtime status, windows, and responsiveness of an application."""

    name = "app_get_status"
    description = "Check if an application is running, find its open windows, and memory consumption."
    category = "applications"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "process_name": {
                    "type": "string",
                    "description": "Process name to check (e.g. 'notepad', 'chrome', 'code')",
                },
                "pid": {
                    "type": "integer",
                    "description": "Optional PID to check directly",
                },
            },
            "additionalProperties": False,
        }

    def _run(self, process_name: Optional[str] = None, pid: Optional[int] = None) -> Dict[str, Any]:
        return SystemProviderFactory.get_gui_provider().get_app_status(
            process_name=process_name, pid=pid
        )
