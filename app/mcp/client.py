"""
Stdio Model Context Protocol (MCP) Client
"""

import json
import os
import shutil
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional
from app.logging import logger
from app.mcp.protocol import JSONRPCError, JSONRPCRequest, JSONRPCResponse, MCPServerConfig, MCPToolDefinition


class MCPClient:
    """Client for communicating with an external MCP server over stdio using JSON-RPC 2.0."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._initialized = False

    def start(self) -> None:
        """Start the MCP server subprocess."""
        if self.process is not None and self.process.poll() is None:
            return

        executable = self.config.command
        if executable in ("python", "python3") and (shutil.which(executable) is None or sys.executable):
            executable = sys.executable

        cmd = [executable] + self.config.args
        env = os.environ.copy()
        env.update(self.config.env)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                bufsize=1,
            )
            logger.info("Started MCP server '%s' (PID %s)", self.config.name, self.process.pid)
            self._initialize_handshake()
        except Exception as e:
            logger.error("Failed to start MCP server '%s': %s", self.config.name, e)
            raise RuntimeError(f"Failed to start MCP server '{self.config.name}': {e}")

    def _initialize_handshake(self) -> None:
        """Perform MCP initialize handshake."""
        init_params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {},
            },
            "clientInfo": {
                "name": "WindowsAIAgent",
                "version": "0.1.0",
            },
        }
        res = self._send_request("initialize", init_params)
        if res.error:
            raise RuntimeError(f"MCP Initialize failed for '{self.config.name}': {res.error.message}")
        self._initialized = True

    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> JSONRPCResponse:
        """Send a JSON-RPC 2.0 request over stdin and await response from stdout."""
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError(f"MCP server '{self.config.name}' is not running.")

        with self._lock:
            self._request_id += 1
            req_id = self._request_id
            req = JSONRPCRequest(id=req_id, method=method, params=params)
            req_str = req.model_dump_json() + "\n"

            try:
                assert self.process.stdin is not None
                self.process.stdin.write(req_str)
                self.process.stdin.flush()

                # Read line response
                assert self.process.stdout is not None
                line = self.process.stdout.readline()
                if not line:
                    stderr_out = self.process.stderr.read() if self.process.stderr else ""
                    raise RuntimeError(f"Empty response from MCP server '{self.config.name}'. Stderr: {stderr_out}")

                data = json.loads(line)
                return JSONRPCResponse(**data)
            except Exception as e:
                logger.error("Error communicating with MCP server '%s': %s", self.config.name, e)
                return JSONRPCResponse(
                    id=req_id,
                    error=JSONRPCError(code=-32000, message=str(e)),
                )

    def list_tools(self) -> List[MCPToolDefinition]:
        """Query available tools from the MCP server."""
        res = self._send_request("tools/list", {})
        if res.error:
            logger.error("Failed to list tools from MCP server '%s': %s", self.config.name, res.error.message)
            return []

        result = res.result or {}
        raw_tools = result.get("tools", [])
        tools = []
        for rt in raw_tools:
            try:
                tools.append(MCPToolDefinition(
                    name=rt.get("name", ""),
                    description=rt.get("description", ""),
                    inputSchema=rt.get("inputSchema", {"type": "object", "properties": {}}),
                ))
            except Exception as e:
                logger.warning("Error parsing tool schema from MCP server '%s': %s", self.config.name, e)
        return tools

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via the MCP server."""
        res = self._send_request("tools/call", {"name": tool_name, "arguments": arguments})
        if res.error:
            raise RuntimeError(f"MCP tool '{tool_name}' failed: {res.error.message}")
        return res.result or {}

    def stop(self) -> None:
        """Terminate the MCP server subprocess."""
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            finally:
                self.process = None
                self._initialized = False
