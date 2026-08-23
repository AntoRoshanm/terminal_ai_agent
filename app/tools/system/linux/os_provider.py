"""
Linux System & OS Information Provider with Env Persistence Parsing
"""

import os
from pathlib import Path
import platform
import re
from typing import Any, Dict, Optional
from app.platform.contracts import SystemInfoProvider


class LinuxSystemInfoProvider(SystemInfoProvider):
    """Linux implementation for OS and environment metadata."""

    def get_os_info(self) -> Dict[str, Any]:
        os_name = "Linux"
        os_version = platform.release()
        build_number = platform.version()

        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            clean_v = v.strip().strip('"').strip("'")
                            if k.strip() == "PRETTY_NAME":
                                os_name = clean_v
                            elif k.strip() == "VERSION_ID":
                                os_version = clean_v
            except Exception:
                pass

        is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False

        return {
            "system": "Linux",
            "os_name": os_name,
            "os_version": os_version,
            "build_number": build_number,
            "architecture": platform.machine(),
            "hostname": platform.node(),
            "current_user": os.getenv("USER") or os.getenv("LOGNAME") or "unknown",
            "system_root": "/",
            "is_admin": is_root,
            "kernel_version": platform.release(),
        }

    def _parse_persisted_vars(self) -> Dict[str, str]:
        """Parse persisted variables from ~/.bashrc, ~/.profile, and /etc/environment."""
        persisted: Dict[str, str] = {}
        files_to_check = [
            Path.home() / ".bashrc",
            Path.home() / ".profile",
            Path("/etc/environment"),
        ]

        export_pattern = re.compile(r'^\s*(?:export\s+)?([a-zA-Z_][a-zA-Z0-9_]*)=["\']?(.*?)["\']?\s*$')

        for file_path in files_to_check:
            if file_path.exists() and file_path.is_file():
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            match = export_pattern.match(line)
                            if match:
                                k, v = match.groups()
                                persisted[k] = v
                except Exception:
                    pass

        return persisted

    def get_environment_info(
        self,
        var_name: Optional[str] = None,
        variable_name: Optional[str] = None,
        inspect_path: bool = False,
    ) -> Dict[str, Any]:
        env = dict(os.environ)
        target_var = var_name or variable_name
        persisted = self._parse_persisted_vars()

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
                "persisted_value": persisted.get(target_var),
            }

        res = dict(env)
        path_entries = [p for p in env.get("PATH", "").split(os.pathsep) if p]
        res["total_variables"] = len(env)
        res["path_entries_count"] = len(path_entries)
        res["path_entries"] = path_entries
        res["persisted_variables"] = persisted
        return res
