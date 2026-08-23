"""
File Writing Tool with Resource Safety Gate (B.38), Argument Agnosticism (B.39), and Independent Verification (B.40)
"""

import os
from pathlib import Path
import shutil
from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel, ToolExecutionResult
from app.tools.base import BaseTool
from app.tools.filesystem.safety import PathSafety


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    if size_bytes >= 1024**3:
        return f"~{size_bytes / (1024**3):.1f} GB"
    elif size_bytes >= 1024**2:
        return f"~{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        return f"~{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} bytes"


class WriteFileTool(BaseTool):
    """Tool to create or overwrite text files safely with resource limits and verification."""

    name = "file_write"
    description = "Create a new text file or overwrite an existing file with provided content."
    category = "filesystem"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    # Maximum allowed single write without explicit override: 1 GB
    MAX_SINGLE_WRITE_BYTES = 1024 * 1024 * 1024

    def __init__(self, safety: Optional[PathSafety] = None):
        self.safety = safety or PathSafety()

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path of the file to create or overwrite",
                },
                "content": {
                    "type": "string",
                    "description": "The exact text content or template to write to the file",
                },
                "repeat_count": {
                    "type": "integer",
                    "description": "Number of times to repeat the content string (e.g. 100 for bulk generation, default: 1)",
                    "default": 1,
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite if file already exists (default: true)",
                    "default": True,
                },
                "allow_large_write": {
                    "type": "boolean",
                    "description": "Explicit override to allow writes larger than 1.0 GB ceiling",
                    "default": False,
                },
                "target_words": {
                    "type": "integer",
                    "description": "Optional target word count requested for generative text verification (Directive B.42)",
                },
            },
            "required": ["file_path", "content"],
            "additionalProperties": False,
        }

    def _run(
        self,
        file_path: Optional[str] = None,
        content: str = "",
        repeat_count: int = 1,
        overwrite: bool = True,
        allow_large_write: bool = False,
        target_words: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        # Directive B.39: Argument-Agnostic Path Parameter Resolution
        raw_path = (
            file_path
            or kwargs.get("path")
            or kwargs.get("file")
            or kwargs.get("target_path")
            or kwargs.get("source_path")
            or kwargs.get("destination_path")
        )
        if not raw_path:
            raise ValueError("Missing required file path parameter ('file_path' or 'path').")

        # Resolve path safely with placeholder canonicalization
        resolved = self.safety.check_safe_write(str(raw_path))

        if resolved.exists() and not overwrite:
            raise FileExistsError(f"File '{resolved}' already exists and overwrite is set to False.")

        # Directive B.38: Resource Safety Gate for Writes
        try:
            count = max(1, int(repeat_count or 1))
        except (ValueError, TypeError):
            count = 1

        # Directive B.42: Generative Content Length Verification
        actual_words = len(content.split()) * count
        tgt_words = target_words or kwargs.get("target_words")
        if tgt_words and int(tgt_words) > 0 and count == 1:
            int_tgt = int(tgt_words)
            if actual_words < int(int_tgt * 0.5):
                raise ValueError(
                    f"Generative Length Verification Failure (Directive B.42): The target length requested was {int_tgt:,} words, "
                    f"but only {actual_words:,} words were generated and written to '{resolved}'. Operation failed verification."
                )

        content_bytes_len = len(content.encode("utf-8")) if content else 0
        chunk_bytes_len = content_bytes_len if (content.endswith("\n") or count == 1) else (content_bytes_len + 1)
        estimated_total_bytes = chunk_bytes_len * count

        # Check available disk space before constructing content or touching disk
        check_dir = resolved.parent if resolved.parent.exists() else Path.home()
        try:
            _, _, free_disk = shutil.disk_usage(str(check_dir))
        except Exception:
            free_disk = 100 * 1024 * 1024 * 1024  # Fallback assumption 100 GB

        # Check 1: Exceeds available disk space
        if estimated_total_bytes > free_disk:
            raise ValueError(
                f"Resource Safety Gate Refusal (Directive B.38): The requested write size of {format_size(estimated_total_bytes)} "
                f"exceeds available disk space ({format_size(free_disk)}). Write operation was aborted before disk or memory allocation."
            )

        # Check 2: Exceeds 1.0 GB single-write hard ceiling without explicit override
        if estimated_total_bytes > self.MAX_SINGLE_WRITE_BYTES and not allow_large_write:
            raise ValueError(
                f"Resource Safety Gate Refusal (Directive B.38): The requested write size of {format_size(estimated_total_bytes)} "
                f"exceeds the 1.0 GB single-write safety ceiling (available disk space: {format_size(free_disk)}). "
                f"Write operation was aborted before disk or memory allocation."
            )

        # Auto-create parent directory safely
        resolved.parent.mkdir(parents=True, exist_ok=True)

        total_bytes = 0
        total_lines = 0

        # Stream write in small chunks to prevent high memory usage
        with open(resolved, "w", encoding="utf-8") as f:
            if count == 1:
                f.write(content)
                total_bytes = content_bytes_len
                total_lines = len(content.splitlines())
            else:
                chunk = content if content.endswith("\n") else (content + "\n")
                chunk_size = min(10000, count)
                chunk_str = chunk * chunk_size
                remaining = count
                while remaining > 0:
                    batch = min(remaining, chunk_size)
                    if batch == chunk_size:
                        f.write(chunk_str)
                    else:
                        f.write(chunk * batch)
                    remaining -= batch
                total_bytes = len(chunk.encode("utf-8")) * count
                total_lines = count

        # Directive B.40: Independent Post-Action Verification
        if not resolved.exists():
            raise FileNotFoundError(f"Verification Failed (Directive B.40): File '{resolved}' does not exist after write operation.")

        actual_size = resolved.stat().st_size
        if actual_size < total_bytes:
            raise IOError(
                f"Verification Failed (Directive B.40): File size on disk ({actual_size} bytes) is less than expected ({total_bytes} bytes)."
            )

        return {
            "file_path": str(resolved),
            "bytes_written": total_bytes,
            "lines_written": total_lines,
            "words_written": actual_words,
            "target_words": tgt_words,
            "repeat_count": count,
            "verified_success": True,
            "status": "success",
        }
