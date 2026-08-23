"""
File Management Tool with Argument Agnosticism (B.39) and Independent Post-Action Verification (B.40)
"""

import os
from pathlib import Path
import shutil
from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel, ToolExecutionResult
from app.tools.base import BaseTool
from app.tools.filesystem.safety import PathSafety


class ManageFilesTool(BaseTool):
    """Tool to copy, move, rename, or safely delete files and directories with independent verification."""

    name = "file_manage"
    description = "Perform file operations: 'copy', 'move', 'rename', or 'delete' on files and directories."
    category = "filesystem"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def __init__(self, safety: Optional[PathSafety] = None):
        self.safety = safety or PathSafety()

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Operation to perform: 'copy', 'move', 'rename', or 'delete'",
                    "enum": ["copy", "move", "rename", "delete"],
                },
                "source_path": {
                    "type": "string",
                    "description": "Path to the source file or directory (aliases: path, file_path, file, target_path)",
                },
                "destination_path": {
                    "type": "string",
                    "description": "Path to the destination (required for copy, move, and rename; aliases: destination, target_path)",
                },
            },
            "required": ["operation"],
            "additionalProperties": False,
        }

    def _run(
        self,
        operation: str = "delete",
        source_path: Optional[str] = None,
        destination_path: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        op = str(operation or "delete").lower().strip()

        # Directive B.39: Argument-Agnostic Source Path Parameter Resolution
        raw_src = (
            source_path
            or kwargs.get("path")
            or kwargs.get("file_path")
            or kwargs.get("file")
            or kwargs.get("source")
            or kwargs.get("target")
            or kwargs.get("target_path")
        )
        if not raw_src:
            raise ValueError("Missing required source path parameter ('source_path' or 'path').")

        src = self.safety.check_safe_write(str(raw_src))

        # Directive B.40: Pre-Action Existence Validation
        if not src.exists():
            raise FileNotFoundError(f"Verification Error: Target '{src}' does not exist on disk. Cannot {op} nonexistent path.")

        if op == "delete":
            if src.is_dir():
                shutil.rmtree(src)
            else:
                src.unlink()

            # Directive B.40: Post-Action Independent Verification
            if src.exists():
                raise IOError(f"Verification Failed (Directive B.40): Target '{src}' still exists on disk after deletion attempt.")

            return {
                "operation": "delete",
                "target": str(src),
                "verified_success": True,
                "status": "deleted",
            }

        # For copy, move, rename, resolve destination path
        raw_dst = (
            destination_path
            or kwargs.get("destination")
            or kwargs.get("target_path")
            or kwargs.get("target")
            or kwargs.get("dst")
            or kwargs.get("to_path")
        )
        if not raw_dst:
            raise ValueError(f"Destination path is required for operation '{op}'.")

        dst = self.safety.check_safe_write(str(raw_dst))

        if op == "copy":
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

            # Directive B.40 Verification
            if not dst.exists():
                raise IOError(f"Verification Failed (Directive B.40): Destination '{dst}' does not exist after copy.")

            return {
                "operation": "copy",
                "source": str(src),
                "destination": str(dst),
                "verified_success": True,
                "status": "copied",
            }

        elif op in ("move", "rename"):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)

            # Directive B.40 Verification
            if not dst.exists() or src.exists():
                raise IOError(f"Verification Failed (Directive B.40): Move failed. Destination exists: {dst.exists()}, source remains: {src.exists()}.")

            return {
                "operation": op,
                "source": str(src),
                "destination": str(dst),
                "verified_success": True,
                "status": "moved",
            }

        else:
            raise ValueError(f"Unsupported operation '{operation}'. Choose from: copy, move, rename, delete.")
