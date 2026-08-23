"""
Abstract Provider Contracts for Cross-Platform System Capabilities
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class SystemInfoProvider(ABC):
    @abstractmethod
    def get_os_info(self) -> Dict[str, Any]:
        """Return OS name, version, build, architecture, hostname, user."""
        pass

    @abstractmethod
    def get_environment_info(self, var_name: Optional[str] = None) -> Dict[str, Any]:
        """Return environment variables and PATH breakdown."""
        pass


class HardwareInfoProvider(ABC):
    @abstractmethod
    def get_hardware_info(self) -> Dict[str, Any]:
        """Return CPU specs, RAM usage/capacity, and GPU details."""
        pass


class StorageInfoProvider(ABC):
    @abstractmethod
    def get_storage_info(self) -> List[Dict[str, Any]]:
        """Return drive/mount details, total/free space, and filesystem type."""
        pass


class NetworkInfoProvider(ABC):
    @abstractmethod
    def get_network_info(self) -> Dict[str, Any]:
        """Return active adapters, IP addresses, gateways, and DNS configuration."""
        pass


class ProcessProvider(ABC):
    @abstractmethod
    def get_process_info(
        self, query: Optional[str] = None, limit: int = 20, sort_by: str = "memory"
    ) -> List[Dict[str, Any]]:
        """List active processes with PID, memory, CPU, and command line."""
        pass


class ServiceProvider(ABC):
    @abstractmethod
    def get_service_info(
        self, query: Optional[str] = None, limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Enumerate system background services and statuses."""
        pass

    @abstractmethod
    def manage_service(self, name: str, action: str) -> Dict[str, Any]:
        """Start, stop, or restart a system service."""
        pass


class SoftwareProvider(ABC):
    @abstractmethod
    def get_installed_software(
        self, query: Optional[str] = None, limit: int = 40
    ) -> List[Dict[str, Any]]:
        """List installed applications, versions, and publishers."""
        pass

    @abstractmethod
    def detect_managers(self) -> List[Dict[str, Any]]:
        """Detect available package managers and versions."""
        pass

    @abstractmethod
    def find_executable(self, name: str) -> Dict[str, Any]:
        """Find executable in PATH or standard system directories."""
        pass

    @abstractmethod
    def install_package(
        self, package_name: str, manager: Optional[str] = None, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Install a package via OS-appropriate package manager."""
        pass

    @abstractmethod
    def verify_installation(
        self, package_name: str, executable_name: Optional[str] = None, expected_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify package installation, version output, and executable presence."""
        pass


class DiagnosticsProvider(ABC):
    @abstractmethod
    def get_system_health(self) -> Dict[str, Any]:
        """Compute system health score, resource bottlenecks, and top consumers."""
        pass

    @abstractmethod
    def query_event_log(
        self, channel: str = "System", limit: int = 20, level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query system logs (Windows Event Log or Linux journalctl/syslog)."""
        pass

    @abstractmethod
    def check_updates(self) -> Dict[str, Any]:
        """Query pending system updates."""
        pass

    @abstractmethod
    def clean_temp(self, dry_run: bool = True) -> Dict[str, Any]:
        """Identify or clean temporary and cache directories."""
        pass


class GUIProvider(ABC):
    @abstractmethod
    def list_windows(
        self, title_filter: Optional[str] = None, include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        """List desktop application windows."""
        pass

    @abstractmethod
    def focus_window(self, title: Optional[str] = None, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """Focus an application window."""
        pass

    @abstractmethod
    def launch_app(self, target: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Launch an application or open a file/URI."""
        pass

    @abstractmethod
    def get_app_status(self, process_name: Optional[str] = None, pid: Optional[int] = None) -> Dict[str, Any]:
        """Inspect application process status."""
        pass

    @abstractmethod
    def close_app(
        self, process_name: Optional[str] = None, pid: Optional[int] = None, force: bool = False
    ) -> Dict[str, Any]:
        """Close or terminate an application process."""
        pass

    @abstractmethod
    def capture_screenshot(
        self, output_path: Optional[str] = None, region: Optional[Tuple[int, int, int, int]] = None
    ) -> Dict[str, Any]:
        """Capture screenshot."""
        pass

    @abstractmethod
    def send_input(
        self, keys: Optional[str] = None, text: Optional[str] = None, click_coords: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        """Simulate keyboard or mouse input."""
        pass
