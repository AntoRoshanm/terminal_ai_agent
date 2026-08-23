"""
Cross-Platform Environment Detection Engine (Windows, Linux, macOS)
"""

import os
import platform
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple
from app.models.state import PlatformInfo

_CACHED_PLATFORM_INFO: Optional[PlatformInfo] = None


def is_wsl() -> bool:
    """Detect if running inside Windows Subsystem for Linux (WSL)."""
    if sys.platform != "linux":
        return False
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                return "microsoft" in content or "wsl" in content
    except Exception:
        pass
    return False


def is_admin_or_root() -> bool:
    """Detect if current execution has root/administrator privileges."""
    if sys.platform == "win32":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    elif sys.platform == "darwin":
        try:
            if os.geteuid() == 0:
                return True
            # Check if user is in admin or wheel group
            res = subprocess.run(["id", "-Gn"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                groups = res.stdout.strip().split()
                return "admin" in groups or "wheel" in groups
        except Exception:
            return False
        return False
    else:
        try:
            return os.geteuid() == 0
        except Exception:
            return False


def detect_display_server() -> Optional[str]:
    """Detect active Linux display server (X11 or Wayland)."""
    if sys.platform in ("win32", "darwin"):
        return None
    session_type = os.getenv("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        return "wayland"
    if session_type == "x11":
        return "x11"
    if os.getenv("DISPLAY"):
        return "x11"
    if os.getenv("WAYLAND_DISPLAY"):
        return "wayland"
    return "none"


def detect_apple_silicon() -> bool:
    """Detect if host machine is Apple Silicon (arm64)."""
    if sys.platform != "darwin":
        return False
    arch = platform.machine().lower()
    return arch in ("arm64", "aarch64")


def detect_rosetta_translated() -> bool:
    """Detect if running under Rosetta translation on macOS."""
    if sys.platform != "darwin":
        return False
    try:
        res = subprocess.run(["sysctl", "-n", "sysctl.proc_translated"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip() == "1":
            return True
    except Exception:
        pass
    return False


def detect_sip_status() -> Optional[bool]:
    """Detect System Integrity Protection (SIP) status on macOS."""
    if sys.platform != "darwin":
        return None
    try:
        res = subprocess.run(["csrutil", "status"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            out = res.stdout.lower()
            if "enabled" in out:
                return True
            elif "disabled" in out:
                return False
    except Exception:
        pass
    return None


def detect_package_managers(os_family: str) -> List[str]:
    """Detect available package managers on the host."""
    managers = []
    if os_family == "windows":
        candidates = ["winget", "choco", "scoop", "pip", "npm", "cargo"]
    elif os_family == "macos":
        candidates = ["brew", "port", "pkgutil", "pip", "npm", "cargo"]
    else:
        candidates = ["apt", "apt-get", "dnf", "pacman", "zypper", "snap", "flatpak", "pip", "npm", "cargo"]

    for cmd in candidates:
        if shutil.which(cmd):
            managers.append(cmd)
    return managers


def detect_linux_distro() -> Tuple[str, str]:
    """Parse Linux distribution name and version from /etc/os-release."""
    os_name = "Linux"
    os_version = platform.release()

    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as f:
                data = {}
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        data[k.strip()] = v.strip().strip('"').strip("'")
                os_name = data.get("PRETTY_NAME") or data.get("NAME") or "Linux"
                os_version = data.get("VERSION_ID") or data.get("VERSION") or platform.release()
        except Exception:
            pass
    return os_name, os_version


def detect_macos_version() -> Tuple[str, str]:
    """Detect macOS marketing name and version string."""
    mac_ver = platform.mac_ver()[0]
    os_name = "macOS"
    os_version = mac_ver or platform.release()

    # Try sw_vers for exact name & version
    try:
        prod_name_res = subprocess.run(["sw_vers", "-productName"], capture_output=True, text=True, timeout=2)
        prod_ver_res = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True, timeout=2)
        if prod_name_res.returncode == 0 and prod_name_res.stdout.strip():
            os_name = prod_name_res.stdout.strip()
        if prod_ver_res.returncode == 0 and prod_ver_res.stdout.strip():
            os_version = prod_ver_res.stdout.strip()
    except Exception:
        pass

    # Append marketing name if known
    major = os_version.split(".")[0] if os_version else ""
    marketing_names = {
        "15": "Sequoia",
        "14": "Sonoma",
        "13": "Ventura",
        "12": "Monterey",
        "11": "Big Sur",
    }
    if major in marketing_names and marketing_names[major] not in os_name:
        os_name = f"{os_name} {os_version} ({marketing_names[major]})"
    elif os_version and os_version not in os_name:
        os_name = f"{os_name} {os_version}"

    return os_name, os_version


def detect_platform() -> PlatformInfo:
    """Perform evidence-based platform detection across Windows, Linux, and macOS."""
    arch = platform.machine() or "x86_64"
    admin_detected = is_admin_or_root()

    if sys.platform == "win32":
        win_ver = sys.getwindowsversion()
        os_name = f"Windows {win_ver.major} (Build {win_ver.build})"
        os_version = f"{win_ver.major}.{win_ver.minor}.{win_ver.build}"
        shell_default = "powershell" if shutil.which("powershell") else "cmd"
        pkg_managers = detect_package_managers("windows")
        display_server = None
        os_family = "windows"
        kernel_version = None
        is_apple_sil = False
        is_rosetta = False
        sip_stat = None
        wsl_detected = False
    elif sys.platform == "darwin":
        os_name, os_version = detect_macos_version()
        kernel_version = platform.release()
        # macOS default shell since Catalina is zsh
        raw_shell = os.getenv("SHELL") or shutil.which("zsh") or shutil.which("bash") or "zsh"
        shell_default = raw_shell.split("/")[-1] if "/" in raw_shell else raw_shell
        pkg_managers = detect_package_managers("macos")
        display_server = None
        os_family = "macos"
        is_apple_sil = detect_apple_silicon()
        is_rosetta = detect_rosetta_translated()
        sip_stat = detect_sip_status()
        wsl_detected = False
    else:
        os_name, os_version = detect_linux_distro()
        kernel_version = platform.release()
        raw_shell = os.getenv("SHELL") or shutil.which("bash") or shutil.which("sh") or "sh"
        shell_default = raw_shell.split("/")[-1] if "/" in raw_shell else raw_shell
        pkg_managers = detect_package_managers("linux")
        display_server = detect_display_server()
        os_family = "linux"
        is_apple_sil = False
        is_rosetta = False
        sip_stat = None
        wsl_detected = is_wsl()

    return PlatformInfo(
        os_family=os_family,
        os_name=os_name,
        os_version=os_version,
        kernel_version=kernel_version,
        architecture=arch,
        is_apple_silicon=is_apple_sil,
        is_rosetta_translated=is_rosetta,
        shell_default=shell_default,
        package_managers=pkg_managers,
        display_server=display_server,
        sip_enabled=sip_stat,
        is_admin_or_root=admin_detected,
        is_wsl=wsl_detected,
    )


def get_platform_info() -> PlatformInfo:
    """Retrieve cached PlatformInfo."""
    global _CACHED_PLATFORM_INFO
    if _CACHED_PLATFORM_INFO is None:
        _CACHED_PLATFORM_INFO = detect_platform()
    return _CACHED_PLATFORM_INFO


def reset_platform_cache() -> None:
    """Reset cached platform info for testing."""
    global _CACHED_PLATFORM_INFO
    _CACHED_PLATFORM_INFO = None
