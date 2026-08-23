"""
Integration and Unit tests for Phase 10 System Diagnostics & Maintenance Tools.
"""

from app.models.tools import PermissionLevel
from app.tools.diagnostics import (
    GetEventLogsTool,
    GetSystemHealthTool,
    GetUpdateStatusTool,
    SafeCleanupTool,
    register_diagnostics_tools,
)
from app.tools.registry import ToolRegistry


def test_get_event_logs_tool():
    tool = GetEventLogsTool()
    res = tool.execute("call_event_log", log_name="Application", level="Error", hours=48, limit=5)
    assert res.success
    assert isinstance(res.data, list)


def test_get_system_health_tool():
    tool = GetSystemHealthTool()
    res = tool.execute("call_health")
    assert res.success
    assert "ram" in res.data
    assert "total_mb" in res.data["ram"]
    assert "used_percent" in res.data["ram"]
    assert "top_memory_consumers" in res.data


def test_safe_cleanup_dry_run():
    tool = SafeCleanupTool()
    assert tool.permission_level == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
    res = tool.execute("call_cleanup_dry", dry_run=True, older_than_days=1)
    assert res.success
    assert res.data["dry_run"] is True
    assert "total_files_scanned" in res.data
    assert "total_temp_size_mb" in res.data
    assert res.data["deleted_files_count"] == 0  # No files deleted in dry-run


def test_get_update_status_tool():
    tool = GetUpdateStatusTool()
    res = tool.execute("call_updates", limit=5)
    assert res.success
    assert isinstance(res.data, list)


def test_register_diagnostics_tools():
    registry = ToolRegistry()
    register_diagnostics_tools(registry)
    tools = registry.list_tools()
    assert len(tools) == 4
    names = {t.name for t in tools}
    assert names == {
        "diagnostics_get_event_logs",
        "diagnostics_get_system_health",
        "diagnostics_safe_cleanup",
        "diagnostics_get_update_status",
    }
