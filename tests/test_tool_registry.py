"""
Unit tests for Tool registry, permission boundaries, and execution.
"""

from typing import Any, Dict
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


class MockSystemInfoTool(BaseTool):
    name = "get_system_info"
    description = "Inspect system metadata"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"section": {"type": "string"}},
        }

    def _run(self, section: str = "all") -> Dict[str, Any]:
        return {"os": "Windows 11", "section": section}


class MockDeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Delete a file from disk"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

    def _run(self, path: str) -> str:
        return f"File {path} deleted."


def test_tool_registry_registration_and_filtering():
    registry = ToolRegistry()
    tool1 = MockSystemInfoTool()
    tool2 = MockDeleteFileTool()

    registry.register(tool1)
    registry.register(tool2)

    # All tools
    assert len(registry.list_tools()) == 2

    # Level 0 read-only tools only
    level_0_tools = registry.list_tools(max_permission=PermissionLevel.LEVEL_0_READ_ONLY)
    assert len(level_0_tools) == 1
    assert level_0_tools[0].name == "get_system_info"


def test_tool_execution_success():
    registry = ToolRegistry()
    registry.register(MockSystemInfoTool())

    res = registry.execute(
        name="get_system_info",
        tool_call_id="call_99",
        arguments={"section": "cpu"},
    )
    assert res.success
    assert res.tool_call_id == "call_99"
    assert res.data == {"os": "Windows 11", "section": "cpu"}
    assert res.duration_ms >= 0


def test_tool_execution_not_found():
    registry = ToolRegistry()
    res = registry.execute(
        name="non_existent_tool",
        tool_call_id="call_100",
        arguments={},
    )
    assert not res.success
    assert "not found" in res.error
