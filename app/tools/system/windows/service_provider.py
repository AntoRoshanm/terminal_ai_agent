"""
Windows Services Provider
"""

import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import ServiceProvider


class WindowsServiceProvider(ServiceProvider):
    """Windows implementation for Windows Services (SCM)."""

    def get_service_info(
        self, query: Optional[str] = None, limit: int = 30
    ) -> List[Dict[str, Any]]:
        services = []
        if query:
            q_clean = query.strip()
            ps_script = f"Get-Service -ErrorAction SilentlyContinue | Where-Object {{ $_.Name -like '*{q_clean}*' -or $_.DisplayName -like '*{q_clean}*' }} | Select-Object -First {limit} -Property Name, DisplayName, Status, StartType | ConvertTo-Json -Compress"
        else:
            ps_script = f"Get-Service -ErrorAction SilentlyContinue | Select-Object -First {limit} -Property Name, DisplayName, Status, StartType | ConvertTo-Json -Compress"

        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps_script,
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout.strip())
                if isinstance(data, dict):
                    data = [data]

                status_map = {1: "Stopped", 4: "Running", 2: "StartPending", 3: "StopPending"}
                start_type_map = {2: "Automatic", 3: "Manual", 4: "Disabled"}

                for s in data:
                    name = str(s.get("Name", ""))
                    display_name = str(s.get("DisplayName", ""))
                    raw_status = s.get("Status")
                    status_str = status_map.get(raw_status, str(raw_status))
                    raw_start = s.get("StartType")
                    start_str = start_type_map.get(raw_start, str(raw_start))

                    services.append({
                        "name": name,
                        "display_name": display_name,
                        "status": status_str,
                        "start_type": start_str,
                    })

                    if len(services) >= limit:
                        break
        except Exception:
            pass

        return services

    def manage_service(self, name: str, action: str) -> Dict[str, Any]:
        action_lower = action.lower().strip()
        if action_lower in ("status", "query", "info", "get"):
            info = self.get_service_info(query=name)
            return {"success": True, "service": name, "action": "status", "services": info}

        if action_lower not in ("start", "stop", "restart", "enable", "disable"):
            raise ValueError(f"Unsupported action: '{action}'. Must be start, stop, restart, enable, disable, or status.")

        # Check administrative elevation (Rule B.36)
        import ctypes
        is_admin = False
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False

        if not is_admin:
            return {
                "success": False,
                "service": name,
                "action": action_lower,
                "needs_elevation": True,
                "error": f"Managing system service '{name}' ({action_lower}) requires administrative privileges. Please run the agent in an elevated terminal.",
            }

        # Resolve service name or display name to canonical service name
        svc_name = name
        info = self.get_service_info(query=name, limit=5)
        for s in info:
            if s.get("name", "").lower() == name.lower() or s.get("display_name", "").lower() == name.lower():
                svc_name = s.get("name", name)
                break

        if action_lower in ("enable", "disable"):
            startup_type = "Automatic" if action_lower == "enable" else "Disabled"
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"Set-Service -Name '{svc_name}' -StartupType {startup_type} -PassThru | Select-Object Name, Status, StartType | ConvertTo-Json -Compress",
            ]
        else:
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"{action_lower.capitalize()}-Service -Name '{svc_name}' -PassThru | Select-Object Name, Status, StartType | ConvertTo-Json -Compress",
            ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                return {"success": True, "service": name, "action": action_lower, "output": res.stdout.strip()}
            return {"success": False, "service": name, "action": action_lower, "error": res.stderr.strip() or res.stdout.strip()}
        except Exception as e:
            return {"success": False, "service": name, "action": action_lower, "error": str(e)}
