"""
Integration and Unit tests for Phase 4 Filesystem Intelligence Tools.
"""

from pathlib import Path
from unittest.mock import patch
import pytest
from app.models.state import PlatformInfo
from app.models.tools import PermissionLevel
from app.tools.filesystem import (
    EditFileTool,
    InspectDirectoryTool,
    ManageFilesTool,
    PathSafety,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
    register_filesystem_tools,
)
from app.tools.registry import ToolRegistry


@pytest.mark.cross_platform
def test_path_safety(tmp_path: Path):
    safety = PathSafety()

    # User temp path is safe
    safe_file = safety.check_safe_write(str(tmp_path / "test.txt"))
    assert safe_file == (tmp_path / "test.txt").resolve()

    # Protected path raises PermissionError
    import sys
    protected_path = "C:\\Windows\\System32\\calc.exe" if sys.platform == "win32" else ("/System/Library" if sys.platform == "darwin" else "/etc/shadow")
    with pytest.raises(PermissionError):
        safety.check_safe_write(protected_path)


@pytest.mark.cross_platform
def test_write_and_read_file(tmp_path: Path):
    write_tool = WriteFileTool()
    read_tool = ReadFileTool()

    target = tmp_path / "subfolder" / "sample.txt"
    content = "Line 1: Alpha\nLine 2: Beta\nLine 3: Gamma\nLine 4: Delta\n"

    # 1. Write file
    w_res = write_tool.execute("call_w1", file_path=str(target), content=content)
    assert w_res.success
    assert w_res.data["lines_written"] == 4

    # 2. Read full file
    r_res = read_tool.execute("call_r1", file_path=str(target))
    assert r_res.success
    assert r_res.data["total_lines"] == 4
    assert "Line 1: Alpha" in r_res.data["content"]

    # 3. Read slice (lines 2 to 3)
    slice_res = read_tool.execute("call_r2", file_path=str(target), start_line=2, end_line=3)
    assert slice_res.success
    assert slice_res.data["content"] == "Line 2: Beta\nLine 3: Gamma\n"
    assert slice_res.data["start_line"] == 2
    assert slice_res.data["end_line"] == 3


@pytest.mark.cross_platform
def test_edit_file(tmp_path: Path):
    write_tool = WriteFileTool()
    edit_tool = EditFileTool()

    target = tmp_path / "edit_test.txt"
    write_tool.execute("call_w", file_path=str(target), content="Hello World!\nWelcome to AI Agent.")

    # Edit single occurrence
    e_res = edit_tool.execute(
        "call_e",
        file_path=str(target),
        target_content="World",
        replacement_content="Windows",
    )
    assert e_res.success
    assert e_res.data["replacements_made"] == 1

    # Verify content
    read_tool = ReadFileTool()
    r_res = read_tool.execute("call_r", file_path=str(target))
    assert "Hello Windows!" in r_res.data["content"]


@pytest.mark.cross_platform
def test_file_edit_crlf_lf_normalization_and_path_audit(tmp_path: Path):
    """Directive A.5.A/A.5.B: Test CRLF/LF line-ending normalization and cross-platform path protection."""
    edit_tool = EditFileTool()
    write_tool = WriteFileTool()

    # 1. CRLF file edited with LF target content
    crlf_target = tmp_path / "crlf_test.txt"
    with open(crlf_target, "wb") as f:
        f.write(b"Line 1\r\nLine 2\r\nLine 3\r\n")

    # Search with LF string should match and replace successfully
    res = edit_tool.execute(
        "call_crlf",
        file_path=str(crlf_target),
        target_content="Line 2\n",
        replacement_content="Line 2 Modified\n",
    )
    assert res.success
    assert res.data["replacements_made"] == 1

    # 2. Linux protected path audit
    linux_platform = PlatformInfo(
        os_family="linux",
        os_name="Ubuntu",
        os_version="24.04",
        architecture="x86_64",
        shell_default="bash",
    )
    with patch("app.security.guard.get_platform_info", return_value=linux_platform):
        linux_safety = PathSafety()
        with pytest.raises(PermissionError):
            linux_safety.check_safe_write("/etc/shadow")
        with pytest.raises(PermissionError):
            linux_safety.check_safe_write("/boot/vmlinuz")


@pytest.mark.cross_platform
def test_search_files(tmp_path: Path):
    write_tool = WriteFileTool()
    search_tool = SearchFilesTool()

    (tmp_path / "a.py").write_text("print('a')")
    (tmp_path / "b.txt").write_text("text")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.py").write_text("print('c')")

    res = search_tool.execute("call_search", directory_path=str(tmp_path), pattern="*.py")
    assert res.success
    assert len(res.data) == 2
    names = {item["name"] for item in res.data}
    assert names == {"a.py", "c.py"}


@pytest.mark.cross_platform
def test_inspect_directory_and_project_detection(tmp_path: Path):
    inspect_tool = InspectDirectoryTool()

    # Create dummy python project files
    (tmp_path / "requirements.txt").write_text("pydantic\nrich\n")
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "src").mkdir()

    res = inspect_tool.execute("call_inspect", directory_path=str(tmp_path))
    assert res.success
    assert res.data["file_count"] == 2
    assert res.data["directory_count"] == 1

    # Project detection
    detected = res.data["detected_projects"]
    assert any(p["type"] == "Python" for p in detected)


@pytest.mark.cross_platform
def test_manage_files(tmp_path: Path):
    write_tool = WriteFileTool()
    manage_tool = ManageFilesTool()

    src = tmp_path / "original.txt"
    write_tool.execute("call_w", file_path=str(src), content="original content")

    # 1. Copy
    copy_dst = tmp_path / "copied.txt"
    c_res = manage_tool.execute("call_copy", operation="copy", source_path=str(src), destination_path=str(copy_dst))
    assert c_res.success
    assert copy_dst.exists()

    # 2. Move / Rename
    moved_dst = tmp_path / "moved.txt"
    m_res = manage_tool.execute("call_move", operation="move", source_path=str(copy_dst), destination_path=str(moved_dst))
    assert m_res.success
    assert not copy_dst.exists()
    assert moved_dst.exists()

    # 3. Delete
    d_res = manage_tool.execute("call_del", operation="delete", source_path=str(moved_dst))
    assert d_res.success
    assert not moved_dst.exists()


@pytest.mark.cross_platform
def test_register_filesystem_tools():
    registry = ToolRegistry()
    register_filesystem_tools(registry)
    tools = registry.list_tools()
    assert len(tools) == 6
    names = {t.name for t in tools}
    assert names == {"file_read", "file_write", "file_edit", "file_search", "dir_inspect", "file_manage"}
