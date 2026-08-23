"""
Multi-Tier Persistent Memory Store (SQLite)
"""

from datetime import datetime
import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional
from app.memory.models import KnowledgeItem, OperationalRecord, UserPreference
from app.storage.database import Database


class MemoryStore:
    """Store for user preferences, operational history, and structured knowledge."""

    def __init__(self, db: Database):
        self.db = db
        self._init_tables()

    def _init_tables(self) -> None:
        """Create memory tables if not already existing."""
        conn = self.db.get_connection()
        with conn:
            # 1. User preferences
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # 2. Operational memory (fixes and outcomes)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operational_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    tool_used TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_type TEXT,
                    fix_applied TEXT,
                    verified INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # 3. Knowledge items
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    # --- User Preferences ---
    def set_preference(self, key: str, value: Any, category: str = "general") -> UserPreference:
        now = datetime.utcnow().isoformat()
        val_str = json.dumps(value)
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO user_preferences (key, value, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    updated_at = excluded.updated_at;
                """,
                (key, val_str, category, now, now),
            )
        return UserPreference(key=key, value=value, category=category)

    def get_preference(self, key: str, default: Any = None) -> Any:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM user_preferences WHERE key = ?;", (key,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]
        return default

    def list_preferences(self, category: Optional[str] = None) -> List[UserPreference]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT key, value, category, created_at, updated_at FROM user_preferences WHERE category = ?;", (category,))
        else:
            cursor.execute("SELECT key, value, category, created_at, updated_at FROM user_preferences;")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            try:
                val = json.loads(r["value"])
            except Exception:
                val = r["value"]
            result.append(UserPreference(
                key=r["key"],
                value=val,
                category=r["category"],
                created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
                updated_at=datetime.fromisoformat(r["updated_at"]) if isinstance(r["updated_at"], str) else r["updated_at"],
            ))
        return result

    def delete_preference(self, key: str) -> bool:
        conn = self.db.get_connection()
        with conn:
            cursor = conn.execute("DELETE FROM user_preferences WHERE key = ?;", (key,))
            return cursor.rowcount > 0

    # --- Operational Memory ---
    def record_operation(
        self,
        goal: str,
        tool_used: str,
        status: str,
        error_type: Optional[str] = None,
        fix_applied: Optional[str] = None,
        verified: bool = False,
    ) -> OperationalRecord:
        conn = self.db.get_connection()
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO operational_memory (goal, tool_used, status, error_type, fix_applied, verified)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (goal, tool_used, status, error_type, fix_applied, 1 if verified else 0),
            )
            record_id = cursor.lastrowid
        return OperationalRecord(
            id=record_id,
            goal=goal,
            tool_used=tool_used,
            status=status,
            error_type=error_type,
            fix_applied=fix_applied,
            verified=verified,
        )

    def find_successful_fixes(self, query: str) -> List[OperationalRecord]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, goal, tool_used, status, error_type, fix_applied, verified, timestamp
            FROM operational_memory
            WHERE (error_type LIKE ? OR goal LIKE ?) AND (status = 'SUCCESS' OR status = 'RECOVERED')
            ORDER BY id DESC LIMIT 5;
            """,
            (f"%{query}%", f"%{query}%"),
        )
        rows = cursor.fetchall()
        return [
            OperationalRecord(
                id=r["id"],
                goal=r["goal"],
                tool_used=r["tool_used"],
                status=r["status"],
                error_type=r["error_type"],
                fix_applied=r["fix_applied"],
                verified=bool(r["verified"]),
            )
            for r in rows
        ]

    # --- Knowledge Items ---
    def save_knowledge(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> KnowledgeItem:
        item_id = str(uuid.uuid4())[:8]
        tags_str = json.dumps(tags or [])
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO knowledge_items (id, title, content, tags, source)
                VALUES (?, ?, ?, ?, ?);
                """,
                (item_id, title, content, tags_str, source),
            )
        return KnowledgeItem(id=item_id, title=title, content=content, tags=tags or [], source=source)

    def search_knowledge(self, query: str) -> List[KnowledgeItem]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, content, tags, source, created_at
            FROM knowledge_items
            WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
            ORDER BY created_at DESC LIMIT 10;
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        )
        rows = cursor.fetchall()
        items = []
        for r in rows:
            try:
                t_list = json.loads(r["tags"]) if r["tags"] else []
            except Exception:
                t_list = []
            items.append(KnowledgeItem(
                id=r["id"],
                title=r["title"],
                content=r["content"],
                tags=t_list,
                source=r["source"],
            ))
        return items

    def delete_knowledge(self, item_id: str) -> bool:
        conn = self.db.get_connection()
        with conn:
            cursor = conn.execute("DELETE FROM knowledge_items WHERE id = ?;", (item_id,))
            return cursor.rowcount > 0

    def clear_all(self) -> None:
        """Clear all memory tables (privacy / user requested wipe)."""
        conn = self.db.get_connection()
        with conn:
            conn.execute("DELETE FROM user_preferences;")
            conn.execute("DELETE FROM operational_memory;")
            conn.execute("DELETE FROM knowledge_items;")
