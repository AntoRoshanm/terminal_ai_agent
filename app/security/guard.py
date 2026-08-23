"""
Cross-Platform Security Guard and Prompt Injection Defense (Windows, Linux, macOS)
"""

import os
import re
from typing import List, Optional, Tuple
from app.platform.detect import get_platform_info


class SecurityGuard:
    """Detects prompt-injections, malicious payloads, and unauthorized system access across Windows, Linux & macOS."""

    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts|rules)", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(system|safety|security)\s+(instructions|policies|rules)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"bypass\s+security\s+checks", re.IGNORECASE),
        re.compile(r"exfiltrate\s+(api\s+key|password|credential|secret)", re.IGNORECASE),
        re.compile(r"send\s+all\s+(passwords|tokens|keys)\s+to\s+http", re.IGNORECASE),
    ]

    DESTRUCTIVE_COMMANDS = [
        # Windows destructive patterns
        re.compile(r"format\s+[a-zA-Z]:", re.IGNORECASE),
        re.compile(r"del(ete)?\s+/[sfq]\s+c:\\windows", re.IGNORECASE),
        re.compile(r"rmdir\s+/[sq]\s+c:\\windows", re.IGNORECASE),
        re.compile(r"bcdedit\s+/delete", re.IGNORECASE),
        re.compile(r"diskpart\s+/s", re.IGNORECASE),
        # Linux & macOS destructive patterns
        re.compile(r"rm\s+-[rf]*\s+/(etc|boot|usr|bin|sbin|root|proc|sys|dev|System|Library)?\b", re.IGNORECASE),
        re.compile(r"mkfs(\.[a-z0-9]+)?\s+/dev/", re.IGNORECASE),
        re.compile(r"dd\s+if=.*of=/dev/(sd[a-z]|nvme[0-9]|vd[a-z]|disk[0-9])", re.IGNORECASE),
        re.compile(r"diskutil\s+erase(Disk|Volume)", re.IGNORECASE),
        re.compile(r"csrutil\s+disable", re.IGNORECASE),
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),  # Fork bomb
    ]

    @classmethod
    def get_protected_paths(cls) -> List[str]:
        """Return platform-specific protected root directories."""
        info = get_platform_info()
        if info.os_family == "windows":
            return [
                "C:\\Windows",
                "C:\\Windows\\System32",
                "C:\\Program Files",
                "C:\\Program Files (x86)",
            ]
        elif info.os_family == "macos":
            return [
                "/System",
                "/Library",
                "/usr",
                "/bin",
                "/sbin",
                "/private/etc",
                "/private/var",
                "/Applications",
            ]
        return [
            "/etc",
            "/boot",
            "/usr",
            "/bin",
            "/sbin",
            "/root",
            "/lib",
            "/proc",
            "/sys",
            "/dev",
        ]

    @classmethod
    def is_path_protected(cls, target_path: str) -> bool:
        """Check if a path is inside a protected system location."""
        norm_target = os.path.abspath(target_path).lower()
        for p in cls.get_protected_paths():
            norm_p = os.path.abspath(p).lower()
            if norm_target == norm_p or norm_target.startswith(norm_p + os.sep):
                return True
        return False

    @classmethod
    def analyze_input(cls, text: str) -> Tuple[bool, List[str]]:
        """
        Analyze text for prompt injection attempts or high-risk destructive commands.
        Returns (is_suspicious, reasons).
        """
        if not text:
            return False, []

        reasons: List[str] = []

        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(text):
                reasons.append(f"Prompt injection pattern detected: '{pattern.pattern}'")

        for pattern in cls.DESTRUCTIVE_COMMANDS:
            if pattern.search(text):
                reasons.append(f"Potentially destructive system command pattern detected: '{pattern.pattern}'")

        return len(reasons) > 0, reasons
