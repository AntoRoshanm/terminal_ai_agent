"""
Tests for Model Context Protocol (MCP) Client, Protocol, Web Search Server, and Tool Wrapping
"""

from unittest.mock import MagicMock
from app.mcp.client import MCPClient
from app.mcp.manager import MCPManager, MCPToolWrapper
from app.mcp.protocol import JSONRPCError, JSONRPCRequest, JSONRPCResponse, MCPServerConfig, MCPToolDefinition
from app.mcp.servers.web_search_server import handle_request
from app.tools.registry import ToolRegistry


def test_mcp_protocol_serialization():
    req = JSONRPCRequest(id=1, method="tools/call", params={"name": "test_tool", "arguments": {}})
    req_json = req.model_dump_json()
    assert '"jsonrpc":"2.0"' in req_json
    assert '"method":"tools/call"' in req_json

    resp = JSONRPCResponse(id=1, result={"status": "ok"})
    assert resp.result == {"status": "ok"}
    assert resp.error is None

    err_resp = JSONRPCResponse(id=1, error=JSONRPCError(code=-32601, message="Method not found"))
    assert err_resp.error.code == -32601


def test_mcp_tool_wrapper_schema_and_execution():
    mock_client = MagicMock(spec=MCPClient)
    mock_client.call_tool.return_value = {"content": [{"type": "text", "text": "Search results for Windows"}]}

    wrapper = MCPToolWrapper(
        server_name="web-search",
        client=mock_client,
        tool_name="search",
        description="Search web",
        schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )

    assert wrapper.name == "mcp_web-search_search"
    assert wrapper.get_parameters_schema()["properties"]["query"]["type"] == "string"

    res = wrapper.execute(tool_call_id="call_mcp", query="Windows")
    assert res.success is True
    assert "Search results for Windows" in res.stdout
    mock_client.call_tool.assert_called_once_with("search", {"query": "Windows"})


def test_mcp_web_search_server_protocol_handlers():
    # 1. Initialize
    init_resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init_resp["result"]["serverInfo"]["name"] == "duckduckgo-web-search"
    assert "tools" in init_resp["result"]["capabilities"]

    # 2. List tools
    tools_resp = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
    assert "web_search" in tool_names
    assert "fetch_web_content" in tool_names

    # 3. Call unknown tool
    err_resp = handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "unknown_tool", "arguments": {}}})
    assert "error" in err_resp
    assert err_resp["error"]["code"] == -32601


def test_mcp_manager_add_and_stop():
    manager = MCPManager()
    cfg = MCPServerConfig(name="test_server", command="python", args=["-c", "print('hello')"], enabled=False)
    manager.add_server(cfg)
    assert "test_server" in manager.clients

    manager.stop_all()
    assert len(manager.clients) == 0


import sys

def test_mcp_manager_live_web_search_server_lifecycle():
    registry = ToolRegistry()
    manager = MCPManager()
    cfg = MCPServerConfig(
        name="web-search",
        command=sys.executable,
        args=["-m", "app.mcp.servers.web_search_server"],
        enabled=True,
    )
    manager.add_server(cfg)
    count = manager.start_all(registry)
    try:
        assert count >= 2
        assert registry.get("mcp_web-search_web_search") is not None
        assert registry.get("mcp_web-search_fetch_web_content") is not None
    finally:
        manager.stop_all()


def test_mcp_manager_live_document_servers_lifecycle():
    registry = ToolRegistry()
    manager = MCPManager()
    count = manager.start_all(registry)
    try:
        assert count >= 3
        assert registry.get("mcp_pdf-generator_create_pdf") is not None
        assert registry.get("mcp_docx-generator_create_docx") is not None
        assert registry.get("mcp_pptx-generator_create_pptx") is not None
    finally:
        manager.stop_all()

