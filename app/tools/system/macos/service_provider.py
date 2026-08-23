"""
macOS Background Services and Launchd Daemons Provider
"""

import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import ServiceProvider


class MacOSServiceProvider(ServiceProvider):
    """macOS implementation for launchd services, LaunchDaemons, and LaunchAgents."""

    def get_service_info(
        self, query: Optional[str] = None, limit: int = 30
    ) -> List[Dict[str, Any]]:
        services: List[Dict[str, Any]] = []

        try:
            res = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().split("\n")
                for line in lines[1:]:
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        pid_str = parts[0].strip()
                        status_str = parts[1].strip()
                        label = parts[2].strip()

                        if query and query.lower() not in label.lower():
                            continue

                        is_running = pid_str != "-" and pid_str.isdigit()
                        services.append({
                            "name": label,
                            "display_name": label,
                            "status": "Running" if is_running else "Stopped",
                            "start_type": "Launchd",
                            "pid": int(pid_str) if is_running else None,
                            "exit_code": int(status_str) if status_str.isdigit() else 0,
                        })
        except Exception:
            pass

        return services[:limit]

    def manage_service(self, name: str, action: str) -> Dict[str, Any]:
        action_clean = action.lower().strip()
        cmd: List[str] = []

        if action_clean == "start":
            cmd = ["launchctl", "start", name]
        elif action_clean == "stop":
            cmd = ["launchctl", "stop", name]
        elif action_clean == "restart":
            # launchctl kickstart -k gui/<uid>/<label> or stop + start
            cmd = ["launchctl", "kickstart", "-k", f"system/{name}"]
        else:
            return {
                "success": False,
                "service_name": name,
                "action": action,
                "error": f"Unsupported service action '{action}'. Valid actions: start, stop, restart.",
            }

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            return {
                "success": res.returncode == 0,
                "service_name": name,
                "action": action,
                "error": res.stderr.strip() if res.returncode != 0 else None,
            }
        except Exception as e:
            return {
                "success": False,
                "service_name": name,
                "action": action,
                "error": str(e),
            }
