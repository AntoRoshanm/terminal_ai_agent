"""
Linux Systemd & Init Service Provider
"""

import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import ServiceProvider


class LinuxServiceProvider(ServiceProvider):
    """Linux implementation for systemd/init services."""

    def get_service_info(
        self, query: Optional[str] = None, limit: int = 30
    ) -> List[Dict[str, Any]]:
        services: List[Dict[str, Any]] = []

        # Try systemctl
        try:
            cmd = ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().split("\n"):
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        unit = parts[0]
                        active = parts[2]
                        sub = parts[3]
                        desc = parts[4] if len(parts) >= 5 else unit

                        if query and query.lower() not in unit.lower() and query.lower() not in desc.lower():
                            continue

                        services.append({
                            "name": unit,
                            "display_name": desc,
                            "status": f"{active} ({sub})",
                            "start_type": "systemd",
                        })

                        if len(services) >= limit:
                            break
                if services:
                    return services
        except Exception:
            pass

        # Fallback via service --status-all
        try:
            res = subprocess.run(["service", "--status-all"], capture_output=True, text=True, timeout=5)
            if res.stdout.strip():
                for line in res.stdout.strip().split("\n"):
                    parts = line.split()
                    if len(parts) >= 4:
                        status_char = parts[1].strip("[]")
                        name = parts[3]
                        if query and query.lower() not in name.lower():
                            continue
                        services.append({
                            "name": name,
                            "display_name": name,
                            "status": "Running" if status_char == "+" else "Stopped",
                            "start_type": "SysVInit",
                        })
                        if len(services) >= limit:
                            break
        except Exception:
            pass

        return services

    def manage_service(self, name: str, action: str) -> Dict[str, Any]:
        import os
        action_lower = action.lower().strip()
        if action_lower in ("status", "query", "info", "get"):
            info = self.get_service_info(query=name)
            return {"success": True, "service": name, "action": "status", "services": info}

        if action_lower not in ("start", "stop", "restart", "enable", "disable"):
            raise ValueError(f"Unsupported action: '{action}'. Must be start, stop, restart, enable, disable, or status.")

        is_admin = (os.geteuid() == 0) if hasattr(os, "geteuid") else False
        if not is_admin:
            return {
                "success": False,
                "service": name,
                "action": action_lower,
                "needs_elevation": True,
                "error": f"Managing system service '{name}' ({action_lower}) on Linux requires root/sudo privileges.",
            }

        cmd = ["systemctl", action_lower, name]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return {
                "success": res.returncode == 0,
                "service": name,
                "action": action_lower,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
            }
        except Exception as e:
            return {"success": False, "service": name, "action": action_lower, "error": str(e)}
