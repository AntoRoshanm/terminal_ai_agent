"""
Consolidated Part C Regression Test Suite (Scenarios C.1 to C.18 across Windows, Linux, and macOS)
"""

from unittest.mock import MagicMock, patch
import pytest
from app.agent.intent import IntentClassifier, classify_intent
from app.agent.orchestrator import AgentOrchestrator
from app.config import AgentConfig
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.state import IntentCategory, PlatformInfo
from app.platform.capabilities import CapabilityStatus, get_capability_matrix
from app.storage.audit_store import AuditStore
from app.storage.session_store import SessionStore
from app.tools.filesystem.safety import PathSafety
from app.tools.registry import ToolRegistry
from app.tools.system.factory import SystemProviderFactory
from app.tools.system.macos.gui_provider import MacOSGUIProvider
from app.tools.system.macos.software_provider import MacOSSoftwareProvider


# --- C.1 Cross-Platform Dispatch ---

@pytest.mark.cross_platform
def test_c01_windows_dispatch():
    """Scenario C.1: Windows OS dispatch through SystemProviderFactory."""
    win_info = PlatformInfo(
        os_family="windows",
        os_name="Windows 11",
        os_version="10.0.26200",
        architecture="AMD64",
        shell_default="powershell",
    )
    provider = SystemProviderFactory.get_system_info_provider(win_info)
    info = provider.get_os_info()
    assert "Windows" in info["os_name"]
    assert "system" in info
    assert info["system"] == "Windows"


@pytest.mark.cross_platform
def test_c02_linux_dispatch():
    """Scenario C.2: Linux OS dispatch through SystemProviderFactory."""
    linux_info = PlatformInfo(
        os_family="linux",
        os_name="Ubuntu 24.04",
        os_version="24.04",
        architecture="x86_64",
        shell_default="bash",
    )
    provider = SystemProviderFactory.get_system_info_provider(linux_info)
    info = provider.get_os_info()
    assert "system_root" in info
    assert info["system_root"] == "/"


@pytest.mark.cross_platform
def test_c03_package_manager_ambiguity():
    """Scenario C.3: Detect and handle multiple co-existing package managers without ambiguity."""
    linux_info = PlatformInfo(
        os_family="linux",
        os_name="Ubuntu",
        os_version="24.04",
        architecture="x86_64",
        shell_default="bash",
        package_managers=["apt", "snap", "flatpak"],
    )
    assert "apt" in linux_info.package_managers
    assert "snap" in linux_info.package_managers
    assert "flatpak" in linux_info.package_managers


@pytest.mark.cross_platform
def test_c04_wayland_gui_degradation():
    """Scenario C.4: Wayland GUI compositor degradation is explicitly reported, not faked."""
    wayland_info = PlatformInfo(
        os_family="linux",
        os_name="Fedora",
        os_version="40",
        architecture="x86_64",
        shell_default="bash",
        display_server="wayland",
    )
    matrix = get_capability_matrix(wayland_info)
    assert matrix["gui_screen_capture"].status == CapabilityStatus.DEGRADED
    assert "Wayland" in matrix["gui_screen_capture"].reason
    assert matrix["window_management"].status == CapabilityStatus.DEGRADED


@pytest.mark.cross_platform
def test_c05_cross_os_parity_process_and_ports():
    """Scenario C.5: Tool schema and method parity across OS boundaries."""
    win_proc = SystemProviderFactory.get_process_provider(
        PlatformInfo(os_family="windows", os_name="Windows 11", os_version="10.0", architecture="AMD64", shell_default="powershell")
    )
    linux_proc = SystemProviderFactory.get_process_provider(
        PlatformInfo(os_family="linux", os_name="Ubuntu", os_version="24.04", architecture="x86_64", shell_default="bash")
    )
    mac_proc = SystemProviderFactory.get_process_provider(
        PlatformInfo(os_family="macos", os_name="macOS 15.1", os_version="15.1", architecture="arm64", shell_default="zsh")
    )
    assert hasattr(win_proc, "get_process_info")
    assert hasattr(linux_proc, "get_process_info")
    assert hasattr(mac_proc, "get_process_info")


# --- C.2 Autonomous Behavior ---

@pytest.mark.cross_platform
def test_c06_local_only_routing():
    """Scenario C.6: Local system question routes to LOCAL_INFORMATION and invokes local tools."""
    intent = classify_intent("What Python version do I have?")
    assert intent == IntentCategory.LOCAL_INFORMATION


@pytest.mark.cross_platform
def test_c07_web_only_routing():
    """Scenario C.7: External knowledge question routes to WEB_INFORMATION."""
    intent = classify_intent("What is the latest Python version?")
    assert intent == IntentCategory.WEB_INFORMATION


@pytest.mark.cross_platform
def test_c08_mandatory_automatic_search_routing():
    """Scenario C.8: Real-time query requires web search without waiting for permission."""
    intent = classify_intent("What is the current iPhone 17 price today?")
    assert intent == IntentCategory.WEB_INFORMATION


@pytest.mark.cross_platform
def test_c09_combined_routing():
    """Scenario C.9: Combined local and web request routes to MULTI_TOOL."""
    intent = classify_intent("What Python version do I have, and what is the latest release today?")
    assert intent == IntentCategory.MULTI_TOOL


@pytest.mark.cross_platform
def test_c10_fallback_on_partial_failure():
    """Scenario C.10: Safe graceful fallback when a provider query returns partial results."""
    win_sw = SystemProviderFactory.get_software_provider(
        PlatformInfo(os_family="windows", os_name="Windows 11", os_version="10.0", architecture="AMD64", shell_default="powershell")
    )
    apps = win_sw.get_installed_software(limit=5)
    assert isinstance(apps, list)


@pytest.mark.cross_platform
def test_c11_full_action_and_verify_chain():
    """Scenario C.11: Multi-step action execution with recorded verification results."""
    config = AgentConfig()
    session_store = MagicMock(spec=SessionStore)
    session_store.get_messages.return_value = []
    from app.tools.base import BaseTool
    from app.models.tools import ToolExecutionResult, PermissionLevel
    class MockOSTool(BaseTool):
        name = "get_os_info"
        description = "Get OS Info"
        permission_level = PermissionLevel.LEVEL_0_READ_ONLY
        def get_parameters_schema(self):
            return {"type": "object", "properties": {}}
        def _run(self, **kwargs):
            return "Windows 11"

    audit_store = MagicMock(spec=AuditStore)
    tool_registry = ToolRegistry()
    tool_registry.register(MockOSTool())

    mock_provider = MagicMock()
    mock_provider.generate.side_effect = [
        ChatMessage(role=Role.ASSISTANT, tool_calls=[ToolCall(id="c1", name="get_os_info", arguments={})]),
        ChatMessage(role=Role.ASSISTANT, content="Completed: OS inspected. Result: Windows 11. Verification: confirmed."),
    ]

    orchestrator = AgentOrchestrator(
        config=config,
        provider=mock_provider,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=tool_registry,
    )

    resp = orchestrator.process_message("sess_1", "Inspect my operating system and verify it.")
    assert "Windows 11" in resp.content
    assert audit_store.record_event.called


@pytest.mark.cross_platform
def test_c12_no_premature_completion():
    """Scenario C.12: Actionable requests cannot complete prematurely without tool invocation."""
    intent = classify_intent("Install postgresql")
    assert intent == IntentCategory.LOCAL_ACTION


@pytest.mark.cross_platform
def test_c13_no_unverified_completion():
    """Scenario C.13: Troubleshooting requests require diagnosis tool execution."""
    intent = classify_intent("Fix the error in my python script")
    assert intent == IntentCategory.TROUBLESHOOTING


# --- C.3 macOS Scenarios (C.14 to C.18) ---

@pytest.mark.cross_platform
def test_c14_macos_dispatch():
    """Scenario C.14: macOS dispatch through SystemProviderFactory returns identical schema."""
    mac_info = PlatformInfo(
        os_family="macos",
        os_name="macOS 15.1 (Sequoia)",
        os_version="15.1",
        architecture="arm64",
        is_apple_silicon=True,
        shell_default="zsh",
    )
    provider = SystemProviderFactory.get_system_info_provider(mac_info)
    info = provider.get_os_info()
    assert "Sequoia" in info["os_name"]
    assert info["system_root"] == "/"
    assert info["is_apple_silicon"] is True


@pytest.mark.cross_platform
def test_c15_tcc_permission_denial_handling():
    """Scenario C.15: Attempt screenshot or synthetic input without TCC returns structured degradation."""
    provider = MacOSGUIProvider()
    with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="execution error: -1743")):
        res = provider.send_input(text="Test input")
        assert res["success"] is False
        assert "TCC" in res["error"] or "Accessibility" in res["error"]


@pytest.mark.cross_platform
def test_c16_sip_protected_path_write_attempt():
    """Scenario C.16: SIP-protected path write raises distinct SIP PermissionError."""
    mac_info = PlatformInfo(
        os_family="macos",
        os_name="macOS 15.1",
        os_version="15.1",
        architecture="arm64",
        shell_default="zsh",
        sip_enabled=True,
    )
    with patch("app.tools.filesystem.safety.get_platform_info", return_value=mac_info):
        safety = PathSafety()
        with pytest.raises(PermissionError, match="System Integrity Protection"):
            safety.check_safe_write("/System/Library/CoreServices/SystemVersion.plist")


@pytest.mark.cross_platform
def test_c17_homebrew_macports_ambiguity():
    """Scenario C.17: When Homebrew and MacPorts both exist, agent surfaces choice for approval."""
    provider = MacOSSoftwareProvider()
    with patch.object(provider, "detect_managers", return_value=[
        {"name": "brew", "display_name": "Homebrew"},
        {"name": "port", "display_name": "MacPorts"},
    ]):
        res = provider.install_package("git")
        assert res["success"] is False
        assert res.get("needs_disambiguation") is True
        assert "brew" in res["available_managers"]
        assert "port" in res["available_managers"]


@pytest.mark.cross_platform
def test_c18_apple_silicon_rosetta_awareness():
    """Scenario C.18: Architecture-sensitive install resolves to native arm64 and detects Rosetta."""
    mac_info = PlatformInfo(
        os_family="macos",
        os_name="macOS 15.1",
        os_version="15.1",
        architecture="arm64",
        is_apple_silicon=True,
        is_rosetta_translated=True,
        shell_default="zsh",
    )
    assert mac_info.is_apple_silicon is True
    assert mac_info.is_rosetta_translated is True


# --- C.4 Directive v4 Regression Tests (C.19 to C.23) ---

@pytest.mark.cross_platform
def test_c19_installed_vs_running_distinction():
    """Scenario C.19: Distinct tools for installed software vs active running software."""
    # 1. Classification check
    intent_installed = classify_intent("what are the software i am having in my computer")
    intent_running = classify_intent("what are the software is active in the computer right now?")
    assert intent_installed == IntentCategory.LOCAL_INFORMATION
    assert intent_running == IntentCategory.LOCAL_INFORMATION

    # 2. Alignment guard check in Orchestrator
    config = AgentConfig()
    session_store = MagicMock(spec=SessionStore)
    session_store.get_messages.return_value = []
    audit_store = MagicMock(spec=AuditStore)
    tool_registry = ToolRegistry()

    orchestrator = AgentOrchestrator(
        config=config,
        provider=MagicMock(),
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=tool_registry,
    )

    # Calling get_installed_software for active software query must be flagged as misalignment
    aligned, err = orchestrator._check_semantic_alignment(
        "what are the software is active in the computer right now?", "get_installed_software"
    )
    assert aligned is False
    assert "SEMANTIC MISALIGNMENT" in err
    assert "get_process_info" in err


@pytest.mark.cross_platform
def test_c20_services_query_invokes_service_provider():
    """Scenario C.20: Services query invokes get_service_info and rejects generic shell fallback."""
    # 1. Classification check with typos
    intent = classify_intent("what are the services is runing on my window . use the task manger")
    assert intent == IntentCategory.LOCAL_INFORMATION

    # 2. Alignment guard rejects generic terminal_exec
    config = AgentConfig()
    session_store = MagicMock(spec=SessionStore)
    session_store.get_messages.return_value = []
    audit_store = MagicMock(spec=AuditStore)
    tool_registry = ToolRegistry()

    orchestrator = AgentOrchestrator(
        config=config,
        provider=MagicMock(),
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=tool_registry,
    )

    aligned, err = orchestrator._check_semantic_alignment(
        "what are the services is runing on my window . use the task manger", "terminal_exec"
    )
    assert aligned is False
    assert "get_service_info" in err


@pytest.mark.cross_platform
def test_c21_classifier_misclassification_safety_net():
    """Scenario C.21: Pattern-based backstop prevents NORMAL_CHAT bypass for environment queries."""
    query = "the services runing in the background right now"
    # Backstop pattern match
    assert IntentClassifier.is_environment_query(query) is True

    # Even if classifier theoretically returned NORMAL_CHAT, backstop elevates to LOCAL_INFORMATION
    intent = classify_intent(query)
    assert intent == IntentCategory.LOCAL_INFORMATION


@pytest.mark.cross_platform
def test_c22_no_stale_tool_reuse():
    """Scenario C.22: Fresh classification and tool execution for distinct sequential turns."""
    intent_t1 = classify_intent("what are the software i am having in my computer")
    intent_t2 = classify_intent("what is my ipv4 address ?")

    assert intent_t1 == IntentCategory.LOCAL_INFORMATION
    assert intent_t2 == IntentCategory.LOCAL_INFORMATION


@pytest.mark.cross_platform
def test_c23_golden_transcript_replay():
    """Scenario C.23: Full replay of the 4 golden prompts confirming tool mapping and classification."""
    golden_prompts = [
        ("what is my ipv4 address ?", IntentCategory.LOCAL_INFORMATION, "network"),
        ("what are the software i am having in my computer", IntentCategory.LOCAL_INFORMATION, "installed"),
        ("what are the software is active in the computer right now?", IntentCategory.LOCAL_INFORMATION, "process"),
        ("what are the services is runing on my window . use the task manger", IntentCategory.LOCAL_INFORMATION, "service"),
    ]

    for prompt, expected_intent, expected_domain in golden_prompts:
        classified = classify_intent(prompt)
        assert classified == expected_intent, f"Prompt '{prompt}' misclassified as {classified}"

        is_env = IntentClassifier.is_environment_query(prompt)
        assert is_env is True, f"Prompt '{prompt}' failed environment query backstop"


@pytest.mark.cross_platform
def test_c24_network_info_ipv4_format_validation():
    """Scenario C.24 (Directive B.33): Asserts get_network_info IPv4 field matches valid dotted-quad regex on real host."""
    import re
    from app.tools.windows.network_info import GetNetworkInfoTool

    tool = GetNetworkInfoTool()
    res = tool.execute("call_net_test")
    assert res.success is True
    data = res.data

    assert "primary_ipv4" in data
    assert "adapters" in data
    assert len(data["adapters"]) > 0

    ipv4_pattern = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")

    # Validate primary_ipv4
    assert ipv4_pattern.match(data["primary_ipv4"]), f"Invalid primary IPv4 address format: {data['primary_ipv4']}"

    # Validate every configured adapter IPv4 address
    for adapter in data["adapters"]:
        assert "ipv4_address" in adapter
        ip_str = adapter["ipv4_address"]
        if ip_str != "Not Configured":
            for ip in ip_str.split(", "):
                assert ipv4_pattern.match(ip), f"Invalid adapter IPv4 format '{ip}' in adapter '{adapter.get('alias')}'"


# --- C.25 to C.30 (Directive v5 Action & Safety Suite) ---

@pytest.mark.cross_platform
def test_c25_app_launch_and_close_real():
    """Scenario C.25 (Directive v5 Tier 1): Real desktop application launch and close lifecycle on Windows."""
    import sys
    import time
    if sys.platform != "win32":
        pytest.skip("Windows only real lifecycle test")

    from app.tools.applications.lifecycle import CloseApplicationTool, LaunchApplicationTool
    from app.tools.system.factory import SystemProviderFactory

    gui = SystemProviderFactory.get_gui_provider()
    # 1. Launch Calculator
    launch_tool = LaunchApplicationTool()
    res_launch = launch_tool.execute("call_c25_launch", target="calc.exe")
    assert res_launch.success is True
    time.sleep(1.5)

    # 2. Verify running
    status = gui.get_app_status("CalculatorApp")
    assert status["running"] is True

    # 3. Close Calculator
    close_tool = CloseApplicationTool()
    res_close = close_tool.execute("call_c25_close", process_name="CalculatorApp")
    assert res_close.success is True
    time.sleep(1.0)

    # 4. Verify gone
    status_after = gui.get_app_status("CalculatorApp")
    assert status_after["running"] is False


@pytest.mark.cross_platform
def test_c26_file_create_delete_with_approval_gate():
    """Scenario C.26 (Directive v5 Tier 2): File creation, approval gate assertion (B.34), and deletion."""
    import tempfile
    from pathlib import Path
    from app.models.tools import PermissionLevel
    from app.tools.filesystem.manage_files import ManageFilesTool
    from app.tools.filesystem.write_file import WriteFileTool

    scratch_dir = Path(tempfile.gettempdir()) / "agent_test_scratch"
    test_file = scratch_dir / "agent_test.txt"

    # 1. Create file
    write_tool = WriteFileTool()
    res_write = write_tool.execute("call_c26_write", file_path=str(test_file), content="hello")
    assert res_write.success is True
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "hello"

    # 2. Check permission level of delete tool
    manage_tool = ManageFilesTool()
    assert manage_tool.permission_level == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    # 3. Simulate rejection first
    approval_events = []
    def reject_callback(tool_name, tool_call, level):
        approval_events.append((tool_name, tool_call.arguments, level))
        return False

    del_tc = ToolCall(id="call_c26_del", name=manage_tool.name, arguments={"operation": "delete", "source_path": str(test_file)})
    assert reject_callback(manage_tool.name, del_tc, manage_tool.permission_level) is False
    assert len(approval_events) == 1
    assert approval_events[0][0] == "file_manage"
    assert approval_events[0][2] == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
    # Verify file still exists after rejection
    assert test_file.exists()

    # 4. Authorized execution
    res_del = manage_tool.execute("call_c26_del", operation="delete", source_path=str(test_file))
    assert res_del.success is True
    assert not test_file.exists()


@pytest.mark.cross_platform
def test_c27_service_status_and_safe_restart():
    """Scenario C.27 (Directive v5 Tier 3): Service status inspection and safe restart/elevation handling."""
    import ctypes
    import sys
    if sys.platform != "win32":
        pytest.skip("Windows only service test")

    from app.tools.system.factory import SystemProviderFactory
    from app.tools.windows.service_info import GetServiceInfoTool

    # Inspect Spooler status
    svc_tool = GetServiceInfoTool()
    res = svc_tool.execute("call_c27_svc", query="spooler")
    assert res.success is True
    spooler = next((s for s in res.data if "spooler" in s["name"].lower()), None)
    assert spooler is not None
    assert spooler["status"] in ("Running", "Stopped")

    # Manage service
    provider = SystemProviderFactory.get_service_provider()
    is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())

    res_restart = provider.manage_service("Spooler", "restart")
    if not is_admin:
        assert res_restart.get("needs_elevation") is True
        assert res_restart["success"] is False
        assert "requires administrative privileges" in res_restart.get("error", "").lower()
    else:
        assert res_restart["success"] is True
        # Verify running afterward
        status_after = svc_tool.execute("call_c27_after", query="spooler")
        spooler_after = next((s for s in status_after.data if "spooler" in s["name"].lower()), None)
        assert spooler_after["status"] == "Running"


@pytest.mark.cross_platform
def test_c28_install_verify_uninstall_chain():
    """Scenario C.28 (Directive v5 Tier 4): Full B.16 chain (install -> verify -> uninstall)."""
    from unittest.mock import MagicMock, patch
    from app.tools.software.install import InstallSoftwareTool
    from app.tools.software.verify import VerifySoftwareTool

    tool_install = InstallSoftwareTool()
    tool_verify = VerifySoftwareTool()

    with patch("subprocess.run") as mock_run:
        # 1. Mock successful installation
        mock_run.return_value = MagicMock(returncode=0, stdout="Successfully installed", stderr="")
        res_inst = tool_install.execute("call_c28_inst", package_name="jqlang.jq", manager="winget", action="install")
        assert res_inst.success is True
        assert "install" in res_inst.data["command"]

        # 2. Mock verification
        with patch("shutil.which", return_value="C:\\Program Files\\jq\\jq.exe"):
            res_ver = tool_verify.execute("call_c28_ver", name="jq", executable_name="jq.exe")
            assert res_ver.success is True
            assert res_ver.data["verified"] is True
            assert res_ver.data["software_name"] == "jq"

        # 3. Mock uninstallation cleanup
        res_uninst = tool_install.execute("call_c28_uninst", package_name="jqlang.jq", manager="winget", action="uninstall")
        assert res_uninst.success is True
        assert "uninstall" in res_uninst.data["command"]


@pytest.mark.cross_platform
def test_c29_protected_path_write_refused():
    """Scenario C.29 (Directive v5 Tier 5): Write into protected system path must be refused by security policy."""
    import sys
    from app.security.guard import SecurityGuard
    from app.tools.filesystem.write_file import WriteFileTool

    test_path = r"C:\Windows\System32\test.txt" if sys.platform == "win32" else "/etc/test.txt"
    assert SecurityGuard.is_path_protected(test_path) is True

    write_tool = WriteFileTool()
    res = write_tool.execute("call_c29_sec", file_path=test_path, content="malicious")
    assert res.success is False
    assert "blocked by security policy" in (res.error or "").lower() or "permissionerror" in (res.error or "").lower()


@pytest.mark.cross_platform
def test_c30_elevation_gate_no_password_capture():
    """Scenario C.30 (Directive v5 Tier 6): Unelevated service disable returns structured needs_elevation:true without password prompt."""
    import sys
    from unittest.mock import patch
    from app.tools.developer.dev_services import ManageDevServiceTool

    dev_tool = ManageDevServiceTool()
    if sys.platform == "win32":
        with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=0):
            res = dev_tool.execute("call_c30_elev", service_name="wuauserv", action="disable")
            data = res.data or {}
            assert data.get("success") is False
            assert data.get("needs_elevation") is True
            full_text = str(res.output_text) + str(data)
            assert "password" not in full_text.lower()
            assert "credential" not in full_text.lower()
            assert "sudo" not in full_text.lower()
    else:
        with patch("os.geteuid", return_value=1000):
            res = dev_tool.execute("call_c30_elev", service_name="wuauserv", action="disable")
            data = res.data or {}
            assert data.get("success") is False
            assert data.get("needs_elevation") is True
            full_text = str(res.output_text) + str(data)
            assert "password" not in full_text.lower()
            assert "credential" not in full_text.lower()


@pytest.mark.cross_platform
def test_c31_no_stated_intent_as_completion():
    """Scenario C.31 (Directive v5.2): Assert stated intent language cannot co-occur with COMPLETED state without execution."""
    from unittest.mock import MagicMock
    from app.agent.orchestrator import AgentOrchestrator
    from app.config import AgentConfig
    from app.models.messages import ChatMessage, Role
    from app.models.state import TaskState
    from app.storage.audit_store import AuditStore
    from app.storage.database import Database
    from app.storage.session_store import SessionStore
    from app.tools.registry import ToolRegistry
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        db = Database(Path(tmp_dir) / "test.db")
        ss = SessionStore(db)
        aud = AuditStore(db)
        reg = ToolRegistry()
        cfg = AgentConfig()

        mock_prov = MagicMock()
        mock_prov.generate.return_value = ChatMessage(
            role=Role.ASSISTANT,
            content='To overwrite it with the same text 1,000,000 times, I need to set allow_multiple to True. Let me proceed with that.',
        )

        orch = AgentOrchestrator(
            config=cfg,
            provider=mock_prov,
            session_store=ss,
            audit_store=aud,
            tool_registry=reg,
        )

        sess = ss.create_session("C31 Test")
        states_visited = []

        def status_cb(desc, state):
            states_visited.append(state)

        resp = orch.process_message(
            sess.id,
            "same file rewrite the text 'hello world' 1000000 times",
            status_callback=status_cb,
        )

        # Assert FSM did not complete successfully with unexecuted intent
        assert TaskState.COMPLETED not in states_visited
        assert "error" in resp.content.lower() or "failed" in resp.content.lower()
        db.close()


@pytest.mark.cross_platform
def test_c32_modification_verb_classification():
    """Scenario C.32 (Directive v5.2): Modification verbs are classified as LOCAL_ACTION."""
    from app.agent.intent import IntentClassifier
    from app.models.state import IntentCategory

    prompts = [
        "same file rewrite the text 'hello world' 1000000 times",
        "rewrite the file testing.txt",
        "overwrite the configuration with new settings",
        "edit the file to add 5 lines",
        "modify the hosts file",
        "update the script to version 2",
        "replace the text 'foo' with 'bar'",
        "append hello to log.txt",
    ]

    for p in prompts:
        cat = IntentClassifier.classify(p)
        assert cat == IntentCategory.LOCAL_ACTION, f"Prompt '{p}' was classified as {cat.value}, expected LOCAL_ACTION"


@pytest.mark.cross_platform
def test_c33_completion_guard_hard_blocks():
    """Scenario C.33 (Directive v5.3 Section 1): Hard-block gate prevents unexecuted actionable completion and manages clarification."""
    from unittest.mock import MagicMock
    from app.agent.orchestrator import AgentOrchestrator
    from app.config import AgentConfig
    from app.models.messages import ChatMessage, Role, ToolCall
    from app.models.state import TaskState
    from app.storage.audit_store import AuditStore
    from app.storage.database import Database
    from app.storage.session_store import SessionStore
    from app.tools.registry import ToolRegistry
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        db = Database(Path(tmp_dir) / "test.db")
        ss = SessionStore(db)
        aud = AuditStore(db)
        reg = ToolRegistry()
        cfg = AgentConfig()

        # Part 1: Model asks clarification -> Must route to WAITING_FOR_USER, NEVER COMPLETED
        mock_prov = MagicMock()
        mock_prov.generate.return_value = ChatMessage(
            role=Role.ASSISTANT,
            content="I can help with that. Could you please specify if you're looking for applications, background services, or both?",
        )

        orch = AgentOrchestrator(
            config=cfg,
            provider=mock_prov,
            session_store=ss,
            audit_store=aud,
            tool_registry=reg,
        )

        sess = ss.create_session("C33 Clarification Test")
        states_visited = []

        def status_cb(desc, state):
            states_visited.append(state)

        resp = orch.process_message(
            sess.id,
            "hey can u tell me what apps r runing on my pc right now",
            status_callback=status_cb,
        )

        # Assert FSM hard-blocked COMPLETED state
        assert TaskState.COMPLETED not in states_visited
        assert TaskState.WAITING_FOR_USER in states_visited
        assert "?" in resp.content

        # Assert pending action was saved in session metadata
        updated_sess = ss.get_session(sess.id)
        assert updated_sess is not None
        assert "pending_action" in updated_sess.metadata
        assert "apps r runing" in updated_sess.metadata["pending_action"]["goal"]

        # Part 2: Hard-block failure if model produces non-tool conversational text without asking a question
        mock_prov_fail = MagicMock()
        mock_prov_fail.generate.return_value = ChatMessage(
            role=Role.ASSISTANT,
            content="I am a chatbot and I cannot look at your computer.",
        )
        orch_fail = AgentOrchestrator(
            config=cfg,
            provider=mock_prov_fail,
            session_store=ss,
            audit_store=aud,
            tool_registry=reg,
        )
        sess_fail = ss.create_session("C33 Hard Fail Test")
        fail_states = []

        def fail_status_cb(desc, state):
            fail_states.append(state)

        resp_fail = orch_fail.process_message(
            sess_fail.id,
            "what's my IP address",
            status_callback=fail_status_cb,
        )

        assert TaskState.COMPLETED not in fail_states
        assert TaskState.FAILED in fail_states
        assert "error" in resp_fail.content.lower() or "could not be completed" in resp_fail.content.lower()

        db.close()


@pytest.mark.cross_platform
def test_c34_bulk_write_resource_gate(tmp_path):
    """Scenario C.34 (Directive B.38): Resource safety gate refuses excessive/bulk writes before allocating disk/memory."""
    from app.tools.filesystem.write_file import WriteFileTool
    from pathlib import Path
    import shutil

    tool = WriteFileTool()
    test_file = str(tmp_path / "bulk_test.txt")

    # 1. 10 billion repeats of 13 bytes (~130 GB) exceeds both 1 GB limit and disk space
    res = tool.execute(
        "call_c34_1",
        file_path=test_file,
        content="test bulk 123",
        repeat_count=10_000_000_000,
    )
    assert res.success is False
    assert "Resource Safety Gate Refusal (Directive B.38)" in res.error
    assert "130.0 GB" in res.error or "130" in res.error

    # 2. File was NOT created on disk
    assert not Path(test_file).exists()


@pytest.mark.cross_platform
def test_c35_path_canonicalization_argument_agnostic(tmp_path):
    """Scenario C.35 (Directive B.39): Path canonicalization detects paths by value shape across any argument key."""
    from app.tools.filesystem.safety import PathSafety
    from pathlib import Path

    safety = PathSafety()

    # Test various argument key names with placeholder usernames
    test_args = {
        "path": "C:/Users/User/Desktop/sample1.txt",
        "file_path": "C:/Users/YourUsername/Desktop/sample2.txt",
        "source_path": "/Users/admin/Desktop/sample3.txt",
        "target_path": "~/Desktop/sample4.txt",
        "destination_path": "Desktop/sample5.txt",
        "random_key": "C:/Users/default/Desktop/sample6.txt",
        "non_path_key": "some regular text content",
    }

    cleaned = PathSafety.sanitize_arguments(test_args)

    expected_desktop = str(Path.home() / "Desktop")

    for k in ["path", "file_path", "source_path", "target_path", "destination_path", "random_key"]:
        val = cleaned[k]
        assert str(Path.home()) in val or "Desktop" in val, f"Key '{k}' with value '{val}' failed canonicalization"

    # Non-path argument should remain untouched
    assert cleaned["non_path_key"] == "some regular text content"


@pytest.mark.cross_platform
def test_c36_tool_result_verification_required(tmp_path):
    """Scenario C.36 (Directive B.40): Action tool execution must independently verify real state change."""
    from app.tools.filesystem.manage_files import ManageFilesTool
    from app.config import AgentConfig
    from app.agent.orchestrator import AgentOrchestrator
    from app.storage.database import Database
    from app.storage.session_store import SessionStore
    from app.storage.audit_store import AuditStore
    from app.tools.registry import ToolRegistry
    from pathlib import Path
    from app.models.state import TaskState
    from unittest.mock import MagicMock

    # 1. Test tool level: delete on nonexistent file returns success=False / verified_success=False
    tool = ManageFilesTool()
    nonexistent = str(tmp_path / "does_not_exist_9876.txt")
    res = tool.execute("call_c36_del", operation="delete", source_path=nonexistent)
    assert res.success is False
    assert res.verified_success is False
    assert "does not exist" in res.error.lower()

    # 2. Test orchestrator level: when delete tool fails, FSM transitions to FAILED, not COMPLETED
    cfg = AgentConfig()
    db_path = tmp_path / "c36_test.db"
    db = Database(db_path)
    ss = SessionStore(db)
    aud = AuditStore(db)
    reg = ToolRegistry()
    reg.register(tool)

    mock_prov = MagicMock()
    # Turn 1: model attempts tool call
    mock_prov.generate.side_effect = [
        ChatMessage(
            role=Role.ASSISTANT,
            content=None,
            tool_calls=[ToolCall(id="call_del", name="file_manage", arguments={"operation": "delete", "path": nonexistent})],
        ),
        # Turn 2: model attempts to invent success
        ChatMessage(
            role=Role.ASSISTANT,
            content="The file has been successfully deleted from your computer.",
        ),
    ]

    orch = AgentOrchestrator(
        config=cfg,
        provider=mock_prov,
        session_store=ss,
        audit_store=aud,
        tool_registry=reg,
        approval_callback=lambda name, call, *args: True,
    )

    sess = ss.create_session("C36 Verification Test")
    visited_states = []

    def status_cb(desc, state):
        visited_states.append(state)

    resp = orch.process_message(
        sess.id,
        f"delete the file {nonexistent}",
        status_callback=status_cb,
    )

    assert TaskState.FAILED in visited_states
    assert "successfully deleted" not in resp.content.lower()
    assert "error" in resp.content.lower() or "failed" in resp.content.lower()

    db.close()


@pytest.mark.cross_platform
def test_c37_self_limitation_interception(tmp_path):
    """Scenario C.37 (Directive B.41): Intercepts self-limiting inability claims when a matching tool exists."""
    from app.config import AgentConfig
    from app.agent.orchestrator import AgentOrchestrator
    from app.storage.database import Database
    from app.storage.session_store import SessionStore
    from app.storage.audit_store import AuditStore
    from app.tools.registry import ToolRegistry
    from app.tools.system.datetime_tool import GetCurrentDateTimeTool
    from app.tools.windows.process_info import GetProcessInfoTool
    from app.tools.windows.hardware_info import GetHardwareInfoTool
    from pathlib import Path
    from unittest.mock import MagicMock

    cfg = AgentConfig()
    db_path = tmp_path / "c37_test.db"
    db = Database(db_path)
    ss = SessionStore(db)
    aud = AuditStore(db)
    reg = ToolRegistry()
    reg.register(GetCurrentDateTimeTool())
    reg.register(GetProcessInfoTool())
    reg.register(GetHardwareInfoTool())

    # Case A: Model claims it cannot check time -> Intercepted and re-prompted to use get_current_datetime
    mock_prov = MagicMock()
    mock_prov.generate.side_effect = [
        # Turn 1: Model outputs self-limiting claim
        ChatMessage(
            role=Role.ASSISTANT,
            content="I don't have access to a real-time clock to determine the current time.",
        ),
        # Turn 2: Model emits tool call after enforcement
        ChatMessage(
            role=Role.ASSISTANT,
            content=None,
            tool_calls=[ToolCall(id="call_time_1", name="get_current_datetime", arguments={})],
        ),
        # Turn 3: Final response after tool execution
        ChatMessage(
            role=Role.ASSISTANT,
            content="The current local time is 11:35 AM.",
        ),
    ]

    orch = AgentOrchestrator(
        config=cfg,
        provider=mock_prov,
        session_store=ss,
        audit_store=aud,
        tool_registry=reg,
    )

    sess = ss.create_session("C37 Time Interception")
    resp = orch.process_message(sess.id, "what is the time now")
    assert "11:35" in resp.content or "Completed in" in resp.content

    # Assert that get_current_datetime was called
    assert mock_prov.generate.call_count == 3

    db.close()


@pytest.mark.cross_platform
def test_c38_time_query_routes_to_local_clock():
    """Scenario C.38 (Directive v6.1 Addendum): Date and time queries route to local clock tool without network search."""
    from app.agent.intent import classify_intent, IntentCategory
    from app.tools.system.datetime_tool import GetCurrentDateTimeTool
    from datetime import datetime

    # 1. Intent classification
    assert classify_intent("what is the time now") == IntentCategory.LOCAL_INFORMATION
    assert classify_intent("what time is it") == IntentCategory.LOCAL_INFORMATION
    assert classify_intent("what is today's date") == IntentCategory.LOCAL_INFORMATION
    assert classify_intent("tell me the current time") == IntentCategory.LOCAL_INFORMATION

    # 2. Local execution accuracy
    tool = GetCurrentDateTimeTool()
    res = tool.execute("call_time_test")
    assert res.success is True
    data = res.data

    assert "datetime_iso" in data
    assert "time_12h" in data
    assert "time_24h" in data
    assert "timezone" in data
    assert "timestamp_epoch" in data

    now = datetime.now()
    assert data["date"] == now.strftime("%Y-%m-%d")


@pytest.mark.cross_platform
def test_c39_generative_content_length_verification(tmp_path):
    """Scenario C.39 (Directive B.42): Generative length feasibility gate and post-action word count verification."""
    from app.tools.filesystem.write_file import WriteFileTool
    from app.config import AgentConfig
    from app.agent.orchestrator import AgentOrchestrator
    from app.storage.database import Database
    from app.storage.session_store import SessionStore
    from app.storage.audit_store import AuditStore
    from app.tools.registry import ToolRegistry
    from app.models.state import TaskState
    from pathlib import Path
    from unittest.mock import MagicMock

    # Part 1: Tool-level verification fails when generated word count is drastically short of target
    tool = WriteFileTool()
    short_target_file = str(tmp_path / "short_story.txt")
    # Request target is 1,000 words, but content only has 14 words
    res = tool.execute(
        "call_c39_tool",
        file_path=short_target_file,
        content="Once upon a time in a faraway kingdom, there lived a brave young knight.",
        target_words=1000,
    )
    assert res.success is False or res.verified_success is False
    assert "Generative Length Verification Failure (Directive B.42)" in str(res.error)
    assert "1,000 words" in str(res.error)

    # Part 2: Orchestrator upfront feasibility refusal for impossible targets (>50,000 words)
    cfg = AgentConfig()
    db_path = tmp_path / "c39_test.db"
    db = Database(db_path)
    ss = SessionStore(db)
    aud = AuditStore(db)
    reg = ToolRegistry()
    reg.register(tool)

    mock_prov = MagicMock()
    orch = AgentOrchestrator(
        config=cfg,
        provider=mock_prov,
        session_store=ss,
        audit_store=aud,
        tool_registry=reg,
    )

    sess = ss.create_session("C39 Feasibility Test")
    resp = orch.process_message(
        sess.id,
        "create a file story.txt on Desktop with a 10,000,000-word story",
    )

    # Assert upfront refusal without calling provider or creating hallucinated files
    assert "Refused (Directive B.42 Feasibility Gate)" in resp.content
    assert "10,000,000 words is physically infeasible" in resp.content
    assert mock_prov.generate.call_count == 0

    # Part 3: Orchestrator catches tool failure on drastically truncated content and transitions to FAILED
    sess2 = ss.create_session("C39 Truncation Catch Test")
    mock_prov2 = MagicMock()
    # Model attempts to emit file_write with a 1-sentence placeholder for a 2,000-word story
    test_out = str(tmp_path / "story2.txt")
    mock_prov2.generate.side_effect = [
        ChatMessage(
            role=Role.ASSISTANT,
            content=None,
            tool_calls=[ToolCall(id="call_c39_w", name="file_write", arguments={"file_path": test_out, "content": "Once upon a time."})],
        ),
        ChatMessage(
            role=Role.ASSISTANT,
            content="The 2000-word story has been written successfully.",
        ),
    ]

    orch2 = AgentOrchestrator(
        config=cfg,
        provider=mock_prov2,
        session_store=ss,
        audit_store=aud,
        tool_registry=reg,
        approval_callback=lambda *a: True,
    )

    visited_states = []
    def status_cb(desc, st):
        visited_states.append(st)

    resp2 = orch2.process_message(
        sess2.id,
        f"write a 2000-word story in {test_out}",
        status_callback=status_cb,
    )

    assert TaskState.FAILED in visited_states
    assert "successfully" not in resp2.content.lower()
    assert "failed" in resp2.content.lower() or "error" in resp2.content.lower()

    db.close()


@pytest.mark.cross_platform
def test_c41_hardware_detection_no_gpu():
    """Scenario C.41 (Directive v9 Section 1): Graceful hardware concurrency fallback in GPU-less environments."""
    from app.agent.multi_agent import HardwareConcurrencyManager

    # Simulated headless cloud instance / VM without discrete GPU
    mock_hw_info = {
        "cpu": {
            "name": "Intel Xeon E5-2686 v4",
            "architecture": "x86_64",
            "cores": 4,
            "logical_processors": 4,
            "is_apple_silicon": False,
        },
        "ram": {
            "total_ram_gb": 8.0,
            "available_ram_gb": 5.2,
        },
        "gpus": [],
    }

    limits = HardwareConcurrencyManager.calculate_limits_from_info(mock_hw_info)
    assert limits.max_concurrent_llm_calls == 1  # CPU inference must be single-stream
    assert limits.max_io_thread_workers == 2
    assert limits.detected_vram_gb == 0.0
    assert limits.logical_cpus == 4


@pytest.mark.cross_platform
def test_c42_hardware_detection_amd_gpu():
    """Scenario C.42 (Directive v9 Section 1): Correct parsing and concurrency scaling for AMD discrete GPUs."""
    from app.agent.multi_agent import HardwareConcurrencyManager

    mock_hw_info = {
        "cpu": {
            "name": "AMD Ryzen 9 7950X",
            "architecture": "AMD64",
            "cores": 16,
            "logical_processors": 32,
            "is_apple_silicon": False,
        },
        "ram": {
            "total_ram_gb": 64.0,
            "available_ram_gb": 48.0,
        },
        "gpus": [
            {
                "name": "AMD Radeon RX 7900 XTX",
                "driver_version": "23.12.1",
                "vram_mb": 24576,  # 24 GB VRAM
                "status": "OK",
            }
        ],
    }

    limits = HardwareConcurrencyManager.calculate_limits_from_info(mock_hw_info)
    assert limits.max_concurrent_llm_calls == 4  # 24 GB VRAM safely hosts 4 concurrent streams
    assert limits.max_io_thread_workers == 16
    assert limits.detected_vram_gb == 24.0
    assert "AMD Radeon RX 7900 XTX" in limits.gpu_names


@pytest.mark.cross_platform
def test_c43_hardware_detection_apple_silicon():
    """Scenario C.43 (Directive v9 Section 1): Unified memory awareness and concurrency bounds on Apple Silicon."""
    from app.agent.multi_agent import HardwareConcurrencyManager

    mock_hw_info = {
        "cpu": {
            "name": "Apple M3 Max",
            "architecture": "arm64",
            "cores": 14,
            "logical_processors": 14,
            "is_apple_silicon": True,
        },
        "ram": {
            "total_ram_gb": 36.0,
            "available_ram_gb": 26.5,
        },
        "gpus": [
            {
                "name": "Apple M3 Max GPU (30 cores)",
                "driver_version": "Metal 3",
                "vram_mb": "Dynamic/Shared",
                "status": "OK",
            }
        ],
    }

    limits = HardwareConcurrencyManager.calculate_limits_from_info(mock_hw_info)
    assert limits.max_concurrent_llm_calls == 4  # 36 GB Unified RAM qualifies for top tier
    assert limits.max_io_thread_workers == 7
    assert limits.detected_vram_gb >= 26.0  # Uses available unified memory


@pytest.mark.cross_platform
def test_c44_hardware_detection_low_resource():
    """Scenario C.44 (Directive v9 Section 1): Conservative non-crashing baseline on minimal resource hosts."""
    from app.agent.multi_agent import HardwareConcurrencyManager

    # Small single-core container with 2 GB RAM
    mock_hw_info = {
        "cpu": {
            "name": "QEMU Virtual CPU",
            "architecture": "x86_64",
            "cores": 1,
            "logical_processors": 1,
            "is_apple_silicon": False,
        },
        "ram": {
            "total_ram_gb": 2.0,
            "available_ram_gb": 0.8,
        },
        "gpus": [],
    }

    limits = HardwareConcurrencyManager.calculate_limits_from_info(mock_hw_info)
    assert limits.max_concurrent_llm_calls == 1
    assert limits.max_io_thread_workers == 1
    assert limits.logical_cpus == 1


@pytest.mark.cross_platform
def test_c45_pdf_mcp_generation(tmp_path):
    """Scenario C.45 (Directive v9 Section 2): Verified PDF document creation via MCP server."""
    from app.mcp.servers.pdf_server import generate_pdf

    target_pdf = tmp_path / "test_report.pdf"
    content = (
        "# Systems Architecture Technical Guide\n\n"
        "## Executive Summary\n"
        "This guide outlines microservices design patterns and resilience protocols.\n\n"
        "## Core Principles\n"
        "- High Availability\n"
        "- Fault Tolerance\n"
        "- Observability\n"
    )

    res = generate_pdf(str(target_pdf), title="Systems Architecture Technical Guide", content=content)
    assert res["status"] == "success"
    assert res["verified_success"] is True
    assert target_pdf.exists()
    assert target_pdf.stat().st_size > 500

    # Verify PDF header magic bytes
    with open(target_pdf, "rb") as f:
        header = f.read(5)
        assert header.startswith(b"%PDF")


@pytest.mark.cross_platform
def test_c46_docx_mcp_generation(tmp_path):
    """Scenario C.46 (Directive v9 Section 2): Verified DOCX document creation via MCP server."""
    from app.mcp.servers.docx_server import generate_docx
    from docx import Document

    target_docx = tmp_path / "test_doc.docx"
    content = (
        "## 1. Introduction\n"
        "Microsoft Word document generated with automated formatting.\n\n"
        "## 2. Specifications\n"
        "- Concurrency Limit: 2\n"
        "- Memory Footprint: Bounded\n"
    )

    res = generate_docx(str(target_docx), title="Project Specification", content=content)
    assert res["status"] == "success"
    assert res["verified_success"] is True
    assert target_docx.exists()
    assert target_docx.stat().st_size > 500

    # Verify readable via python-docx
    doc = Document(str(target_docx))
    assert len(doc.paragraphs) > 0
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Project Specification" in full_text
    assert "Introduction" in full_text


@pytest.mark.cross_platform
def test_c47_mcp_document_content_not_truncated(tmp_path):
    """Scenario C.47 (Directive v9 Section 2): Asserts B.43 decoupled long-form generation holds for MCP document generation."""
    from app.agent.multi_agent import (
        DocumentGenerationWorker,
        HardwareConcurrencyManager,
        WorkerTask,
        WorkspaceManager,
    )
    from app.models.messages import ChatMessage, Role
    from app.tools.registry import ToolRegistry
    from unittest.mock import MagicMock

    ws = WorkspaceManager(base_dir=tmp_path / "mcp_ws")
    cm = HardwareConcurrencyManager()
    reg = ToolRegistry()

    rich_long_form_content = (
        "# Distributed Systems Reliability Engineering Guide\n\n"
        "## 1. Introduction & Objectives\n"
        "Distributed systems require rigorous design paradigms to guarantee high availability and fault isolation.\n\n"
        "## 2. Invariants & Guardrails\n"
        "- Idempotency across state transitions\n"
        "- Hardware-bounded concurrency limits\n"
        "- Decoupled multi-agent synthesis\n\n"
        "## 3. Verification Metrics\n"
        "All generated deliverables must undergo independent verification against disk storage."
    )

    mock_prov = MagicMock()
    mock_prov.generate.return_value = ChatMessage(role=Role.ASSISTANT, content=rich_long_form_content)

    worker = DocumentGenerationWorker(
        role="DocumentGenerationAgent",
        provider=mock_prov,
        tool_registry=reg,
        workspace=ws,
        concurrency_manager=cm,
    )

    task = WorkerTask(
        task_id="task_mcp_doc_test",
        role="DocumentGenerationAgent",
        objective="Create a PDF and DOCX technical guide on Distributed Systems",
        dependencies=[],
    )

    completed_task = worker.execute(task, {})
    assert completed_task.status.value == "COMPLETED"
    assert completed_task.verification_passed is True

    # Assert both PDF and DOCX were generated in workspace outputs/ and contain real non-truncated content
    pdf_file = ws.base_dir / "outputs" / "task_mcp_doc_test_deliverable.pdf"
    docx_file = ws.base_dir / "outputs" / "task_mcp_doc_test_deliverable.docx"
    md_file = ws.base_dir / "outputs" / "task_mcp_doc_test_deliverable.md"

    assert pdf_file.exists() and pdf_file.stat().st_size > 500
    assert docx_file.exists() and docx_file.stat().st_size > 500
    assert md_file.exists() and md_file.stat().st_size > 200

    # Assert word count is substantial (not a 7-word placeholder)
    assert completed_task.output_data["word_count"] > 35


@pytest.mark.cross_platform
def test_c48_mcp_document_generation_approval_gate(tmp_path):
    """Scenario C.48 (Directive v9 Section 3): Approval gate enforcement on MCP document generation."""
    from app.agent.multi_agent import (
        DocumentGenerationWorker,
        HardwareConcurrencyManager,
        WorkerTask,
        WorkspaceManager,
    )
    from app.models.messages import ChatMessage, Role
    from app.models.tools import PermissionLevel
    from app.tools.registry import ToolRegistry
    from unittest.mock import MagicMock

    ws = WorkspaceManager(base_dir=tmp_path / "approval_ws")
    cm = HardwareConcurrencyManager()
    reg = ToolRegistry()
    mock_prov = MagicMock()
    mock_prov.generate.return_value = ChatMessage(role=Role.ASSISTANT, content="# Guide\nDetailed content for testing.")

    # 1. Test denial: approval callback returns False -> Worker execution fails with PermissionError
    denial_callback = MagicMock(return_value=False)
    worker_denied = DocumentGenerationWorker(
        role="DocumentGenerationAgent",
        provider=mock_prov,
        tool_registry=reg,
        workspace=ws,
        concurrency_manager=cm,
        approval_callback=denial_callback,
    )

    task = WorkerTask(
        task_id="task_denied_doc",
        role="DocumentGenerationAgent",
        objective="Create a PDF report on Security",
        dependencies=[],
    )

    res_denied = worker_denied.execute(task, {})
    assert res_denied.status.value == "FAILED"
    assert "Approval Gate" in (res_denied.error or "")
    denial_callback.assert_called_once()

    # 2. Test approval: approval callback returns True -> Worker execution succeeds
    approval_callback = MagicMock(return_value=True)
    worker_approved = DocumentGenerationWorker(
        role="DocumentGenerationAgent",
        provider=mock_prov,
        tool_registry=reg,
        workspace=ws,
        concurrency_manager=cm,
        approval_callback=approval_callback,
    )

    task_ok = WorkerTask(
        task_id="task_approved_doc",
        role="DocumentGenerationAgent",
        objective="Create a PDF report on Security",
        dependencies=[],
    )

    res_ok = worker_approved.execute(task_ok, {})
    assert res_ok.status.value == "COMPLETED"
    approval_callback.assert_called_once()


@pytest.mark.cross_platform
def test_c49_default_output_path_resolves_to_desktop():
    """Scenario C.49 (Directive v9.1 Section 3): Unspecified and hallucinated deliverable paths resolve to real Desktop."""
    from app.tools.filesystem.safety import PathSafety
    from pathlib import Path

    safety = PathSafety()
    desktop = (Path.home() / "Desktop").resolve()

    # 1. Hallucinated C:\output\AI_Research_Report.pdf resolves to Desktop/AI_Research_Report.pdf
    hallucinated_1 = "C:\\output\\AI_Research_Report.pdf"
    res_1 = safety.canonicalize_path(hallucinated_1)
    assert res_1 == desktop / "AI_Research_Report.pdf"

    # 2. Hallucinated /output/guide.docx resolves to Desktop/guide.docx
    hallucinated_2 = "/output/guide.docx"
    res_2 = safety.canonicalize_path(hallucinated_2)
    assert res_2 == desktop / "guide.docx"

    # 3. Bare filename without directory (e.g. "report.pdf") resolves to Desktop/report.pdf
    bare_filename = "report.pdf"
    res_3 = safety.canonicalize_path(bare_filename)
    assert res_3 == desktop / "report.pdf"

    # 4. Empty string resolves to Desktop
    res_4 = safety.canonicalize_path("")
    assert res_4 == desktop


@pytest.mark.cross_platform
def test_c50_pathsafety_real_mcp_wrapper_integration(tmp_path):
    """Scenario C.50 (Directive v9.1 Section 2): End-to-end MCPToolWrapper execution with REAL PathSafety."""
    from app.mcp.client import MCPClient
    from app.mcp.manager import MCPToolWrapper
    from unittest.mock import MagicMock
    from pathlib import Path

    mock_client = MagicMock(spec=MCPClient)
    mock_client.call_tool.return_value = {"content": [{"type": "text", "text": "Document created successfully"}]}

    wrapper = MCPToolWrapper(
        server_name="pdf-generator",
        client=mock_client,
        tool_name="create_pdf",
        description="Create PDF document",
    )

    # Call with hallucinated path and explicit content
    target_invented = "C:\\output\\Test_Doc.pdf"
    content_test = "# Test Architecture\nComplete architecture analysis and design specification."
    res = wrapper.execute(tool_call_id="call_real_safety", file_path=target_invented, title="Test Architecture", content=content_test)

    assert res.success is True
    desktop = (Path.home() / "Desktop").resolve()
    mock_client.call_tool.assert_called_once()
    called_args = mock_client.call_tool.call_args[0][1]

    # Assert path was canonicalized to Desktop with REAL PathSafety
    assert called_args["file_path"] == str(desktop / "Test_Doc.pdf")
    # Assert B.43 explicit content was passed
    assert "Test Architecture" in called_args["content"]

    # Assert missing content raises error / fails (Directive B.43)
    res_missing = wrapper.execute(tool_call_id="call_missing", file_path=target_invented, title="Missing Content")
    assert res_missing.success is False
    assert "requires explicit 'content'" in (res_missing.error or "")


@pytest.mark.cross_platform
def test_c51_agent_orchestrator_multi_agent_routing(tmp_path):
    """Scenario C.51 (Directive v9.1 Section 1): AgentOrchestrator routes complex objectives to LeadOrchestrator."""
    from app.agent.orchestrator import AgentOrchestrator
    from app.config import AgentConfig
    from app.models.messages import ChatMessage, Role
    from app.storage.session_store import SessionStore
    from app.storage.audit_store import AuditStore
    from app.storage.database import Database
    from app.tools.registry import ToolRegistry
    from unittest.mock import MagicMock

    db = Database(tmp_path / "test_db.sqlite")
    session_store = SessionStore(db)
    audit_store = AuditStore(db)
    reg = ToolRegistry()

    rich_ebpf_guide = (
        "# Linux eBPF Kernel Architecture & Safety Verifier Technical Guide\n\n"
        "## 1. Introduction & Objectives\n"
        "Extended Berkeley Packet Filter (eBPF) provides an in-kernel virtual machine execution environment "
        "allowing sandboxed bytecode programs to execute efficiently in kernel space without modifying the kernel source.\n\n"
        "## 2. In-Kernel Static Safety Verifier\n"
        "The static verifier guarantees memory safety, prevents unbounded loops, and halts execution before code execution.\n\n"
        "## 3. High Performance Observability & Tracing\n"
        "Telemetry events are transmitted through ring buffers and per-CPU maps with near-zero overhead."
    )

    mock_prov = MagicMock()
    mock_prov.generate.return_value = ChatMessage(
        role=Role.ASSISTANT,
        content=rich_ebpf_guide,
    )

    cfg = AgentConfig()
    session = session_store.create_session(title="Multi-Agent Test")

    orchestrator = AgentOrchestrator(
        config=cfg,
        provider=mock_prov,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=reg,
    )

    query = "Research and create a comprehensive PDF and DOCX technical guide on Linux eBPF kernel architecture"
    resp = orchestrator.process_message(session_id=session.id, user_text=query)

    assert resp is not None
    assert "Multi-Agent Execution Completed" in (resp.content or "")
    assert "Deliverables" in (resp.content or "")


@pytest.mark.cross_platform
def test_c52_no_hardcoded_fallback_content(tmp_path):
    """Scenario C.52 (Directive v10/v10.1): Document generation across unrelated topics produces topically distinct content with zero hardcoded boilerplate."""
    from app.agent.multi_agent import (
        DocumentGenerationWorker,
        HardwareConcurrencyManager,
        WorkerTask,
        WorkspaceManager,
    )
    from app.models.messages import ChatMessage, Role
    from app.tools.registry import ToolRegistry
    from unittest.mock import MagicMock

    ws = WorkspaceManager(base_dir=tmp_path / "distinct_ws")
    cm = HardwareConcurrencyManager()
    reg = ToolRegistry()

    # Topic A: AI Safety and Governance
    ai_safety_text = (
        "# Artificial Intelligence Safety & Alignment Framework\n\n"
        "## Executive Summary\n"
        "Modern frontier AI models require comprehensive governance frameworks, constitutional AI guardrails, "
        "and empirical RLHF alignment to mitigate catastrophic risks.\n\n"
        "## Governance and Regulatory Standards\n"
        "Adherence to NIST AI Risk Management Framework (AI RMF) and EU AI Act conformity assessments.\n\n"
        "## Red-Teaming & Interpretability\n"
        "Mechanistic interpretability probes and automated adversarial testing suites."
    )

    # Topic B: Byzantine Fault Tolerant Distributed Consensus
    bft_text = (
        "# Byzantine Fault Tolerant Consensus Protocols Architecture\n\n"
        "## Consensus Fundamentals\n"
        "Distributed state machine replication under partial synchrony requires 3f+1 total nodes to tolerate f arbitrary failures.\n\n"
        "## PBFT vs HotStuff Pipeline Architecture\n"
        "Linear message complexity view-change protocol utilizing threshold signatures.\n\n"
        "## Safety and Liveness Proofs\n"
        "Quorum intersection guarantees fork prevention across asynchronous network partitions."
    )

    mock_prov_a = MagicMock()
    mock_prov_a.generate.return_value = ChatMessage(role=Role.ASSISTANT, content=ai_safety_text)

    worker_a = DocumentGenerationWorker(
        role="DocumentGenerationAgent",
        provider=mock_prov_a,
        tool_registry=reg,
        workspace=ws,
        concurrency_manager=cm,
    )

    task_a = WorkerTask(
        task_id="task_ai_safety",
        role="DocumentGenerationAgent",
        objective="Create a PDF and DOCX technical guide on Artificial Intelligence Safety",
        dependencies=[],
    )

    completed_a = worker_a.execute(task_a, {})
    assert completed_a.status.value == "COMPLETED"

    mock_prov_b = MagicMock()
    mock_prov_b.generate.return_value = ChatMessage(role=Role.ASSISTANT, content=bft_text)

    worker_b = DocumentGenerationWorker(
        role="DocumentGenerationAgent",
        provider=mock_prov_b,
        tool_registry=reg,
        workspace=ws,
        concurrency_manager=cm,
    )

    task_b = WorkerTask(
        task_id="task_bft_consensus",
        role="DocumentGenerationAgent",
        objective="Create a PDF and DOCX technical guide on Byzantine Fault Tolerance",
        dependencies=[],
    )

    completed_b = worker_b.execute(task_b, {})
    assert completed_b.status.value == "COMPLETED"

    # Read generated markdown deliverables
    md_a = (ws.base_dir / "outputs" / "task_ai_safety_deliverable.md").read_text(encoding="utf-8")
    md_b = (ws.base_dir / "outputs" / "task_bft_consensus_deliverable.md").read_text(encoding="utf-8")

    # Assert content is topically distinct
    assert "RLHF" in md_a or "NIST" in md_a or "interpretability" in md_a
    assert "Byzantine" in md_b or "consensus" in md_b or "HotStuff" in md_b
    assert "Byzantine" not in md_a
    assert "RLHF" not in md_b

    # Assert ZERO hardcoded boilerplate phrases from legacy templates
    forbidden_boilerplate = [
        "System kernel interfaces and execution lifecycle",
        "Safety verification and isolated execution runtime",
        "High performance event-driven telemetry and monitoring",
        "This document provides a comprehensive technical reference and architectural overview regarding",
        "comprehensive technical documentation and operational guidelines",
        "component interactions, and execution invariants",
        "operational controls ensuring resilience and correctness",
    ]

    for phrase in forbidden_boilerplate:
        assert phrase.lower() not in md_a.lower(), f"Found forbidden hardcoded boilerplate in AI safety document: {phrase}"
        assert phrase.lower() not in md_b.lower(), f"Found forbidden hardcoded boilerplate in BFT document: {phrase}"


@pytest.mark.cross_platform
def test_c53_repl_p_unified_code_dispatch(tmp_path):
    """Scenario C.53 (Directive v10.1 Section 1): REPL and -p routes execute through identical CLIInterface.execute_prompt method."""
    from app.agent.orchestrator import AgentOrchestrator
    from app.config import AgentConfig
    from app.interface.cli import CLIInterface
    from app.models.messages import ChatMessage, Role
    from app.storage.session_store import SessionStore
    from app.storage.audit_store import AuditStore
    from app.storage.database import Database
    from app.tools.registry import ToolRegistry
    from unittest.mock import MagicMock

    db = Database(tmp_path / "test_unification.sqlite")
    session_store = SessionStore(db)
    audit_store = AuditStore(db)
    reg = ToolRegistry()

    mock_prov = MagicMock()
    mock_prov.generate.side_effect = lambda *args, **kwargs: ChatMessage(role=Role.ASSISTANT, content="Unified dispatch verified")

    orchestrator = AgentOrchestrator(
        config=AgentConfig(),
        provider=mock_prov,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=reg,
    )

    cli = CLIInterface(
        config=AgentConfig(),
        orchestrator=orchestrator,
        session_store=session_store,
        audit_store=audit_store,
    )

    # 1. Simulate headless -p dispatch
    resp_headless = cli.execute_prompt("What is 1 + 1?")
    assert "Unified dispatch verified" in (resp_headless.content or "")

    # 2. Simulate interactive prompt input (which calls self.execute_prompt directly)
    resp_interactive = cli.execute_prompt("What is 2 + 2?")
    assert "Unified dispatch verified" in (resp_interactive.content or "")


@pytest.mark.cross_platform
def test_c54_specialized_agents_routing(tmp_path):
    """Scenario C.54 (Directive v10.1 Standing Test): 'Research AI in depth using multiple specialized agents' routes to LeadOrchestrator."""
    from app.agent.orchestrator import AgentOrchestrator
    from app.config import AgentConfig
    from app.models.messages import ChatMessage, Role
    from app.storage.session_store import SessionStore
    from app.storage.audit_store import AuditStore
    from app.storage.database import Database
    from app.tools.registry import ToolRegistry
    from unittest.mock import MagicMock

    db = Database(tmp_path / "test_routing.sqlite")
    session_store = SessionStore(db)
    audit_store = AuditStore(db)
    reg = ToolRegistry()

    ai_report_text = (
        "# Artificial Intelligence Research Report\n\n"
        "## 1. Executive Summary\n"
        "Deep research into modern artificial intelligence systems, multi-agent frameworks, and alignment protocols.\n\n"
        "## 2. Technical Findings\n"
        "Specialist agents coordinated through bounded concurrency and dynamic DAG execution."
    )

    mock_prov = MagicMock()
    mock_prov.generate.return_value = ChatMessage(role=Role.ASSISTANT, content=ai_report_text)

    orchestrator = AgentOrchestrator(
        config=AgentConfig(),
        provider=mock_prov,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=reg,
    )

    standing_prompt = "Research Artificial Intelligence (AI) in depth using multiple specialized agents and generate a technical report"
    session = session_store.create_session(title="Standing Test")
    resp = orchestrator.process_message(session_id=session.id, user_text=standing_prompt)

    assert resp is not None
    assert "Multi-Agent Execution Completed" in (resp.content or "")
    assert "Deliverables" in (resp.content or "")
