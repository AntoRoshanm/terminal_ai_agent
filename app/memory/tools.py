"""
Memory & Knowledge Management Tools
"""

from typing import Any, Dict, List, Optional
from app.memory.store import MemoryStore
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class SetPreferenceTool(BaseTool):
    """Tool to save a user preference into persistent memory."""

    name = "memory_set_preference"
    description = "Store a user preference or persistent setting (e.g., preferred editor, project directory, interaction style)."
    category = "memory"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def __init__(self, store: MemoryStore):
        self.store = store

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Unique preference key (e.g. 'editor', 'default_project_dir')",
                },
                "value": {
                    "type": "string",
                    "description": "Preference value to save",
                },
                "category": {
                    "type": "string",
                    "description": "Category: 'general', 'developer', 'ui', 'system' (default: 'general')",
                    "default": "general",
                },
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        }

    def _run(self, key: str, value: Any, category: str = "general") -> Dict[str, Any]:
        pref = self.store.set_preference(key, value, category)
        return {
            "status": "saved",
            "key": pref.key,
            "value": pref.value,
            "category": pref.category,
        }


class GetPreferencesTool(BaseTool):
    """Tool to query stored user preferences."""

    name = "memory_get_preferences"
    description = "Retrieve stored user preferences to personalize behavior or find default directories/tools."
    category = "memory"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def __init__(self, store: MemoryStore):
        self.store = store

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Optional specific preference key to retrieve",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
            },
            "additionalProperties": False,
        }

    def _run(self, key: Optional[str] = None, category: Optional[str] = None) -> Any:
        all_prefs = self.store.list_preferences(category)
        if key:
            val = self.store.get_preference(key)
            if val is not None:
                return {"key": key, "value": val, "found": True}

            # Substring / partial key matching
            matches = [
                {"key": p.key, "value": p.value, "category": p.category}
                for p in all_prefs
                if key.lower() in p.key.lower() or p.key.lower() in key.lower()
            ]
            if matches:
                return {"matched_preferences": matches, "found": True}

        return {
            "preferences": [
                {"key": p.key, "value": p.value, "category": p.category}
                for p in all_prefs
            ],
            "count": len(all_prefs),
        }


class SaveKnowledgeTool(BaseTool):
    """Tool to save a document, technical note, or researched knowledge."""

    name = "memory_save_knowledge"
    description = "Store technical notes, documentation snippets, or researched solutions in persistent knowledge memory."
    category = "memory"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def __init__(self, store: MemoryStore):
        self.store = store

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the knowledge item",
                },
                "content": {
                    "type": "string",
                    "description": "Knowledge or documentation content to store",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional search tags",
                },
                "source": {
                    "type": "string",
                    "description": "Optional source URL or document reference",
                },
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        }

    def _run(self, title: str, content: str, tags: Optional[List[str]] = None, source: Optional[str] = None) -> Dict[str, Any]:
        item = self.store.save_knowledge(title, content, tags, source)
        return {
            "status": "saved",
            "id": item.id,
            "title": item.title,
            "tags": item.tags,
        }


class SearchKnowledgeTool(BaseTool):
    """Tool to search persistent knowledge memory."""

    name = "memory_search_knowledge"
    description = "Search stored technical knowledge, documentation, and past notes."
    category = "memory"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def __init__(self, store: MemoryStore):
        self.store = store

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword or topic",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def _run(self, query: str) -> List[Dict[str, Any]]:
        items = self.store.search_knowledge(query)
        return [
            {
                "id": it.id,
                "title": it.title,
                "content": it.content,
                "tags": it.tags,
                "source": it.source,
            }
            for it in items
        ]
