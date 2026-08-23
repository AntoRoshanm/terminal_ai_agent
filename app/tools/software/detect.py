"""
Package Manager and Executable Detection Tools
"""

import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class DetectPackageManagersTool(BaseTool):
    """Tool to discover installed package managers on the Windows machine."""

    name = "software_detect_managers"
    description = "Check which package managers (winget, choco, scoop, pip, npm, cargo, dotnet) are installed and available."
    category = "software"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def _check_manager(self, name: str, version_cmd: List[str]) -> Dict[str, Any]:
        path = shutil.which(name)
        if not path:
            return {"name": name, "installed": False}

        version_str = "Unknown"
        try:
            res = subprocess.run(version_cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                version_str = res.stdout.strip().splitlines()[0]
        except Exception:
            pass

        return {
            "name": name,
            "installed": True,
            "path": path,
            "version": version_str,
        }

    def _run(self) -> Dict[str, Any]:
        managers = {
            "winget": ["winget.exe", "--version"],
            "choco": ["choco.exe", "--version"],
            "scoop": ["scoop.cmd", "--version"],
            "pip": ["pip.exe", "--version"],
            "npm": ["npm.cmd", "--version"],
            "cargo": ["cargo.exe", "--version"],
            "dotnet": ["dotnet.exe", "--version"],
        }

        results = {}
        available_list = []
        for name, cmd in managers.items():
            info = self._check_manager(name, cmd)
            results[name] = info
            if info["installed"]:
                available_list.append(name)

        return {
            "available_managers": available_list,
            "details": results,
        }


class FindExecutableTool(BaseTool):
    """Tool to locate an executable by name across PATH and common program folders."""

    name = "software_find_executable"
    description = "Search for an executable on PATH and standard Windows install directories, and retrieve its version."
    category = "software"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "executable_name": {
                    "type": "string",
                    "description": "Name of the executable (e.g. 'postgres', 'python', 'git', 'node', 'docker', 'code')",
                },
                "version_flag": {
                    "type": "string",
                    "description": "Flag to pass to get version (default: '--version')",
                    "default": "--version",
                },
            },
            "required": ["executable_name"],
            "additionalProperties": False,
        }

    def _run(self, executable_name: str, version_flag: str = "--version") -> Dict[str, Any]:
        target = executable_name.strip()
        if not target.lower().endswith((".exe", ".cmd", ".bat")):
            target_exe = target + ".exe"
            target_cmd = target + ".cmd"
        else:
            target_exe = target
            target_cmd = target

        # 1. Search PATH
        found_path = shutil.which(target) or shutil.which(target_exe) or shutil.which(target_cmd)

        # 2. Search common folders if not in PATH
        if not found_path:
            search_roots = [
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                os.environ.get("LocalAppData", "C:\\Users\\Default\\AppData\\Local"),
            ]
            for root_dir in search_roots:
                if not os.path.exists(root_dir):
                    continue
                for dirpath, dirnames, filenames in os.walk(root_dir):
                    # Stop descending beyond 2 subfolder levels
                    if dirpath.count(os.sep) - root_dir.count(os.sep) >= 2:
                        dirnames[:] = []
                        continue
                    if target_exe.lower() in [f.lower() for f in filenames]:
                        found_path = os.path.join(dirpath, target_exe)
                        break
                if found_path:
                    break

        if not found_path:
            return {
                "executable_name": executable_name,
                "found": False,
            }

        # 3. Retrieve version
        version_str = "Unknown"
        try:
            res = subprocess.run([found_path, version_flag], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                output = res.stdout.strip() or res.stderr.strip()
                if output:
                    version_str = output.splitlines()[0]
        except Exception:
            pass

        return {
            "executable_name": executable_name,
            "found": True,
            "path": found_path,
            "version": version_str,
            "in_path": shutil.which(target) is not None,
        }
