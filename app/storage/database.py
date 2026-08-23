"""
SQLite Database Connection and Migration Manager
"""

from pathlib import Path
import sqlite3
import threading
from typing import Optional


class Database:
    """Thread-safe SQLite database connection manager with WAL mode."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for high concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        """Initialize database tables if they do not exist."""
        conn = self.get_connection()
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    active_task_id TEXT,
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    tool_calls TEXT,
                    tool_call_id TEXT,
                    name TEXT,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    state TEXT NOT NULL,
                    current_step_index INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_summary TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_steps (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    tool_name TEXT,
                    parameters TEXT DEFAULT '{}',
                    state TEXT NOT NULL,
                    result TEXT,
                    verification_rule TEXT,
                    verified INTEGER DEFAULT 0,
                    error TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    task_id TEXT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_session_id ON audit_log(session_id);
                """
            )

    def close(self) -> None:
        """Close thread-local connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None
