"""
Windows System & OS Information Provider
"""

import os
import platform
import subprocess
import sys
from typing import Any, Dict, Optional
from app.platform.contracts import SystemInfoProvider


class WindowsSystemInfoProvider(SystemInfoProvider):
    """Windows implementation for OS and environment metadata."""

    def get_os_info(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "system": "Windows",
            "os_name": "Windows",
            "os_version": platform.version(),
            "build_number": "",
            "architecture": platform.machine(),
            "hostname": platform.node(),
            "current_user": os.getenv("USERNAME", "Unknown"),
            "system_root": os.getenv("SystemRoot", "C:\\Windows"),
            "is_admin": False,
        }

        if sys.platform == "win32":
            try:
                import ctypes
                info["is_admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
            except Exception:
                pass

            try:
                win_ver = sys.getwindowsversion()
                info["os_version"] = f"{win_ver.major}.{win_ver.minor}.{win_ver.build}"
                info["build_number"] = str(win_ver.build)
                edition = "Windows 11" if win_ver.build >= 22000 else f"Windows {win_ver.major}"
                info["os_name"] = f"{edition} ({platform.win32_edition() or 'Standard'})"
            except Exception:
                pass

        return info

    def get_environment_info(
        self,
        var_name: Optional[str] = None,
        variable_name: Optional[str] = None,
        inspect_path: bool = False,
    ) -> Dict[str, Any]:
        env = dict(os.environ)
        target_var = var_name or variable_name

        if inspect_path:
            path_entries = [p for p in env.get("PATH", "").split(os.pathsep) if p]
            return {
                "count": len(path_entries),
                "path_entries": path_entries,
            }

        if target_var:
            val = env.get(target_var)
            return {
                "variable": target_var,
                "value": val,
                "found": val is not None,
                "exists": val is not None,
            }

        # Return full dictionary with summary metadata for compatibility
        res = dict(env)
        path_entries = [p for p in env.get("PATH", "").split(os.pathsep) if p]
        res["total_variables"] = len(env)
        res["path_entries_count"] = len(path_entries)
        res["path_entries"] = path_entries
        return res
