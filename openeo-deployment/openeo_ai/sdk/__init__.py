# ABOUTME: SDK module for Claude API integration with OpenEO.
# Provides client, session manager, permission callbacks, and MCP server.

"""SDK module for Claude integration."""

from .client import OpenEOAIClient, OpenEOAIConfig
from .sessions import SessionManager
from .permissions import openeo_permission_callback
from .mcp_server import (
    MCPServer,
    MCPWebSocketServer,
    MCPTool,
    MCPResource,
    PermissionLevel,
    get_mcp_server,
)
from .mcp_lifecycle import (
    MCPLifecycleMonitor,
    LifecycleEvent,
    ToolMetrics,
    get_lifecycle_monitor,
    wrap_tool_with_monitoring,
)
from .claude_sdk_bridge import ClaudeSDKBridge
from .viz_extractor import extract_visualization

__all__ = [
    "OpenEOAIClient",
    "OpenEOAIConfig",
    "SessionManager",
    "openeo_permission_callback",
    "MCPServer",
    "MCPWebSocketServer",
    "MCPTool",
    "MCPResource",
    "PermissionLevel",
    "get_mcp_server",
    "MCPLifecycleMonitor",
    "LifecycleEvent",
    "ToolMetrics",
    "get_lifecycle_monitor",
    "wrap_tool_with_monitoring",
    "ClaudeSDKBridge",
    "extract_visualization",
]
