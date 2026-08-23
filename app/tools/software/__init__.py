"""
Software and Environment Management Tools Subsystem
"""

from app.tools.registry import ToolRegistry
from app.tools.software.detect import DetectPackageManagersTool, FindExecutableTool
from app.tools.software.env_config import ConfigureEnvironmentTool
from app.tools.software.install import InstallSoftwareTool
from app.tools.software.verify import VerifySoftwareTool

__all__ = [
    "DetectPackageManagersTool",
    "FindExecutableTool",
    "InstallSoftwareTool",
    "ConfigureEnvironmentTool",
    "VerifySoftwareTool",
    "register_software_tools",
]


def register_software_tools(registry: ToolRegistry) -> None:
    """Register software tools into the registry."""
    registry.register(DetectPackageManagersTool())
    registry.register(FindExecutableTool())
    registry.register(InstallSoftwareTool())
    registry.register(ConfigureEnvironmentTool())
    registry.register(VerifySoftwareTool())
