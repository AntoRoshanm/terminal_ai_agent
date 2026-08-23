"""
Git Version Control Operations and Repository Automation Tools
"""

import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class GitStatusTool(BaseTool):
    """Tool to inspect Git working directory status and branch tracking."""

    name = "dev_git_status"
    description = "Check git repository status: current branch, staged/modified files, and untracked items."
    category = "developer"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Optional repository path (default: current working directory)",
                },
            },
            "additionalProperties": False,
        }

    def _run(self, repo_path: Optional[str] = None) -> Dict[str, Any]:
        cwd = repo_path or os.getcwd()

        try:
            res = subprocess.run(
                ["git", "status", "--porcelain=v1", "-b"],
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if res.returncode != 0:
                return {
                    "is_git_repo": False,
                    "error": (res.stderr or "").strip(),
                }

            stdout_text = res.stdout or ""
            lines = stdout_text.splitlines()
            branch_info = lines[0][3:] if lines and lines[0].startswith("## ") else "Unknown"

            staged: List[str] = []
            modified: List[str] = []
            untracked: List[str] = []

            for line in lines[1:]:
                if len(line) < 3:
                    continue
                x, y, path = line[0], line[1], line[3:].strip()
                if x in ("M", "A", "D", "R", "C"):
                    staged.append(path)
                if y in ("M", "D"):
                    modified.append(path)
                if x == "?" and y == "?":
                    untracked.append(path)

            return {
                "is_git_repo": True,
                "branch": branch_info,
                "staged_count": len(staged),
                "staged_files": staged,
                "modified_count": len(modified),
                "modified_files": modified,
                "untracked_count": len(untracked),
                "untracked_files": untracked[:20],
                "clean": len(staged) == 0 and len(modified) == 0 and len(untracked) == 0,
            }
        except Exception as e:
            return {"is_git_repo": False, "error": str(e)}


class GitLogTool(BaseTool):
    """Tool to inspect recent Git commit history."""

    name = "dev_git_log"
    description = "View recent Git commit log with commit hashes, authors, timestamps, and messages."
    category = "developer"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of commits to retrieve (default: 10)",
                    "default": 10,
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional repository path (default: current working directory)",
                },
            },
            "additionalProperties": False,
        }

    def _run(self, limit: int = 10, repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
        cwd = repo_path or os.getcwd()

        try:
            cmd = ["git", "log", f"-n{limit}", '--pretty=format:%H|%an|%ad|%s', "--date=iso"]
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if res.returncode != 0:
                return [{"error": (res.stderr or "").strip()}]

            commits = []
            stdout_text = res.stdout or ""
            for line in stdout_text.splitlines():
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append(
                        {
                            "commit_hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3],
                        }
                    )
            return commits
        except Exception as e:
            return [{"error": str(e)}]


class GitDiffTool(BaseTool):
    """Tool to inspect uncommitted changes in Git."""

    name = "dev_git_diff"
    description = "View unified diff of uncommitted changes or staged modifications."
    category = "developer"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "staged": {
                    "type": "boolean",
                    "description": "Whether to view staged diff (--cached) (default: false)",
                    "default": False,
                },
                "file_path": {
                    "type": "string",
                    "description": "Optional specific file path to diff",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional repository directory",
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        staged: bool = False,
        file_path: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        cwd = repo_path or os.getcwd()
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")
        if file_path:
            cmd.extend(["--", file_path])

        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if res.returncode != 0:
                return {"diff": "", "error": (res.stderr or "").strip()}

            diff_text = (res.stdout or "").strip()
            return {
                "staged": staged,
                "has_diff": bool(diff_text),
                "diff": diff_text[:15000],  # Cap output size
                "truncated": len(diff_text) > 15000,
            }
        except Exception as e:
            return {"diff": "", "error": str(e)}


class GitCommitTool(BaseTool):
    """Tool to stage files and create a Git commit."""

    name = "dev_git_commit"
    description = "Stage files and commit changes with a commit message. Requires user approval."
    category = "developer"
    permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message describing the changes",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of specific files to stage (default: all modified files '.')",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional repository directory",
                },
            },
            "required": ["message"],
            "additionalProperties": False,
        }

    def _run(
        self,
        message: str,
        files: Optional[List[str]] = None,
        repo_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        cwd = repo_path or os.getcwd()

        try:
            # 1. Stage
            stage_targets = files if files else ["."]
            stage_cmd = ["git", "add"] + stage_targets
            add_res = subprocess.run(
                stage_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if add_res.returncode != 0:
                raise RuntimeError(f"Git add failed: {(add_res.stderr or '').strip()}")

            # 2. Commit
            commit_cmd = ["git", "commit", "-m", message]
            commit_res = subprocess.run(
                commit_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if commit_res.returncode != 0:
                raise RuntimeError(f"Git commit failed: {(commit_res.stderr or '').strip()}")

            return {
                "status": "committed",
                "message": message,
                "output": (commit_res.stdout or "").strip(),
            }
        except Exception as e:
            raise RuntimeError(f"Commit operation failed: {str(e)}")


class GitBranchTool(BaseTool):
    """Tool to list or switch/create Git branches."""

    name = "dev_git_branch"
    description = "List existing branches or create/switch to a new Git branch."
    category = "developer"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: 'list', 'create', or 'checkout' (default: 'list')",
                    "enum": ["list", "create", "checkout"],
                    "default": "list",
                },
                "branch_name": {
                    "type": "string",
                    "description": "Branch name (required for 'create' and 'checkout')",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional repository path",
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        action: str = "list",
        branch_name: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        cwd = repo_path or os.getcwd()

        try:
            if action == "list":
                res = subprocess.run(
                    ["git", "branch", "-a"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )
                if res.returncode != 0:
                    return {"error": (res.stderr or "").strip()}
                stdout_text = res.stdout or ""
                branches = [b.strip() for b in stdout_text.splitlines() if b.strip()]
                return {"action": "list", "branches": branches}

            elif action == "create":
                if not branch_name:
                    raise ValueError("branch_name is required for create action.")
                res = subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )
                if res.returncode != 0:
                    raise RuntimeError(f"Failed to create branch: {(res.stderr or '').strip()}")
                return {"action": "create", "branch": branch_name, "status": "created_and_checked_out"}

            elif action == "checkout":
                if not branch_name:
                    raise ValueError("branch_name is required for checkout action.")
                res = subprocess.run(
                    ["git", "checkout", branch_name],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )
                if res.returncode != 0:
                    raise RuntimeError(f"Failed to checkout branch: {(res.stderr or '').strip()}")
                return {"action": "checkout", "branch": branch_name, "status": "checked_out"}

            raise ValueError(f"Unknown action: {action}")
        except Exception as e:
            return {"error": str(e)}
