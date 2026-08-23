"""
Terminal Execution Tool Subsystem
"""

from app.tools.registry import ToolRegistry
from app.tools.terminal.exec_tool import ExecuteTerminalCommandTool
from app.tools.terminal.policy import CommandPolicyEngine
from app.tools.terminal.runner import CommandRunner

__all__ = [
    "ExecuteTerminalCommandTool",
    "CommandRunner",
    "CommandPolicyEngine",
    "register_terminal_tools",
]


def register_terminal_tools(registry: ToolRegistry) -> None:
    """Register terminal execution tools into registry."""
    registry.register(ExecuteTerminalCommandTool())
