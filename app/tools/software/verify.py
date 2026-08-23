"""
Multi-Point Software and Service Verification Engine
"""

import shutil
import subprocess
from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.software.detect import FindExecutableTool
from app.tools.windows.installed_software import GetInstalledSoftwareTool
from app.tools.windows.network_info import GetNetworkInfoTool
from app.tools.windows.service_info import GetServiceInfoTool


class VerifySoftwareTool(BaseTool):
    """Tool to perform multi-point ground-truth verification on installed software."""

    name = "software_verify"
    description = (
        "Verify whether software is installed, functional, and operational. "
        "Checks executable location, version command, registry, Windows services, and ports."
    )
    category = "software"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def __init__(self):
        self.find_exec = FindExecutableTool()
        self.get_sw = GetInstalledSoftwareTool()
        self.get_svc = GetServiceInfoTool()
        self.get_net = GetNetworkInfoTool()

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the software to verify (e.g. 'python', 'git', 'postgresql', 'docker', 'node')",
                },
                "executable_name": {
                    "type": "string",
                    "description": "Optional specific executable name (e.g. 'postgres.exe', 'git.exe')",
                },
                "service_name": {
                    "type": "string",
                    "description": "Optional Windows service name associated with this software (e.g. 'postgresql-x64-16', 'docker')",
                },
                "port": {
                    "type": "integer",
                    "description": "Optional TCP port associated with this software (e.g. 5432 for Postgres, 8080 for web apps)",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        }

    def _run(
        self,
        name: str,
        executable_name: Optional[str] = None,
        service_name: Optional[str] = None,
        port: Optional[int] = None,
    ) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {}
        target_exec = executable_name or name

        # 1. Executable Verification
        exec_info = self.find_exec._run(executable_name=target_exec)
        evidence["executable"] = exec_info

        # 2. Registry Check
        registry_matches = self.get_sw._run(query=name, limit=5)
        evidence["registry_matches"] = registry_matches

        # 3. Service Verification (if specified)
        if service_name:
            svc_info = self.get_svc._run(service_name=service_name, limit=5)
            evidence["service"] = svc_info

        # 4. Port Verification (if specified)
        if port is not None:
            net_info = self.get_net._run(include_listening_ports=True, port=port)
            evidence["listening_ports"] = net_info.get("listening_ports", [])

        # Calculate overall verdict
        has_exec = exec_info.get("found", False)
        has_reg = len(registry_matches) > 0
        has_svc = bool(evidence.get("service")) and len(evidence.get("service", [])) > 0

        verified = has_exec or has_reg or has_svc

        summary_points = []
        if has_exec:
            summary_points.append(f"Found executable at {exec_info.get('path')} (Version: {exec_info.get('version')})")
        if has_reg:
            summary_points.append(f"Found {len(registry_matches)} registry install entry/entries")
        if service_name and has_svc:
            summary_points.append(f"Found matching Windows service '{service_name}'")
        if port is not None and evidence.get("listening_ports"):
            summary_points.append(f"Port {port} is active and listening")

        return {
            "software_name": name,
            "verified": verified,
            "summary": "; ".join(summary_points) if summary_points else "No matching executable, registry, or service found.",
            "evidence": evidence,
        }
