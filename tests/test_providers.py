"""
Unit tests for Provider factory and LLM message adapters.
"""

import pytest
from app.config import ProviderConfig
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.tools import ToolDefinition
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.factory import create_provider
from app.providers.gemini_provider import GeminiProvider
from app.providers.openai_provider import OpenAIProvider


def test_provider_factory():
    openai_cfg = ProviderConfig(provider="openai", api_key="sk-test", model="gpt-4o")
    p1 = create_provider(openai_cfg)
    assert isinstance(p1, OpenAIProvider)

    anthropic_cfg = ProviderConfig(provider="anthropic", api_key="sk-ant", model="claude-3-5-sonnet")
    p2 = create_provider(anthropic_cfg)
    assert isinstance(p2, AnthropicProvider)

    gemini_cfg = ProviderConfig(provider="gemini", api_key="gem-test", model="gemini-2.5-flash")
    p3 = create_provider(gemini_cfg)
    assert isinstance(p3, GeminiProvider)

    with pytest.raises(ValueError):
        create_provider(ProviderConfig(provider="unknown_provider"))


def test_openai_message_formatting():
    provider = OpenAIProvider(api_key="test", model="gpt-4o")
    tc = ToolCall(id="call_abc", name="test_fn", arguments={"x": 1})
    messages = [
        ChatMessage(role=Role.SYSTEM, content="System prompt"),
        ChatMessage(role=Role.USER, content="Run tool"),
        ChatMessage(role=Role.ASSISTANT, tool_calls=[tc]),
        ChatMessage(role=Role.TOOL, tool_call_id="call_abc", name="test_fn", content="Result 42"),
    ]

    formatted = provider._format_messages(messages)
    assert len(formatted) == 4
    assert formatted[0]["role"] == "system"
    assert formatted[2]["role"] == "assistant"
    assert "tool_calls" in formatted[2]
    assert formatted[3]["role"] == "tool"
    assert formatted[3]["tool_call_id"] == "call_abc"


def test_anthropic_message_formatting():
    provider = AnthropicProvider(api_key="test", model="claude-3-5-sonnet")
    tc = ToolCall(id="call_ant_1", name="test_fn", arguments={"x": 1})
    messages = [
        ChatMessage(role=Role.SYSTEM, content="Claude system prompt"),
        ChatMessage(role=Role.USER, content="Hello Claude"),
        ChatMessage(role=Role.ASSISTANT, tool_calls=[tc]),
        ChatMessage(role=Role.TOOL, tool_call_id="call_ant_1", name="test_fn", content="Anthropic Result"),
    ]

    system_prompt, formatted = provider._format_messages_and_system(messages)
    assert system_prompt == "Claude system prompt"
    assert len(formatted) == 3
    assert formatted[0]["role"] == "user"
    assert formatted[1]["role"] == "assistant"
    assert formatted[1]["content"][0]["type"] == "tool_use"
    assert formatted[2]["role"] == "user"
    assert formatted[2]["content"][0]["type"] == "tool_result"
