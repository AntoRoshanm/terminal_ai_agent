"""
Cross-Platform Environment and User PATH Configuration Tool (Windows, Linux, macOS)
"""

import os
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.platform.detect import get_platform_info
from app.tools.base import BaseTool


class ConfigureEnvironmentTool(BaseTool):
    """Tool to configure persistent User environment variables and append to User PATH."""

    name = "software_configure_env"
    description = (
        "Set or update a persistent User environment variable or append a directory to the User PATH. "
        "Requires user approval."
    )
    category = "software"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: 'set_variable' or 'append_path'",
                    "enum": ["set_variable", "append_path"],
                },
                "variable_name": {
                    "type": "string",
                    "description": "Name of the environment variable (e.g. 'JAVA_HOME', 'PYTHONPATH')",
                },
                "value": {
                    "type": "string",
                    "description": "Value to set, or directory to append to PATH",
                },
            },
            "required": ["action", "value"],
            "additionalProperties": False,
        }

    def _run(
        self,
        action: str,
        value: str,
        variable_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        val = value.strip()
        info = get_platform_info()

        if info.os_family == "windows":
            if action == "append_path":
                ps_script = f"""
                $curr = [Environment]::GetEnvironmentVariable('Path', 'User')
                $entries = if ($curr) {{ $curr -split ';' }} else {{ @() }}
                $target = '{val}'
                if ($entries -notcontains $target) {{
                    $newPath = ($entries + $target) -join ';'
                    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
                    Write-Output "Appended"
                }} else {{
                    Write-Output "AlreadyExists"
                }}
                """
                cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode != 0:
                    raise RuntimeError(f"Failed to update User PATH: {res.stderr}")

                status = res.stdout.strip()
                return {
                    "action": "append_path",
                    "directory": val,
                    "status": "appended" if status == "Appended" else "already_present",
                }

            elif action == "set_variable":
                if not variable_name:
                    raise ValueError("variable_name is required for set_variable action.")

                ps_script = f"[Environment]::SetEnvironmentVariable('{variable_name}', '{val}', 'User')"
                cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode != 0:
                    raise RuntimeError(f"Failed to set variable '{variable_name}': {res.stderr}")

                return {
                    "action": "set_variable",
                    "variable": variable_name,
                    "value": val,
                    "status": "set",
                }
        else:
            # POSIX implementation: ~/.zprofile on macOS, ~/.bashrc on Linux
            target_rc = Path.home() / (".zprofile" if info.os_family == "macos" else ".bashrc")
            if action == "append_path":
                line_to_add = f'export PATH="$PATH:{val}"\n'
                already_present = False
                if target_rc.exists():
                    with open(target_rc, "r", encoding="utf-8") as f:
                        if val in f.read():
                            already_present = True

                if not already_present:
                    with open(target_rc, "a", encoding="utf-8") as f:
                        f.write(line_to_add)

                return {
                    "action": "append_path",
                    "directory": val,
                    "status": "already_present" if already_present else "appended",
                    "target_file": str(target_rc),
                }

            elif action == "set_variable":
                if not variable_name:
                    raise ValueError("variable_name is required for set_variable action.")

                line_to_add = f'export {variable_name}="{val}"\n'
                with open(target_rc, "a", encoding="utf-8") as f:
                    f.write(line_to_add)

                return {
                    "action": "set_variable",
                    "variable": variable_name,
                    "value": val,
                    "status": "set",
                    "target_file": str(target_rc),
                }

        raise ValueError(f"Unsupported action: {action}")
