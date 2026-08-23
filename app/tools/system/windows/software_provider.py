"""
Windows Software and Package Management Provider
"""

import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
from app.platform.contracts import SoftwareProvider


class WindowsSoftwareProvider(SoftwareProvider):
    """Windows implementation for software registry, winget, pip, and npm."""

    def _query_hive(self, hive: int, subkey: str, flags: int = 0) -> List[Dict[str, Any]]:
        apps = []
        if sys.platform != "win32":
            return apps

        try:
            import winreg
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | flags) as root_key:
                num_subkeys, _, _ = winreg.QueryInfoKey(root_key)
                for i in range(num_subkeys):
                    try:
                        key_name = winreg.EnumKey(root_key, i)
                        with winreg.OpenKey(root_key, key_name) as app_key:
                            try:
                                name, _ = winreg.QueryValueEx(app_key, "DisplayName")
                            except FileNotFoundError:
                                continue

                            if not name or not isinstance(name, str) or not name.strip():
                                continue

                            clean_name = str(name).strip()
                            if clean_name.startswith("{") and clean_name.endswith("}"):
                                continue

                            version = ""
                            publisher = ""

                            try:
                                v_val, _ = winreg.QueryValueEx(app_key, "DisplayVersion")
                                if v_val:
                                    version = str(v_val).strip()
                            except FileNotFoundError:
                                pass

                            try:
                                p_val, _ = winreg.QueryValueEx(app_key, "Publisher")
                                if p_val and not str(p_val).startswith("http"):
                                    publisher = str(p_val).strip()
                            except FileNotFoundError:
                                pass

                            apps.append({
                                "name": clean_name,
                                "version": version or "Unknown",
                                "publisher": publisher or "Unknown",
                            })
                    except Exception:
                        continue
        except Exception:
            pass
        return apps

    def get_installed_software(
        self, query: Optional[str] = None, limit: int = 40
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen_names = set()

        if sys.platform == "win32":
            import winreg
            hives_and_keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_WOW64_64KEY),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_WOW64_32KEY),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0),
            ]

            for hive, subkey, flag in hives_and_keys:
                apps = self._query_hive(hive, subkey, flag)
                for app in apps:
                    name_key = app["name"].lower()
                    if name_key in seen_names:
                        continue
                    seen_names.add(name_key)

                    if query:
                        q = query.lower()
                        if q not in name_key and q not in app["publisher"].lower():
                            continue

                    results.append(app)
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

        results.sort(key=lambda x: x["name"].lower())
        return results

    def detect_managers(self) -> List[Dict[str, Any]]:
        managers = []
        for name in ["winget", "choco", "scoop", "pip", "npm", "cargo"]:
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
        if not path and not name.lower().endswith(".exe"):
            path = shutil.which(f"{name}.exe")

        if path:
            ver = "Unknown"
            try:
                res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    ver = res.stdout.strip()
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
        mgr = manager or ("winget" if shutil.which("winget") else ("pip" if shutil.which("pip") else "npm"))
        if not shutil.which(mgr):
            return {"success": False, "error": f"Package manager '{mgr}' is not installed or available in PATH."}

        target = f"{package_name}=={version}" if version and mgr == "pip" else package_name

        if mgr == "winget":
            cmd = ["winget", "install", "--id", package_name, "--silent", "--accept-source-agreements", "--accept-package-agreements"]
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
