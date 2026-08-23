"""
Native Ollama LLM Provider with Local Tool Calling
"""

import ast
import json
import re
import uuid
from typing import Any, Dict, List, Optional
import httpx
from app.logging import logger
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.tools import ToolDefinition
from app.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Provider for local Ollama instances using native /api/chat with tool calling support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen2.5:3b",
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_seconds: int = 120,
        num_ctx: int = 8192,
    ):
        raw_url = base_url or "http://localhost:11434"
        if raw_url.endswith("/v1"):
            raw_url = raw_url[:-3]
        super().__init__(
            api_key=api_key or "ollama",
            model=model,
            base_url=raw_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
        self.num_ctx = num_ctx

    def _format_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Format ChatMessage list into Ollama /api/chat format."""
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
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]

            if msg.role == Role.TOOL:
                item["role"] = "tool"
                item["content"] = msg.content or ""
                if msg.name:
                    item["name"] = msg.name
                if msg.tool_call_id:
                    item["tool_call_id"] = msg.tool_call_id

            formatted.append(item)
        return formatted

    def _extract_text_tool_calls(self, content: str, tools: List[ToolDefinition]) -> Optional[List[ToolCall]]:
        """Extract tool calls emitted as text or markdown blocks if native tool calling was bypassed."""
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
                        parsed_node = ast.parse(f"fn({args_raw})")
                        call_node = parsed_node.body[0].value  # type: ignore
                        param_props = list(tool_def.parameters.get("properties", {}).keys())
                        for i, arg in enumerate(call_node.args):
                            if i < len(param_props):
                                parsed_args[param_props[i]] = ast.literal_eval(arg)
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
        """Call Ollama native /api/chat endpoint."""
        endpoint = f"{self.base_url.rstrip('/')}/api/chat"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.num_ctx,
            },
        }

        if tools:
            payload["tools"] = [tool.to_openai_schema() for tool in tools]

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        message = data.get("message", {})
        content = message.get("content")
        raw_tool_calls = message.get("tool_calls")

        tool_calls: Optional[List[ToolCall]] = None
        if raw_tool_calls:
            tool_calls = []
            for rtc in raw_tool_calls:
                fn = rtc.get("function", {})
                tool_name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw": args}
                tool_calls.append(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name=tool_name,
                        arguments=args if isinstance(args, dict) else {},
                    )
                )
        elif tools and content:
            tool_calls = self._extract_text_tool_calls(content, tools)

        if content:
            # Strip Llama 3 / Qwen raw chat template role headers (Directive v5.3 Section 2)
            content = re.sub(r"^(?:<\|start_header_id\|>)?\s*(?:assistant|system|user)\s*(?:<\|end_header_id\|>)?\s*\n*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"<\|(?:start_header_id|end_header_id|eot_id|im_start|im_end)\|>", "", content)
            content = content.strip()

        return ChatMessage(
            role=Role.ASSISTANT,
            content=content if not tool_calls else None,
            tool_calls=tool_calls,
            metadata={"eval_count": data.get("eval_count", 0), "total_duration": data.get("total_duration", 0)},
        )
