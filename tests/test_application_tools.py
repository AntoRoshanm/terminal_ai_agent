"""
Integration and Unit tests for Phase 7 Application Control Tools.
"""

from app.models.tools import PermissionLevel
from app.tools.applications import (
    CloseApplicationTool,
    FocusWindowTool,
    GetApplicationStatusTool,
    LaunchApplicationTool,
    ListWindowsTool,
    register_application_tools,
)
from app.tools.registry import ToolRegistry


def test_list_windows_tool():
    tool = ListWindowsTool()
    res = tool.execute("call_list_wnd")
    assert res.success
    assert isinstance(res.data, list)
    if res.data:
        first = res.data[0]
        assert "title" in first
        assert "pid" in first or "hwnd" in first or "window_id" in first


def test_application_lifecycle_schemas():
    launch_tool = LaunchApplicationTool()
    assert launch_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    l_schema = launch_tool.get_parameters_schema()
    assert "target" in l_schema["properties"]

    close_tool = CloseApplicationTool()
    assert close_tool.permission_level == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
    c_schema = close_tool.get_parameters_schema()
    assert "process_name" in c_schema["properties"]
    assert "pid" in c_schema["properties"]


def test_focus_window_schema():
    focus_tool = FocusWindowTool()
    assert focus_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    f_schema = focus_tool.get_parameters_schema()
    assert "hwnd" in f_schema["properties"]
    assert "window_title" in f_schema["properties"]


def test_get_application_status_tool():
    tool = GetApplicationStatusTool()

    # Query running process (python)
    res = tool.execute("call_status_py", process_name="python")
    assert res.success
    assert res.data["running"] is True
    assert res.data["process_count"] >= 1
    assert "total_memory_mb" in res.data

    # Query non-running process
    res_none = tool.execute("call_status_none", process_name="non_existent_dummy_app_xyz")
    assert res_none.success
    assert res_none.data["running"] is False


def test_register_application_tools():
    registry = ToolRegistry()
    register_application_tools(registry)
    tools = registry.list_tools()
    assert len(tools) == 5
    names = {t.name for t in tools}
    assert names == {
        "app_list_windows",
        "app_launch",
        "app_close",
        "app_focus_window",
        "app_get_status",
    }
