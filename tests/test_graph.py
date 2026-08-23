"""
Tests for Agent State Graph and Benchmark Suite
"""

from unittest.mock import MagicMock
from app.agent.graph import AgentStateGraph, GraphState
from app.benchmarks.runner import BenchmarkRunner
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.tools import ToolExecutionResult
from app.providers.base import BaseLLMProvider
from app.tools.registry import ToolRegistry


def test_state_graph_conversational_flow():
    mock_provider = MagicMock(spec=BaseLLMProvider)
    mock_provider.generate.return_value = ChatMessage(
        role=Role.ASSISTANT,
        content="Hello! How can I assist you today?",
    )
    registry = ToolRegistry()

    graph = AgentStateGraph(provider=mock_provider, registry=registry)
    state = GraphState(
        session_id="test_sess_1",
        messages=[ChatMessage(role=Role.USER, content="Hello")],
    )

    final_state = graph.run(state)
    assert final_state.completed is True
    assert final_state.final_output == "Hello! How can I assist you today?"
    assert final_state.current_node == "COMPLETE"


def test_state_graph_tool_execution_flow():
    mock_provider = MagicMock(spec=BaseLLMProvider)
    # First response: requests tool call
    mock_provider.generate.side_effect = [
        ChatMessage(
            role=Role.ASSISTANT,
            content=None,
            tool_calls=[ToolCall(id="call_os_info", name="os_info", arguments={})],
        ),
        ChatMessage(
            role=Role.ASSISTANT,
            content="You are running Windows 11 Build 22631.",
        ),
    ]

    registry = ToolRegistry()
    mock_tool = MagicMock()
    mock_tool.name = "os_info"
    mock_tool.execute.return_value = ToolExecutionResult(
        tool_call_id="call_os_info",
        tool_name="os_info",
        success=True,
        data={"os": "Windows 11", "build": "22631"},
    )
    registry.register(mock_tool)

    graph = AgentStateGraph(provider=mock_provider, registry=registry)
    state = GraphState(
        session_id="test_sess_2",
        messages=[ChatMessage(role=Role.USER, content="What is my OS version?")],
    )

    final_state = graph.run(state)
    assert final_state.completed is True
    assert final_state.final_output == "You are running Windows 11 Build 22631."
    assert len(final_state.messages) == 3


def test_benchmark_runner_execution():
    mock_provider = MagicMock(spec=BaseLLMProvider)
    mock_provider.model = "mock-model"
    mock_provider.generate.return_value = ChatMessage(
        role=Role.ASSISTANT,
        content="General AI response.",
    )

    runner = BenchmarkRunner(mock_provider)
    result = runner.run_benchmarks()

    assert result.total_tests == 5
    assert result.model_name == "mock-model"
    assert result.avg_latency_ms >= 0.0
    assert len(result.details) == 5
