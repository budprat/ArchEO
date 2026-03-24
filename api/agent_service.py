"""Agent service: boots MCP servers once at startup, streams SSE responses."""

import asyncio
import base64
import json
import logging
import shutil
from pathlib import Path
from typing import AsyncGenerator, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    SYSTEM_PROMPT,
    TOOLS_DIR,
    UPLOADS_DIR,
    VENV_PYTHON,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state — initialised once at startup
# ---------------------------------------------------------------------------
_mcp_client: Optional[MultiServerMCPClient] = None
_tools: list = []
_agent = None

# Shared temp dir for MCP tool outputs
MCP_TEMP_DIR = UPLOADS_DIR / "_mcp_temp"


# ---------------------------------------------------------------------------
# MCP server configuration
# ---------------------------------------------------------------------------

TOOL_SERVERS = ["Analysis", "Index", "Inversion", "Perception", "Statistics", "Archaeology"]


def get_mcp_server_configs() -> dict:
    """Build MCP server configs for all 6 tool servers."""
    MCP_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    configs: dict = {}
    for server_name in TOOL_SERVERS:
        script_path = str(Path(TOOLS_DIR) / f"{server_name}.py")
        configs[server_name] = {
            "command": VENV_PYTHON,
            "args": [script_path, "--temp_dir", str(MCP_TEMP_DIR)],
            "transport": "stdio",
        }
    return configs


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

async def startup_mcp() -> None:
    """Boot MCP client, load tools, create agent. Called once at startup."""
    global _mcp_client, _tools, _agent

    logger.info("Starting MCP servers…")
    configs = get_mcp_server_configs()

    try:
        _mcp_client = MultiServerMCPClient(configs)
        _tools = await _mcp_client.get_tools()
        logger.info(f"Loaded {len(_tools)} tools from MCP servers.")
    except Exception as exc:
        logger.warning(f"MCP startup failed: {exc}. Agent will be unavailable.")
        _mcp_client = None
        _tools = []
        return

    llm = ChatOpenAI(
        api_key=OPENAI_API_KEY,
        model=OPENAI_MODEL,
        streaming=True,
    )

    _agent = create_react_agent(
        llm,
        tools=_tools,
        prompt=SYSTEM_PROMPT,
    )
    logger.info("ArchEO agent ready.")


async def shutdown_mcp() -> None:
    """Clean up MCP client resources."""
    global _mcp_client, _tools, _agent
    _mcp_client = None
    _tools = []
    _agent = None
    logger.info("MCP servers shut down.")


def get_mcp_status() -> dict:
    """Return current MCP/agent status."""
    return {
        "tools_loaded": len(_tools),
        "agent_ready": _agent is not None,
    }


# ---------------------------------------------------------------------------
# Message history helpers
# ---------------------------------------------------------------------------

def build_history(history: list[dict]) -> list:
    """Convert frontend HistoryEntry list to LangChain messages."""
    messages = []
    for entry in history:
        role = entry.get("role", "")
        content = entry.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


# ---------------------------------------------------------------------------
# Vision input helper
# ---------------------------------------------------------------------------

def encode_thumbnail(file_id: str) -> Optional[str]:
    """Return base64-encoded PNG thumbnail for GPT-5.4 vision, or None."""
    thumb_path = UPLOADS_DIR / file_id / "thumbnail.png"
    if not thumb_path.exists():
        return None
    with open(thumb_path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("utf-8")


def _build_user_message(message: str, file_id: Optional[str]) -> HumanMessage:
    """Build a HumanMessage, embedding the thumbnail image when available."""
    if not file_id:
        return HumanMessage(content=message)

    b64 = encode_thumbnail(file_id)
    if not b64:
        return HumanMessage(content=message)

    # Multimodal content block for OpenAI vision
    return HumanMessage(
        content=[
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            },
            {"type": "text", "text": message},
        ]
    )


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

async def stream_agent_response(
    message: str,
    file_id: Optional[str],
    history: list[dict],
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE-formatted strings."""

    if _agent is None:
        yield _sse("error", {"message": "Agent not ready. MCP servers may have failed to start."})
        yield _sse("done", {})
        return

    # Determine upload results dir for copying tool outputs
    results_dir: Optional[Path] = None
    if file_id:
        results_dir = UPLOADS_DIR / file_id / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

    lc_history = build_history(history)
    user_msg = _build_user_message(message, file_id)
    all_messages = lc_history + [user_msg]

    final_text_parts: list[str] = []

    try:
        async for event in _agent.astream_events(
            {"messages": all_messages}, version="v2"
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    if isinstance(content, list):
                        # Multimodal chunks
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                final_text_parts.append(block["text"])
                                yield _sse("thinking", {"text": block["text"]})
                    else:
                        final_text_parts.append(str(content))
                        yield _sse("thinking", {"text": str(content)})

            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown_tool")
                tool_input = event.get("data", {}).get("input", {})
                yield _sse("tool_call", {"tool": tool_name, "input": tool_input})

            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown_tool")
                tool_output = event.get("data", {}).get("output")
                output_str = str(tool_output) if tool_output is not None else ""

                # Copy any result images produced in MCP_TEMP_DIR to upload results dir
                result_images: list[str] = []
                if results_dir is not None:
                    result_images = _copy_mcp_results(results_dir, tool_name)

                yield _sse(
                    "tool_result",
                    {
                        "tool": tool_name,
                        "output": output_str[:2000],  # truncate for SSE
                        "result_images": result_images,
                    },
                )

    except Exception as exc:
        logger.exception("Agent stream error")
        yield _sse("error", {"message": str(exc)})
        yield _sse("done", {})
        return

    # Emit the complete assembled message
    final_text = "".join(final_text_parts)
    if final_text:
        yield _sse("message", {"text": final_text})

    yield _sse("done", {})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _copy_mcp_results(results_dir: Path, tool_name: str) -> list[str]:
    """Copy new PNG/TIFF files from MCP_TEMP_DIR to results_dir.

    Returns list of relative paths suitable for /api/results/{file_id}/ URLs.
    """
    copied: list[str] = []
    if not MCP_TEMP_DIR.exists():
        return copied

    for src in MCP_TEMP_DIR.iterdir():
        if src.suffix.lower() in {".png", ".tif", ".tiff", ".jpg", ".jpeg"}:
            dest = results_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)
                copied.append(src.name)

    return copied
