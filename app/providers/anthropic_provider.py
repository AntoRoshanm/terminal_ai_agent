"""
Anthropic Claude API Provider
"""

from typing import Any, Dict, List, Optional
import httpx
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.tools import ToolDefinition
from app.providers.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Provider for Anthropic Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_seconds: int = 60,
    ):
        super().__init__(
            api_key=api_key or "",
            model=model,
            base_url=base_url or "https://api.anthropic.com/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )

    def _format_messages_and_system(
        self, messages: List[ChatMessage]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """Separate system message and format Claude message blocks."""
        system_content: Optional[str] = None
        formatted: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_content = msg.content
                continue

            if msg.role == Role.USER:
                formatted.append({"role": "user", "content": msg.content or ""})
            elif msg.role == Role.ASSISTANT:
                content_blocks: List[Dict[str, Any]] = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.name,
                                "input": tc.arguments,
                            }
                        )
                formatted.append({"role": "assistant", "content": content_blocks})
            elif msg.role == Role.TOOL:
                formatted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id or "",
                                "content": msg.content or "",
                            }
                        ],
                    }
                )

        return system_content, formatted

    def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
    ) -> ChatMessage:
        """Call Anthropic Messages API."""
        endpoint = f"{self.base_url.rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
        }

        system_prompt, formatted_msgs = self._format_messages_and_system(messages)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_msgs,
            "max_tokens": self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = [t.to_anthropic_schema() for t in tools]

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        text_content = ""
        tool_calls: List[ToolCall] = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        return ChatMessage(
            role=Role.ASSISTANT,
            content=text_content if text_content else None,
            tool_calls=tool_calls if tool_calls else None,
            metadata={"usage": data.get("usage", {})},
        )
