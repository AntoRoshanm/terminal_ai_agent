"""
Chat and Message Data Models
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """Represents a tool call requested by the model."""
    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Represents the output of an executed tool call."""
    tool_call_id: str
    name: str
    output: str
    is_error: bool = False


class ChatMessage(BaseModel):
    """Unified message format across all providers and storage."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: Role
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation."""
        data: Dict[str, Any] = {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
        if self.tool_calls:
            data["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.name:
            data["name"] = self.name
        return data
