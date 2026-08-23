"""
Base Abstract LLM Provider Interface
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Iterator, List, Optional
from app.models.messages import ChatMessage
from app.models.tools import ToolDefinition


class BaseLLMProvider(ABC):
    """Abstract interface for all model providers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "default",
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_seconds: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
    ) -> ChatMessage:
        """Generate a model response given message history and optional tools."""
        pass
