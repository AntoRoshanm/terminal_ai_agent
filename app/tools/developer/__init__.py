"""
Developer and Engineering Tools Subsystem
"""

from app.tools.developer.dev_services import ManageDevServiceTool
from app.tools.developer.git_tools import (
    GitBranchTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitStatusTool,
)
from app.tools.developer.test_runner import RunProjectTestsTool
from app.tools.registry import ToolRegistry

__all__ = [
    "GitStatusTool",
    "GitLogTool",
    "GitDiffTool",
    "GitCommitTool",
    "GitBranchTool",
    "RunProjectTestsTool",
    "ManageDevServiceTool",
    "register_developer_tools",
]


def register_developer_tools(registry: ToolRegistry) -> None:
    """Register software developer tools into the registry."""
    registry.register(GitStatusTool())
    registry.register(GitLogTool())
    registry.register(GitDiffTool())
    registry.register(GitCommitTool())
    registry.register(GitBranchTool())
    registry.register(RunProjectTestsTool())
    registry.register(ManageDevServiceTool())
