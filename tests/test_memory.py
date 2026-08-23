"""
Tests for Multi-Tier Memory Store and Tools
"""

import tempfile
from pathlib import Path
import pytest
from app.memory.models import UserPreference
from app.memory.store import MemoryStore
from app.memory.tools import GetPreferencesTool, SaveKnowledgeTool, SearchKnowledgeTool, SetPreferenceTool
from app.storage.database import Database
from app.tools.registry import ToolRegistry


@pytest.fixture
def temp_memory_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    db = Database(db_path)
    store = MemoryStore(db)
    yield store
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass


def test_user_preferences_crud(temp_memory_store: MemoryStore):
    # Set
    pref = temp_memory_store.set_preference("editor", "vscode", category="developer")
    assert pref.key == "editor"
    assert pref.value == "vscode"

    # Get
    val = temp_memory_store.get_preference("editor")
    assert val == "vscode"
    assert temp_memory_store.get_preference("nonexistent", default="default_val") == "default_val"

    # List
    all_prefs = temp_memory_store.list_preferences()
    assert len(all_prefs) == 1
    assert all_prefs[0].key == "editor"

    # Update
    temp_memory_store.set_preference("editor", "cursor", category="developer")
    assert temp_memory_store.get_preference("editor") == "cursor"

    # Delete
    assert temp_memory_store.delete_preference("editor") is True
    assert temp_memory_store.get_preference("editor") is None


def test_operational_memory_records_and_fixes(temp_memory_store: MemoryStore):
    # Record failed operation then successful fix
    rec1 = temp_memory_store.record_operation(
        goal="Connect PostgreSQL",
        tool_used="terminal_exec",
        status="FAILED",
        error_type="PortConflict",
        fix_applied=None,
        verified=False,
    )
    assert rec1.id is not None

    rec2 = temp_memory_store.record_operation(
        goal="Connect PostgreSQL",
        tool_used="service_info",
        status="RECOVERED",
        error_type="PortConflict",
        fix_applied="Restarted postgresql-x64-16 service",
        verified=True,
    )
    assert rec2.verified is True

    # Search fixes
    fixes = temp_memory_store.find_successful_fixes("PostgreSQL")
    assert len(fixes) == 1
    assert fixes[0].fix_applied == "Restarted postgresql-x64-16 service"


def test_knowledge_items_search_and_delete(temp_memory_store: MemoryStore):
    # Save knowledge
    k1 = temp_memory_store.save_knowledge(
        title="Ollama Setup Notes",
        content="Ollama runs on port 11434. Qwen 3.5 and Llama 3.2 models are supported.",
        tags=["ai", "ollama", "local"],
    )
    assert k1.id is not None

    # Search
    results = temp_memory_store.search_knowledge("11434")
    assert len(results) == 1
    assert results[0].title == "Ollama Setup Notes"

    # Delete
    assert temp_memory_store.delete_knowledge(k1.id) is True
    assert len(temp_memory_store.search_knowledge("11434")) == 0


def test_memory_tools_execution(temp_memory_store: MemoryStore):
    set_tool = SetPreferenceTool(temp_memory_store)
    get_tool = GetPreferencesTool(temp_memory_store)
    save_k_tool = SaveKnowledgeTool(temp_memory_store)
    search_k_tool = SearchKnowledgeTool(temp_memory_store)

    # 1. Set Preference
    res_set = set_tool.execute(tool_call_id="call_set", key="theme", value="dark", category="ui")
    assert res_set.success is True

    # 2. Get Preference
    res_get = get_tool.execute(tool_call_id="call_get", key="theme")
    assert res_get.success is True
    assert res_get.data["value"] == "dark"

    # 3. Save Knowledge
    res_save_k = save_k_tool.execute(tool_call_id="call_save_k", title="Git Workflow", content="Use dev_git_commit for commits", tags=["git"])
    assert res_save_k.success is True

    # 4. Search Knowledge
    res_search_k = search_k_tool.execute(tool_call_id="call_search_k", query="commits")
    assert res_search_k.success is True
    assert len(res_search_k.data) == 1
