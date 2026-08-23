"""
macOS Concrete System Providers Package
"""

from app.tools.system.macos.diagnostics_provider import MacOSDiagnosticsProvider
from app.tools.system.macos.gui_provider import MacOSGUIProvider
from app.tools.system.macos.hardware_provider import MacOSHardwareInfoProvider
from app.tools.system.macos.network_provider import MacOSNetworkInfoProvider
from app.tools.system.macos.os_provider import MacOSSystemInfoProvider
from app.tools.system.macos.process_provider import MacOSProcessProvider
from app.tools.system.macos.service_provider import MacOSServiceProvider
from app.tools.system.macos.software_provider import MacOSSoftwareProvider
from app.tools.system.macos.storage_provider import MacOSStorageInfoProvider

__all__ = [
    "MacOSSystemInfoProvider",
    "MacOSHardwareInfoProvider",
    "MacOSStorageInfoProvider",
    "MacOSNetworkInfoProvider",
    "MacOSProcessProvider",
    "MacOSServiceProvider",
    "MacOSSoftwareProvider",
    "MacOSDiagnosticsProvider",
    "MacOSGUIProvider",
]
