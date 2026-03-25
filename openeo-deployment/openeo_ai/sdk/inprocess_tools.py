"""In-process MCP server for OpenEO tools using create_sdk_mcp_server().

Replaces the subprocess-based mcp_stdio_server.py with an in-process MCP
server that runs within the same Python process. This eliminates:
  - Subprocess spawning overhead per session
  - JSON-RPC serialization/deserialization latency
  - Process management complexity

All 22 tool handlers are reused from openeo_ai/tools/*.py — no logic
duplication. Tool schemas come from TOOL_DEFINITIONS in client.py.

Usage:
    from openeo_ai.sdk.inprocess_tools import create_openeo_mcp_server
    config = create_openeo_mcp_server()
    # Returns McpSdkServerConfig for ClaudeAgentOptions.mcp_servers
"""

import json
import traceback
import sys
from typing import Any, Dict

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server

from openeo_ai.sdk.client import TOOL_DEFINITIONS, OpenEOAIConfig
from openeo_ai.tools.openeo_tools import create_openeo_tools
from openeo_ai.tools.job_tools import create_job_tools
from openeo_ai.tools.geoai_tools import create_geoai_tools
from openeo_ai.tools.viz_tools import create_viz_tools
from openeo_ai.tools.saved_jobs_tools import create_saved_jobs_tools


def _create_all_handlers(config: OpenEOAIConfig) -> Dict[str, Any]:
    """Create all tool handler functions from the 5 tool modules.

    Returns:
        Dict mapping tool_name -> async handler(args) -> dict
    """
    handlers: Dict[str, Any] = {}
    handlers.update(create_openeo_tools(config))
    handlers.update(create_job_tools(config))
    handlers.update(create_geoai_tools(config))
    handlers.update(create_viz_tools(config))
    handlers.update(create_saved_jobs_tools(config))
    return handlers


def _wrap_handler(name: str, handler):
    """Wrap a tool handler with error handling matching mcp_stdio_server.py."""
    async def safe_handler(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await handler(args)
            # Handlers return {"content": [{"type": "text", "text": "..."}]}
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
    return safe_handler


def create_openeo_mcp_server(config: OpenEOAIConfig = None):
    """Create an in-process MCP server with all 22 OpenEO tools.

    Args:
        config: OpenEOAIConfig instance. Created from env vars if None.

    Returns:
        McpSdkServerConfig dict for use in ClaudeAgentOptions.mcp_servers
    """
    if config is None:
        config = OpenEOAIConfig()

    # Build all handlers from existing tool modules
    handlers = _create_all_handlers(config)

    # Build SdkMcpTool objects from TOOL_DEFINITIONS + handlers
    tools = []
    for td in TOOL_DEFINITIONS:
        name = td["name"]
        if name not in handlers:
            print(f"[InProcess MCP] Warning: no handler for tool '{name}'", file=sys.stderr)
            continue
        tools.append(SdkMcpTool(
            name=name,
            description=td["description"],
            input_schema=td["input_schema"],
            handler=_wrap_handler(name, handlers[name]),
        ))

    # AskUserQuestion — interactive clarification tool.
    # The can_use_tool callback in claude_sdk_bridge intercepts this tool
    # call, routes questions to the frontend, waits for answers, then
    # injects them into updated_input. The handler simply returns the answers.
    async def ask_user_handler(args: Dict[str, Any]) -> Dict[str, Any]:
        answers = args.get("answers", {})
        return {"content": [{"type": "text", "text": json.dumps(answers)}]}

    tools.append(SdkMcpTool(
        name="AskUserQuestion",
        description=(
            "Ask the user clarification questions before running expensive operations. "
            "Use when the query is ambiguous about location, time range, collection, "
            "bands, or analysis parameters. Provide 2-4 clear options per question."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "The question to ask the user"},
                            "header": {"type": "string", "description": "Short label (max 12 chars)"},
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["label", "description"],
                                },
                            },
                            "multiSelect": {"type": "boolean", "default": False},
                        },
                        "required": ["question", "header", "options"],
                    },
                },
            },
            "required": ["questions"],
        },
        handler=ask_user_handler,
    ))

    print(f"[InProcess MCP] Registered {len(tools)} tools", file=sys.stderr)
    return create_sdk_mcp_server("openeo", "1.0.0", tools)
