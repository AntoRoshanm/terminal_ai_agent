"""
Multi-Tier Memory and Knowledge Data Models
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UserPreference(BaseModel):
    """Persistent user preference setting."""
    key: str
    value: Any
    category: str = "general"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OperationalRecord(BaseModel):
    """Operational record of task execution, fixes, and outcomes."""
    id: Optional[int] = None
    goal: str
    tool_used: str
    status: str  # "SUCCESS", "FAILED", "RECOVERED"
    error_type: Optional[str] = None
    fix_applied: Optional[str] = None
    verified: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeItem(BaseModel):
    """Structured knowledge base item for persistent reference."""
    id: str
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
