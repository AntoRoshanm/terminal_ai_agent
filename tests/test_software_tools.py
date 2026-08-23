"""
Integration and Unit tests for Phase 5 Software and Environment Management Tools.
"""

from app.models.tools import PermissionLevel
from app.tools.registry import ToolRegistry
from app.tools.software import (
    ConfigureEnvironmentTool,
    DetectPackageManagersTool,
    FindExecutableTool,
    InstallSoftwareTool,
    VerifySoftwareTool,
    register_software_tools,
)


def test_detect_package_managers():
    tool = DetectPackageManagersTool()
    res = tool.execute("call_pkg_mgr")
    assert res.success
    assert "available_managers" in res.data
    assert "pip" in res.data["available_managers"]
    assert res.data["details"]["pip"]["installed"] is True


def test_find_executable_tool():
    tool = FindExecutableTool()

    # 1. Existing executable (python)
    res_py = tool.execute("call_find_py", executable_name="python")
    assert res_py.success
    assert res_py.data["found"] is True
    assert "python" in res_py.data["path"].lower()

    # 2. Non-existent executable
    res_none = tool.execute("call_find_none", executable_name="non_existent_fake_app_xyz")
    assert res_none.success
    assert res_none.data["found"] is False


def test_verify_software_tool():
    tool = VerifySoftwareTool()

    # Verify python on the live host
    res = tool.execute("call_verify_py", name="python")
    assert res.success
    assert res.data["verified"] is True
    assert "executable" in res.data["evidence"]
    assert res.data["evidence"]["executable"]["found"] is True


import sys

def test_install_software_command_builder():
    tool = InstallSoftwareTool()
    assert tool.permission_level == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    # Test winget command construction
    cmd_winget = tool._build_command("winget", "Git.Git", version="2.43.0", global_install=False)
    assert cmd_winget == [
        "winget.exe", "install", "--id", "Git.Git", "--exact", "--silent",
        "--accept-package-agreements", "--accept-source-agreements",
        "--disable-interactivity", "--version", "2.43.0"
    ]

    # Test pip command construction
    pip_bin = "pip.exe" if sys.platform == "win32" else "pip"
    cmd_pip = tool._build_command("pip", "pydantic", version="2.5.0", global_install=False)
    assert cmd_pip == [pip_bin, "install", "pydantic==2.5.0"]

    # Test npm global command construction
    npm_bin = "npm.cmd" if sys.platform == "win32" else "npm"
    cmd_npm = tool._build_command("npm", "typescript", version=None, global_install=True)
    assert cmd_npm == [npm_bin, "install", "-g", "typescript"]


def test_configure_environment_tool_schema():
    tool = ConfigureEnvironmentTool()
    assert tool.permission_level == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
    schema = tool.get_parameters_schema()
    assert "action" in schema["properties"]
    assert "value" in schema["properties"]


def test_register_software_tools():
    registry = ToolRegistry()
    register_software_tools(registry)
    tools = registry.list_tools()
    assert len(tools) == 5
    names = {t.name for t in tools}
    assert names == {
        "software_detect_managers",
        "software_find_executable",
        "software_install",
        "software_configure_env",
        "software_verify",
    }
