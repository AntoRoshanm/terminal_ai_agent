"""
Local Developer Services and Docker Container Management Tool
"""

import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


from app.tools.system.factory import SystemProviderFactory


class ManageDevServiceTool(BaseTool):
    """Tool to inspect and manage Docker containers, background services, Windows/system services, and local dev environments."""

    name = "dev_manage_service"
    description = "Inspect and manage background services, Windows/system services (start, stop, restart, enable, disable), Docker containers, or check active dev ports."
    category = "developer"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": "string",
                    "description": "Type of service: 'system', 'docker', or 'ports' (default: 'system')",
                    "enum": ["system", "docker", "ports"],
                    "default": "system",
                },
                "service_name": {
                    "type": "string",
                    "description": "Name of the system or Windows service (e.g. 'spooler', 'wuauserv', 'nginx')",
                },
                "action": {
                    "type": "string",
                    "description": "Action to perform on system service: 'start', 'stop', 'restart', 'enable', 'disable' (default: 'restart')",
                    "enum": ["start", "stop", "restart", "enable", "disable"],
                    "default": "restart",
                },
                "docker_action": {
                    "type": "string",
                    "description": "Docker action: 'ps', 'logs', 'start', 'stop' (default: 'ps')",
                    "enum": ["ps", "logs", "start", "stop"],
                    "default": "ps",
                },
                "container_id": {
                    "type": "string",
                    "description": "Optional container ID or name (for logs, start, stop)",
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        service_type: Optional[str] = None,
        service_name: Optional[str] = None,
        action: Optional[str] = "restart",
        docker_action: str = "ps",
        container_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # If service_name is provided, treat as system service
        if service_name or service_type == "system" or (service_type is None and not container_id and docker_action == "ps" and service_name):
            target_name = service_name or "spooler"
            act = action or "restart"
            return SystemProviderFactory.get_service_provider().manage_service(
                name=target_name, action=act
            )

        stype = service_type or ("docker" if container_id else "docker")

        if stype == "docker":
            if not shutil.which("docker"):
                return {
                    "docker_installed": False,
                    "message": "Docker executable not found on PATH.",
                }

            if docker_action == "ps":
                cmd = ["docker", "ps", "-a", "--format", "{{json .}}"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode != 0:
                    return {"docker_installed": True, "error": res.stderr.strip()}

                containers = []
                for line in res.stdout.splitlines():
                    if line.strip():
                        try:
                            containers.append(json.loads(line.strip()))
                        except Exception:
                            pass
                return {
                    "docker_installed": True,
                    "container_count": len(containers),
                    "containers": containers,
                }

            elif docker_action in ("start", "stop"):
                if not container_id:
                    raise ValueError("container_id is required for start/stop action.")
                cmd = ["docker", docker_action, container_id]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                return {
                    "action": docker_action,
                    "container_id": container_id,
                    "success": res.returncode == 0,
                    "output": res.stdout.strip() or res.stderr.strip(),
                }

        elif stype == "ports":
            # Quick netstat for common dev ports (3000, 5000, 5173, 8000, 8080, 5432, 3306, 27017)
            ps_script = """
            $ports = 3000, 5000, 5173, 8000, 8080, 5432, 3306, 27017
            Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -Property LocalPort, OwningProcess | ConvertTo-Json -Compress
            """
            res = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script], capture_output=True, text=True, timeout=10)
            ports_data = []
            if res.returncode == 0 and res.stdout.strip():
                try:
                    parsed = json.loads(res.stdout.strip())
                    if isinstance(parsed, dict):
                        parsed = [parsed]
                    ports_data = parsed
                except Exception:
                    pass
            return {"service_type": "ports", "active_dev_ports": ports_data}

        raise ValueError(f"Unknown service_type: {stype}")
