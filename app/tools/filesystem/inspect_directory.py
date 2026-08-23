"""
Directory Inspection and Project Type Detection Tool
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.filesystem.safety import PathSafety


class InspectDirectoryTool(BaseTool):
    """Tool to inspect directory contents and auto-detect software project types."""

    name = "dir_inspect"
    description = "Inspect a directory, list its files and subdirectories, and detect project technologies."
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
                    "description": "Path to the directory to inspect (default: current directory)",
                },
            },
            "additionalProperties": False,
        }

    def _detect_projects(self, root: Path, file_names: set) -> List[Dict[str, str]]:
        """Identify project types and frameworks present in the directory."""
        projects = []

        if "package.json" in file_names:
            projects.append({"type": "Node.js / JavaScript", "indicator": "package.json"})
        if "pyproject.toml" in file_names or "requirements.txt" in file_names or "setup.py" in file_names:
            projects.append({"type": "Python", "indicator": "pyproject.toml/requirements.txt"})
        if "Cargo.toml" in file_names:
            projects.append({"type": "Rust", "indicator": "Cargo.toml"})
        if "go.mod" in file_names:
            projects.append({"type": "Go", "indicator": "go.mod"})
        if any(f.endswith(".sln") or f.endswith(".csproj") for f in file_names):
            projects.append({"type": ".NET / C#", "indicator": "*.sln or *.csproj"})
        if "pom.xml" in file_names or "build.gradle" in file_names:
            projects.append({"type": "Java / Gradle / Maven", "indicator": "pom.xml/build.gradle"})
        if "Dockerfile" in file_names or "docker-compose.yml" in file_names:
            projects.append({"type": "Docker Containerized", "indicator": "Dockerfile"})
        if (root / ".git").exists():
            projects.append({"type": "Git Repository", "indicator": ".git"})

        return projects

    def _run(self, directory_path: Optional[str] = None) -> Dict[str, Any]:
        root = self.safety.resolve_path(directory_path or ".")
        if not root.exists() or not root.is_dir():
            raise NotADirectoryError(f"Directory '{root}' does not exist.")

        entries = list(root.iterdir())
        file_names = {e.name for e in entries}

        directories = []
        files = []

        for e in entries:
            try:
                st = e.stat()
                if e.is_dir():
                    directories.append(
                        {
                            "name": e.name,
                            "path": str(e),
                        }
                    )
                else:
                    files.append(
                        {
                            "name": e.name,
                            "path": str(e),
                            "size_bytes": st.st_size,
                        }
                    )
            except Exception:
                continue

        detected_projects = self._detect_projects(root, file_names)

        return {
            "directory_path": str(root),
            "total_items": len(entries),
            "directory_count": len(directories),
            "file_count": len(files),
            "detected_projects": detected_projects,
            "directories": directories[:30],
            "files": files[:50],
        }
