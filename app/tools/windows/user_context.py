"""
Windows User and Privilege Context Inspection Tool
"""

import ctypes
import os
import subprocess
from typing import Any, Dict
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class GetUserContextTool(BaseTool):
    """Tool to inspect current Windows user, domain, SID, and administrative privileges."""

    name = "get_user_context"
    description = "Get current username, domain, home directory, and check if running with Administrator privileges."
    category = "windows_system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def _is_admin(self) -> bool:
        """Check if current process has elevated administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _run(self) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "username": os.environ.get("USERNAME", "Unknown"),
            "user_domain": os.environ.get("USERDOMAIN", "Unknown"),
            "user_profile": os.environ.get("USERPROFILE", "Unknown"),
            "is_elevated_admin": self._is_admin(),
        }

        # Query user SID via whoami /user
        try:
            res = subprocess.run(
                ["whoami.exe", "/user", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip(' "\r\n') for p in res.stdout.strip().split(",")]
                if len(parts) >= 2:
                    context["user_account"] = parts[0]
                    context["user_sid"] = parts[1]
        except Exception:
            pass

        return context
