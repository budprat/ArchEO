#!/usr/bin/env python3
"""Standalone MCP stdio server for OpenEO tools.

This script implements the MCP (Model Context Protocol) over stdio, speaking
JSON-RPC 2.0. It is spawned as a subprocess by the Claude CLI when configured
via McpStdioServerConfig.

It imports and delegates to our existing tool handler functions (the same ones
used by the direct Anthropic API path), so tool behavior is identical.

Usage (by Claude CLI, not directly):
    python -m openeo_ai.sdk.mcp_stdio_server
"""

import asyncio
import json
import os
import sys
import traceback
from typing import Any, Dict, List, Optional


# Ensure the project root is on the path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def _build_tool_schemas() -> List[Dict[str, Any]]:
    """Build MCP tool list from TOOL_DEFINITIONS."""
    from openeo_ai.sdk.client import TOOL_DEFINITIONS
    tools = []
    for td in TOOL_DEFINITIONS:
        tools.append({
            "name": td["name"],
            "description": td["description"],
            "inputSchema": td["input_schema"],
        })
    return tools


def _create_handlers() -> Dict[str, Any]:
    """Create all tool handler functions."""
    from openeo_ai.sdk.client import OpenEOAIConfig

    config = OpenEOAIConfig()

    from openeo_ai.tools.openeo_tools import create_openeo_tools
    from openeo_ai.tools.job_tools import create_job_tools
    from openeo_ai.tools.geoai_tools import create_geoai_tools
    from openeo_ai.tools.viz_tools import create_viz_tools
    from openeo_ai.tools.saved_jobs_tools import create_saved_jobs_tools

    handlers: Dict[str, Any] = {}
    handlers.update(create_openeo_tools(config))
    handlers.update(create_job_tools(config))
    handlers.update(create_geoai_tools(config))
    handlers.update(create_viz_tools(config))
    handlers.update(create_saved_jobs_tools(config))
    return handlers


async def handle_call_tool(
    handlers: Dict[str, Any],
    name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a tool and return MCP-formatted result."""
    if name not in handlers:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"})}],
            "isError": True,
        }

    try:
        result = await handlers[name](arguments)

        # Handlers return {"content": [{"type": "text", "text": "..."}]} format
        if isinstance(result, dict) and "content" in result:
            return result

        # Wrap unexpected formats
        text = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
        return {"content": [{"type": "text", "text": text}]}

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {
            "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
            "isError": True,
        }


async def handle_jsonrpc(
    msg: Dict[str, Any],
    tool_schemas: List[Dict[str, Any]],
    handlers: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Handle a single JSON-RPC message and return a response (or None for notifications)."""
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "openeo", "version": "1.0.0"},
            },
        }

    elif method == "notifications/initialized":
        # Notification — no response
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": tool_schemas},
        }

    elif method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = await handle_call_tool(handlers, name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


async def main():
    """Main loop: read JSON-RPC from stdin, write responses to stdout."""
    print("[MCP Server] Starting OpenEO MCP stdio server...", file=sys.stderr)

    # Initialize tools
    tool_schemas = _build_tool_schemas()
    handlers = _create_handlers()
    print(f"[MCP Server] Registered {len(tool_schemas)} tools", file=sys.stderr)

    # Read from stdin line by line
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break  # EOF

        line = line.decode("utf-8").strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stderr.write(f"[MCP Server] Invalid JSON: {line[:200]}\n")
            continue

        response = await handle_jsonrpc(msg, tool_schemas, handlers)

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
