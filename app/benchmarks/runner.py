"""
Model Evaluation and Agent Benchmark Runner
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.messages import ChatMessage, Role
from app.models.tools import ToolDefinition
from app.providers.base import BaseLLMProvider


class BenchmarkResult(BaseModel):
    """Result of an evaluation benchmark run on a model."""
    provider_name: str
    model_name: str
    total_tests: int = 0
    passed_tests: int = 0
    avg_latency_ms: float = 0.0
    tool_calling_accuracy: float = 0.0
    intent_detection_accuracy: float = 0.0
    details: List[Dict[str, Any]] = Field(default_factory=list)


class BenchmarkRunner:
    """Runs standard evaluation scenarios to benchmark LLM reasoning and agent quality."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def run_benchmarks(self) -> BenchmarkResult:
        """Run full evaluation suite against the active provider."""
        tests = [
            self._test_intent_conversational,
            self._test_intent_inspection,
            self._test_tool_calling_single,
            self._test_tool_calling_parameters,
            self._test_error_interpretation,
        ]

        latencies: List[float] = []
        details: List[Dict[str, Any]] = []
        passed_count = 0
        tool_correct = 0
        intent_correct = 0

        dummy_tools = [
            ToolDefinition(
                name="os_info",
                description="Get Windows OS version and build",
                parameters_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="check_port",
                description="Check if a specific TCP port is listening",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "port": {"type": "integer", "description": "Port number"}
                    },
                    "required": ["port"],
                },
            ),
        ]

        for test_fn in tests:
            start = time.perf_counter()
            try:
                res = test_fn(dummy_tools)
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies.append(elapsed_ms)
                if res.get("passed"):
                    passed_count += 1
                if res.get("tool_correct"):
                    tool_correct += 1
                if res.get("intent_correct"):
                    intent_correct += 1
                res["latency_ms"] = round(elapsed_ms, 2)
                details.append(res)
            except Exception as e:
                details.append({"name": test_fn.__name__, "passed": False, "error": str(e)})

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        return BenchmarkResult(
            provider_name=type(self.provider).__name__,
            model_name=self.provider.model,
            total_tests=len(tests),
            passed_tests=passed_count,
            avg_latency_ms=round(avg_latency, 2),
            tool_calling_accuracy=round((tool_correct / 2) * 100, 1),
            intent_detection_accuracy=round((intent_correct / 2) * 100, 1),
            details=details,
        )

    def _test_intent_conversational(self, tools: List[ToolDefinition]) -> Dict[str, Any]:
        msgs = [ChatMessage(role=Role.USER, content="Hello, what is machine learning?")]
        resp = self.provider.generate(msgs, tools=tools)
        is_conversational = not resp.tool_calls and bool(resp.content)
        return {
            "name": "intent_conversational",
            "passed": is_conversational,
            "intent_correct": is_conversational,
        }

    def _test_intent_inspection(self, tools: List[ToolDefinition]) -> Dict[str, Any]:
        msgs = [ChatMessage(role=Role.USER, content="What is my Windows OS version?")]
        resp = self.provider.generate(msgs, tools=tools)
        called_os_info = any(tc.name == "os_info" for tc in (resp.tool_calls or []))
        return {
            "name": "intent_inspection",
            "passed": called_os_info,
            "intent_correct": called_os_info,
            "tool_correct": called_os_info,
        }

    def _test_tool_calling_single(self, tools: List[ToolDefinition]) -> Dict[str, Any]:
        msgs = [ChatMessage(role=Role.USER, content="Check if port 8080 is listening")]
        resp = self.provider.generate(msgs, tools=tools)
        called_port = any(tc.name == "check_port" for tc in (resp.tool_calls or []))
        return {
            "name": "tool_calling_single",
            "passed": called_port,
            "tool_correct": called_port,
        }

    def _test_tool_calling_parameters(self, tools: List[ToolDefinition]) -> Dict[str, Any]:
        msgs = [ChatMessage(role=Role.USER, content="Check if port 5432 is open")]
        resp = self.provider.generate(msgs, tools=tools)
        param_correct = False
        if resp.tool_calls:
            for tc in resp.tool_calls:
                if tc.name == "check_port" and tc.arguments.get("port") == 5432:
                    param_correct = True
        return {
            "name": "tool_calling_parameters",
            "passed": param_correct,
        }

    def _test_error_interpretation(self, tools: List[ToolDefinition]) -> Dict[str, Any]:
        msgs = [
            ChatMessage(role=Role.USER, content="Why did my command fail?"),
            ChatMessage(role=Role.TOOL, content="Error: Port 5432 is already in use by another process.", tool_call_id="call_1", name="check_port"),
        ]
        resp = self.provider.generate(msgs)
        understood_conflict = bool(resp.content and ("in use" in resp.content.lower() or "conflict" in resp.content.lower() or "5432" in resp.content))
        return {
            "name": "error_interpretation",
            "passed": understood_conflict,
        }
