"""
Tests for Platform Detection Layer and Capability Matrix across Windows, Linux, and macOS (Part A.1 & A.7)
"""

import os
import subprocess
from unittest.mock import MagicMock, mock_open, patch
import pytest
from app.models.state import PlatformInfo
from app.platform.capabilities import CapabilityStatus, get_capability_matrix
from app.platform.detect import (
    detect_apple_silicon,
    detect_display_server,
    detect_linux_distro,
    detect_macos_version,
    detect_package_managers,
    detect_platform,
    detect_rosetta_translated,
    detect_sip_status,
    get_platform_info,
    is_admin_or_root,
    is_wsl,
    reset_platform_cache,
)


def test_platform_info_cached():
    reset_platform_cache()
    info1 = get_platform_info()
    info2 = get_platform_info()
    assert info1 is info2
    assert info1.os_family in ("windows", "linux", "macos")
    assert info1.architecture != ""


def test_detect_package_managers():
    mgrs_win = detect_package_managers("windows")
    assert isinstance(mgrs_win, list)

    mgrs_linux = detect_package_managers("linux")
    assert isinstance(mgrs_linux, list)

    mgrs_mac = detect_package_managers("macos")
    assert isinstance(mgrs_mac, list)


def test_detect_linux_distro_parsing():
    sample_os_release = """
NAME="Ubuntu"
VERSION="24.04 LTS (Noble Numbat)"
ID=ubuntu
VERSION_ID="24.04"
PRETTY_NAME="Ubuntu 24.04 LTS"
"""
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=sample_os_release)):
            name, ver = detect_linux_distro()
            assert name == "Ubuntu 24.04 LTS"
            assert ver == "24.04"


def test_detect_macos_version_and_marketing_names():
    with patch("platform.mac_ver", return_value=("15.1", ("", "", ""), "arm64")):
        with patch("subprocess.run", side_effect=[
            MagicMock(returncode=0, stdout="macOS\n"),
            MagicMock(returncode=0, stdout="15.1\n"),
        ]):
            name, ver = detect_macos_version()
            assert "Sequoia" in name
            assert ver == "15.1"

    with patch("platform.mac_ver", return_value=("14.5", ("", "", ""), "arm64")):
        with patch("subprocess.run", side_effect=[
            MagicMock(returncode=0, stdout="macOS\n"),
            MagicMock(returncode=0, stdout="14.5\n"),
        ]):
            name, ver = detect_macos_version()
            assert "Sonoma" in name
            assert ver == "14.5"


def test_detect_apple_silicon_and_rosetta():
    with patch("sys.platform", "darwin"):
        with patch("platform.machine", return_value="arm64"):
            assert detect_apple_silicon() is True

        with patch("platform.machine", return_value="x86_64"):
            assert detect_apple_silicon() is False

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="1\n")):
            assert detect_rosetta_translated() is True

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="0\n")):
            assert detect_rosetta_translated() is False


def test_detect_sip_status():
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="System Integrity Protection status: enabled.\n")):
            assert detect_sip_status() is True

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="System Integrity Protection status: disabled.\n")):
            assert detect_sip_status() is False


def test_is_wsl_detection():
    with patch("sys.platform", "linux"):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="Linux version 5.15.153.1-microsoft-standard-WSL2")):
                assert is_wsl() is True

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="Linux version 6.8.0-generic")):
                assert is_wsl() is False


def test_detect_display_server():
    with patch("sys.platform", "linux"):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}, clear=True):
            assert detect_display_server() == "wayland"

        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}, clear=True):
            assert detect_display_server() == "x11"

        with patch.dict(os.environ, {}, clear=True):
            assert detect_display_server() == "none"

    with patch("sys.platform", "darwin"):
        assert detect_display_server() is None


def test_capability_matrix_wayland_degradation():
    wayland_platform = PlatformInfo(
        os_family="linux",
        os_name="Ubuntu 24.04",
        os_version="24.04",
        architecture="x86_64",
        shell_default="bash",
        package_managers=["apt"],
        display_server="wayland",
        is_admin_or_root=False,
        is_wsl=False,
    )
    matrix = get_capability_matrix(wayland_platform)
    assert matrix["system_inspection"].status == CapabilityStatus.AVAILABLE
    assert matrix["gui_screen_capture"].status == CapabilityStatus.DEGRADED
    assert "Wayland" in matrix["gui_screen_capture"].reason
    assert matrix["window_management"].status == CapabilityStatus.DEGRADED


def test_capability_matrix_windows():
    win_platform = PlatformInfo(
        os_family="windows",
        os_name="Windows 11",
        os_version="10.0.26200",
        architecture="AMD64",
        shell_default="powershell",
        package_managers=["winget", "pip"],
        display_server=None,
        is_admin_or_root=True,
        is_wsl=False,
    )
    matrix = get_capability_matrix(win_platform)
    assert matrix["system_inspection"].status == CapabilityStatus.AVAILABLE
    assert matrix["gui_screen_capture"].status == CapabilityStatus.AVAILABLE
    assert matrix["service_management"].status == CapabilityStatus.AVAILABLE


def test_capability_matrix_macos():
    mac_platform = PlatformInfo(
        os_family="macos",
        os_name="macOS 15.1 (Sequoia)",
        os_version="15.1",
        architecture="arm64",
        is_apple_silicon=True,
        is_rosetta_translated=False,
        shell_default="zsh",
        package_managers=["brew", "pip"],
        display_server=None,
        sip_enabled=True,
        is_admin_or_root=False,
        is_wsl=False,
    )
    matrix = get_capability_matrix(mac_platform)
    assert matrix["system_inspection"].status == CapabilityStatus.AVAILABLE
    assert matrix["service_management"].status == CapabilityStatus.AVAILABLE
    assert matrix["gui_screen_capture"].status == CapabilityStatus.DEGRADED
    assert "TCC" in matrix["gui_screen_capture"].reason or "Screen Recording" in matrix["gui_screen_capture"].reason
    assert matrix["gui_input_simulation"].status == CapabilityStatus.DEGRADED
    assert "TCC" in matrix["gui_input_simulation"].reason or "Accessibility" in matrix["gui_input_simulation"].reason
    assert matrix["window_management"].status == CapabilityStatus.AVAILABLE
