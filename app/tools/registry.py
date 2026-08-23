"""
Tool Registry for Discovery, Permissions, and Dispatch
"""

import logging
from typing import Dict, List, Optional
from app.models.tools import PermissionLevel, ToolDefinition, ToolExecutionResult
from app.tools.base import BaseTool

logger = logging.getLogger("windows_ai_agent.tools")


class ToolRegistry:
    """Central registry for managing, filtering, and executing agent tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool '{tool.name}'")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool '{tool.name}' (Level {tool.permission_level.value})")

    def get(self, name: str) -> Optional[BaseTool]:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(
        self, max_permission: Optional[PermissionLevel] = None
    ) -> List[BaseTool]:
        """List all registered tools, optionally filtered by permission ceiling."""
        if max_permission is None:
            return list(self._tools.values())
        return [
            t for t in self._tools.values() if t.permission_level <= max_permission
        ]

    def get_definitions(
        self, max_permission: Optional[PermissionLevel] = None
    ) -> List[ToolDefinition]:
        """Return tool definitions for LLM schema generation."""
        tools = self.list_tools(max_permission=max_permission)
        return [t.definition for t in tools]

    def execute(
        self, name: str, tool_call_id: str, arguments: Optional[Dict[str, any]] = None, **kwargs: any
    ) -> ToolExecutionResult:
        """Dispatch execution to the matching tool."""
        tool = self.get(name)
        if not tool:
            return ToolExecutionResult(
                tool_name=name,
                tool_call_id=tool_call_id,
                success=False,
                error=f"Tool '{name}' not found in registry",
                permission_level=PermissionLevel.LEVEL_0_READ_ONLY,
            )

        combined_args = {}
        if arguments and isinstance(arguments, dict):
            combined_args.update(arguments)
        combined_args.update(kwargs)

        return tool.execute(tool_call_id=tool_call_id, **combined_args)

