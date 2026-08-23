"""
Linux Software and Package Management Provider
"""

import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
from app.platform.contracts import SoftwareProvider


class LinuxSoftwareProvider(SoftwareProvider):
    """Linux implementation for package managers (apt, dnf, pacman, snap, flatpak, pip, npm)."""

    def get_installed_software(
        self, query: Optional[str] = None, limit: int = 500
    ) -> List[Dict[str, Any]]:
        apps: List[Dict[str, Any]] = []
        seen = set()

        # 1. dpkg -l
        if shutil.which("dpkg-query"):
            try:
                cmd = ["dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Maintainer}\\n"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            name = parts[0]
                            ver = parts[1]
                            maint = parts[2] if len(parts) >= 3 else "Debian/Ubuntu"
                            if query and query.lower() not in name.lower():
                                continue
                            if name not in seen:
                                seen.add(name)
                                apps.append({"name": name, "version": ver, "publisher": maint})
                                if len(apps) >= limit:
                                    return apps
            except Exception:
                pass

        # 2. rpm -qa
        if len(apps) < limit and shutil.which("rpm"):
            try:
                cmd = ["rpm", "-qa", "--qf", "%{NAME}\\t%{VERSION}-%{RELEASE}\\t%{VENDOR}\\n"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            name = parts[0]
                            ver = parts[1]
                            vend = parts[2] if len(parts) >= 3 else "RedHat/Fedora"
                            if query and query.lower() not in name.lower():
                                continue
                            if name not in seen:
                                seen.add(name)
                                apps.append({"name": name, "version": ver, "publisher": vend})
                                if len(apps) >= limit:
                                    return apps
            except Exception:
                pass

        # 3. pacman -Q
        if len(apps) < limit and shutil.which("pacman"):
            try:
                cmd = ["pacman", "-Q"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().split("\n"):
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            ver = parts[1]
                            if query and query.lower() not in name.lower():
                                continue
                            if name not in seen:
                                seen.add(name)
                                apps.append({"name": name, "version": ver, "publisher": "Arch Linux"})
                                if len(apps) >= limit:
                                    return apps
            except Exception:
                pass

        # 4. snap list
        if len(apps) < limit and shutil.which("snap"):
            try:
                cmd = ["snap", "list"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
                if res.returncode == 0 and res.stdout.strip():
                    lines = res.stdout.strip().split("\n")
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) >= 3:
                            name = parts[0]
                            ver = parts[1]
                            pub = parts[4] if len(parts) >= 5 else "Snapcraft"
                            if query and query.lower() not in name.lower():
                                continue
                            if name not in seen:
                                seen.add(name)
                                apps.append({"name": name, "version": ver, "publisher": f"Snap ({pub})"})
                                if len(apps) >= limit:
                                    return apps
            except Exception:
                pass

        # 5. flatpak list
        if len(apps) < limit and shutil.which("flatpak"):
            try:
                cmd = ["flatpak", "list", "--columns=application,version,origin"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            name = parts[0]
                            ver = parts[1]
                            pub = parts[2] if len(parts) >= 3 else "Flatpak"
                            if query and query.lower() not in name.lower():
                                continue
                            if name not in seen:
                                seen.add(name)
                                apps.append({"name": name, "version": ver, "publisher": f"Flatpak ({pub})"})
                                if len(apps) >= limit:
                                    return apps
            except Exception:
                pass

        apps.sort(key=lambda x: x["name"].lower())
        return apps

    def detect_managers(self) -> List[Dict[str, Any]]:
        managers = []
        candidates = ["apt", "apt-get", "dnf", "pacman", "zypper", "snap", "flatpak", "pip", "npm", "cargo"]
        for name in candidates:
            path = shutil.which(name)
            if path:
                version = "Unknown"
                try:
                    ver_cmd = [name, "--version"]
                    res = subprocess.run(ver_cmd, capture_output=True, text=True, timeout=3)
                    if res.returncode == 0:
                        version = res.stdout.strip().split("\n")[0]
                except Exception:
                    pass
                managers.append({
                    "name": name,
                    "available": True,
                    "path": path,
                    "version": version,
                })
        return managers

    def find_executable(self, name: str) -> Dict[str, Any]:
        path = shutil.which(name)
        if path:
            ver = "Unknown"
            try:
                res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    ver = res.stdout.strip().split("\n")[0]
            except Exception:
                pass
            return {
                "found": True,
                "name": name,
                "path": path,
                "version": ver,
                "in_path": True,
            }
        return {"found": False, "name": name, "path": None, "in_path": False}

    def install_package(
        self, package_name: str, manager: Optional[str] = None, version: Optional[str] = None
    ) -> Dict[str, Any]:
        mgr = manager
        if not mgr:
            for candidate in ["apt", "apt-get", "dnf", "pacman", "snap", "pip", "npm"]:
                if shutil.which(candidate):
                    mgr = candidate
                    break
            mgr = mgr or "pip"

        if not shutil.which(mgr):
            return {"success": False, "error": f"Package manager '{mgr}' is not installed or available in PATH."}

        target = f"{package_name}=={version}" if version and mgr == "pip" else package_name

        if mgr in ("apt", "apt-get"):
            cmd = ["sudo", "-n", mgr, "install", "-y", target]
        elif mgr == "dnf":
            cmd = ["sudo", "-n", "dnf", "install", "-y", target]
        elif mgr == "pacman":
            cmd = ["sudo", "-n", "pacman", "-S", "--noconfirm", target]
        elif mgr == "snap":
            cmd = ["sudo", "-n", "snap", "install", target]
        elif mgr == "pip":
            cmd = [sys.executable, "-m", "pip", "install", target]
        elif mgr == "npm":
            cmd = ["npm", "install", "-g", target]
        else:
            cmd = [mgr, "install", target]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return {
                "success": res.returncode == 0,
                "manager": mgr,
                "package": package_name,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
                "exit_code": res.returncode,
            }
        except Exception as e:
            return {"success": False, "manager": mgr, "package": package_name, "error": str(e)}

    def verify_installation(
        self, package_name: str, executable_name: Optional[str] = None, expected_version: Optional[str] = None
    ) -> Dict[str, Any]:
        exe_name = executable_name or package_name
        lookup = self.find_executable(exe_name)
        return {
            "verified": lookup["found"],
            "package": package_name,
            "executable_found": lookup["found"],
            "path": lookup.get("path"),
            "detected_version": lookup.get("version"),
            "expected_version": expected_version,
            "version_matched": expected_version in str(lookup.get("version")) if expected_version and lookup.get("version") else None,
        }
