"""
Execute Terminal Command Tool Implementation with Elevation Protection
"""

import os
from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel, ToolExecutionResult
from app.platform.detect import get_platform_info
from app.tools.base import BaseTool
from app.tools.terminal.policy import CommandPolicyEngine
from app.tools.terminal.runner import CommandRunner


class ExecuteTerminalCommandTool(BaseTool):
    """Tool allowing the agent to safely execute shell commands."""

    name = "terminal_exec"
    description = (
        "Execute a terminal command (PowerShell/CMD on Windows, Bash/Sh on Linux). "
        "Captures stdout, stderr, and exit code. "
        "Use for inspecting files, running build tools, testing, or managing processes."
    )
    category = "terminal"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK  # Base level, dynamically adjusted per command
    timeout_seconds = 60

    def __init__(
        self,
        runner: Optional[CommandRunner] = None,
        policy: Optional[CommandPolicyEngine] = None,
    ):
        self.runner = runner or CommandRunner()
        self.policy = policy or CommandPolicyEngine()

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact shell command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory for the command execution",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum seconds to wait before terminating the command (default: 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        }

    def execute(self, tool_call_id: str, **kwargs) -> ToolExecutionResult:
        """Override execute to dynamically check command risk and elevation before running."""
        command = kwargs.get("command", "").strip()
        cwd = kwargs.get("cwd")
        timeout = kwargs.get("timeout_seconds", 30)

        # Dynamically classify risk level
        cmd_risk = self.policy.classify_command(command)

        # Check protected paths
        if cwd and self.policy.is_path_protected(cwd):
            cmd_risk = max(cmd_risk, PermissionLevel.LEVEL_2_APPROVAL_REQUIRED)

        if not command:
            return ToolExecutionResult(
                tool_name=self.name,
                tool_call_id=tool_call_id,
                success=False,
                error="Empty command provided",
                permission_level=cmd_risk,
            )

        # Sudo / Elevation handling (Directive A.5.D)
        info = get_platform_info()
        requires_elevation = any(command.startswith(p) for p in ("sudo ", "pkexec ", "doas ")) or (
            info.os_family == "windows" and "runas" in command.lower()
        )
        if requires_elevation and not info.is_admin_or_root:
            return ToolExecutionResult(
                tool_name=self.name,
                tool_call_id=tool_call_id,
                success=False,
                error="ELEVATION REQUIRED: This operation requires administrator/root privileges. The agent cannot receive or store sudo passwords. Please execute the command with elevation directly in the terminal.",
                stdout="",
                stderr="ELEVATION REQUIRED: Human privilege escalation required in terminal.",
                data={"needs_elevation": True, "command": command},
                permission_level=PermissionLevel.LEVEL_2_APPROVAL_REQUIRED,
            )

        # Run command
        output = self.runner.run(
            command=command,
            cwd=cwd,
            timeout_seconds=timeout,
        )

        success = output.exit_code == 0 and not output.timed_out
        error_msg = None
        if output.timed_out:
            error_msg = f"Command timed out after {timeout} seconds and was terminated"
        elif output.exit_code != 0:
            error_msg = f"Command exited with non-zero code {output.exit_code}"

        return ToolExecutionResult(
            tool_name=self.name,
            tool_call_id=tool_call_id,
            success=success,
            stdout=output.stdout,
            stderr=output.stderr,
            data={
                "exit_code": output.exit_code,
                "timed_out": output.timed_out,
                "command": command,
            },
            error=error_msg,
            duration_ms=output.duration_ms,
            permission_level=cmd_risk,
        )

    def _run(self, **kwargs) -> Any:
        pass  # Handled in execute() override
