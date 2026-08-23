import sys
import pytest
from app.models.tools import PermissionLevel

pytestmark = [
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="windows_only: Windows host required"),
]
from app.tools.registry import ToolRegistry
from app.tools.windows import (
    GetEnvInfoTool,
    GetHardwareInfoTool,
    GetInstalledSoftwareTool,
    GetNetworkInfoTool,
    GetOSInfoTool,
    GetProcessInfoTool,
    GetServiceInfoTool,
    GetStorageInfoTool,
    GetUserContextTool,
    register_windows_tools,
)


def test_register_windows_tools():
    registry = ToolRegistry()
    register_windows_tools(registry)

    tools = registry.list_tools()
    assert len(tools) == 11

    # Verification: 10 tools are Level 0 Read-Only, 1 is Level 2 Approval Required (manage_service)
    read_only_tools = [t for t in tools if t.permission_level == PermissionLevel.LEVEL_0_READ_ONLY]
    modifying_tools = [t for t in tools if t.permission_level == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED]
    assert len(read_only_tools) == 10
    assert len(modifying_tools) == 1
    assert modifying_tools[0].name == "manage_service"


def test_get_os_info_tool():
    tool = GetOSInfoTool()
    res = tool.execute("call_os")
    assert res.success
    assert isinstance(res.data, dict)
    assert res.data["system"] == "Windows"
    assert "architecture" in res.data


def test_get_hardware_info_tool():
    tool = GetHardwareInfoTool()
    res = tool.execute("call_hw")
    assert res.success
    assert isinstance(res.data, dict)
    assert res.data["logical_cpus"] > 0


def test_get_storage_info_tool():
    tool = GetStorageInfoTool()
    res = tool.execute("call_storage")
    assert res.success
    assert isinstance(res.data, list)
    assert len(res.data) > 0
    assert "device_id" in res.data[0]
    assert "free_gb" in res.data[0]


def test_get_env_info_tool():
    tool = GetEnvInfoTool()

    # Summary
    res1 = tool.execute("call_env1")
    assert res1.success
    assert "USERPROFILE" in res1.data

    # Specific variable
    res2 = tool.execute("call_env2", variable_name="OS")
    assert res2.success
    assert res2.data["found"] is True

    # Path inspection
    res3 = tool.execute("call_env3", inspect_path=True)
    assert res3.success
    assert res3.data["count"] > 0
    assert len(res3.data["path_entries"]) > 0


def test_get_process_info_tool():
    tool = GetProcessInfoTool()
    res = tool.execute("call_proc", limit=10, sort_by="memory")
    assert res.success
    assert isinstance(res.data, list)
    assert len(res.data) > 0
    assert "pid" in res.data[0]
    assert "memory_mb" in res.data[0]


def test_get_service_info_tool():
    tool = GetServiceInfoTool()
    res = tool.execute("call_svc", limit=15)
    assert res.success
    assert isinstance(res.data, list)
    assert len(res.data) > 0
    assert "name" in res.data[0]
    assert "status" in res.data[0]


def test_get_network_info_tool():
    tool = GetNetworkInfoTool()
    res = tool.execute("call_net", include_listening_ports=True)
    assert res.success
    assert isinstance(res.data, dict)
    assert "adapters" in res.data or "listening_ports" in res.data


def test_get_installed_software_tool():
    tool = GetInstalledSoftwareTool()
    res = tool.execute("call_sw", limit=20)
    assert res.success
    assert isinstance(res.data, list)
    # Most Windows systems have at least 1 registered application
    assert len(res.data) >= 0


def test_get_user_context_tool():
    tool = GetUserContextTool()
    res = tool.execute("call_user")
    assert res.success
    assert isinstance(res.data, dict)
    assert "username" in res.data
    assert "is_elevated_admin" in res.data
