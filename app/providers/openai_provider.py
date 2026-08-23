"""
OpenAI & OpenAI-Compatible Endpoint Provider
"""

import ast
import json
import re
import uuid
from typing import Any, Dict, List, Optional
import httpx
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.tools import ToolDefinition
from app.providers.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """Provider for OpenAI and OpenAI-compatible endpoints (Ollama, OpenRouter, vLLM)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_seconds: int = 60,
    ):
        super().__init__(
            api_key=api_key or "no-key-required",
            model=model,
            base_url=base_url or "https://api.openai.com/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )

    def _format_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Format ChatMessage instances into OpenAI API format."""
        formatted = []
        for msg in messages:
            item: Dict[str, Any] = {"role": msg.role.value}

            if msg.content is not None:
                item["content"] = msg.content
            else:
                item["content"] = ""

            if msg.role == Role.ASSISTANT and msg.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]

            if msg.role == Role.TOOL:
                item["tool_call_id"] = msg.tool_call_id or ""
                if msg.name:
                    item["name"] = msg.name

            formatted.append(item)
        return formatted

    def _extract_text_tool_calls(self, content: str, tools: List[ToolDefinition]) -> Optional[List[ToolCall]]:
        """Extract tool calls emitted as text or markdown blocks by smaller local LLMs."""
        if not content or not tools:
            return None

        tool_map = {t.name: t for t in tools}

        # 1. Check for JSON objects
        json_matches = re.findall(r"\{[^{}]*(?:name|tool)[^{}]*\}", content, re.DOTALL)
        for jm in json_matches:
            try:
                data = json.loads(jm)
                t_name = data.get("name") or data.get("tool")
                if t_name in tool_map:
                    args = data.get("arguments") or data.get("parameters") or {}
                    return [ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=t_name, arguments=args)]
            except Exception:
                pass

        # 2. Check for function-call syntax: tool_name(arg1, arg2) or tool_name(k1=v1, k2=v2)
        for t_name, tool_def in tool_map.items():
            pattern = rf"\b{re.escape(t_name)}\s*\((.*?)\)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                args_raw = match.group(1).strip()
                parsed_args: Dict[str, Any] = {}
                if args_raw:
                    try:
                        # Parse python-style arguments safely
                        parsed_node = ast.parse(f"fn({args_raw})")
                        call_node = parsed_node.body[0].value  # type: ignore
                        # Positional args mapped to tool parameter properties
                        param_props = list(tool_def.parameters.get("properties", {}).keys())
                        for i, arg in enumerate(call_node.args):
                            if i < len(param_props):
                                parsed_args[param_props[i]] = ast.literal_eval(arg)
                        # Keyword args
                        for kw in call_node.keywords:
                            if kw.arg:
                                parsed_args[kw.arg] = ast.literal_eval(kw.value)
                        return [ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=t_name, arguments=parsed_args)]
                    except Exception:
                        pass

        return None

    def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
    ) -> ChatMessage:
        """Call OpenAI chat completion API."""
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = [tool.to_openai_schema() for tool in tools]
            payload["tool_choice"] = "auto"

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]["message"]
        content = choice.get("content")
        raw_tool_calls = choice.get("tool_calls")

        tool_calls: Optional[List[ToolCall]] = None
        if raw_tool_calls:
            tool_calls = []
            for rtc in raw_tool_calls:
                fn = rtc.get("function", {})
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {"raw": args_str}
                tool_calls.append(
                    ToolCall(
                        id=rtc.get("id", ""),
                        name=fn.get("name", ""),
                        arguments=args,
                    )
                )
        elif tools and content:
            # Fallback parser for text tool calls emitted by smaller local models
            tool_calls = self._extract_text_tool_calls(content, tools)

        return ChatMessage(
            role=Role.ASSISTANT,
            content=content if not tool_calls else None,
            tool_calls=tool_calls,
            metadata={"usage": data.get("usage", {})},
        )
