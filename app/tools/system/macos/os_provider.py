"""
macOS System and Environment Information Provider
"""

import getpass
import os
from pathlib import Path
import platform
import socket
import subprocess
import time
from typing import Any, Dict, Optional
from app.models.state import PlatformInfo
from app.platform.contracts import SystemInfoProvider
from app.platform.detect import get_platform_info


class MacOSSystemInfoProvider(SystemInfoProvider):
    """macOS implementation for OS metadata, user context, and environment."""

    def __init__(self, platform_info: Optional[PlatformInfo] = None):
        self._platform_info = platform_info

    def get_os_info(self) -> Dict[str, Any]:
        info = self._platform_info or get_platform_info()
        uptime_sec = 0.0

        # Try sysctl for boot time
        try:
            res = subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and "sec =" in res.stdout:
                # Format: { sec = 1716380000, usec = 0 }
                parts = res.stdout.split("sec =")[1].split(",")[0].strip()
                boot_epoch = int(parts)
                uptime_sec = round(time.time() - boot_epoch, 2)
        except Exception:
            pass

        return {
            "os_name": info.os_name,
            "os_version": info.os_version,
            "kernel_version": info.kernel_version,
            "architecture": info.architecture,
            "hostname": socket.gethostname(),
            "current_user": getpass.getuser(),
            "is_admin": info.is_admin_or_root,
            "system_root": "/",
            "uptime_seconds": uptime_sec,
            "sip_enabled": info.sip_enabled,
            "is_apple_silicon": info.is_apple_silicon,
            "is_rosetta_translated": info.is_rosetta_translated,
        }

    def get_environment_info(self, var_name: Optional[str] = None) -> Dict[str, Any]:
        env_vars = dict(os.environ)
        if var_name:
            return {
                "variable": var_name,
                "value": env_vars.get(var_name),
                "is_defined": var_name in env_vars,
            }

        path_entries = [p for p in env_vars.get("PATH", "").split(":") if p]
        persisted = self._parse_persisted_vars()

        return {
            "total_variables": len(env_vars),
            "environment_variables": env_vars,
            "path_entries_count": len(path_entries),
            "path_entries": path_entries,
            "persisted_variables": persisted,
        }

    def _parse_persisted_vars(self) -> Dict[str, str]:
        """Scan ~/.zprofile, ~/.zshrc, ~/.bash_profile, and ~/.profile for export declarations."""
        persisted: Dict[str, str] = {}
        home = Path.home()
        config_files = [
            home / ".zprofile",
            home / ".zshrc",
            home / ".bash_profile",
            home / ".profile",
        ]

        for cfg in config_files:
            if cfg.exists() and cfg.is_file():
                try:
                    with open(cfg, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            clean = line.strip()
                            if clean.startswith("export ") and "=" in clean:
                                pair = clean[7:].strip()
                                k, v = pair.split("=", 1)
                                k = k.strip()
                                v = v.strip().strip('"').strip("'")
                                if k and k not in persisted:
                                    persisted[k] = v
                except Exception:
                    pass

        return persisted
