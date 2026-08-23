"""
Filesystem Security, Protected Paths, and Canonical Path Resolution across Windows, Linux, and macOS
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.platform.detect import get_platform_info
from app.security.guard import SecurityGuard


class PathSafety:
    """Enforces protected path boundaries across Windows, Linux, and macOS."""

    def __init__(self, protected_paths: Optional[List[str]] = None):
        paths = protected_paths or SecurityGuard.get_protected_paths()
        self.protected_paths = [
            os.path.normpath(p).lower()
            for p in paths
        ]

    def resolve_path(self, target_path: str, cwd: Optional[str] = None) -> Path:
        """Resolve a path to its absolute, canonical form, defaulting unspecified deliverables to Desktop."""
        raw_str = str(target_path).strip()
        if not raw_str:
            return (Path.home() / "Desktop").resolve()

        # Directive v9.1 Section 3: Default invented / hallucinated output paths (e.g. C:\output\...) to Desktop
        norm_fwd = raw_str.replace("\\", "/")
        if re.match(r'^(?:[a-zA-Z]:)?/(?:output|out|exports?|build|temp_output)/', norm_fwd, re.IGNORECASE):
            fname = norm_fwd.split("/")[-1] or "document"
            return (Path.home() / "Desktop" / fname).resolve()

        # Canonicalize common user directory shortcuts across platforms
        if raw_str.startswith("~/") or raw_str.startswith("~\\"):
            p = Path.home() / raw_str[2:].lstrip("/\\")
        elif raw_str.lower().startswith("desktop/") or raw_str.lower().startswith("desktop\\") or raw_str.lower() in ("desktop", "desktop/"):
            p = Path.home() / raw_str
        elif (raw_str.startswith("/") or raw_str.startswith("\\")) and (
            raw_str.lower().startswith("/desktop") or raw_str.lower().startswith("\\desktop")
            or raw_str.lower().startswith("/documents") or raw_str.lower().startswith("\\documents")
            or raw_str.lower().startswith("/downloads") or raw_str.lower().startswith("\\downloads")
        ):
            p = Path.home() / raw_str.lstrip("/\\")
        else:
            # Canonicalize generic placeholder usernames (e.g. C:/Users/User/Desktop -> Path.home() / Desktop)
            m_user = re.match(r'^(?:[a-zA-Z]:)?/(?:users|home)/([^/]+)/(.*)', norm_fwd, re.IGNORECASE)
            if m_user:
                uname = m_user.group(1).lower()
                rest = m_user.group(2)
                if uname in ("user", "username", "admin", "administrator", "<username>", "<user>", "default", "your_username", "name") or not (
                    Path(f"C:/Users/{m_user.group(1)}").exists() if os.name == "nt" else Path(f"/home/{m_user.group(1)}").exists()
                ):
                    p = Path.home() / rest
                    return p.resolve()

            # If it's a standalone filename with document extension and no directory separator, default to Desktop
            if not ("/" in norm_fwd) and any(
                norm_fwd.lower().endswith(ext) for ext in (".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md", ".json")
            ):
                return (Path.home() / "Desktop" / norm_fwd).resolve()

            p = Path(os.path.expanduser(raw_str))
            if not p.is_absolute():
                base = Path(cwd) if cwd else Path.cwd()
                p = base / p
        return p.resolve()

    def canonicalize_path(self, target_path: str, cwd: Optional[str] = None) -> Path:
        """Alias for resolve_path (Directive B.39)."""
        return self.resolve_path(target_path, cwd)

    def check_write_resource_safety(
        self, target_path: str, estimated_size_bytes: int = 0, allow_large_write: bool = False
    ) -> None:
        """Directive B.38: Resource Safety Gate for Writes."""
        resolved = self.resolve_path(target_path)
        import shutil
        check_dir = resolved.parent if resolved.parent.exists() else Path.home()
        try:
            _, _, free_disk = shutil.disk_usage(str(check_dir))
        except Exception:
            free_disk = 100 * 1024 * 1024 * 1024

        if estimated_size_bytes > free_disk:
            raise ValueError(
                f"Resource Safety Gate Refusal (Directive B.38): The requested write size of {estimated_size_bytes} bytes "
                f"exceeds available disk space ({free_disk} bytes)."
            )

        MAX_SINGLE_WRITE_BYTES = 1024 * 1024 * 1024  # 1 GB
        if estimated_size_bytes > MAX_SINGLE_WRITE_BYTES and not allow_large_write:
            raise ValueError(
                f"Resource Safety Gate Refusal (Directive B.38): The requested write size of {estimated_size_bytes} bytes "
                f"exceeds the 1.0 GB single-write safety ceiling."
            )

    def is_protected(self, path: Path) -> bool:
        """Check if target path falls within protected system directories."""
        norm_str = str(path).lower().replace("\\", "/")
        norm_str_no_drive = norm_str[2:] if len(norm_str) >= 2 and norm_str[1] == ":" else norm_str

        for protected in self.protected_paths:
            prot_norm = protected.replace("\\", "/")
            prot_no_drive = prot_norm[2:] if len(prot_norm) >= 2 and prot_norm[1] == ":" else prot_norm
            if (
                norm_str == prot_norm
                or norm_str.startswith(prot_norm + "/")
                or norm_str_no_drive == prot_no_drive
                or norm_str_no_drive.startswith(prot_no_drive + "/")
            ):
                return True
        return False

    def is_sip_blocked(self, path: Path) -> bool:
        """Check if target path is specifically protected by macOS System Integrity Protection."""
        info = get_platform_info()
        if info.os_family != "macos" or info.sip_enabled is False:
            return False

        norm_str = str(path).replace("\\", "/")
        norm_no_drive = norm_str[2:] if len(norm_str) >= 2 and norm_str[1] == ":" else norm_str

        sip_roots = ["/System", "/bin", "/sbin", "/usr/bin", "/usr/sbin"]
        for sr in sip_roots:
            if (
                norm_str == sr
                or norm_str.startswith(sr + "/")
                or norm_no_drive == sr
                or norm_no_drive.startswith(sr + "/")
            ):
                return True
        return False

    def check_safe_write(self, target_path: str, cwd: Optional[str] = None) -> Path:
        """Validate that a path is safe for modification/deletion."""
        resolved = self.resolve_path(target_path, cwd)
        if self.is_sip_blocked(resolved):
            raise PermissionError(f"Modification of path '{resolved}' is blocked by System Integrity Protection (SIP). Sudo will not override SIP.")
        if self.is_protected(resolved):
            raise PermissionError(f"Modification of protected system path '{resolved}' is blocked by security policy.")
        return resolved

    def is_path_like_value(self, val: Any) -> bool:
        """Directive B.39: Check if a value is a path-like string by shape, regardless of parameter name."""
        if not isinstance(val, str):
            return False
        s = val.strip()
        if not s:
            return False
        if s.startswith("~/") or s.startswith("~\\"):
            return True
        if s.lower().startswith("desktop/") or s.lower().startswith("desktop\\") or s.lower() in ("desktop", "desktop/"):
            return True
        if s.startswith("/") or s.startswith("\\"):
            return True
        if len(s) >= 3 and s[1] == ":" and s[2] in ("/\\"):
            return True
        if re.search(r"[/\\]", s) and any(ext in s.lower() for ext in (".txt", ".log", ".json", ".py", ".md", ".sh", ".bat", ".csv", ".docx", ".pdf", ".exe", ".bin")):
            return True
        if re.match(r'^(?:[a-zA-Z]:)?/(?:users|home)/', s.replace("\\", "/"), re.IGNORECASE):
            return True
        return False

    @classmethod
    def sanitize_arguments(cls, arguments: Dict[str, Any], cwd: Optional[str] = None) -> Dict[str, Any]:
        """
        Directive B.39: Argument-Name-Agnostic Path Value Canonicalization.
        Detects any argument whose value matches path-like patterns by shape,
        regardless of parameter name (e.g. path, file_path, source_path, target_path, destination, file, etc.).
        """
        safety = cls()
        cleaned = {}
        for k, v in arguments.items():
            if isinstance(v, str) and safety.is_path_like_value(v):
                resolved = safety.resolve_path(v, cwd=cwd)
                cleaned[k] = str(resolved)
            else:
                cleaned[k] = v
        return cleaned

