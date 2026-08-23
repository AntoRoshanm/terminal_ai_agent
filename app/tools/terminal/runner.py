"""
Controlled Cross-Platform Terminal Command Runner
"""

import os
import signal
import subprocess
import time
from typing import NamedTuple, Optional
from app.platform.detect import get_platform_info


class CommandOutput(NamedTuple):
    """Output structure of a completed command execution."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


class CommandRunner:
    """Spawns and monitors shell processes with timeout and process-tree termination."""

    def __init__(self, default_shell: Optional[str] = None):
        info = get_platform_info()
        self.default_shell = default_shell or info.shell_default

    def _decode_output(self, data: bytes) -> str:
        """Decode process byte stream with fallback encodings."""
        if not data:
            return ""
        for encoding in ("utf-8", "cp1252", "cp437", "latin1"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def run(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout_seconds: int = 30,
        shell_type: Optional[str] = None,
    ) -> CommandOutput:
        """Execute a command in PowerShell/CMD (Windows) or Bash/Sh (Linux) with strict timeout."""
        target_shell = (shell_type or self.default_shell).lower()
        working_dir = cwd or os.getcwd()
        info = get_platform_info()

        if info.os_family == "windows":
            if target_shell in ("powershell", "pwsh"):
                args = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ]
            else:
                args = ["cmd.exe", "/c", command]
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            preexec_fn = None
        else:
            shell_bin = target_shell if target_shell in ("bash", "zsh", "sh") else "sh"
            args = [shell_bin, "-c", command]
            creationflags = 0
            preexec_fn = os.setsid if hasattr(os, "setsid") else None

        start_time = time.time()
        timed_out = False

        try:
            process = subprocess.Popen(
                args,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                preexec_fn=preexec_fn,
            )

            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_seconds)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                if info.os_family == "windows":
                    subprocess.run(
                        ["taskkill.exe", "/F", "/T", "/PID", str(process.pid)],
                        capture_output=True,
                    )
                else:
                    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        except Exception:
                            process.kill()
                    else:
                        process.kill()
                stdout_bytes, stderr_bytes = process.communicate()
                exit_code = -1

            duration_ms = int((time.time() - start_time) * 1000)
            return CommandOutput(
                command=command,
                exit_code=exit_code,
                stdout=self._decode_output(stdout_bytes),
                stderr=self._decode_output(stderr_bytes),
                duration_ms=duration_ms,
                timed_out=timed_out,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return CommandOutput(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                duration_ms=duration_ms,
                timed_out=False,
            )
