"""
Automated Test Runner and Failure Diagnostic Tool
"""

import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class RunProjectTestsTool(BaseTool):
    """Tool to auto-detect, run, and summarize project test suites."""

    name = "dev_run_tests"
    description = "Auto-detect project test runner (pytest, jest, cargo test, go test, dotnet test) and execute test suite."
    category = "developer"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK
    timeout_seconds = 180

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Optional project root path (default: current working directory)",
                },
                "custom_command": {
                    "type": "string",
                    "description": "Optional custom test command to run instead of auto-detecting",
                },
            },
            "additionalProperties": False,
        }

    def _detect_test_command(self, root: Path) -> Optional[list[str]]:
        """Determine test command based on manifest files."""
        if (root / "pytest.ini").exists() or (root / "tests").exists() or (root / "pyproject.toml").exists():
            return ["python", "-m", "pytest", "-v"]
        if (root / "package.json").exists():
            return ["npm.cmd", "test"]
        if (root / "Cargo.toml").exists():
            return ["cargo.exe", "test"]
        if (root / "go.mod").exists():
            return ["go.exe", "test", "./..."]
        if list(root.glob("*.sln")) or list(root.glob("*.csproj")):
            return ["dotnet.exe", "test"]
        return None

    def _run(
        self,
        project_path: Optional[str] = None,
        custom_command: Optional[str] = None,
    ) -> Dict[str, Any]:
        cwd = Path(project_path).resolve() if project_path else Path(os.getcwd())

        if custom_command:
            cmd = custom_command.split()
        else:
            cmd = self._detect_test_command(cwd)

        if not cmd:
            return {
                "success": False,
                "error": "Could not auto-detect test runner. Provide a custom_command.",
            }

        try:
            res = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            stdout = res.stdout
            stderr = res.stderr
            all_output = stdout + "\n" + stderr

            # Simple pass/fail counter matching pytest / standard test output
            passed_match = re.search(r"(\d+)\s+passed", all_output, re.IGNORECASE)
            failed_match = re.search(r"(\d+)\s+failed", all_output, re.IGNORECASE)

            passed_count = int(passed_match.group(1)) if passed_match else (0 if res.returncode != 0 else 1)
            failed_count = int(failed_match.group(1)) if failed_match else (1 if res.returncode != 0 else 0)

            return {
                "command": " ".join(cmd),
                "exit_code": res.returncode,
                "success": res.returncode == 0,
                "passed_count": passed_count,
                "failed_count": failed_count,
                "summary": "All tests passed" if res.returncode == 0 else f"{failed_count} test(s) failed",
                "output": all_output[-4000:],  # Return tail of output
            }
        except subprocess.TimeoutExpired:
            return {
                "command": " ".join(cmd),
                "success": False,
                "error": f"Test run timed out after {self.timeout_seconds} seconds.",
            }
        except Exception as e:
            return {"command": " ".join(cmd), "success": False, "error": str(e)}
