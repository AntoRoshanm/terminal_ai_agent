"""
Per-OS Capability Matrix and Degradation Explanations (Windows, Linux, macOS)
"""

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel
from app.models.state import PlatformInfo
from app.platform.detect import get_platform_info


class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    ABSENT = "ABSENT"


class CapabilityDetail(BaseModel):
    name: str
    status: CapabilityStatus
    reason: Optional[str] = None
    fallback: Optional[str] = None


def get_capability_matrix(platform_info: Optional[PlatformInfo] = None) -> Dict[str, CapabilityDetail]:
    """Evaluate full capability matrix for the detected or specified platform."""
    info = platform_info or get_platform_info()
    matrix: Dict[str, CapabilityDetail] = {}

    # 1. Core OS & System inspection (Always available across all OSes)
    matrix["system_inspection"] = CapabilityDetail(
        name="system_inspection",
        status=CapabilityStatus.AVAILABLE,
    )
    matrix["hardware_inspection"] = CapabilityDetail(
        name="hardware_inspection",
        status=CapabilityStatus.AVAILABLE,
    )
    matrix["storage_inspection"] = CapabilityDetail(
        name="storage_inspection",
        status=CapabilityStatus.AVAILABLE,
    )
    matrix["network_inspection"] = CapabilityDetail(
        name="network_inspection",
        status=CapabilityStatus.AVAILABLE,
    )
    matrix["filesystem_operations"] = CapabilityDetail(
        name="filesystem_operations",
        status=CapabilityStatus.AVAILABLE,
        reason="System Integrity Protection (SIP) protects /System and root binaries on macOS" if info.os_family == "macos" and info.sip_enabled else None,
    )
    matrix["terminal_execution"] = CapabilityDetail(
        name="terminal_execution",
        status=CapabilityStatus.AVAILABLE,
    )
    matrix["package_management"] = CapabilityDetail(
        name="package_management",
        status=CapabilityStatus.AVAILABLE if info.package_managers else CapabilityStatus.DEGRADED,
        reason=None if info.package_managers else "No standard package manager found in PATH",
    )

    # 2. Services
    if info.os_family == "windows":
        matrix["service_management"] = CapabilityDetail(
            name="service_management",
            status=CapabilityStatus.AVAILABLE,
        )
    elif info.os_family == "macos":
        matrix["service_management"] = CapabilityDetail(
            name="service_management",
            status=CapabilityStatus.AVAILABLE,
            reason="Managed via launchctl and LaunchDaemons/LaunchAgents plists.",
        )
    else:
        # Linux: check systemd / init
        matrix["service_management"] = CapabilityDetail(
            name="service_management",
            status=CapabilityStatus.AVAILABLE if not info.is_wsl else CapabilityStatus.DEGRADED,
            reason="WSL instances without systemd enabled may have degraded service management" if info.is_wsl else None,
        )

    # 3. GUI, Window Management & Screen Capture
    if info.os_family == "windows":
        matrix["gui_screen_capture"] = CapabilityDetail(
            name="gui_screen_capture",
            status=CapabilityStatus.AVAILABLE,
        )
        matrix["gui_input_simulation"] = CapabilityDetail(
            name="gui_input_simulation",
            status=CapabilityStatus.AVAILABLE,
        )
        matrix["window_management"] = CapabilityDetail(
            name="window_management",
            status=CapabilityStatus.AVAILABLE,
        )
    elif info.os_family == "macos":
        matrix["gui_screen_capture"] = CapabilityDetail(
            name="gui_screen_capture",
            status=CapabilityStatus.DEGRADED,
            reason="Capability degraded: Requires macOS Screen Recording TCC permission (System Settings → Privacy & Security → Screen Recording). In headless CI runners, TCC permission cannot be granted non-interactively.",
            fallback="Use terminal/process tools or execute screencapture CLI when permission is granted interactively.",
        )
        matrix["gui_input_simulation"] = CapabilityDetail(
            name="gui_input_simulation",
            status=CapabilityStatus.DEGRADED,
            reason="Capability degraded: Requires macOS Accessibility TCC permission (System Settings → Privacy & Security → Accessibility). In headless CI runners, TCC permission cannot be granted non-interactively.",
            fallback="Use terminal CLI tools directly.",
        )
        matrix["window_management"] = CapabilityDetail(
            name="window_management",
            status=CapabilityStatus.AVAILABLE,
            reason="Managed via AppleScript / System Events (requires Accessibility permission; degrades gracefully if denied with AppleScript error -1743).",
        )
    else:
        # Linux
        if info.display_server == "wayland":
            matrix["gui_screen_capture"] = CapabilityDetail(
                name="gui_screen_capture",
                status=CapabilityStatus.DEGRADED,
                reason="Wayland security model restricts direct screen reading; requires xdg-desktop-portal or grim.",
                fallback="Use terminal/process tools or grim/slurp if installed.",
            )
            matrix["gui_input_simulation"] = CapabilityDetail(
                name="gui_input_simulation",
                status=CapabilityStatus.DEGRADED,
                reason="Wayland security model restricts synthetic input injection (uinput or ydotool required).",
                fallback="Use terminal CLI tools directly.",
            )
            matrix["window_management"] = CapabilityDetail(
                name="window_management",
                status=CapabilityStatus.DEGRADED,
                reason="Wayland compositor does not expose global window handles via X11 wmctrl protocol.",
                fallback="Inspect active processes via get_process_info.",
            )
        elif info.display_server == "x11":
            matrix["gui_screen_capture"] = CapabilityDetail(
                name="gui_screen_capture",
                status=CapabilityStatus.AVAILABLE,
            )
            matrix["gui_input_simulation"] = CapabilityDetail(
                name="gui_input_simulation",
                status=CapabilityStatus.AVAILABLE,
            )
            matrix["window_management"] = CapabilityDetail(
                name="window_management",
                status=CapabilityStatus.AVAILABLE,
            )
        else:
            matrix["gui_screen_capture"] = CapabilityDetail(
                name="gui_screen_capture",
                status=CapabilityStatus.ABSENT,
                reason="Headless Linux environment with no display server.",
            )
            matrix["gui_input_simulation"] = CapabilityDetail(
                name="gui_input_simulation",
                status=CapabilityStatus.ABSENT,
                reason="Headless Linux environment with no display server.",
            )
            matrix["window_management"] = CapabilityDetail(
                name="window_management",
                status=CapabilityStatus.ABSENT,
                reason="Headless Linux environment with no display server.",
            )

    return matrix
