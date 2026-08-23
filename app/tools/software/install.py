"""
Software Installation Tool via Windows Package Managers
"""

import subprocess
from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.platform.detect import get_platform_info
from app.tools.base import BaseTool


class InstallSoftwareTool(BaseTool):
    """Tool to install or uninstall software packages via winget, choco, pip, or npm."""

    name = "software_install"
    description = "Install or uninstall a package or application using winget, choco, pip, or npm. Requires user approval."
    category = "software"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
    timeout_seconds = 30  # 30s timeout to prevent hanging on interactive/network locks

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "package_name": {
                    "type": "string",
                    "description": "Package identifier or name (e.g. 'jqlang.jq', 'jq', 'requests', 'typescript')",
                },
                "manager": {
                    "type": "string",
                    "description": "Package manager to use: 'winget', 'choco', 'pip', or 'npm'",
                    "enum": ["winget", "choco", "pip", "npm"],
                },
                "action": {
                    "type": "string",
                    "description": "Action to perform: 'install' or 'uninstall' (default: 'install')",
                    "enum": ["install", "uninstall"],
                    "default": "install",
                },
                "version": {
                    "type": "string",
                    "description": "Optional specific version to install",
                },
                "global_install": {
                    "type": "boolean",
                    "description": "Whether to install globally (for npm -g)",
                    "default": False,
                },
            },
            "required": ["package_name", "manager"],
            "additionalProperties": False,
        }

    def _build_command(
        self, manager: str, package_name: str, version: Optional[str], global_install: bool, action: str = "install"
    ) -> list[str]:
        mgr = manager.lower()
        act = action.lower()

        if mgr == "winget":
            if act == "uninstall":
                if "." in package_name:
                    return [
                        "winget.exe",
                        "uninstall",
                        "--id",
                        package_name,
                        "--exact",
                        "--silent",
                        "--accept-source-agreements",
                        "--disable-interactivity",
                    ]
                return [
                    "winget.exe",
                    "uninstall",
                    package_name,
                    "--silent",
                    "--accept-source-agreements",
                    "--disable-interactivity",
                ]

            if "." in package_name:
                cmd = [
                    "winget.exe",
                    "install",
                    "--id",
                    package_name,
                    "--exact",
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    "--disable-interactivity",
                ]
            else:
                cmd = [
                    "winget.exe",
                    "install",
                    package_name,
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    "--disable-interactivity",
                ]
            if version:
                cmd.extend(["--version", version])
            return cmd

        elif mgr == "choco":
            if act == "uninstall":
                return ["choco.exe", "uninstall", package_name, "-y"]
            cmd = ["choco.exe", "install", package_name, "-y"]
            if version:
                cmd.extend(["--version", version])
            return cmd

        elif mgr == "pip":
            bin_name = "pip.exe" if get_platform_info().os_family == "windows" else "pip"
            if act == "uninstall":
                return [bin_name, "uninstall", "-y", package_name]
            pkg = f"{package_name}=={version}" if version else package_name
            return [bin_name, "install", pkg]

        elif mgr == "npm":
            bin_name = "npm.cmd" if get_platform_info().os_family == "windows" else "npm"
            if act == "uninstall":
                cmd = [bin_name, "uninstall"]
                if global_install:
                    cmd.append("-g")
                cmd.append(package_name)
                return cmd
            pkg = f"{package_name}@{version}" if version else package_name
            cmd = [bin_name, "install"]
            if global_install:
                cmd.append("-g")
            cmd.append(pkg)
            return cmd

        raise ValueError(f"Unsupported manager: {manager}")

    def _run(
        self,
        package_name: str,
        manager: str,
        action: str = "install",
        version: Optional[str] = None,
        global_install: bool = False,
    ) -> Dict[str, Any]:
        cmd = self._build_command(manager, package_name, version, global_install, action=action)

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            success = res.returncode in (0, 3010)  # 3010 is Windows ERROR_SUCCESS_REBOOT_REQUIRED

            return {
                "manager": manager,
                "package_name": package_name,
                "action": action,
                "command": " ".join(cmd),
                "exit_code": res.returncode,
                "success": success,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "reboot_required": res.returncode == 3010,
            }
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Operation '{action}' on '{package_name}' timed out after {self.timeout_seconds} seconds.")
