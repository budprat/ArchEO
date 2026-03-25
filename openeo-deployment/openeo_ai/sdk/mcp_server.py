# ABOUTME: MCP (Model Context Protocol) server for tool integration.
# Provides standardized tool interface for AI model integration.

"""
MCP Server for OpenEO AI.

Implements the Model Context Protocol for standardized tool integration:
- Tool listing and schema
- Tool execution
- Resource access
- WebSocket transport

Reference: https://modelcontextprotocol.io/
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for MCP tools."""
    READ = "read"  # Read-only operations
    WRITE = "write"  # Can modify data
    EXECUTE = "execute"  # Can execute processes
    ADMIN = "admin"  # Full access


@dataclass
class MCPTool:
    """Definition of an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Awaitable[Any]]
    permission_level: PermissionLevel = PermissionLevel.READ
    category: str = "general"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "permissionLevel": self.permission_level.value,
                "category": self.category,
                "tags": self.tags,
            }
        }


@dataclass
class MCPResource:
    """Definition of an MCP resource."""
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


class MCPMessage:
    """MCP JSON-RPC message wrapper."""

    @staticmethod
    def request(method: str, params: Optional[Dict] = None, id: Optional[str] = None) -> Dict:
        """Create a JSON-RPC request."""
        msg = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            msg["params"] = params
        if id:
            msg["id"] = id
        return msg

    @staticmethod
    def response(id: str, result: Any) -> Dict:
        """Create a JSON-RPC response."""
        return {
            "jsonrpc": "2.0",
            "id": id,
            "result": result,
        }

    @staticmethod
    def error(id: Optional[str], code: int, message: str, data: Any = None) -> Dict:
        """Create a JSON-RPC error response."""
        error_obj = {
            "code": code,
            "message": message,
        }
        if data:
            error_obj["data"] = data
        return {
            "jsonrpc": "2.0",
            "id": id,
            "error": error_obj,
        }


# Standard MCP error codes
class MCPError:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


class MCPServer:
    """
    MCP Server implementation.

    Handles:
    - initialize: Protocol handshake
    - tools/list: List available tools
    - tools/call: Execute a tool
    - resources/list: List available resources
    - resources/read: Read a resource

    Usage:
        server = MCPServer()
        server.register_tool(MCPTool(...))

        # Handle incoming message
        response = await server.handle_message(message)
    """

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "openeo-ai"
    SERVER_VERSION = "1.0.0"

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._initialized = False
        self._client_info: Optional[Dict] = None

    def register_tool(self, tool: MCPTool) -> None:
        """Register a tool with the server."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered MCP tool: {tool.name}")

    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def register_resource(self, resource: MCPResource) -> None:
        """Register a resource."""
        self._resources[resource.uri] = resource
        logger.debug(f"Registered MCP resource: {resource.uri}")

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools."""
        return [tool.to_dict() for tool in self._tools.values()]

    def list_resources(self) -> List[Dict[str, Any]]:
        """List all resources."""
        return [resource.to_dict() for resource in self._resources.values()]

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming MCP message.

        Args:
            message: JSON-RPC message

        Returns:
            JSON-RPC response
        """
        # Validate JSON-RPC format
        if "jsonrpc" not in message or message["jsonrpc"] != "2.0":
            return MCPMessage.error(
                message.get("id"),
                MCPError.INVALID_REQUEST,
                "Invalid JSON-RPC version"
            )

        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        if not method:
            return MCPMessage.error(msg_id, MCPError.INVALID_REQUEST, "Missing method")

        # Route to handler
        try:
            if method == "initialize":
                result = await self._handle_initialize(params)
            elif method == "tools/list":
                result = await self._handle_tools_list(params)
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "resources/list":
                result = await self._handle_resources_list(params)
            elif method == "resources/read":
                result = await self._handle_resources_read(params)
            elif method == "ping":
                result = {"pong": True}
            else:
                return MCPMessage.error(
                    msg_id,
                    MCPError.METHOD_NOT_FOUND,
                    f"Unknown method: {method}"
                )

            return MCPMessage.response(msg_id, result)

        except Exception as e:
            logger.error(f"MCP handler error: {e}")
            return MCPMessage.error(
                msg_id,
                MCPError.INTERNAL_ERROR,
                str(e)
            )

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        self._client_info = params.get("clientInfo", {})
        self._initialized = True

        logger.info(f"MCP initialized with client: {self._client_info.get('name', 'unknown')}")

        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "serverInfo": {
                "name": self.SERVER_NAME,
                "version": self.SERVER_VERSION,
            },
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"listChanged": True, "subscribe": False},
            },
        }

    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        cursor = params.get("cursor")
        # For now, return all tools (pagination can be added later)
        return {
            "tools": self.list_tools(),
        }

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name required")

        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Execute tool handler
        try:
            result = await tool.handler(arguments)

            # Format response
            if isinstance(result, dict) and "content" in result:
                return result
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        }
                    ]
                }

        except Exception as e:
            logger.error(f"Tool execution error: {tool_name}: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": str(e)})
                    }
                ],
                "isError": True,
            }

    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        return {
            "resources": self.list_resources(),
        }

    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI required")

        resource = self._resources.get(uri)
        if not resource:
            raise ValueError(f"Unknown resource: {uri}")

        # Return resource contents (subclass can override for actual content)
        return {
            "contents": [
                {
                    "uri": resource.uri,
                    "mimeType": resource.mime_type,
                    "text": json.dumps(resource.to_dict()),
                }
            ]
        }


class MCPWebSocketServer(MCPServer):
    """
    MCP Server with WebSocket transport.

    Usage:
        server = MCPWebSocketServer()
        server.register_tools_from_openeo()

        # In WebSocket handler
        async def ws_handler(websocket):
            await server.handle_websocket(websocket)
    """

    def __init__(self):
        super().__init__()
        self._connections: Dict[str, Any] = {}

    async def handle_websocket(self, websocket, path: str = None):
        """
        Handle WebSocket connection for MCP.

        Args:
            websocket: WebSocket connection
            path: Optional path
        """
        conn_id = str(uuid.uuid4())
        self._connections[conn_id] = websocket

        logger.info(f"MCP WebSocket connected: {conn_id}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    response = await self.handle_message(data)
                    await websocket.send(json.dumps(response))
                except json.JSONDecodeError:
                    error = MCPMessage.error(
                        None,
                        MCPError.PARSE_ERROR,
                        "Invalid JSON"
                    )
                    await websocket.send(json.dumps(error))
        except Exception as e:
            logger.error(f"MCP WebSocket error: {e}")
        finally:
            del self._connections[conn_id]
            logger.info(f"MCP WebSocket disconnected: {conn_id}")

    async def broadcast(self, method: str, params: Dict = None):
        """Broadcast notification to all connections."""
        message = MCPMessage.request(method, params)
        for websocket in self._connections.values():
            try:
                await websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

    def register_tools_from_openeo(self):
        """Register all OpenEO AI tools as MCP tools."""
        from ..tools import (
            create_openeo_tools,
            create_job_tools,
            create_viz_tools,
            create_geoai_tools,
            create_udf_tools,
        )
        from ..sdk.client import TOOL_DEFINITIONS

        # Create tool instances
        openeo_tools = create_openeo_tools(None)
        job_tools = create_job_tools(None)
        viz_tools = create_viz_tools(None)
        geoai_tools = create_geoai_tools(None)
        udf_tools = create_udf_tools(None)

        all_tools = {
            **openeo_tools,
            **job_tools,
            **viz_tools,
            **geoai_tools,
            **udf_tools,
        }

        # Register each tool
        for tool_def in TOOL_DEFINITIONS:
            name = tool_def["name"]
            if name in all_tools:
                self.register_tool(MCPTool(
                    name=name,
                    description=tool_def["description"],
                    input_schema=tool_def["input_schema"],
                    handler=all_tools[name],
                    permission_level=self._infer_permission_level(name),
                    category=self._infer_category(name),
                ))

        logger.info(f"Registered {len(self._tools)} MCP tools from OpenEO AI")

    def _infer_permission_level(self, tool_name: str) -> PermissionLevel:
        """Infer permission level from tool name."""
        if tool_name.startswith("openeo_list") or tool_name.startswith("openeo_get"):
            return PermissionLevel.READ
        if tool_name.startswith("openeo_create") or tool_name.startswith("openeo_start"):
            return PermissionLevel.EXECUTE
        if "delete" in tool_name:
            return PermissionLevel.ADMIN
        if tool_name.startswith("viz_"):
            return PermissionLevel.READ
        if tool_name.startswith("geoai_"):
            return PermissionLevel.EXECUTE
        if tool_name.startswith("udf_"):
            return PermissionLevel.EXECUTE
        return PermissionLevel.WRITE

    def _infer_category(self, tool_name: str) -> str:
        """Infer category from tool name."""
        if tool_name.startswith("openeo_"):
            return "openeo"
        if tool_name.startswith("viz_"):
            return "visualization"
        if tool_name.startswith("geoai_"):
            return "geoai"
        if tool_name.startswith("udf_"):
            return "udf"
        return "general"


# Module-level singleton
_mcp_server: Optional[MCPWebSocketServer] = None


def get_mcp_server() -> MCPWebSocketServer:
    """Get the global MCP server singleton."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPWebSocketServer()
        _mcp_server.register_tools_from_openeo()
    return _mcp_server
