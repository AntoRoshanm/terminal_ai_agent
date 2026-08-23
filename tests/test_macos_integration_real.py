"""
REAL macOS INTEGRATION TESTS — These call actual Darwin system binaries.
Gate: @pytest.mark.macos_only — skipped on non-macOS platforms.

These tests execute real subprocess I/O against:
  sw_vers, sysctl, df -Pk, ifconfig, launchctl, ps, vm_stat, screencapture.

DO NOT MOCK subprocess.run in this file.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

# ── gate ──────────────────────────────────────────────────────────────────────
pytestmark = [
    pytest.mark.macos_only,
    pytest.mark.skipif(sys.platform != "darwin", reason="macos_only: requires macOS (Darwin)"),
]

# ── imports ───────────────────────────────────────────────────────────────────
from app.tools.system.macos.diagnostics_provider import MacOSDiagnosticsProvider
from app.tools.system.macos.gui_provider import MacOSGUIProvider
from app.tools.system.macos.hardware_provider import MacOSHardwareInfoProvider
from app.tools.system.macos.network_provider import MacOSNetworkInfoProvider
from app.tools.system.macos.os_provider import MacOSSystemInfoProvider
from app.tools.system.macos.process_provider import MacOSProcessProvider
from app.tools.system.macos.service_provider import MacOSServiceProvider
from app.tools.system.macos.software_provider import MacOSSoftwareProvider
from app.tools.system.macos.storage_provider import MacOSStorageInfoProvider


def test_macos_os_info_real():
    """Real sw_vers and uname on macOS CI runner."""
    provider = MacOSSystemInfoProvider()
    info = provider.get_os_info()
    assert info["os_name"]
    assert info["system_root"] == "/"
    assert isinstance(info.get("uptime_seconds", 0.0), (int, float))


def test_macos_env_info_persistence_real(tmp_path: Path):
    """Write real export to a temp .zprofile and verify parsing with real provider."""
    fake_zprofile = tmp_path / ".zprofile"
    fake_zprofile.write_text('export MACOS_AGENT_TEST="valid_val"\nexport MACOS_PATH_EXT="/opt/bin"\n')

    provider = MacOSSystemInfoProvider()
    old_home = os.environ.get("HOME", "")
    os.environ["HOME"] = str(tmp_path)
    try:
        env_info = provider.get_environment_info()
    finally:
        os.environ["HOME"] = old_home

    persisted = env_info.get("persisted_variables", {})
    assert persisted.get("MACOS_AGENT_TEST") == "valid_val"
    assert persisted.get("MACOS_PATH_EXT") == "/opt/bin"


def test_macos_hardware_info_real():
    """Real sysctl hw.memsize + hw.ncpu on macOS runner."""
    provider = MacOSHardwareInfoProvider()
    hw = provider.get_hardware_info()
    assert hw["ram"]["total_ram_gb"] > 0.5
    assert hw["cpu"]["cores_logical"] >= 1
    assert hw["cpu"]["name"]


def test_macos_storage_info_real():
    """Real df -Pk on macOS runner."""
    provider = MacOSStorageInfoProvider()
    mounts = provider.get_storage_info()
    assert len(mounts) >= 1
    root_mount = next((m for m in mounts if m["volume_name"] == "/"), None)
    assert root_mount is not None, "Root mount / must exist"
    assert root_mount["total_space_gb"] > 0


def test_macos_network_info_real():
    """Real ifconfig and scutil DNS on macOS runner."""
    provider = MacOSNetworkInfoProvider()
    net = provider.get_network_info()
    assert net["adapter_count"] >= 1
    names = [a["name"] for a in net["adapters"]]
    assert any(n in ("lo0", "en0", "en1") for n in names)


def test_macos_process_info_real():
    """Real ps -eo pid,ppid on macOS runner."""
    provider = MacOSProcessProvider()
    procs = provider.get_process_info(limit=10)
    assert len(procs) >= 1
    assert "pid" in procs[0]
    assert "name" in procs[0]


def test_macos_service_info_real():
    """Real launchctl list on macOS runner."""
    provider = MacOSServiceProvider()
    services = provider.get_service_info(limit=10)
    assert isinstance(services, list)
    if services:
        assert "name" in services[0]
        assert "status" in services[0]


def test_macos_installed_software_real():
    """Real /Applications scan or Homebrew query on macOS runner."""
    provider = MacOSSoftwareProvider()
    apps = provider.get_installed_software(limit=20)
    assert isinstance(apps, list)


def test_macos_diagnostics_health_real():
    """Real vm_stat and ps on macOS runner."""
    diag = MacOSDiagnosticsProvider()
    health = diag.get_system_health()
    assert "ram" in health
    assert "status" in health
    assert health["ram"]["total_mb"] > 0


def test_macos_app_launch_and_close_real():
    """Real process launch (sleep 30) and close on macOS runner."""
    provider = MacOSGUIProvider()
    launch_res = provider.launch_app("sleep", args=["30"])
    if launch_res.get("success") and launch_res.get("pid"):
        pid = launch_res["pid"]
        close_res = provider.close_app(pid=pid, force=True)
        assert close_res["success"] is True


def test_macos_gui_screencapture_tcc_degradation_real(tmp_path: Path):
    """Real screencapture call under headless CI asserts structured degradation or success."""
    provider = MacOSGUIProvider()
    out = str(tmp_path / "ci_screen.png")
    res = provider.capture_screenshot(out)
    assert isinstance(res.get("success"), bool)
    if not res["success"]:
        assert "Capability degraded" in res.get("error", "") or "TCC" in res.get("error", "")
