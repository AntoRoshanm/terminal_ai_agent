"""
Unit tests for data models and schema conversions.
"""

from app.models.messages import ChatMessage, Role, ToolCall
from app.models.tools import PermissionLevel, ToolDefinition, ToolExecutionResult


def test_chat_message_serialization():
    tc = ToolCall(id="call_1", name="get_os_info", arguments={"verbose": True})
    msg = ChatMessage(
        role=Role.ASSISTANT,
        content="Inspecting system",
        tool_calls=[tc],
    )
    d = msg.to_dict()
    assert d["role"] == "assistant"
    assert d["content"] == "Inspecting system"
    assert len(d["tool_calls"]) == 1
    assert d["tool_calls"][0]["name"] == "get_os_info"


def test_tool_definition_schemas():
    tool_def = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        permission_level=PermissionLevel.LEVEL_0_READ_ONLY,
    )

    openai_schema = tool_def.to_openai_schema()
    assert openai_schema["type"] == "function"
    assert openai_schema["function"]["name"] == "test_tool"

    anthropic_schema = tool_def.to_anthropic_schema()
    assert anthropic_schema["name"] == "test_tool"
    assert anthropic_schema["input_schema"]["type"] == "object"

    gemini_schema = tool_def.to_gemini_schema()
    assert gemini_schema["name"] == "test_tool"
    assert "parameters" in gemini_schema


def test_tool_execution_result_output():
    res = ToolExecutionResult(
        tool_name="test_tool",
        tool_call_id="call_1",
        success=True,
        stdout="All systems operational",
    )
    assert res.output_text == "All systems operational"

    err_res = ToolExecutionResult(
        tool_name="test_tool",
        tool_call_id="call_1",
        success=False,
        error="Access denied",
        stderr="Elevation required",
    )
    assert "ERROR: Access denied" in err_res.output_text
