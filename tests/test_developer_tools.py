"""
Integration and Unit tests for Phase 11 Developer & Engineering Tools.
"""

from app.models.tools import PermissionLevel
from app.tools.developer import (
    GitBranchTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitStatusTool,
    ManageDevServiceTool,
    RunProjectTestsTool,
    register_developer_tools,
)
from app.tools.registry import ToolRegistry


def test_git_status_tool():
    tool = GitStatusTool()
    res = tool.execute("call_git_status")
    assert res.success
    # In a git repository
    assert res.data["is_git_repo"] is True
    assert "branch" in res.data


def test_git_log_tool():
    tool = GitLogTool()
    res = tool.execute("call_git_log", limit=3)
    assert res.success
    assert isinstance(res.data, list)
    if res.data and "commit_hash" in res.data[0]:
        assert len(res.data[0]["commit_hash"]) > 0


def test_git_diff_tool():
    tool = GitDiffTool()
    res = tool.execute("call_git_diff")
    assert res.success
    assert "has_diff" in res.data
    assert "diff" in res.data


def test_git_commit_and_branch_schemas():
    commit_tool = GitCommitTool()
    assert commit_tool.permission_level == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
    c_schema = commit_tool.get_parameters_schema()
    assert "message" in c_schema["properties"]

    branch_tool = GitBranchTool()
    assert branch_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    b_schema = branch_tool.get_parameters_schema()
    assert "action" in b_schema["properties"]


def test_run_project_tests_tool_detection():
    tool = RunProjectTestsTool()
    assert tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    schema = tool.get_parameters_schema()
    assert "custom_command" in schema["properties"]


def test_manage_dev_service_tool():
    tool = ManageDevServiceTool()
    res_ports = tool.execute("call_dev_ports", service_type="ports")
    assert res_ports.success
    assert "active_dev_ports" in res_ports.data

    res_docker = tool.execute("call_dev_docker", service_type="docker", docker_action="ps")
    assert res_docker.success
    assert "docker_installed" in res_docker.data


def test_register_developer_tools():
    registry = ToolRegistry()
    register_developer_tools(registry)
    tools = registry.list_tools()
    assert len(tools) == 7
    names = {t.name for t in tools}
    assert names == {
        "dev_git_status",
        "dev_git_log",
        "dev_git_diff",
        "dev_git_commit",
        "dev_git_branch",
        "dev_run_tests",
        "dev_manage_service",
    }
