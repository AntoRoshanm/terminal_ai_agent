"""
Audit Log Storage Operations
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from app.security.masker import SecretMasker
from app.storage.database import Database


class AuditStore:
    """Store for queryable audit trail records."""

    def __init__(self, db: Database):
        self.db = db

    def record_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> int:
        """Record an audit trail event with automatic secret masking."""
        safe_payload = SecretMasker.mask_dict(payload)
        conn = self.db.get_connection()
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_log (session_id, task_id, event_type, payload, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    task_id,
                    event_type,
                    json.dumps(safe_payload),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return cursor.lastrowid

    def get_events_for_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve audit records for a given session."""
        conn = self.db.get_connection()
        cursor = conn.execute(
            """
            SELECT id, session_id, task_id, event_type, payload, timestamp
            FROM audit_log
            WHERE session_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (session_id, limit),
        )
        records: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            records.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "task_id": row["task_id"],
                    "event_type": row["event_type"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"],
                }
            )
        return records
