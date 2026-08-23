"""
MCP Server Manager and Dynamic Tool Wrapper
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.logging import logger
from app.mcp.client import MCPClient
from app.mcp.protocol import MCPServerConfig
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


class MCPToolWrapper(BaseTool):
    """Wrapper that adapts an MCP server tool into a native BaseTool."""

    def __init__(
        self,
        server_name: str,
        client: MCPClient,
        tool_name: str,
        description: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        permission_level: Optional[PermissionLevel] = None,
    ):
        self.server_name = server_name
        self.client = client
        self.name = f"mcp_{server_name}_{tool_name}"
        self.raw_tool_name = tool_name
        self.description = description or f"MCP tool from server '{server_name}'"
        self.category = "mcp"
        if permission_level is not None:
            self.permission_level = permission_level
        elif any(verb in tool_name.lower() for verb in ["create", "write", "generate", "delete", "remove", "edit"]):
            self.permission_level = PermissionLevel.LEVEL_2_APPROVAL_REQUIRED
        else:
            self.permission_level = PermissionLevel.LEVEL_1_LOW_RISK
        self._schema = schema or {"type": "object", "properties": {}}

    def get_parameters_schema(self) -> Dict[str, Any]:
        return self._schema

    def _run(self, **kwargs: Any) -> Any:
        # B.38 Resource Safety Gate & B.39 Path Canonicalization
        file_path = kwargs.get("file_path") or kwargs.get("path")
        if file_path and any(v in self.raw_tool_name.lower() for v in ["create", "write", "generate"]):
            from app.tools.filesystem.safety import PathSafety
            safety = PathSafety()
            canon_path = safety.canonicalize_path(file_path)
            content_str = str(kwargs.get("content", ""))
            safety.check_write_resource_safety(str(canon_path), estimated_size_bytes=max(1024, len(content_str.encode("utf-8"))))
            kwargs["file_path"] = str(canon_path)

        # Directive B.43: Document generation tools require explicit content passed from upstream generation
        if any(v in self.raw_tool_name.lower() for v in ["create_pdf", "create_docx", "create_pptx", "generate_pdf", "generate_docx"]):
            content_val = str(kwargs.get("content") or "").strip()
            if not content_val:
                raise ValueError(
                    f"Tool '{self.raw_tool_name}' requires explicit 'content' parameter. "
                    "Decoupled content generation (Directive B.43) requires content to be synthesized upstream."
                )

        result = self.client.call_tool(self.raw_tool_name, kwargs)
        if isinstance(result, dict) and "content" in result and isinstance(result["content"], list):
            texts = [
                c.get("text", "")
                for c in result["content"]
                if isinstance(c, dict) and c.get("type") == "text"
            ]
            if texts:
                return "\n\n".join(texts)
        return result


class MCPManager:
    """Manages active MCP client connections and integrates them into ToolRegistry."""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or Path("configs/mcp_servers.json")
        self.clients: Dict[str, MCPClient] = {}
        self.wrapped_tools: List[MCPToolWrapper] = []

    def load_configs(self) -> List[MCPServerConfig]:
        """Load configured MCP servers from JSON file."""
        if not self.config_file.is_file():
            return []

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            servers = []
            for s_data in data.get("mcpServers", {}).values():
                servers.append(MCPServerConfig(**s_data))
            return servers
        except Exception as e:
            logger.error("Failed to load MCP server configs from %s: %s", self.config_file, e)
            return []

    def add_server(self, config: MCPServerConfig) -> None:
        """Add and start an MCP server client."""
        client = MCPClient(config)
        self.clients[config.name] = client

    def start_all(self, registry: Optional[ToolRegistry] = None) -> int:
        """Start all configured enabled servers and register their tools."""
        configs = self.load_configs()
        for cfg in configs:
            if cfg.enabled and cfg.name not in self.clients:
                self.add_server(cfg)

        registered_count = 0
        for server_name, client in self.clients.items():
            try:
                client.start()
                tools = client.list_tools()
                for t in tools:
                    wrapper = MCPToolWrapper(
                        server_name=server_name,
                        client=client,
                        tool_name=t.name,
                        description=t.description,
                        schema=t.inputSchema,
                    )
                    self.wrapped_tools.append(wrapper)
                    if registry:
                        registry.register(wrapper)
                    registered_count += 1
                logger.info("Registered %d tools from MCP server '%s'", len(tools), server_name)
            except Exception as e:
                logger.error("Failed to start/register MCP server '%s': %s", server_name, e)

        return registered_count

    def stop_all(self) -> None:
        """Stop all active MCP client subprocesses."""
        for name, client in self.clients.items():
            try:
                client.stop()
            except Exception as e:
                logger.warning("Error stopping MCP client '%s': %s", name, e)
        self.clients.clear()
        self.wrapped_tools.clear()
