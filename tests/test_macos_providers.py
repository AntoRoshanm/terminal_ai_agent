"""
MOCKED unit tests for macOS concrete providers.
These run on any platform (Windows dev machine, Linux/macOS CI) using subprocess mocks.
They prove macOS parsing logic, data transformations, and TCC/SIP degradation contracts.
"""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch
import pytest
from app.models.state import PlatformInfo
from app.tools.software.env_config import ConfigureEnvironmentTool
from app.tools.system.macos.diagnostics_provider import MacOSDiagnosticsProvider
from app.tools.system.macos.gui_provider import MacOSGUIProvider
from app.tools.system.macos.hardware_provider import MacOSHardwareInfoProvider
from app.tools.system.macos.network_provider import MacOSNetworkInfoProvider
from app.tools.system.macos.os_provider import MacOSSystemInfoProvider
from app.tools.system.macos.process_provider import MacOSProcessProvider
from app.tools.system.macos.service_provider import MacOSServiceProvider
from app.tools.system.macos.software_provider import MacOSSoftwareProvider
from app.tools.system.macos.storage_provider import MacOSStorageInfoProvider


@pytest.mark.cross_platform
def test_macos_os_provider_mocked():
    """MOCKED: macOS OS and environment info parsing with ~/.zprofile."""
    mac_info = PlatformInfo(
        os_family="macos",
        os_name="macOS 15.1 (Sequoia)",
        os_version="15.1",
        architecture="arm64",
        is_apple_silicon=True,
        is_rosetta_translated=False,
        shell_default="zsh",
        package_managers=["brew"],
        display_server=None,
        sip_enabled=True,
        is_admin_or_root=True,
        is_wsl=False,
    )
    provider = MacOSSystemInfoProvider()
    sample_zprofile = 'export ANDROID_HOME="/opt/android"\nexport PATH="$PATH:/opt/homebrew/bin"\n'

    with patch("app.tools.system.macos.os_provider.get_platform_info", return_value=mac_info):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="{ sec = 1716380000, usec = 0 }\n")):
            info = provider.get_os_info()
            assert "Sequoia" in info["os_name"]
            assert info["is_apple_silicon"] is True
            assert info["sip_enabled"] is True
            assert info["system_root"] == "/"

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.is_file", return_value=True):
            with patch("builtins.open", mock_open(read_data=sample_zprofile)):
                env_info = provider.get_environment_info()
                assert "persisted_variables" in env_info
                assert env_info["persisted_variables"].get("ANDROID_HOME") == "/opt/android"


@pytest.mark.cross_platform
def test_macos_hardware_provider_mocked():
    """MOCKED: sysctl hw.memsize, cpu brand, and vm_stat page sizes."""
    mac_info = PlatformInfo(
        os_family="macos", os_name="macOS 15.1", os_version="15.1",
        architecture="arm64", is_apple_silicon=True, shell_default="zsh",
    )
    vm_stat_sample = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 200000.\nPages inactive: 150000.\n"

    provider = MacOSHardwareInfoProvider()
    with patch("app.tools.system.macos.hardware_provider.get_platform_info", return_value=mac_info):
        with patch("subprocess.run", side_effect=[
            MagicMock(returncode=0, stdout="Apple M3 Pro\n"),
            MagicMock(returncode=0, stdout="12\n"),
            MagicMock(returncode=0, stdout="11\n"),
            MagicMock(returncode=0, stdout="17179869184\n"),  # 16 GB
            MagicMock(returncode=0, stdout=vm_stat_sample),
            MagicMock(returncode=0, stdout="Chipset Model: Apple M3 Pro\n"),
        ]):
            hw = provider.get_hardware_info()
            assert hw["cpu"]["name"] == "Apple M3 Pro"
            assert hw["cpu"]["cores_logical"] == 12
            assert hw["ram"]["total_ram_gb"] == 16.0
            assert hw["ram"]["available_ram_gb"] > 0
            assert hw["gpus"][0]["name"] == "Apple M3 Pro"


@pytest.mark.cross_platform
def test_macos_storage_provider_mocked():
    """MOCKED: df -Pk with APFS volumes on macOS."""
    df_sample = (
        "Filesystem     1024-blocks      Used Available Capacity Mounted on\n"
        "/dev/disk3s1s1   488245288 120000000 368245288      25% /\n"
        "/dev/disk3s5     488245288  50000000 438245288      11% /System/Volumes/Data\n"
    )
    provider = MacOSStorageInfoProvider()
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=df_sample)):
        mounts = provider.get_storage_info()
        assert len(mounts) == 2
        assert mounts[0]["volume_name"] == "/"
        assert mounts[0]["file_system_type"] == "HFS+" or mounts[0]["file_system_type"] == "APFS"
        assert mounts[0]["total_space_gb"] > 400


@pytest.mark.cross_platform
def test_macos_network_provider_mocked():
    """MOCKED: ifconfig network interfaces and scutil DNS servers."""
    ifconfig_sample = (
        "lo0: flags=8049<UP,LOOPBACK,RUNNING> mtu 16384\n"
        "\tinet 127.0.0.1 netmask 0xff000000\n"
        "en0: flags=8863<UP,BROADCAST,SMART,RUNNING> mtu 1500\n"
        "\tether a1:b2:c3:d4:e5:f6\n"
        "\tinet 192.168.1.120 netmask 0xffffff00 broadcast 192.168.1.255\n"
    )
    provider = MacOSNetworkInfoProvider()
    with patch("subprocess.run", side_effect=[
        MagicMock(returncode=0, stdout=ifconfig_sample),
        MagicMock(returncode=0, stdout="gateway: 192.168.1.1\n"),
    ]):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="nameserver 1.1.1.1\nnameserver 8.8.8.8\n")):
                net = provider.get_network_info()
                assert net["adapter_count"] >= 1
                en0 = next((a for a in net["adapters"] if a["name"] == "en0"), None)
                assert en0 is not None
                assert en0["ipv4_address"] == "192.168.1.120"
                assert "1.1.1.1" in net["dns_servers"]


@pytest.mark.cross_platform
def test_macos_process_provider_mocked():
    """MOCKED: psutil process query and fallback on Darwin."""
    provider = MacOSProcessProvider()
    mock_psutil = MagicMock()
    mock_p = MagicMock()
    mock_p.info = {
        "pid": 1234,
        "name": "Safari",
        "memory_info": MagicMock(rss=419430400),
        "cpu_percent": 5.2,
        "cmdline": ["/Applications/Safari.app/Contents/MacOS/Safari"],
    }
    mock_psutil.process_iter.return_value = [mock_p]

    with patch.dict("sys.modules", {"psutil": mock_psutil}):
        procs = provider.get_process_info(query="Safari")
        assert len(procs) == 1
        assert procs[0]["name"] == "Safari"
        assert procs[0]["pid"] == 1234
        assert procs[0]["memory_mb"] == 400.0
        assert "cpu_time_s" in procs[0]


@pytest.mark.cross_platform
def test_macos_service_provider_mocked():
    """MOCKED: launchctl list and service management."""
    launchctl_sample = (
        "PID\tStatus\tLabel\n"
        "1234\t0\tcom.apple.Safari.History\n"
        "-\t0\tcom.apple.Spotlight\n"
    )
    provider = MacOSServiceProvider()
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=launchctl_sample)):
        services = provider.get_service_info()
        assert len(services) == 2
        assert services[0]["name"] == "com.apple.Safari.History"
        assert services[0]["status"] == "Running"
        assert services[1]["status"] == "Stopped"

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="")):
        res_start = provider.manage_service("com.apple.Spotlight", "start")
        assert res_start["success"] is True


@pytest.mark.cross_platform
def test_macos_software_provider_mocked(tmp_path: Path):
    """MOCKED: /Applications scan, Homebrew versions, and install command building."""
    provider = MacOSSoftwareProvider()

    # Mock Homebrew list
    with patch("shutil.which", return_value="/opt/homebrew/bin/brew"):
        with patch("subprocess.run", side_effect=[
            MagicMock(returncode=0, stdout="python@3.11 3.11.8\nnode 20.11.1\n"),
            MagicMock(returncode=0, stdout="Homebrew 4.2.10\n"),
            MagicMock(returncode=0, stdout="Homebrew 4.2.10\n"),
        ]):
            apps = provider.get_installed_software()
            assert any(a["name"] == "python@3.11" for a in apps)

            mgrs = provider.detect_managers()
            assert any(m["name"] == "brew" for m in mgrs)

            install_res = provider.install_package("htop", manager="brew")
            assert install_res["success"] is True
            assert "brew install htop" in install_res["command"]


@pytest.mark.cross_platform
def test_macos_software_disambiguation_brew_port_mocked():
    """MOCKED: Ambiguity gate when both Homebrew and MacPorts are detected."""
    provider = MacOSSoftwareProvider()
    with patch.object(provider, "detect_managers", return_value=[
        {"name": "brew", "display_name": "Homebrew"},
        {"name": "port", "display_name": "MacPorts"},
    ]):
        res = provider.install_package("ffmpeg")
        assert res["success"] is False
        assert res.get("needs_disambiguation") is True
        assert "brew" in res["available_managers"]
        assert "port" in res["available_managers"]


@pytest.mark.cross_platform
def test_macos_diagnostics_provider_mocked():
    """MOCKED: vm_stat memory, unified logging, and softwareupdate."""
    diag = MacOSDiagnosticsProvider()
    with patch("subprocess.run", side_effect=[
        MagicMock(returncode=0, stdout="17179869184\n"),  # 16 GB
        MagicMock(returncode=0, stdout="page size of 4096 bytes\nPages free: 1000000.\nPages inactive: 500000.\n"),
        MagicMock(returncode=0, stdout="{ 1.25 1.10 0.95 }\n"),
        MagicMock(returncode=0, stdout="COMM RSS %MEM\nlaunchd 10240 0.1\n"),
    ]):
        health = diag.get_system_health()
        assert health["status"] == "Healthy"
        assert health["ram"]["total_mb"] > 15000
        assert "top_memory_consumers" in health

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Software Update Tool\nFinding available software\n* macOS Sonoma 14.5\n")):
        with patch("shutil.which", return_value=None):
            updates = diag.check_updates()
            assert updates["pending_updates_count"] == 1
            assert "Sonoma 14.5" in updates["updates"][0]["Title"]


@pytest.mark.cross_platform
def test_macos_gui_provider_lifecycle_mocked():
    """MOCKED: AppleScript list_windows, focus_window, launch_app, and status."""
    provider = MacOSGUIProvider()

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Finder|100, Safari|200\n")):
        windows = provider.list_windows()
        assert len(windows) == 2
        assert windows[0]["title"] == "Finder"
        assert windows[1]["pid"] == 200

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="")):
        focus_res = provider.focus_window(title="Safari")
        assert focus_res["success"] is True

    with patch("subprocess.run", side_effect=[
        MagicMock(returncode=0, stdout=""),
        MagicMock(returncode=0, stdout="200\n"),
    ]):
        launch_res = provider.launch_app("Calculator")
        assert launch_res["success"] is True

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="")):
        close_res = provider.close_app(process_name="Calculator", force=True)
        assert close_res["success"] is True


@pytest.mark.cross_platform
def test_macos_gui_tcc_permission_denial_mocked():
    """MOCKED: AppleScript error -1743 triggers structured TCC degradation."""
    provider = MacOSGUIProvider()
    tcc_err = "execution error: Not authorized to send Apple events to System Events. (-1743)"

    with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr=tcc_err)):
        focus_res = provider.focus_window(title="Notes")
        assert focus_res["success"] is False
        assert "TCC" in focus_res["error"]

    with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr=tcc_err)):
        input_res = provider.send_input(text="Hello")
        assert input_res["success"] is False
        assert "TCC" in input_res["error"]

    with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="screencapture: not permitted\n")):
        scr_res = provider.capture_screenshot("/tmp/test.png")
        assert scr_res["success"] is False
        assert "TCC" in scr_res["error"] or "Screen Recording" in scr_res["error"]


@pytest.mark.cross_platform
def test_macos_env_config_tool_mocked():
    """MOCKED: ConfigureEnvironmentTool writes export to ~/.zprofile on macOS."""
    mac_info = PlatformInfo(
        os_family="macos", os_name="macOS 15.1", os_version="15.1",
        architecture="arm64", is_apple_silicon=True, shell_default="zsh",
    )
    tool = ConfigureEnvironmentTool()
    with patch("app.tools.software.env_config.get_platform_info", return_value=mac_info):
        with patch("builtins.open", mock_open(read_data="")) as m:
            res = tool._run(action="set_variable", variable_name="HOMEBREW_NO_ANALYTICS", value="1")
            assert res["action"] == "set_variable"
            assert res["status"] == "set"
            assert ".zprofile" in res["target_file"]
