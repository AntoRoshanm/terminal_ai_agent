"""
Unit tests for persistence and storage layer (SQLite WAL).
"""

from pathlib import Path
import pytest
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.state import TaskExecutionRecord, TaskState, TaskStep
from app.storage.audit_store import AuditStore
from app.storage.database import Database
from app.storage.session_store import SessionStore


@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_agent.db"
    return Database(db_file)


def test_session_lifecycle(temp_db: Database):
    store = SessionStore(temp_db)

    # Create session
    session = store.create_session(title="Test Session")
    assert session.id.startswith("session_")
    assert session.title == "Test Session"

    # Get session
    retrieved = store.get_session(session.id)
    assert retrieved is not None
    assert retrieved.id == session.id

    # List sessions
    sessions = store.list_sessions()
    assert len(sessions) == 1

    # Update session
    session.title = "Updated Title"
    store.update_session(session)
    updated = store.get_session(session.id)
    assert updated.title == "Updated Title"

    # Delete session
    store.delete_session(session.id)
    assert store.get_session(session.id) is None


def test_messages_persistence(temp_db: Database):
    store = SessionStore(temp_db)
    session = store.create_session()

    # Add user message
    user_msg = ChatMessage(role=Role.USER, content="Hello Windows AI Agent")
    store.add_message(session.id, user_msg)

    # Add assistant message with tool call
    tc = ToolCall(name="get_system_info", arguments={"scope": "cpu"})
    assistant_msg = ChatMessage(
        role=Role.ASSISTANT,
        content="Checking CPU",
        tool_calls=[tc],
    )
    store.add_message(session.id, assistant_msg)

    # Retrieve messages
    messages = store.get_messages(session.id)
    assert len(messages) == 2
    assert messages[0].content == "Hello Windows AI Agent"
    assert messages[1].tool_calls is not None
    assert messages[1].tool_calls[0].name == "get_system_info"


def test_task_record_persistence(temp_db: Database):
    store = SessionStore(temp_db)
    session = store.create_session()

    task = TaskExecutionRecord(
        session_id=session.id,
        goal="Install Python 3.11",
        state=TaskState.PLANNING,
        steps=[
            TaskStep(
                step_number=1,
                description="Check existing python",
                tool_name="terminal_exec",
                parameters={"command": "python --version"},
            )
        ],
    )
    store.save_task(task)

    retrieved_task = store.get_task(task.id)
    assert retrieved_task is not None
    assert retrieved_task.goal == "Install Python 3.11"
    assert len(retrieved_task.steps) == 1
    assert retrieved_task.steps[0].tool_name == "terminal_exec"


def test_audit_store(temp_db: Database):
    audit_store = AuditStore(temp_db)
    event_id = audit_store.record_event(
        session_id="session_123",
        event_type="USER_COMMAND",
        payload={"input": "dir C:\\"},
    )
    assert event_id > 0

    events = audit_store.get_events_for_session("session_123")
    assert len(events) == 1
    assert events[0]["event_type"] == "USER_COMMAND"
    assert events[0]["payload"]["input"] == "dir C:\\"
