import sys
import pytest
from app.models.tools import PermissionLevel
from app.tools.registry import ToolRegistry
from app.tools.terminal import (
    CommandPolicyEngine,
    CommandRunner,
    ExecuteTerminalCommandTool,
    register_terminal_tools,
)


@pytest.mark.cross_platform
def test_command_runner_stdout_and_exit_code():
    runner = CommandRunner()
    cmd = 'Write-Output "Hello Terminal"' if sys.platform == "win32" else 'echo "Hello Terminal"'
    out = runner.run(cmd, timeout_seconds=5)
    assert out.exit_code == 0
    assert "Hello Terminal" in out.stdout
    assert not out.timed_out
    assert out.duration_ms > 0


@pytest.mark.cross_platform
def test_command_runner_exit_code_failure():
    runner = CommandRunner()
    out = runner.run("exit 7", timeout_seconds=5)
    assert out.exit_code == 7


@pytest.mark.cross_platform
def test_command_runner_timeout():
    runner = CommandRunner()
    cmd = "Start-Sleep -Seconds 5" if sys.platform == "win32" else "sleep 5"
    out = runner.run(cmd, timeout_seconds=1)
    assert out.timed_out
    assert out.exit_code == -1


@pytest.mark.cross_platform
def test_command_runner_working_directory(tmp_path):
    runner = CommandRunner()
    cmd = "Get-Location" if sys.platform == "win32" else "pwd"
    out = runner.run(cmd, cwd=str(tmp_path), timeout_seconds=5)
    assert out.exit_code == 0
    assert str(tmp_path).lower() in out.stdout.lower()


def test_policy_engine_classification():
    policy = CommandPolicyEngine()

    # Level 0 (Read-Only)
    assert policy.classify_command("dir") == PermissionLevel.LEVEL_0_READ_ONLY
    assert policy.classify_command("Get-ChildItem -Path .") == PermissionLevel.LEVEL_0_READ_ONLY
    assert policy.classify_command("git status") == PermissionLevel.LEVEL_0_READ_ONLY
    assert policy.classify_command("python --version") == PermissionLevel.LEVEL_0_READ_ONLY
    assert policy.classify_command("echo 'test'") == PermissionLevel.LEVEL_0_READ_ONLY

    # Level 1 (Low-Risk / Local Project)
    assert policy.classify_command("pip install pydantic") == PermissionLevel.LEVEL_1_LOW_RISK
    assert policy.classify_command("npm test") == PermissionLevel.LEVEL_1_LOW_RISK
    assert policy.classify_command("pytest tests/") == PermissionLevel.LEVEL_1_LOW_RISK

    # Level 2 (User Approval Required)
    assert policy.classify_command("winget install PostgreSQL") == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
    assert policy.classify_command("Stop-Process -Name notepad") == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
    assert policy.classify_command("npm install -g typescript") == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    # Level 3 (High-Risk / Destructive)
    assert policy.classify_command("rmdir /s /q C:\\") == PermissionLevel.LEVEL_3_HIGH_RISK
    assert policy.classify_command("reg delete HKLM\\Software\\Test") == PermissionLevel.LEVEL_3_HIGH_RISK
    assert policy.classify_command("format D: /FS:NTFS") == PermissionLevel.LEVEL_3_HIGH_RISK


def test_policy_engine_protected_paths():
    policy = CommandPolicyEngine()
    assert policy.is_path_protected("C:\\Windows\\System32\\drivers") is True
    assert policy.is_path_protected("C:\\Program Files\\app") is True
    assert policy.is_path_protected("C:\\Users\\Roshan\\my_project") is False


def test_execute_terminal_command_tool():
    import sys
    tool = ExecuteTerminalCommandTool()
    cmd = 'Write-Output "Terminal Tool Operational"' if sys.platform == "win32" else 'echo "Terminal Tool Operational"'
    res = tool.execute("call_term_1", command=cmd)
    assert res.success
    assert "Terminal Tool Operational" in res.stdout
    assert res.data["exit_code"] == 0


def test_register_terminal_tools():
    registry = ToolRegistry()
    register_terminal_tools(registry)
    tool = registry.get("terminal_exec")
    assert tool is not None
    assert tool.name == "terminal_exec"
