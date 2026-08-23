"""
Filesystem Tools Subsystem
"""

from app.tools.filesystem.edit_file import EditFileTool
from app.tools.filesystem.inspect_directory import InspectDirectoryTool
from app.tools.filesystem.manage_files import ManageFilesTool
from app.tools.filesystem.read_file import ReadFileTool
from app.tools.filesystem.safety import PathSafety
from app.tools.filesystem.search_files import SearchFilesTool
from app.tools.filesystem.write_file import WriteFileTool
from app.tools.registry import ToolRegistry

__all__ = [
    "PathSafety",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "SearchFilesTool",
    "InspectDirectoryTool",
    "ManageFilesTool",
    "register_filesystem_tools",
]


def register_filesystem_tools(registry: ToolRegistry) -> None:
    """Register all filesystem tools into the registry."""
    safety = PathSafety()
    registry.register(ReadFileTool(safety))
    registry.register(WriteFileTool(safety))
    registry.register(EditFileTool(safety))
    registry.register(SearchFilesTool(safety))
    registry.register(InspectDirectoryTool(safety))
    registry.register(ManageFilesTool(safety))
