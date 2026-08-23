"""
Context Window and History Management
"""

from typing import List
from app.models.messages import ChatMessage, Role


class ContextManager:
    """Manages conversational history, message trimming, and system prompts."""

    def __init__(self, max_messages: int = 40):
        self.max_messages = max_messages

    def trim_history(self, history: List[ChatMessage]) -> List[ChatMessage]:
        """Trim history to the configured maximum window, preserving non-system turns."""
        non_system = [m for m in history if m.role != Role.SYSTEM]
        if len(non_system) > self.max_messages:
            return non_system[-self.max_messages :]
        return non_system

    def prepare_messages(
        self,
        system_prompt: str,
        history: List[ChatMessage],
        new_message: ChatMessage,
    ) -> List[ChatMessage]:
        """Combine system prompt, trimmed history, and new message into a context list."""
        messages: List[ChatMessage] = []

        # Always inject system prompt first
        messages.append(ChatMessage(role=Role.SYSTEM, content=system_prompt))

        # Add trimmed history
        messages.extend(self.trim_history(history))

        # Add new message
        messages.append(new_message)

        return messages
