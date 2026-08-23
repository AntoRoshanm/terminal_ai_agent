"""
REAL LINUX INTEGRATION TESTS — These call actual system binaries.
Gate: @pytest.mark.linux_only — skipped on non-Linux platforms.

Requirements for ubuntu-latest CI runner:
  apt-get install -y xvfb wmctrl xdotool x11-utils
  Xvfb :99 -screen 0 1920x1080x24 &
  export DISPLAY=:99

These tests produce genuine subprocess I/O from:
  systemctl, apt/dpkg, ip, df, /proc/meminfo, /proc/cpuinfo,
  /etc/os-release, wmctrl, xdotool.

DO NOT MOCK subprocess.run in this file.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ── gate ──────────────────────────────────────────────────────────────────────
pytestmark = [
    pytest.mark.linux_only,
    pytest.mark.skipif(not sys.platform.startswith("linux"), reason="linux_only: requires Linux OS"),
]

# ── imports after guard so Windows import paths don't fail ────────────────────
from app.tools.system.linux.diagnostics_provider import LinuxDiagnosticsProvider
from app.tools.system.linux.gui_provider import LinuxGUIProvider
from app.tools.system.linux.hardware_provider import LinuxHardwareInfoProvider
from app.tools.system.linux.network_provider import LinuxNetworkInfoProvider
from app.tools.system.linux.os_provider import LinuxSystemInfoProvider
from app.tools.system.linux.service_provider import LinuxServiceProvider
from app.tools.system.linux.software_provider import LinuxSoftwareProvider
from app.tools.system.linux.storage_provider import LinuxStorageInfoProvider


# ── helpers ───────────────────────────────────────────────────────────────────
def _bin(*names: str) -> bool:
    """Return True if at least one of the named binaries is on PATH."""
    return any(shutil.which(n) for n in names)


def _skip_no_bin(*names: str, reason: str = ""):
    missing = [n for n in names if not shutil.which(n)]
    if missing:
        pytest.skip(f"Binary not found: {missing}. {reason}")


# ═══════════════════════════════════════════════════════════════════════════════
# OS INFO — reads real /etc/os-release
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_os_info_real():
    """Real /etc/os-release parse on the CI runner (no mock)."""
    assert Path("/etc/os-release").exists(), "/etc/os-release must exist on Linux"
    provider = LinuxSystemInfoProvider()
    info = provider.get_os_info()
    assert info["os_name"], "os_name must be non-empty"
    assert info["system_root"] == "/"
    assert isinstance(info.get("uptime_seconds", 0), (int, float))


# ═══════════════════════════════════════════════════════════════════════════════
# ENV INFO — reads real ~/.bashrc and/or /etc/environment
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_env_info_persistence_real(tmp_path: Path):
    """Write a real export to a temp bashrc, then parse it with the real provider."""
    fake_bashrc = tmp_path / ".bashrc"
    fake_bashrc.write_text('export AGENT_TEST_VAR="hello_agent"\nexport AGENT_PATH_EXT="/opt/agent"\n')

    provider = LinuxSystemInfoProvider()
    # Temporarily redirect HOME so the provider reads our temp file
    old_home = os.environ.get("HOME", "")
    os.environ["HOME"] = str(tmp_path)
    try:
        env_info = provider.get_environment_info()
    finally:
        os.environ["HOME"] = old_home

    persisted = env_info.get("persisted_variables", {})
    assert persisted.get("AGENT_TEST_VAR") == "hello_agent", \
        f"Expected AGENT_TEST_VAR in persisted_variables. Got: {persisted}"
    assert persisted.get("AGENT_PATH_EXT") == "/opt/agent"


# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE — reads real /proc/meminfo, /proc/cpuinfo
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_hardware_info_real():
    """Real /proc/meminfo + /proc/cpuinfo parse."""
    assert Path("/proc/meminfo").exists()
    assert Path("/proc/cpuinfo").exists()
    provider = LinuxHardwareInfoProvider()
    hw = provider.get_hardware_info()
    assert hw["ram"]["total_ram_gb"] > 0.1
    assert hw["ram"]["available_ram_gb"] >= 0
    assert hw["cpu"]["name"], "CPU name must be non-empty"


# ═══════════════════════════════════════════════════════════════════════════════
# STORAGE — real `df -Pk`
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_storage_info_real():
    """Real df -Pk on the CI runner."""
    _skip_no_bin("df", reason="coreutils must be present")
    provider = LinuxStorageInfoProvider()
    mounts = provider.get_storage_info()
    assert len(mounts) >= 1
    root_mount = next((m for m in mounts if m["volume_name"] == "/"), None)
    assert root_mount is not None, "/ mount must be present"
    assert root_mount["total_space_gb"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK — real `ip addr` + /etc/resolv.conf
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_network_info_real():
    """Real ip-addr parse on the CI runner."""
    _skip_no_bin("ip", reason="iproute2 must be present")
    provider = LinuxNetworkInfoProvider()
    net = provider.get_network_info()
    assert net["adapter_count"] >= 1
    # lo (loopback) is always present on Linux
    names = [a["name"] for a in net["adapters"]]
    assert any(n in ("lo", "eth0", "ens3", "ens4", "enp0s3") for n in names), \
        f"Expected at least one known adapter name, got: {names}"


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICES — real `systemctl` list
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_service_info_real():
    """Real systemctl list-units on the CI runner."""
    _skip_no_bin("systemctl", reason="systemd must be present")
    provider = LinuxServiceProvider()
    services = provider.get_service_info()
    # CI runners may have very few services, just assert the call completed
    assert isinstance(services, list)
    if services:
        assert "name" in services[0]
        assert "status" in services[0]


# ═══════════════════════════════════════════════════════════════════════════════
# SOFTWARE — real dpkg-query or rpm -qa
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_installed_software_real():
    """Real dpkg-query (ubuntu) or rpm -qa (fedora) on the CI runner."""
    if not _bin("dpkg-query", "rpm", "pacman"):
        pytest.skip("No known package manager query tool available")
    provider = LinuxSoftwareProvider()
    apps = provider.get_installed_software()
    assert len(apps) >= 1, "At least one package must be installed"
    assert "name" in apps[0]
    assert "version" in apps[0]
    # Python must be installed on the CI runner
    python_pkg = next((a for a in apps if "python" in a["name"].lower()), None)
    assert python_pkg is not None, "Python must appear in installed packages"


# ═══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS — real apt list --upgradable (ubuntu)
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_diagnostics_check_updates_real():
    """Real apt list --upgradable on ubuntu-latest CI runner."""
    if not _bin("apt"):
        pytest.skip("apt not available — not an Ubuntu/Debian runner")
    diag = LinuxDiagnosticsProvider()
    result = diag.check_updates()
    # May be 0 updates on a freshly provisioned runner — that's fine.
    assert "pending_updates_count" in result
    assert isinstance(result["pending_updates_count"], int)
    assert isinstance(result["updates"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# WINDOW CONTROL — real wmctrl on Xvfb:99
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_wmctrl_list_real():
    """Real wmctrl -l on Xvfb:99 virtual display."""
    _skip_no_bin("wmctrl", reason="Install wmctrl: apt-get install -y wmctrl")
    display = os.environ.get("DISPLAY", "")
    if not display:
        pytest.skip("DISPLAY not set — Xvfb not running. CI job must start Xvfb first.")

    provider = LinuxGUIProvider()
    windows = provider.list_windows()
    # On a fresh Xvfb display there are typically 0 windows — just check no crash
    assert isinstance(windows, list)


def test_linux_wmctrl_focus_nonexistent_window_real():
    """Real wmctrl focus attempt on non-existent window returns structured failure."""
    _skip_no_bin("wmctrl", reason="Install wmctrl: apt-get install -y wmctrl")
    display = os.environ.get("DISPLAY", "")
    if not display:
        pytest.skip("DISPLAY not set — Xvfb not running.")

    provider = LinuxGUIProvider()
    res = provider.focus_window(title="__nonexistent_window_xyzzy__")
    # wmctrl returns non-zero for missing window — provider must handle gracefully
    assert "success" in res
    # False is expected (window doesn't exist), True would also be acceptable if wmctrl exits 0
    assert isinstance(res["success"], bool)


# ═══════════════════════════════════════════════════════════════════════════════
# GUI SEND INPUT — real xdotool on Xvfb:99
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_xdotool_type_real():
    """Real xdotool type on Xvfb:99 virtual display."""
    _skip_no_bin("xdotool", reason="Install xdotool: apt-get install -y xdotool")
    display = os.environ.get("DISPLAY", "")
    if not display:
        pytest.skip("DISPLAY not set — Xvfb not running.")

    provider = LinuxGUIProvider()
    # xdotool type doesn't need a focused window to exit 0 on Xvfb
    res = provider.send_input(text="AgentIntegrationTest")
    assert res["success"] is True, f"xdotool type failed: {res.get('error')}"
    assert res["input_sent"] is True


def test_linux_xdotool_mousemove_real():
    """Real xdotool mousemove on Xvfb:99 virtual display."""
    _skip_no_bin("xdotool", reason="Install xdotool: apt-get install -y xdotool")
    display = os.environ.get("DISPLAY", "")
    if not display:
        pytest.skip("DISPLAY not set — Xvfb not running.")

    provider = LinuxGUIProvider()
    res = provider.send_input(click_coords=(50, 50))
    assert res["success"] is True, f"xdotool mousemove failed: {res.get('error')}"


# ═══════════════════════════════════════════════════════════════════════════════
# APP LAUNCH — real xdg-open or process launch on Linux
# ═══════════════════════════════════════════════════════════════════════════════
def test_linux_app_launch_and_close_real():
    """Real app launch (sleep) and close via SIGTERM on Linux."""
    provider = LinuxGUIProvider()
    res_launch = provider.launch_app("sleep", args=["30"])
    assert res_launch["success"] is True, f"launch failed: {res_launch}"
    pid = res_launch.get("pid")
    assert pid, "pid must be returned after launch"

    # Immediately terminate it
    res_close = provider.close_app(pid=pid, force=True)
    assert res_close["success"] is True, f"close failed: {res_close}"

    # Confirm process is dead
    import time
    time.sleep(0.2)
    check = subprocess.run(["kill", "-0", str(pid)], capture_output=True)
    assert check.returncode != 0, f"Process {pid} is still alive after close"
