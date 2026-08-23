"""
Multi-Tier Memory Subsystem and Registration
"""

from app.memory.models import KnowledgeItem, OperationalRecord, UserPreference
from app.memory.store import MemoryStore
from app.memory.tools import GetPreferencesTool, SaveKnowledgeTool, SearchKnowledgeTool, SetPreferenceTool
from app.tools.registry import ToolRegistry


def register_memory_tools(registry: ToolRegistry, store: MemoryStore) -> None:
    """Register all memory and knowledge management tools."""
    registry.register(SetPreferenceTool(store))
    registry.register(GetPreferencesTool(store))
    registry.register(SaveKnowledgeTool(store))
    registry.register(SearchKnowledgeTool(store))


__all__ = [
    "MemoryStore",
    "UserPreference",
    "OperationalRecord",
    "KnowledgeItem",
    "SetPreferenceTool",
    "GetPreferencesTool",
    "SaveKnowledgeTool",
    "SearchKnowledgeTool",
    "register_memory_tools",
]
