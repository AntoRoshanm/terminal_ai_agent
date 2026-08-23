"""
File Editing Tool for Precise Search-and-Replace Modifications
"""

from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.filesystem.safety import PathSafety


class EditFileTool(BaseTool):
    """Tool to perform targeted search-and-replace edits on text files with CRLF/LF normalization."""

    name = "file_edit"
    description = "Replace specific lines or substrings in an existing text file with replacement content."
    category = "filesystem"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def __init__(self, safety: Optional[PathSafety] = None):
        self.safety = safety or PathSafety()

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "target_content": {
                    "type": "string",
                    "description": "Exact text or lines to search for and replace",
                },
                "replacement_content": {
                    "type": "string",
                    "description": "The new replacement text to insert",
                },
                "allow_multiple": {
                    "type": "boolean",
                    "description": "Whether to replace multiple occurrences if found (default: false)",
                    "default": False,
                },
            },
            "required": ["file_path", "target_content", "replacement_content"],
            "additionalProperties": False,
        }

    def _run(
        self,
        file_path: str,
        target_content: str,
        replacement_content: str,
        allow_multiple: bool = False,
    ) -> Dict[str, Any]:
        resolved = self.safety.check_safe_write(file_path)

        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"File '{resolved}' not found.")

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            original_content = f.read()

        count = original_content.count(target_content)
        if count == 0:
            # Line-ending normalization fallback (CRLF <-> LF)
            norm_orig = original_content.replace("\r\n", "\n")
            norm_target = target_content.replace("\r\n", "\n")
            norm_replace = replacement_content.replace("\r\n", "\n")
            if norm_orig.count(norm_target) > 0:
                original_content = norm_orig
                target_content = norm_target
                replacement_content = norm_replace
                count = original_content.count(target_content)

        if count == 0:
            raise ValueError(f"Target content not found in '{resolved}'.")
        if count > 1 and not allow_multiple:
            raise ValueError(
                f"Target content found {count} times in '{resolved}'. Set allow_multiple=True to replace all."
            )

        if allow_multiple:
            new_content = original_content.replace(target_content, replacement_content)
        else:
            new_content = original_content.replace(target_content, replacement_content, 1)

        with open(resolved, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {
            "file_path": str(resolved),
            "replacements_made": count if allow_multiple else 1,
            "status": "success",
        }
