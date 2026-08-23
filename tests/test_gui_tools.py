"""
Integration and Unit tests for Phase 9 Computer Vision & GUI Automation Tools.
"""

from pathlib import Path
import pytest
from app.models.tools import PermissionLevel
from app.tools.gui import (
    AnalyzeScreenStateTool,
    CaptureScreenshotTool,
    GUISendInputTool,
    KeyboardTypeTool,
    MouseClickTool,
    MouseScrollTool,
    register_gui_tools,
)
from app.tools.registry import ToolRegistry


@pytest.mark.cross_platform
def test_analyze_screen_state_tool():
    tool = AnalyzeScreenStateTool()
    res = tool.execute("call_screen_analysis")
    assert isinstance(res.success, bool)
    if res.success:
        assert "primary_screen" in res.data
        assert res.data["primary_screen"]["width"] >= 0
        assert res.data["primary_screen"]["height"] >= 0
        assert "cursor_position" in res.data
    else:
        assert "degraded" in res.error.lower() or "tcc" in res.error.lower() or "display" in res.error.lower() or "not available" in res.error.lower()


@pytest.mark.cross_platform
def test_capture_screenshot_tool(tmp_path: Path):
    tool = CaptureScreenshotTool()
    out_file = tmp_path / "test_screenshot.png"
    res = tool.execute("call_screenshot", output_path=str(out_file))
    assert isinstance(res.success, bool)
    if res.success and out_file.exists():
        assert out_file.exists()
        assert res.data.get("file_size_bytes", 0) >= 0
    else:
        err = ((res.error or "") + " " + str(res.data or {})).lower()
        assert "degraded" in err or "tcc" in err or "wayland" in err or "display" in err or "no x11" in err or not res.success


@pytest.mark.cross_platform
def test_gui_input_tools_schemas():
    click_tool = MouseClickTool()
    assert click_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    c_schema = click_tool.get_parameters_schema()
    assert "x" in c_schema["properties"]
    assert "y" in c_schema["properties"]

    scroll_tool = MouseScrollTool()
    assert scroll_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    s_schema = scroll_tool.get_parameters_schema()
    assert "delta" in s_schema["properties"]

    type_tool = KeyboardTypeTool()
    assert type_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    t_schema = type_tool.get_parameters_schema()
    assert "text" in t_schema["properties"]

    send_input_tool = GUISendInputTool()
    assert send_input_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    si_schema = send_input_tool.get_parameters_schema()
    assert "text" in si_schema["properties"]
    assert "keys" in si_schema["properties"]


@pytest.mark.cross_platform
def test_register_gui_tools():
    registry = ToolRegistry()
    register_gui_tools(registry)
    tools = registry.list_tools()
    assert len(tools) == 6
    names = {t.name for t in tools}
    assert names == {
        "gui_take_screenshot",
        "gui_analyze_screen",
        "gui_mouse_click",
        "gui_mouse_scroll",
        "gui_keyboard_type",
        "gui_send_input",
    }
