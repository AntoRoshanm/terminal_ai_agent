"""
Session and Message Storage Operations
"""

from datetime import datetime, timezone
import json
from typing import List, Optional
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.state import Session, TaskExecutionRecord, TaskState, TaskStep
from app.storage.database import Database


class SessionStore:
    """Store for conversational sessions, message history, and task records."""

    def __init__(self, db: Database):
        self.db = db

    # ==================== Sessions ====================

    def create_session(self, title: str = "New Session", session_id: Optional[str] = None) -> Session:
        """Create and store a new session."""
        session = Session(title=title)
        if session_id:
            session.id = session_id

        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO sessions (id, title, created_at, updated_at, message_count, active_task_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.title,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    session.message_count,
                    session.active_task_id,
                    json.dumps(session.metadata),
                ),
            )
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID."""
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return Session(
            id=row["id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            message_count=row["message_count"],
            active_task_id=row["active_task_id"],
            metadata=json.loads(row["metadata"]),
        )

    def list_sessions(self, limit: int = 50) -> List[Session]:
        """List recently updated sessions."""
        conn = self.db.get_connection()
        cursor = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        sessions: List[Session] = []
        for row in cursor.fetchall():
            sessions.append(
                Session(
                    id=row["id"],
                    title=row["title"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    message_count=row["message_count"],
                    active_task_id=row["active_task_id"],
                    metadata=json.loads(row["metadata"]),
                )
            )
        return sessions

    def update_session(self, session: Session) -> None:
        """Update session metadata and updated_at."""
        session.updated_at = datetime.now(timezone.utc)
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                UPDATE sessions
                SET title = ?, updated_at = ?, message_count = ?, active_task_id = ?, metadata = ?
                WHERE id = ?
                """,
                (
                    session.title,
                    session.updated_at.isoformat(),
                    session.message_count,
                    session.active_task_id,
                    json.dumps(session.metadata),
                    session.id,
                ),
            )

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all associated messages/tasks."""
        conn = self.db.get_connection()
        with conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    # ==================== Messages ====================

    def add_message(self, session_id: str, message: ChatMessage) -> None:
        """Add a message to a session history and increment session message count."""
        conn = self.db.get_connection()
        tool_calls_json = (
            json.dumps([tc.model_dump() for tc in message.tool_calls])
            if message.tool_calls
            else None
        )

        with conn:
            conn.execute(
                """
                INSERT INTO messages (id, session_id, role, content, tool_calls, tool_call_id, name, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    session_id,
                    message.role.value,
                    message.content,
                    tool_calls_json,
                    message.tool_call_id,
                    message.name,
                    message.timestamp.isoformat(),
                    json.dumps(message.metadata),
                ),
            )
            conn.execute(
                """
                UPDATE sessions
                SET message_count = message_count + 1, updated_at = ?
                WHERE id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), session_id),
            )

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Get ordered message history for a session."""
        conn = self.db.get_connection()
        query = "SELECT * FROM messages WHERE session_id = ? ORDER BY rowid ASC"
        params: List[object] = [session_id]
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, tuple(params))
        messages: List[ChatMessage] = []
        for row in cursor.fetchall():
            tool_calls = None
            if row["tool_calls"]:
                tool_calls_data = json.loads(row["tool_calls"])
                tool_calls = [ToolCall(**tc) for tc in tool_calls_data]

            messages.append(
                ChatMessage(
                    id=row["id"],
                    role=Role(row["role"]),
                    content=row["content"],
                    tool_calls=tool_calls,
                    tool_call_id=row["tool_call_id"],
                    name=row["name"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    metadata=json.loads(row["metadata"]),
                )
            )
        return messages

    # ==================== Task Records ====================

    def save_task(self, task: TaskExecutionRecord) -> None:
        """Save or update a task execution record with its steps."""
        conn = self.db.get_connection()
        task.updated_at = datetime.now(timezone.utc)

        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (id, session_id, goal, state, current_step_index, created_at, updated_at, completed_at, error_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.session_id,
                    task.goal,
                    task.state.value,
                    task.current_step_index,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.error_summary,
                ),
            )

            # Re-sync task steps
            conn.execute("DELETE FROM task_steps WHERE task_id = ?", (task.id,))
            for step in task.steps:
                conn.execute(
                    """
                    INSERT INTO task_steps (id, task_id, step_number, description, tool_name, parameters, state, result, verification_rule, verified, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        step.id,
                        task.id,
                        step.step_number,
                        step.description,
                        step.tool_name,
                        json.dumps(step.parameters),
                        step.state.value,
                        step.result,
                        step.verification_rule,
                        1 if step.verified else 0,
                        step.error,
                    ),
                )

    def get_task(self, task_id: str) -> Optional[TaskExecutionRecord]:
        """Retrieve a task execution record by ID."""
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return None

        # Fetch steps
        step_cursor = conn.execute(
            "SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_number ASC",
            (task_id,),
        )
        steps: List[TaskStep] = []
        for s_row in step_cursor.fetchall():
            steps.append(
                TaskStep(
                    id=s_row["id"],
                    step_number=s_row["step_number"],
                    description=s_row["description"],
                    tool_name=s_row["tool_name"],
                    parameters=json.loads(s_row["parameters"]),
                    state=TaskState(s_row["state"]),
                    result=s_row["result"],
                    verification_rule=s_row["verification_rule"],
                    verified=bool(s_row["verified"]),
                    error=s_row["error"],
                )
            )

        return TaskExecutionRecord(
            id=task_row["id"],
            session_id=task_row["session_id"],
            goal=task_row["goal"],
            state=TaskState(task_row["state"]),
            steps=steps,
            current_step_index=task_row["current_step_index"],
            created_at=datetime.fromisoformat(task_row["created_at"]),
            updated_at=datetime.fromisoformat(task_row["updated_at"]),
            completed_at=(
                datetime.fromisoformat(task_row["completed_at"])
                if task_row["completed_at"]
                else None
            ),
            error_summary=task_row["error_summary"],
        )
