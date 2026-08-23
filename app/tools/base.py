"""
Base Abstract Tool Class
"""

from abc import ABC, abstractmethod
import inspect
import time
import traceback
from typing import Any, Dict
from app.models.tools import PermissionLevel, ToolDefinition, ToolExecutionResult


class BaseTool(ABC):
    """Abstract Base Class for all agent tools."""

    name: str
    description: str
    category: str = "general"
    permission_level: PermissionLevel = PermissionLevel.LEVEL_0_READ_ONLY
    timeout_seconds: int = 30
    requires_confirmation: bool = False

    @property
    def definition(self) -> ToolDefinition:
        """Generate ToolDefinition for model registration."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.get_parameters_schema(),
            permission_level=self.permission_level,
            timeout_seconds=self.timeout_seconds,
            category=self.category,
            requires_confirmation=self.requires_confirmation,
        )

    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Return the JSON schema for tool arguments."""
        pass

    @abstractmethod
    def _run(self, **kwargs) -> Any:
        """Internal execution implementation."""
        pass

    def execute(self, tool_call_id: str, **kwargs) -> ToolExecutionResult:
        """Execute the tool with argument safety, error handling, and timing."""
        start_time = time.time()
        try:
            # Robust argument filtering to support various model outputs
            clean_kwargs = {str(k).rstrip(":").strip(): v for k, v in kwargs.items()}
            sig = inspect.signature(self._run)
            has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            if not has_var_keyword:
                accepted = set(sig.parameters.keys())
                filtered_kwargs = {k: v for k, v in clean_kwargs.items() if k in accepted}
            else:
                filtered_kwargs = clean_kwargs

            result = self._run(**filtered_kwargs)
            duration_ms = int((time.time() - start_time) * 1000)

            if isinstance(result, ToolExecutionResult):
                result.tool_call_id = tool_call_id
                result.duration_ms = duration_ms
                return result

            stdout_str = ""
            data_val = None
            verified = True
            if isinstance(result, str):
                stdout_str = result
            elif isinstance(result, dict):
                data_val = result
                verified = result.get("verified_success", True)
                if result.get("error") or result.get("status") == "error":
                    verified = False
            elif isinstance(result, list):
                data_val = result
            else:
                stdout_str = str(result)

            return ToolExecutionResult(
                tool_name=self.name,
                tool_call_id=tool_call_id,
                success=True,
                verified_success=verified,
                stdout=stdout_str,
                data=data_val,
                duration_ms=duration_ms,
                permission_level=self.permission_level,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolExecutionResult(
                tool_name=self.name,
                tool_call_id=tool_call_id,
                success=False,
                verified_success=False,
                error=str(e),
                stderr=traceback.format_exc(),
                duration_ms=duration_ms,
                permission_level=self.permission_level,
            )
