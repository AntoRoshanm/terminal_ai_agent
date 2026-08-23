"""
Command Risk Classification and Security Policy Engine
"""

import re
from typing import List, Optional
from app.models.tools import PermissionLevel


class CommandPolicyEngine:
    """Classifies commands into Permission Levels and enforces protected path rules."""

    LEVEL_3_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b(format|diskpart|bcdedit|vssadmin)\b", re.IGNORECASE),
        re.compile(r"\breg\s+delete\b", re.IGNORECASE),
        re.compile(r"\b(del|erase)\b.*(/s|/q).*[c-zC-Z]:\\", re.IGNORECASE),
        re.compile(r"\b(rmdir|rd)\b.*(/s|/q).*[c-zC-Z]:\\", re.IGNORECASE),
        re.compile(r"\bRemove-Item\b.*(-Recurse|-Force).*[c-zC-Z]:\\", re.IGNORECASE),
        re.compile(r"\b(takeown|icacls)\b.*(/grant|/deny|/setowner)", re.IGNORECASE),
        re.compile(r"[c-zC-Z]:\\windows\\system32", re.IGNORECASE),
    ]

    LEVEL_2_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b(winget|choco|scoop)\s+(install|uninstall|upgrade)\b", re.IGNORECASE),
        re.compile(r"\b(npm|yarn|pnpm)\s+install\s+(-g|--global)\b", re.IGNORECASE),
        re.compile(r"\b(Stop-Process|taskkill|kill)\b", re.IGNORECASE),
        re.compile(r"\b(sc|sc\.exe)\s+(stop|start|delete|create|config)\b", re.IGNORECASE),
        re.compile(r"\b(netsh|Set-NetIPAddress|Set-DnsClientServerAddress)\b", re.IGNORECASE),
        re.compile(r"\b(shutdown|Restart-Computer|Stop-Computer)\b", re.IGNORECASE),
        re.compile(r"\b(Set-ItemProperty|New-ItemProperty|Remove-ItemProperty)\b.*(HKLM|HKCU)", re.IGNORECASE),
        re.compile(r"\b(Remove-Item|rm|del|rmdir)\b", re.IGNORECASE),
    ]

    LEVEL_0_PATTERNS: List[re.Pattern] = [
        re.compile(r"^\s*(dir|ls|Get-ChildItem|gci)\b", re.IGNORECASE),
        re.compile(r"^\s*(echo|Write-Host|Write-Output)\b", re.IGNORECASE),
        re.compile(r"^\s*(type|cat|Get-Content|gc)\b", re.IGNORECASE),
        re.compile(r"^\s*git\s+(status|log|diff|show|branch|remote)\b", re.IGNORECASE),
        re.compile(r"^\s*(python|python3|node|npm|cargo|go|rustc|git|docker)\s+(--version|-v|-V|version)\s*$", re.IGNORECASE),
        re.compile(r"^\s*(where|where\.exe|which|Get-Command)\b", re.IGNORECASE),
        re.compile(r"^\s*(Get-Date|date|time|hostname|whoami)\b", re.IGNORECASE),
        re.compile(r"^\s*(Get-Process|Get-Service|ipconfig|ping|tracert|nslookup)\b", re.IGNORECASE),
    ]

    def __init__(self, protected_paths: Optional[List[str]] = None):
        self.protected_paths = protected_paths or [
            "C:\\Windows",
            "C:\\Windows\\System32",
            "C:\\Program Files",
            "C:\\Program Files (x86)",
        ]

    def classify_command(self, command: str) -> PermissionLevel:
        """Evaluate command and return its determined PermissionLevel."""
        clean_cmd = command.strip()

        # Check for Level 3 (High-Risk)
        for pat in self.LEVEL_3_PATTERNS:
            if pat.search(clean_cmd):
                return PermissionLevel.LEVEL_3_HIGH_RISK

        # Check for Level 2 (Approval Required)
        for pat in self.LEVEL_2_PATTERNS:
            if pat.search(clean_cmd):
                return PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

        # Check for Level 0 (Read-Only)
        for pat in self.LEVEL_0_PATTERNS:
            if pat.search(clean_cmd):
                return PermissionLevel.LEVEL_0_READ_ONLY

        # Default fallback is Level 1 (Low-Risk / Local Modification)
        return PermissionLevel.LEVEL_1_LOW_RISK

    def is_path_protected(self, path_str: str) -> bool:
        """Check if target path falls within system-protected directories."""
        import os
        norm = os.path.normpath(path_str).lower()
        for p in self.protected_paths:
            if norm.startswith(os.path.normpath(p).lower()):
                return True
        return False
