"""
Integration and Unit tests for Agent Orchestrator pipeline.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest
from app.agent.orchestrator import AgentOrchestrator
from app.config import AgentConfig
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.tools import PermissionLevel, ToolDefinition
from app.providers.base import BaseLLMProvider
from app.storage.audit_store import AuditStore
from app.storage.database import Database
from app.storage.session_store import SessionStore
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM Provider for deterministic testing."""

    def __init__(self, responses: List[ChatMessage]):
        super().__init__()
        self.responses = responses
        self.call_count = 0

    def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
    ) -> ChatMessage:
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return ChatMessage(role=Role.ASSISTANT, content="Default mock response")


class DummyEchoTool(BaseTool):
    name = "echo_tool"
    description = "Echoes input text"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    def _run(self, text: str) -> str:
        return f"Echo: {text}"


class SensitiveTool(BaseTool):
    name = "sensitive_tool"
    description = "Requires level 2 approval"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    def _run(self) -> str:
        return "Sensitive action performed"


@pytest.fixture
def agent_components(tmp_path: Path):
    db = Database(tmp_path / "test_orchestrator.db")
    session_store = SessionStore(db)
    audit_store = AuditStore(db)
    tool_registry = ToolRegistry()
    tool_registry.register(DummyEchoTool())
    tool_registry.register(SensitiveTool())

    config = AgentConfig()
    return config, db, session_store, audit_store, tool_registry


def test_orchestrator_conversational_response(agent_components):
    config, db, session_store, audit_store, tool_registry = agent_components

    mock_provider = MockLLMProvider([
        ChatMessage(role=Role.ASSISTANT, content="Hello! How can I assist you with Windows today?")
    ])

    orchestrator = AgentOrchestrator(
        config=config,
        provider=mock_provider,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=tool_registry,
    )

    session = session_store.create_session()
    response = orchestrator.process_message(
        session_id=session.id,
        user_text="Hi there",
    )

    assert "Hello! How can I assist you with Windows today?" in response.content
    assert "Completed in" in response.content
    messages = session_store.get_messages(session.id)
    assert len(messages) == 2  # user + assistant
    assert messages[0].content == "Hi there"
    assert "Hello! How can I assist you with Windows today?" in messages[1].content


def test_orchestrator_tool_calling_loop(agent_components):
    config, db, session_store, audit_store, tool_registry = agent_components

    # Step 1: Model asks for tool call
    # Step 2: Model receives tool result and produces final answer
    tool_call = ToolCall(id="call_1", name="echo_tool", arguments={"text": "Windows Agent"})
    mock_provider = MockLLMProvider([
        ChatMessage(role=Role.ASSISTANT, content="Let me run echo.", tool_calls=[tool_call]),
        ChatMessage(role=Role.ASSISTANT, content="The echoed text is 'Echo: Windows Agent'."),
    ])

    orchestrator = AgentOrchestrator(
        config=config,
        provider=mock_provider,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=tool_registry,
    )

    session = session_store.create_session()
    response = orchestrator.process_message(
        session_id=session.id,
        user_text="Echo something",
    )

    assert "The echoed text is 'Echo: Windows Agent'." in response.content
    assert "Completed in" in response.content
    messages = session_store.get_messages(session.id)
    # user -> assistant(tool_call) -> tool(result) -> assistant(final)
    assert len(messages) == 4
    assert messages[2].role == Role.TOOL
    assert messages[2].content == "Echo: Windows Agent"


def test_orchestrator_permission_denial(agent_components):
    config, db, session_store, audit_store, tool_registry = agent_components

    tool_call = ToolCall(id="call_sens", name="sensitive_tool", arguments={})
    mock_provider = MockLLMProvider([
        ChatMessage(role=Role.ASSISTANT, tool_calls=[tool_call]),
        ChatMessage(role=Role.ASSISTANT, content="Action could not be performed due to permissions."),
    ])

    # Explicitly deny in approval callback
    orchestrator = AgentOrchestrator(
        config=config,
        provider=mock_provider,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=tool_registry,
        approval_callback=lambda tool_name, call, level: False,
    )

    session = session_store.create_session()
    response = orchestrator.process_message(
        session_id=session.id,
        user_text="Run sensitive tool",
    )

    assert "permissions" in response.content.lower()
    messages = session_store.get_messages(session.id)
    assert "Permission Denied" in messages[2].content
