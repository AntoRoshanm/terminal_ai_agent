"""
File Search Tool with Glob Patterns and Filters
"""

from datetime import datetime, timezone
import fnmatch
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.filesystem.safety import PathSafety


class SearchFilesTool(BaseTool):
    """Tool to search for files and directories matching glob patterns."""

    name = "file_search"
    description = "Search for files and directories by glob pattern, file extension, or name."
    category = "filesystem"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def __init__(self, safety: Optional[PathSafety] = None):
        self.safety = safety or PathSafety()

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Root directory to search within (default: current working directory)",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '*.py', '*test*', '*.json', 'README.*')",
                    "default": "*",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to search subdirectories recursively (default: true)",
                    "default": True,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 50)",
                    "default": 50,
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        directory_path: Optional[str] = None,
        pattern: str = "*",
        recursive: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        root = self.safety.resolve_path(directory_path or ".")
        if not root.exists() or not root.is_dir():
            raise NotADirectoryError(f"Search directory '{root}' does not exist.")

        results: List[Dict[str, Any]] = []

        if recursive:
            for dirpath, dirnames, filenames in os.walk(root):
                # Ignore hidden dirs like .git, .pytest_cache
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]

                for name in dirnames + filenames:
                    if fnmatch.fnmatch(name, pattern):
                        full_p = Path(dirpath) / name
                        try:
                            st = full_p.stat()
                            results.append(
                                {
                                    "path": str(full_p),
                                    "name": name,
                                    "is_directory": full_p.is_dir(),
                                    "size_bytes": st.st_size if full_p.is_file() else 0,
                                    "modified_at": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                                }
                            )
                        except Exception:
                            continue

                        if len(results) >= limit:
                            return results
        else:
            for item in root.iterdir():
                if fnmatch.fnmatch(item.name, pattern):
                    try:
                        st = item.stat()
                        results.append(
                            {
                                "path": str(item),
                                "name": item.name,
                                "is_directory": item.is_dir(),
                                "size_bytes": st.st_size if item.is_file() else 0,
                                "modified_at": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                            }
                        )
                    except Exception:
                        continue
                    if len(results) >= limit:
                        return results

        return results
