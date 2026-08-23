"""
Google Gemini API Provider
"""

from typing import Any, Dict, List, Optional
import httpx
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.tools import ToolDefinition
from app.providers.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Provider for Google Gemini models via Gemini REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_seconds: int = 60,
    ):
        super().__init__(
            api_key=api_key or "",
            model=model,
            base_url=base_url or "https://generativelanguage.googleapis.com/v1beta",
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )

    def _format_gemini_contents(
        self, messages: List[ChatMessage]
    ) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Convert ChatMessage list to Gemini contents and system instruction."""
        system_instruction: Optional[Dict[str, Any]] = None
        contents: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_instruction = {"parts": [{"text": msg.content or ""}]}
                continue

            gemini_role = "user" if msg.role in (Role.USER, Role.TOOL) else "model"
            parts: List[Dict[str, Any]] = []

            if msg.content:
                parts.append({"text": msg.content})

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append(
                        {
                            "functionCall": {
                                "name": tc.name,
                                "args": tc.arguments,
                            }
                        }
                    )

            if msg.role == Role.TOOL:
                parts.append(
                    {
                        "functionResponse": {
                            "name": msg.name or "tool_output",
                            "response": {"output": msg.content or ""},
                        }
                    }
                )

            if parts:
                contents.append({"role": gemini_role, "parts": parts})

        return system_instruction, contents

    def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
    ) -> ChatMessage:
        """Call Gemini generateContent API."""
        endpoint = (
            f"{self.base_url.rstrip('/')}/models/{self.model}:generateContent?key={self.api_key}"
        )
        headers = {"Content-Type": "application/json"}

        system_instruction, contents = self._format_gemini_contents(messages)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature if temperature is not None else self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }

        if system_instruction:
            payload["system_instruction"] = system_instruction

        if tools:
            declarations = [tool.to_gemini_schema() for tool in tools]
            payload["tools"] = [{"function_declarations": declarations}]

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return ChatMessage(
                role=Role.ASSISTANT,
                content="[No response returned by Gemini model]",
            )

        candidate = candidates[0]
        content_parts = candidate.get("content", {}).get("parts", [])

        text_content = ""
        tool_calls: List[ToolCall] = []

        for part in content_parts:
            if "text" in part:
                text_content += part["text"]
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    ToolCall(
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    )
                )

        return ChatMessage(
            role=Role.ASSISTANT,
            content=text_content if text_content else None,
            tool_calls=tool_calls if tool_calls else None,
            metadata={"usage": data.get("usageMetadata", {})},
        )
