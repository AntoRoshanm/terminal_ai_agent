"""
Tool and Permission Data Models
"""

from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PermissionLevel(IntEnum):
    """Permission levels corresponding to Blueprint Section 7."""
    LEVEL_0_READ_ONLY = 0           # Auto-allowed (OS info, port checks, process list)
    LEVEL_1_LOW_RISK = 1            # Auto-allowed or low policy (temp files, code gen)
    LEVEL_2_APPROVAL_REQUIRED = 2   # Requires user confirmation (install, service, files)
    LEVEL_3_HIGH_RISK = 3           # High risk, explicit confirmation (system, registry)


class ToolParameter(BaseModel):
    """Schema for a single tool argument."""
    name: str
    type: str = "string"
    description: str
    required: bool = True
    enum: Optional[List[Any]] = None
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    """Metadata and interface definition for a tool."""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": []}
    )
    permission_level: PermissionLevel = PermissionLevel.LEVEL_0_READ_ONLY
    timeout_seconds: int = 30
    category: str = "general"
    requires_confirmation: bool = False

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI / Ollama function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Convert to Anthropic tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_gemini_schema(self) -> Dict[str, Any]:
        """Convert to Google Gemini function declaration schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolExecutionResult(BaseModel):
    """Structured execution output from a tool call."""
    tool_name: str
    tool_call_id: str
    success: bool
    verified_success: bool = True
    stdout: str = ""
    stderr: str = ""
    data: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: int = 0
    permission_level: PermissionLevel = PermissionLevel.LEVEL_0_READ_ONLY
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def output_text(self) -> str:
        """Get formatted output string for the model."""
        if self.success:
            if self.stdout:
                return self.stdout
            if self.data is not None:
                import json
                try:
                    return json.dumps(self.data, indent=2)
                except Exception:
                    return str(self.data)
            return "Command executed successfully with no output."
        return f"ERROR: {self.error or self.stderr or self.stdout or 'Execution failed'}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return self.model_dump()
