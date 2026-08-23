"""
Desktop Application Lifecycle Management (Launch & Close)
"""

from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class LaunchApplicationTool(BaseTool):
    """Tool to launch desktop applications, files, or URIs."""

    name = "app_launch"
    description = "Launch an application, document, or system tool."
    category = "applications"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Application executable, file path, or URI protocol to launch",
                },
                "arguments": {
                    "type": "string",
                    "description": "Optional command-line arguments to pass to the application",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Optional working directory for the application",
                },
            },
            "required": ["target"],
            "additionalProperties": False,
        }

    def _run(
        self,
        target: str,
        arguments: Optional[str] = None,
        working_directory: Optional[str] = None,
    ) -> Dict[str, Any]:
        args = [arguments] if arguments else None
        return SystemProviderFactory.get_gui_provider().launch_app(
            target=target, args=args
        )


class CloseApplicationTool(BaseTool):
    """Tool to close or terminate desktop applications."""

    name = "app_close"
    description = "Close or terminate an active desktop application by process name, PID, or HWND. Requires user approval."
    category = "applications"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "process_name": {
                    "type": "string",
                    "description": "Name of the process to close (e.g. 'notepad', 'calc', 'chrome')",
                },
                "pid": {
                    "type": "integer",
                    "description": "Process ID to terminate",
                },
                "hwnd": {
                    "type": "integer",
                    "description": "Window handle to gracefully close",
                },
                "force": {
                    "type": "boolean",
                    "description": "Whether to forcefully terminate the process (default: false)",
                    "default": False,
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        process_name: Optional[str] = None,
        pid: Optional[int] = None,
        hwnd: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        return SystemProviderFactory.get_gui_provider().close_app(
            process_name=process_name, pid=pid, force=force
        )
