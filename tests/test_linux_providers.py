"""
MOCKED unit tests for Linux concrete providers.
These run on any platform (Windows dev machine, CI) using subprocess.run mocks.
They prove the parsing logic, NOT real OS integration.
These tests must NOT be cited as integration proof for real Linux execution.
"""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch
import pytest
from app.models.state import PlatformInfo
from app.tools.software.env_config import ConfigureEnvironmentTool
from app.tools.system.linux.diagnostics_provider import LinuxDiagnosticsProvider
from app.tools.system.linux.gui_provider import LinuxGUIProvider
from app.tools.system.linux.hardware_provider import LinuxHardwareInfoProvider
from app.tools.system.linux.network_provider import LinuxNetworkInfoProvider
from app.tools.system.linux.os_provider import LinuxSystemInfoProvider
from app.tools.system.linux.service_provider import LinuxServiceProvider
from app.tools.system.linux.software_provider import LinuxSoftwareProvider
from app.tools.system.linux.storage_provider import LinuxStorageInfoProvider


@pytest.mark.cross_platform
def test_linux_os_provider_mocked():
    """MOCKED: Parses /etc/os-release and ~/.bashrc for env persistence."""
    sample_os_release = 'PRETTY_NAME="Ubuntu 24.04 LTS"\nVERSION_ID="24.04"\n'
    sample_bashrc = 'export JAVA_HOME="/usr/lib/jvm/default"\nexport PATH="$PATH:/opt/bin"\n'
    provider = LinuxSystemInfoProvider()

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=[
            mock_open(read_data=sample_os_release).return_value,
            mock_open(read_data=sample_bashrc).return_value,
        ]):
            info = provider.get_os_info()
            assert info["os_name"] == "Ubuntu 24.04 LTS"
            assert info["system_root"] == "/"

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.is_file", return_value=True):
            with patch("builtins.open", mock_open(read_data=sample_bashrc)):
                env_info = provider.get_environment_info()
                assert "persisted_variables" in env_info
                assert env_info["persisted_variables"].get("JAVA_HOME") == "/usr/lib/jvm/default"


@pytest.mark.cross_platform
def test_linux_hardware_provider_mocked():
    meminfo_sample = "MemTotal:       16384000 kB\nMemAvailable:    8192000 kB\n"
    cpuinfo_sample = "model name      : AMD Ryzen 7 6800H\ncpu MHz         : 3200.000\n"
    provider = LinuxHardwareInfoProvider()
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=[
            mock_open(read_data=meminfo_sample).return_value,
            mock_open(read_data=cpuinfo_sample).return_value,
        ]):
            hw = provider.get_hardware_info()
            assert hw["ram"]["total_ram_gb"] > 15
            assert hw["cpu"]["name"] == "AMD Ryzen 7 6800H"


@pytest.mark.cross_platform
def test_linux_storage_provider_mocked():
    df_sample = (
        "Filesystem     1024-blocks      Used Available Capacity Mounted on\n"
        "/dev/sda1        104857600  41943040  57610240      43% /\n"
    )
    provider = LinuxStorageInfoProvider()
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=df_sample)):
        mounts = provider.get_storage_info()
        assert len(mounts) == 1
        assert mounts[0]["volume_name"] == "/"
        assert mounts[0]["total_space_gb"] == 100.0


@pytest.mark.cross_platform
def test_linux_network_provider_mocked():
    resolv_sample = "nameserver 1.1.1.1\nnameserver 8.8.8.8\n"
    ip_addr_sample = "2: eth0    inet 192.168.1.50/24 brd 192.168.1.255 scope global eth0\n"
    provider = LinuxNetworkInfoProvider()
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=resolv_sample)):
            with patch("subprocess.run", side_effect=[
                MagicMock(returncode=0, stdout="default via 192.168.1.1 dev eth0\n"),
                MagicMock(returncode=0, stdout=ip_addr_sample),
            ]):
                net = provider.get_network_info()
                assert net["adapter_count"] == 1
                assert net["adapters"][0]["ipv4_address"] == "192.168.1.50"


@pytest.mark.cross_platform
def test_linux_service_provider_mocked():
    systemctl_sample = "nginx.service loaded active running Nginx HTTP Server\nssh.service loaded active running OpenSSH Daemon\n"
    provider = LinuxServiceProvider()
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=systemctl_sample)):
        services = provider.get_service_info()
        assert len(services) == 2
        assert services[0]["name"] == "nginx.service"
        assert "active" in services[0]["status"]


@pytest.mark.cross_platform
def test_linux_software_provider_mocked():
    dpkg_sample = "python3\t3.12.3-0ubuntu1\tUbuntu Developers\ngit\t1:2.43.0-1ubuntu7\tUbuntu Developers\n"
    provider = LinuxSoftwareProvider()
    with patch("shutil.which", return_value="/usr/bin/dpkg-query"):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=dpkg_sample)):
            apps = provider.get_installed_software()
            assert len(apps) == 2
            assert apps[0]["name"] in ("python3", "git")


@pytest.mark.cross_platform
def test_linux_diagnostics_check_updates_mocked():
    """MOCKED: Parses apt list --upgradable output without calling real apt."""
    diag = LinuxDiagnosticsProvider()
    apt_sample = "Listing...\npython3-pip/noble-updates 24.0+dfsg-1ubuntu1 all [upgradable from: 24.0+dfsg-1]\n"
    with patch("shutil.which", return_value="/usr/bin/apt"):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=apt_sample)):
            updates = diag.check_updates()
            assert updates["pending_updates_count"] == 1
            assert "python3-pip" in updates["updates"][0]["Title"]


@pytest.mark.cross_platform
def test_linux_configure_environment_tool_mocked():
    """MOCKED: ConfigureEnvironmentTool writes export to ~/.bashrc on Linux."""
    linux_info = PlatformInfo(os_family="linux", os_name="Ubuntu", os_version="24.04", architecture="x86_64", shell_default="bash")
    tool = ConfigureEnvironmentTool()
    with patch("app.tools.software.env_config.get_platform_info", return_value=linux_info):
        with patch("builtins.open", mock_open(read_data="")) as m:
            res = tool._run(action="set_variable", variable_name="TEST_VAR", value="123")
            assert res["action"] == "set_variable"
            assert res["status"] == "set"
            assert ".bashrc" in res["target_file"]


@pytest.mark.cross_platform
def test_linux_window_control_lifecycle_mocked():
    """MOCKED: app_focus/app_launch/app_close on Linux X11 (wmctrl/Popen mocked)."""
    x11_info = PlatformInfo(
        os_family="linux", os_name="Ubuntu", os_version="24.04",
        architecture="x86_64", shell_default="bash", display_server="x11",
    )
    provider = LinuxGUIProvider()
    with patch("app.tools.system.linux.gui_provider.get_platform_info", return_value=x11_info):
        with patch("shutil.which", return_value="/usr/bin/wmctrl"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="")):
                res_focus = provider.focus_window(title="gedit")
                assert res_focus["success"] is True

        with patch("subprocess.Popen", return_value=MagicMock(pid=1234)):
            res_launch = provider.launch_app("gedit")
            assert res_launch["success"] is True
            assert res_launch["pid"] == 1234

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            res_close = provider.close_app(pid=1234, force=True)
            assert res_close["success"] is True


@pytest.mark.cross_platform
def test_linux_gui_send_input_x11_mocked():
    """MOCKED: gui_send_input on Linux X11 via xdotool (mocked)."""
    x11_info = PlatformInfo(
        os_family="linux", os_name="Ubuntu", os_version="24.04",
        architecture="x86_64", shell_default="bash", display_server="x11",
    )
    provider = LinuxGUIProvider()
    with patch("app.tools.system.linux.gui_provider.get_platform_info", return_value=x11_info):
        with patch("shutil.which", return_value="/usr/bin/xdotool"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                res = provider.send_input(text="Hello Linux", click_coords=(100, 200))
                assert res["success"] is True
                assert res["input_sent"] is True


@pytest.mark.cross_platform
def test_linux_gui_wayland_explicit_degradation():
    """MOCKED: Wayland compositor policy degradation returns explicit error (no real Wayland needed)."""
    wayland_info = PlatformInfo(
        os_family="linux", os_name="Fedora", os_version="40",
        architecture="x86_64", shell_default="bash", display_server="wayland",
    )
    provider = LinuxGUIProvider()
    with patch("app.tools.system.linux.gui_provider.get_platform_info", return_value=wayland_info):
        res = provider.focus_window(title="Firefox")
        assert res["success"] is False
        assert "Wayland" in res["error"]

        with patch("shutil.which", return_value=None):
            scr_res = provider.capture_screenshot("/tmp/test.png")
            assert scr_res["success"] is False
            assert "Wayland" in scr_res["error"]

        inp_res = provider.send_input(text="hello")
        assert inp_res["success"] is False
        assert "Wayland" in inp_res["error"]
