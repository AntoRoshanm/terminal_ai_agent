"""
File Reading Tool with Line Slicing and Safety
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.filesystem.safety import PathSafety


class ReadFileTool(BaseTool):
    """Tool to read text content from files with optional line range slicing."""

    name = "file_read"
    description = "Read the contents of a text file with optional line range slicing (start_line, end_line)."
    category = "filesystem"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def __init__(self, safety: Optional[PathSafety] = None):
        self.safety = safety or PathSafety()

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to read",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional 1-indexed starting line number",
                    "minimum": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional 1-indexed ending line number",
                    "minimum": 1,
                },
                "max_bytes": {
                    "type": "integer",
                    "description": "Maximum bytes to read (default: 65536 = 64KB)",
                    "default": 65536,
                },
            },
            "required": ["file_path"],
            "additionalProperties": False,
        }

    def _is_binary(self, sample: bytes) -> bool:
        """Heuristic check for binary files."""
        return b"\x00" in sample

    def _run(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        max_bytes: int = 65536,
    ) -> Dict[str, Any]:
        resolved = self.safety.resolve_path(file_path)

        if not resolved.exists():
            raise FileNotFoundError(f"File '{resolved}' not found.")
        if not resolved.is_file():
            raise IsADirectoryError(f"Path '{resolved}' is a directory, not a file.")

        file_size = resolved.stat().st_size

        # Check binary
        with open(resolved, "rb") as f:
            sample = f.read(1024)
            if self._is_binary(sample):
                return {
                    "file_path": str(resolved),
                    "is_binary": True,
                    "file_size_bytes": file_size,
                    "content": f"[Binary File: {file_size} bytes]",
                }

        # Read text
        encodings = ["utf-8", "cp1252", "cp437", "latin1"]
        content = ""
        for enc in encodings:
            try:
                with open(resolved, "r", encoding=enc, errors="strict") as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, Exception):
                continue
        else:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        if start_line is not None or end_line is not None:
            s_idx = max(0, (start_line - 1) if start_line else 0)
            e_idx = end_line if end_line else total_lines
            sliced_lines = lines[s_idx:e_idx]
            returned_content = "".join(sliced_lines)
            actual_start = s_idx + 1
            actual_end = min(e_idx, total_lines)
        else:
            returned_content = content[:max_bytes]
            actual_start = 1
            actual_end = total_lines

        truncated = len(returned_content.encode("utf-8")) < file_size

        return {
            "file_path": str(resolved),
            "total_lines": total_lines,
            "start_line": actual_start,
            "end_line": actual_end,
            "file_size_bytes": file_size,
            "truncated": truncated,
            "content": returned_content,
        }
