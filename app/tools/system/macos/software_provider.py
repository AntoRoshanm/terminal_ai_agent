"""
macOS Application Bundles, Homebrew, and Software Management Provider
"""

import os
from pathlib import Path
import plistlib
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import SoftwareProvider
from app.platform.detect import get_platform_info


class MacOSSoftwareProvider(SoftwareProvider):
    """macOS implementation for /Applications scans, Homebrew, and MacPorts."""

    def get_installed_software(
        self, query: Optional[str] = None, limit: int = 40
    ) -> List[Dict[str, Any]]:
        apps: List[Dict[str, Any]] = []
        seen_names = set()

        # 1. Scan /Applications and ~/Applications
        app_dirs = [Path("/Applications"), Path.home() / "Applications", Path("/System/Applications")]
        for adir in app_dirs:
            if adir.exists() and adir.is_dir():
                try:
                    for item in adir.iterdir():
                        if item.name.endswith(".app"):
                            name = item.name[:-4]
                            version = "1.0.0"
                            publisher = "Apple" if "System" in str(adir) else "Third Party"

                            # Try parsing Info.plist
                            plist_path = item / "Contents" / "Info.plist"
                            if plist_path.exists():
                                try:
                                    with open(plist_path, "rb") as fp:
                                        pl = plistlib.load(fp)
                                        version = str(pl.get("CFBundleShortVersionString") or pl.get("CFBundleVersion") or version)
                                        publisher = str(pl.get("CFBundleIdentifier") or publisher)
                                except Exception:
                                    pass

                            if query and query.lower() not in name.lower() and query.lower() not in publisher.lower():
                                continue

                            if name not in seen_names:
                                seen_names.add(name)
                                apps.append({
                                    "name": name,
                                    "version": version,
                                    "publisher": publisher,
                                    "install_date": "N/A",
                                    "source": "Applications",
                                })
                except Exception:
                    pass

        # 2. Query Homebrew
        if shutil.which("brew"):
            try:
                res = subprocess.run(["brew", "list", "--versions"], capture_output=True, text=True, timeout=4)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().splitlines():
                        parts = line.split()
                        if parts:
                            b_name = parts[0]
                            b_ver = parts[1] if len(parts) > 1 else "latest"
                            if query and query.lower() not in b_name.lower():
                                continue
                            if b_name not in seen_names:
                                seen_names.add(b_name)
                                apps.append({
                                    "name": b_name,
                                    "version": b_ver,
                                    "publisher": "Homebrew",
                                    "install_date": "N/A",
                                    "source": "Homebrew",
                                })
            except Exception:
                pass

        return apps[:limit]

    def detect_managers(self) -> List[Dict[str, Any]]:
        managers = []
        if shutil.which("brew"):
            ver_res = subprocess.run(["brew", "--version"], capture_output=True, text=True, timeout=2)
            v = ver_res.stdout.splitlines()[0] if ver_res.returncode == 0 and ver_res.stdout else "Available"
            managers.append({"name": "brew", "display_name": "Homebrew", "version": v, "is_default": True})
        if shutil.which("port"):
            managers.append({"name": "port", "display_name": "MacPorts", "version": "Available", "is_default": False})
        if shutil.which("pip") or shutil.which("pip3"):
            managers.append({"name": "pip", "display_name": "Python PIP", "version": "Available", "is_default": False})
        return managers

    def find_executable(self, name: str) -> Dict[str, Any]:
        p = shutil.which(name)
        if p:
            return {"found": True, "name": name, "path": p}
        # Check standard macOS paths
        mac_paths = [
            Path(f"/Applications/{name}.app"),
            Path(f"/opt/homebrew/bin/{name}"),
            Path(f"/usr/local/bin/{name}"),
        ]
        for mp in mac_paths:
            if mp.exists():
                return {"found": True, "name": name, "path": str(mp)}
        return {"found": False, "name": name, "path": None}

    def install_package(
        self, package_name: str, manager: Optional[str] = None, version: Optional[str] = None
    ) -> Dict[str, Any]:
        available_managers = [m["name"] for m in self.detect_managers()]

        # Check for ambiguity: Homebrew vs MacPorts both present
        if not manager and "brew" in available_managers and "port" in available_managers:
            return {
                "success": False,
                "needs_disambiguation": True,
                "available_managers": ["brew", "port"],
                "package_name": package_name,
                "message": f"Multiple package managers found (Homebrew and MacPorts). Please specify manager='brew' or manager='port'.",
            }

        mgr = manager or ("brew" if "brew" in available_managers else (available_managers[0] if available_managers else "brew"))

        if mgr == "brew":
            cmd = ["brew", "install", package_name]
        elif mgr == "port":
            info = get_platform_info()
            if not info.is_admin_or_root:
                return {
                    "success": False,
                    "needs_elevation": True,
                    "error": "ELEVATION REQUIRED: MacPorts installation requires root/sudo privileges.",
                }
            cmd = ["sudo", "port", "install", package_name]
        else:
            cmd = [mgr, "install", package_name]

        return {
            "success": True,
            "command": " ".join(cmd),
            "manager": mgr,
            "package_name": package_name,
            "instructions": f"Execute command: {' '.join(cmd)}",
        }

    def verify_installation(
        self, package_name: str, executable_name: Optional[str] = None, expected_version: Optional[str] = None
    ) -> Dict[str, Any]:
        target = executable_name or package_name
        found_info = self.find_executable(target)
        if not found_info.get("found"):
            return {
                "verified": False,
                "package_name": package_name,
                "executable": target,
                "error": f"Executable '{target}' not found in PATH or /Applications.",
            }

        exe_path = found_info["path"]
        version_observed = None
        try:
            res = subprocess.run([exe_path, "--version"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                version_observed = res.stdout.strip()
        except Exception:
            pass

        return {
            "verified": True,
            "package_name": package_name,
            "executable": target,
            "path": exe_path,
            "version_observed": version_observed,
            "matches_expected": (expected_version in version_observed) if (expected_version and version_observed) else True,
        }
