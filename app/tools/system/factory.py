"""
System Provider Factory Resolving Windows, Linux, or macOS Implementations
"""

from typing import Optional
from app.models.state import PlatformInfo
from app.platform.contracts import (
    DiagnosticsProvider,
    GUIProvider,
    HardwareInfoProvider,
    NetworkInfoProvider,
    ProcessProvider,
    ServiceProvider,
    SoftwareProvider,
    StorageInfoProvider,
    SystemInfoProvider,
)
from app.platform.detect import get_platform_info


class SystemProviderFactory:
    """Factory resolving OS-specific concrete provider singletons across Windows, Linux, and macOS."""

    @staticmethod
    def get_system_info_provider(platform_info: Optional[PlatformInfo] = None) -> SystemInfoProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.os_provider import WindowsSystemInfoProvider
            return WindowsSystemInfoProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.os_provider import MacOSSystemInfoProvider
            return MacOSSystemInfoProvider(info)
        from app.tools.system.linux.os_provider import LinuxSystemInfoProvider
        return LinuxSystemInfoProvider()

    @staticmethod
    def get_hardware_info_provider(platform_info: Optional[PlatformInfo] = None) -> HardwareInfoProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.hardware_provider import WindowsHardwareInfoProvider
            return WindowsHardwareInfoProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.hardware_provider import MacOSHardwareInfoProvider
            return MacOSHardwareInfoProvider()
        from app.tools.system.linux.hardware_provider import LinuxHardwareInfoProvider
        return LinuxHardwareInfoProvider()

    @staticmethod
    def get_storage_info_provider(platform_info: Optional[PlatformInfo] = None) -> StorageInfoProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.storage_provider import WindowsStorageInfoProvider
            return WindowsStorageInfoProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.storage_provider import MacOSStorageInfoProvider
            return MacOSStorageInfoProvider()
        from app.tools.system.linux.storage_provider import LinuxStorageInfoProvider
        return LinuxStorageInfoProvider()

    @staticmethod
    def get_network_info_provider(platform_info: Optional[PlatformInfo] = None) -> NetworkInfoProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.network_provider import WindowsNetworkInfoProvider
            return WindowsNetworkInfoProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.network_provider import MacOSNetworkInfoProvider
            return MacOSNetworkInfoProvider()
        from app.tools.system.linux.network_provider import LinuxNetworkInfoProvider
        return LinuxNetworkInfoProvider()

    @staticmethod
    def get_process_provider(platform_info: Optional[PlatformInfo] = None) -> ProcessProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.process_provider import WindowsProcessProvider
            return WindowsProcessProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.process_provider import MacOSProcessProvider
            return MacOSProcessProvider()
        from app.tools.system.linux.process_provider import LinuxProcessProvider
        return LinuxProcessProvider()

    @staticmethod
    def get_service_provider(platform_info: Optional[PlatformInfo] = None) -> ServiceProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.service_provider import WindowsServiceProvider
            return WindowsServiceProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.service_provider import MacOSServiceProvider
            return MacOSServiceProvider()
        from app.tools.system.linux.service_provider import LinuxServiceProvider
        return LinuxServiceProvider()

    @staticmethod
    def get_software_provider(platform_info: Optional[PlatformInfo] = None) -> SoftwareProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.software_provider import WindowsSoftwareProvider
            return WindowsSoftwareProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.software_provider import MacOSSoftwareProvider
            return MacOSSoftwareProvider()
        from app.tools.system.linux.software_provider import LinuxSoftwareProvider
        return LinuxSoftwareProvider()

    @staticmethod
    def get_diagnostics_provider(platform_info: Optional[PlatformInfo] = None) -> DiagnosticsProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.diagnostics_provider import WindowsDiagnosticsProvider
            return WindowsDiagnosticsProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.diagnostics_provider import MacOSDiagnosticsProvider
            return MacOSDiagnosticsProvider()
        from app.tools.system.linux.diagnostics_provider import LinuxDiagnosticsProvider
        return LinuxDiagnosticsProvider()

    @staticmethod
    def get_gui_provider(platform_info: Optional[PlatformInfo] = None) -> GUIProvider:
        info = platform_info or get_platform_info()
        if info.os_family == "windows":
            from app.tools.system.windows.gui_provider import WindowsGUIProvider
            return WindowsGUIProvider()
        elif info.os_family == "macos":
            from app.tools.system.macos.gui_provider import MacOSGUIProvider
            return MacOSGUIProvider()
        from app.tools.system.linux.gui_provider import LinuxGUIProvider
        return LinuxGUIProvider()
