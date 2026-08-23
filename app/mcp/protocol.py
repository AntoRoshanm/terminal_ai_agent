"""
Model Context Protocol (MCP) Data Models and JSON-RPC 2.0 Types
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request Object."""
    jsonrpc: str = "2.0"
    id: Union[int, str]
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error Object."""
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response Object."""
    jsonrpc: str = "2.0"
    id: Optional[Union[int, str]] = None
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None


class MCPToolDefinition(BaseModel):
    """Schema of a tool exposed by an MCP Server."""
    name: str
    description: Optional[str] = None
    inputSchema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class MCPServerConfig(BaseModel):
    """Configuration definition for an external MCP server."""
    name: str
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
