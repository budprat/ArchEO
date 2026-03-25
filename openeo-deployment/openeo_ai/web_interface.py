# ABOUTME: Enhanced web interface for OpenEO AI Assistant with researcher-focused features.
# Includes workflow panels, suggestion chips, export capabilities, and quality metrics.

"""
OpenEO AI Enhanced Web Interface

Production-ready chat interface with:
- Natural language workflow generation
- Process graph visualization
- Quality metrics dashboard
- Export capabilities (notebooks, process graphs)
- Workflow history and session management
- Sustainability metrics
"""

import asyncio
import json
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .sdk.client import OpenEOAIClient, OpenEOAIConfig, TOOL_DEFINITIONS
from .visualization.maps import MapComponent


app = FastAPI(title="OpenEO AI Assistant", version="0.2.0")

# Add rate limiting middleware: 20 requests/minute per IP
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from openeo_app.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, max_requests=20, window_seconds=60)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track server start time for uptime calculation
_SERVER_START_TIME = datetime.utcnow()


@app.on_event("shutdown")
async def _shutdown_sdk_bridge():
    """Disconnect all SDK clients on server shutdown to clean up MCP subprocesses."""
    if hasattr(app.state, "sdk_bridge"):
        print("[Shutdown] Disconnecting all SDK sessions...", flush=True)
        await app.state.sdk_bridge.disconnect_all()
        print("[Shutdown] All SDK sessions disconnected.", flush=True)

# Store active connections, sessions, and workflow history
connections: Dict[str, WebSocket] = {}
sessions: Dict[str, dict] = {}  # session_id -> {"messages": [...], "last_active": float}
workflow_history: Dict[str, List[dict]] = {}

# Session TTL: expire sessions inactive for more than 30 minutes
_SESSION_TTL_SECONDS = 1800  # 30 minutes
_SESSION_MAX_COUNT = 100  # Maximum concurrent sessions


def _cleanup_expired_sessions():
    """Remove expired sessions to free memory and prevent unbounded growth."""
    import time as _time
    now = _time.monotonic()
    expired = [
        sid for sid, sdata in sessions.items()
        if now - sdata.get("last_active", 0) > _SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del sessions[sid]
    if expired:
        print(f"[Session cleanup] Removed {len(expired)} expired sessions, {len(sessions)} remaining")


def _truncate_messages(msgs: list, max_tokens: int = 120000) -> list:
    """Truncate messages to stay within token limit."""
    def estimate_tokens(content) -> int:
        if isinstance(content, str):
            return max(len(content) * 10 // 25, 1)
        elif isinstance(content, list):
            total = 0
            for item in content:
                if isinstance(item, dict):
                    total += estimate_tokens(json.dumps(item) if 'tool_use_id' in item or 'type' in item else item.get("text", ""))
                else:
                    total += estimate_tokens(str(item))
            return total
        elif isinstance(content, dict):
            return estimate_tokens(json.dumps(content))
        return 0

    def truncate_tool_results(msg):
        content = msg.get("content")
        if not isinstance(content, list):
            return msg
        max_result_chars = 2000
        new_content = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                result_str = item.get("content", "")
                if isinstance(result_str, str) and len(result_str) > max_result_chars:
                    item = dict(item)
                    item["content"] = result_str[:max_result_chars] + "\n... [truncated]"
            new_content.append(item)
        return {**msg, "content": new_content}

    msgs = [truncate_tool_results(m) for m in msgs]
    total_tokens = sum(estimate_tokens(m.get("content", "")) for m in msgs)
    print(f"[WS] Message history: {len(msgs)} messages, ~{total_tokens} tokens")
    if total_tokens <= max_tokens:
        return msgs
    truncated = list(msgs)
    while len(truncated) > 4 and sum(estimate_tokens(m.get("content", "")) for m in truncated) > max_tokens:
        truncated.pop(0)
        while truncated and truncated[0].get("role") != "user":
            truncated.pop(0)
    print(f"[WS] Truncated to {len(truncated)} messages")
    return truncated


async def _run_query(message: str, session_id: str, websocket, client, app_state,
                     stop_event: asyncio.Event) -> None:
    """Execute a query (SDK or anthropic path) and stream results to WebSocket.

    Runs as an asyncio.Task so the caller can concurrently listen for stop messages.
    """
    import time

    _sdk_backend = os.environ.get("OPENEO_SDK_BACKEND", "anthropic")
    print(f"[_run_query] backend={_sdk_backend}, session={session_id}")

    if _sdk_backend == "claude_sdk":
        try:
            from .sdk.claude_sdk_bridge import ClaudeSDKBridge

            if not hasattr(app_state, "sdk_bridge"):
                app_state.sdk_bridge = ClaudeSDKBridge(config=client.config)
            bridge = app_state.sdk_bridge

            await bridge.query(
                prompt=message,
                websocket=websocket,
                session_id=session_id,
                stop_event=stop_event,
            )
        except Exception as e:
            print(f"[WS] SDK bridge error: {e}")
            import traceback
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "content": str(e)
            })
        return  # SDK path done

    # --- Anthropic path ---
    try:
        from .sdk.client import TOOL_DEFINITIONS
        import anthropic

        messages = sessions[session_id]["messages"]
        messages.append({"role": "user", "content": message})

        max_turns = 10
        turn = 0
        cumulative_tokens = 0
        max_token_budget = 80000
        tools_used_all = []  # Track all tools called across turns
        last_job_title = ""  # Track job title for saved results naming

        while turn < max_turns:
            if stop_event.is_set():
                break

            turn += 1
            print(f"[WS] Turn {turn}/{max_turns} (tokens used: {cumulative_tokens})")

            if turn == 1:
                thinking_id = str(uuid.uuid4())
                await websocket.send_json({
                    "type": "thinking",
                    "thinking_id": thinking_id,
                    "thinking_type": "analyzing",
                    "content": "Understanding your request..."
                })

            messages = _truncate_messages(messages)
            sessions[session_id]["messages"] = messages

            if turn == 1:
                await websocket.send_json({
                    "type": "thinking",
                    "thinking_id": thinking_id,
                    "thinking_type": "analyzing",
                    "content": "Understanding your request...",
                    "thinking_completed": True
                })

            tool_calls = []
            text_content = []
            text_streaming = False

            async with client.client.messages.stream(
                model=client.config.model,
                max_tokens=client.config.max_tokens,
                system=[{
                    "type": "text",
                    "text": client.SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }],
                tools=TOOL_DEFINITIONS,
                messages=messages
            ) as stream:
                text_buffer = ""
                last_flush = time.monotonic()

                async def flush_text():
                    nonlocal text_buffer
                    if text_buffer:
                        await websocket.send_json({"type": "text_delta", "content": text_buffer})
                        text_buffer = ""

                async for event in stream:
                    if stop_event.is_set():
                        await flush_text()
                        if text_streaming:
                            await websocket.send_json({"type": "text_stream_end"})
                        break

                    if event.type == "content_block_start":
                        if event.content_block.type == "text":
                            text_streaming = True
                            await websocket.send_json({"type": "text_stream_start"})
                        elif event.content_block.type == "tool_use":
                            await flush_text()
                            if text_streaming:
                                await websocket.send_json({"type": "text_stream_end"})
                                text_streaming = False

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, 'text'):
                            text_buffer += event.delta.text
                            now = time.monotonic()
                            if now - last_flush >= 0.05:
                                await flush_text()
                                last_flush = now

                    elif event.type == "content_block_stop":
                        await flush_text()
                        if text_streaming:
                            await websocket.send_json({"type": "text_stream_end"})
                            text_streaming = False

                await flush_text()
                if text_streaming:
                    await websocket.send_json({"type": "text_stream_end"})

                if stop_event.is_set():
                    break

                response = await stream.get_final_message()

            if stop_event.is_set():
                break

            if hasattr(response, 'usage'):
                cumulative_tokens += getattr(response.usage, 'input_tokens', 0)
                print(f"[WS] Turn {turn} tokens: input={getattr(response.usage, 'input_tokens', 0)}, output={getattr(response.usage, 'output_tokens', 0)}, cumulative={cumulative_tokens}")
                if cumulative_tokens > max_token_budget:
                    print(f"[WS] Token budget exceeded ({cumulative_tokens} > {max_token_budget}), stopping")
                    await websocket.send_json({
                        "type": "text",
                        "content": "I've reached the processing limit for this request. Here's what I have so far."
                    })
                    break

            for block in response.content:
                if block.type == "text":
                    text_content.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

            if not tool_calls:
                print(f"[WS] No tool calls, ending loop")
                break

            serialized_content = []
            for block in response.content:
                if block.type == "text":
                    serialized_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    serialized_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
            messages.append({
                "role": "assistant",
                "content": serialized_content
            })

            tool_results = []
            for tool_call in tool_calls:
                if stop_event.is_set():
                    break

                tool_thinking_id = str(uuid.uuid4())
                tool_display_name = tool_call["name"].replace("openeo_", "").replace("viz_", "").replace("_", " ").title()
                await websocket.send_json({
                    "type": "thinking",
                    "thinking_id": tool_thinking_id,
                    "thinking_type": "executing",
                    "content": f"Running {tool_display_name}..."
                })

                await websocket.send_json({
                    "type": "tool_start",
                    "tool_name": tool_call["name"],
                    "tool_input": tool_call["input"]
                })

                if tool_call["name"] == "openeo_create_job":
                    progress_done = asyncio.Event()
                    async def _send_progress():
                        elapsed = 0
                        stages = [
                            (0, "Creating batch job..."),
                            (5, "Starting job..."),
                            (15, "Processing satellite data..."),
                            (30, "Computing results..."),
                            (60, "Still processing (large dataset)..."),
                            (90, "Almost done..."),
                        ]
                        while not progress_done.is_set():
                            await asyncio.sleep(5)
                            elapsed += 5
                            msg = "Processing..."
                            for threshold, label in reversed(stages):
                                if elapsed >= threshold:
                                    msg = label
                                    break
                            try:
                                await websocket.send_json({
                                    "type": "thinking",
                                    "thinking_id": tool_thinking_id,
                                    "thinking_type": "executing",
                                    "content": f"{msg} ({elapsed}s)"
                                })
                            except Exception:
                                break

                    progress_task = asyncio.create_task(_send_progress())
                    try:
                        tool_result = await execute_tool(
                            client, tool_call["name"], tool_call["input"]
                        )
                    finally:
                        progress_done.set()
                        progress_task.cancel()
                        try:
                            await progress_task
                        except asyncio.CancelledError:
                            pass
                else:
                    tool_result = await execute_tool(
                        client, tool_call["name"], tool_call["input"]
                    )

                await websocket.send_json({
                    "type": "tool_result",
                    "tool_name": tool_call["name"],
                    "result": tool_result
                })

                await websocket.send_json({
                    "type": "thinking",
                    "thinking_id": tool_thinking_id,
                    "thinking_type": "executing",
                    "content": f"Running {tool_display_name}...",
                    "thinking_completed": True
                })

                tools_used_all.append(tool_call["name"])
                # Track job title for naming saved results
                if tool_call["name"] == "openeo_create_job":
                    last_job_title = tool_call["input"].get("title", "")
                print(f"[WS] Tool result for {tool_call['name']}: {str(tool_result)[:200]}")
                viz = extract_visualization(tool_call["name"], tool_result, title_hint=last_job_title)
                print(f"[WS] Extracted visualization: {viz is not None}")
                if viz:
                    print(f"[WS] Sending visualization: {viz.get('type')}")
                    await websocket.send_json({
                        "type": "visualization",
                        "visualization": viz
                    })

                if tool_call["name"] == "openeo_quality_metrics":
                    await websocket.send_json({
                        "type": "quality_metrics",
                        "metrics": tool_result
                    })

                if tool_call["name"] == "openeo_generate_graph":
                    await websocket.send_json({
                        "type": "process_graph",
                        "graph": tool_result
                    })

                result_content = json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result
                if len(result_content) > 2000:
                    result_content = result_content[:2000] + "\n... [truncated]"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": result_content
                })

            if stop_event.is_set():
                break

            messages.append({
                "role": "user",
                "content": tool_results
            })

        if not stop_event.is_set():
            from .sdk.claude_sdk_bridge import _generate_suggestions
            suggestions = _generate_suggestions(tools_used_all, message)
            if suggestions:
                await websocket.send_json({"type": "suggestions", "suggestions": suggestions})
            await websocket.send_json({"type": "done"})

    except Exception as e:
        print(f"[WS] Error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "type": "error",
            "content": str(e)
        })


# Enhanced HTML Frontend with all PRD components
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenEO AI Assistant - Earth Observation Research Platform</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <style>
        :root {
            --primary: #4ecdc4;
            --primary-dark: #3db3ab;
            --secondary: #ff6b6b;
            --bg-dark: #1a1a2e;
            --bg-darker: #16213e;
            --bg-card: #252542;
            --bg-card-hover: #2d2d4a;
            --text-primary: #e4e4e4;
            --text-secondary: #888;
            --border: #3a3a5c;
            --success: #4CAF50;
            --warning: #FF9800;
            --error: #F44336;
            --info: #2196F3;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, var(--bg-dark) 0%, var(--bg-darker) 100%);
            min-height: 100vh;
            color: var(--text-primary);
        }

        /* Main Layout - Three Column */
        .app-container {
            display: grid;
            grid-template-columns: 280px 1fr 320px;
            height: 100vh;
            gap: 0;
        }

        /* Left Sidebar - Workflow & History */
        .sidebar-left {
            background: var(--bg-card);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .sidebar-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
        }

        .sidebar-header h2 {
            color: var(--primary);
            font-size: 1.1em;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .sidebar-section {
            padding: 15px;
            border-bottom: 1px solid var(--border);
        }

        .sidebar-section h3 {
            font-size: 0.85em;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }

        /* Suggestion Chips */
        .suggestion-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .chip {
            background: var(--bg-darker);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 8px 14px;
            font-size: 0.8em;
            cursor: pointer;
            transition: all 0.2s;
            color: var(--text-primary);
        }

        .chip:hover {
            background: var(--primary);
            color: var(--bg-dark);
            border-color: var(--primary);
        }

        .chip.active {
            background: var(--primary);
            color: var(--bg-dark);
        }

        /* Workflow Status */
        .workflow-status {
            padding: 12px;
            background: var(--bg-darker);
            border-radius: 8px;
            margin-bottom: 10px;
        }

        .workflow-status .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .workflow-status .status-label {
            font-size: 0.8em;
            color: var(--text-secondary);
        }

        .workflow-status .status-value {
            font-size: 0.85em;
            font-weight: 500;
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
        }

        .status-indicator.connected { background: var(--success); }
        .status-indicator.processing { background: var(--warning); animation: pulse 1s infinite; }
        .status-indicator.error { background: var(--error); }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Workflow History */
        .history-list {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }

        .history-item {
            background: var(--bg-darker);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }

        .history-item:hover {
            border-color: var(--primary);
        }

        .history-item .query {
            font-size: 0.85em;
            color: var(--text-primary);
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .history-item .meta {
            font-size: 0.75em;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
        }

        .history-item .grade {
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.7em;
            font-weight: bold;
        }

        .grade-A { background: var(--success); color: white; }
        .grade-B { background: #8BC34A; color: white; }
        .grade-C { background: var(--warning); color: white; }
        .grade-D { background: #FF5722; color: white; }
        .grade-F { background: var(--error); color: white; }

        /* Main Chat Area */
        .main-content {
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .main-header {
            padding: 15px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0,0,0,0.2);
        }

        .main-header h1 {
            color: var(--primary);
            font-size: 1.4em;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .header-actions {
            display: flex;
            gap: 10px;
        }

        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 0.85em;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-primary {
            background: var(--primary);
            color: var(--bg-dark);
        }

        .btn-primary:hover {
            background: var(--primary-dark);
        }

        .btn-secondary {
            background: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--bg-card-hover);
        }

        /* Messages Area */
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }

        .message {
            max-width: 85%;
            margin-bottom: 16px;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            margin-left: auto;
        }

        .message-content {
            padding: 14px 18px;
            border-radius: 12px;
            line-height: 1.5;
        }

        .message.user .message-content {
            background: var(--primary);
            color: var(--bg-dark);
            border-bottom-right-radius: 4px;
        }

        .message.assistant .message-content {
            background: var(--bg-card);
            border-bottom-left-radius: 4px;
        }

        .message-meta {
            font-size: 0.75em;
            color: var(--text-secondary);
            margin-top: 4px;
            padding: 0 4px;
        }

        .message.user .message-meta {
            text-align: right;
        }

        /* Tool Call Indicator */
        .tool-call {
            background: rgba(78, 205, 196, 0.1);
            border: 1px solid var(--primary);
            border-radius: 8px;
            padding: 10px 14px;
            margin: 10px 0;
            font-size: 0.85em;
        }

        .tool-call .tool-name {
            color: var(--primary);
            font-weight: 500;
        }

        /* Input Area */
        .input-container {
            padding: 15px 20px;
            background: var(--bg-card);
            border-top: 1px solid var(--border);
        }

        .input-wrapper {
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }

        .input-field {
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        #messageInput {
            width: 100%;
            padding: 14px 18px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: var(--bg-darker);
            color: var(--text-primary);
            font-size: 0.95em;
            resize: none;
            min-height: 50px;
            max-height: 150px;
        }

        #messageInput:focus {
            outline: none;
            border-color: var(--primary);
        }

        #messageInput::placeholder {
            color: var(--text-secondary);
        }

        .input-hint {
            font-size: 0.75em;
            color: var(--text-secondary);
            margin-top: 6px;
            padding: 0 4px;
        }

        #sendButton {
            padding: 14px 24px;
            background: var(--primary);
            color: var(--bg-dark);
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }

        #sendButton:hover {
            background: var(--primary-dark);
        }

        #sendButton:disabled {
            background: var(--border);
            cursor: not-allowed;
        }

        /* Right Sidebar - Context & Metrics */
        .sidebar-right {
            background: var(--bg-card);
            border-left: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* Tabs */
        .tabs {
            display: flex;
            border-bottom: 1px solid var(--border);
        }

        .tab {
            flex: 1;
            padding: 12px;
            text-align: center;
            cursor: pointer;
            font-size: 0.85em;
            color: var(--text-secondary);
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab:hover {
            color: var(--text-primary);
        }

        .tab.active {
            color: var(--primary);
            border-bottom-color: var(--primary);
        }

        .tab-content {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
        }

        .tab-panel {
            display: none;
        }

        .tab-panel.active {
            display: block;
        }

        /* Process Graph Panel */
        .process-graph-view {
            background: var(--bg-darker);
            border-radius: 8px;
            padding: 15px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.8em;
            overflow-x: auto;
            max-height: 300px;
            overflow-y: auto;
        }

        .process-node {
            padding: 8px 12px;
            margin: 4px 0;
            background: var(--bg-card);
            border-radius: 6px;
            border-left: 3px solid var(--primary);
        }

        .process-node .node-id {
            color: var(--primary);
            font-weight: 500;
        }

        .process-node .node-process {
            color: var(--text-secondary);
            font-size: 0.9em;
        }

        /* Quality Metrics Panel */
        .quality-panel {
            padding: 15px;
        }

        .quality-score {
            text-align: center;
            padding: 20px;
            background: var(--bg-darker);
            border-radius: 12px;
            margin-bottom: 15px;
        }

        .quality-score .grade {
            font-size: 3em;
            font-weight: bold;
        }

        .quality-score .score-label {
            font-size: 0.9em;
            color: var(--text-secondary);
            margin-top: 5px;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 12px;
            background: var(--bg-darker);
            border-radius: 8px;
            margin-bottom: 8px;
        }

        .metric-row .label {
            font-size: 0.85em;
            color: var(--text-secondary);
        }

        .metric-row .value {
            font-weight: 500;
        }

        /* Export Panel */
        .export-panel {
            padding: 15px;
        }

        .export-option {
            display: flex;
            align-items: center;
            padding: 15px;
            background: var(--bg-darker);
            border-radius: 8px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }

        .export-option:hover {
            border-color: var(--primary);
        }

        .export-option .icon {
            font-size: 1.5em;
            margin-right: 15px;
        }

        .export-option .details h4 {
            font-size: 0.95em;
            margin-bottom: 4px;
        }

        .export-option .details p {
            font-size: 0.8em;
            color: var(--text-secondary);
        }

        /* Sustainability Panel */
        .sustainability-panel {
            padding: 15px;
        }

        .eco-score {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%);
            border-radius: 12px;
            margin-bottom: 15px;
        }

        .eco-score .leaf {
            font-size: 2em;
        }

        .eco-score .carbon {
            font-size: 1.5em;
            font-weight: bold;
            margin: 10px 0;
        }

        .eco-score .label {
            font-size: 0.8em;
            opacity: 0.9;
        }

        /* Map Styles */
        .map-container {
            height: 350px;
            border-radius: 8px;
            overflow: hidden;
            margin: 10px 0;
        }

        .map-controls {
            display: flex;
            gap: 8px;
            margin-top: 10px;
            flex-wrap: wrap;
        }

        .map-control {
            padding: 6px 12px;
            background: var(--bg-darker);
            border: 1px solid var(--border);
            border-radius: 4px;
            font-size: 0.8em;
            cursor: pointer;
        }

        .map-control:hover {
            border-color: var(--primary);
        }

        .map-control select {
            background: transparent;
            border: none;
            color: var(--text-primary);
            cursor: pointer;
        }

        /* Chart Styles */
        .chart-container {
            height: 300px;
            margin: 10px 0;
        }

        /* Loading State */
        .loading {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 15px;
            color: var(--text-secondary);
        }

        .loading-dots {
            display: flex;
            gap: 4px;
        }

        .loading-dots span {
            width: 8px;
            height: 8px;
            background: var(--primary);
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }

        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        /* Responsive */
        @media (max-width: 1200px) {
            .app-container {
                grid-template-columns: 1fr;
            }
            .sidebar-left, .sidebar-right {
                display: none;
            }
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-darker);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-secondary);
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Left Sidebar: Workflow & History -->
        <aside class="sidebar-left">
            <div class="sidebar-header">
                <h2>🌍 OpenEO AI</h2>
            </div>

            <!-- Workflow Status -->
            <div class="sidebar-section">
                <h3>Workflow Status</h3>
                <div class="workflow-status">
                    <div class="status-row">
                        <span class="status-label">Connection</span>
                        <span class="status-value" id="connectionStatus">
                            <span class="status-indicator connected"></span>Connected
                        </span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Backend</span>
                        <span class="status-value">openEO v1.1.0</span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Tools</span>
                        <span class="status-value" id="toolCount">18 available</span>
                    </div>
                </div>
            </div>

            <!-- Quick Queries -->
            <div class="sidebar-section">
                <h3>Suggested Queries</h3>
                <div class="suggestion-chips">
                    <div class="chip" onclick="useSuggestion('Show NDVI for Mumbai during monsoon 2024')">NDVI Analysis</div>
                    <div class="chip" onclick="useSuggestion('Compare vegetation change in Kerala between 2020 and 2024')">Change Detection</div>
                    <div class="chip" onclick="useSuggestion('Show elevation map for the Alps region')">Terrain Analysis</div>
                    <div class="chip" onclick="useSuggestion('List available Sentinel-2 collections')">Data Discovery</div>
                    <div class="chip" onclick="useSuggestion('What is the cloud cover expectation for Amazon rainforest in December?')">Quality Check</div>
                </div>
            </div>

            <!-- Workflow History -->
            <div class="sidebar-section" style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
                <h3>Recent Workflows</h3>
                <div class="history-list" id="historyList">
                    <div class="history-item" onclick="replayWorkflow(0)">
                        <div class="query">NDVI analysis for Kerala...</div>
                        <div class="meta">
                            <span>2 min ago</span>
                            <span class="grade grade-B">B</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="sidebar-section">
                <h3>Quick Actions</h3>
                <button class="btn btn-secondary" style="width: 100%; margin-bottom: 8px;" onclick="clearChat()">
                    🗑️ Clear Chat
                </button>
                <button class="btn btn-secondary" style="width: 100%;" onclick="showTutorial()">
                    📚 Tutorial
                </button>
            </div>
        </aside>

        <!-- Main Chat Area -->
        <main class="main-content">
            <header class="main-header">
                <h1>🛰️ Earth Observation Assistant</h1>
                <div class="header-actions">
                    <button class="btn btn-secondary" onclick="exportNotebook()">
                        📓 Export Notebook
                    </button>
                    <button class="btn btn-primary" onclick="showHelp()">
                        ❓ Help
                    </button>
                </div>
            </header>

            <div class="messages-container" id="messages">
                <div class="message assistant">
                    <div class="message-content">
                        <strong>Welcome to OpenEO AI Assistant!</strong><br><br>
                        I'm here to help you with Earth Observation data analysis. I can:
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            <li>Find and explore satellite imagery collections</li>
                            <li>Generate NDVI, NDWI, and other vegetation indices</li>
                            <li>Analyze temporal changes in land cover</li>
                            <li>Create visualizations and interactive maps</li>
                            <li>Estimate data quality and cloud coverage</li>
                        </ul>
                        Try asking: <em>"Show NDVI for Mumbai during monsoon 2024"</em> or click a suggestion on the left!
                    </div>
                    <div class="message-meta">Just now</div>
                </div>
            </div>

            <div class="input-container">
                <div class="input-wrapper">
                    <div class="input-field">
                        <textarea
                            id="messageInput"
                            placeholder="Ask about satellite data, request analysis, or describe your research needs..."
                            rows="1"
                            onkeydown="handleKeyDown(event)"
                        ></textarea>
                        <div class="input-hint">
                            Press Enter to send, Shift+Enter for new line
                        </div>
                    </div>
                    <button id="sendButton" onclick="sendMessage()">Send →</button>
                </div>
            </div>
        </main>

        <!-- Right Sidebar: Context & Metrics -->
        <aside class="sidebar-right">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('quality')">Quality</div>
                <div class="tab" onclick="switchTab('process')">Process</div>
                <div class="tab" onclick="switchTab('export')">Export</div>
                <div class="tab" onclick="switchTab('eco')">Eco</div>
            </div>

            <div class="tab-content">
                <!-- Quality Metrics Tab -->
                <div class="tab-panel active" id="tab-quality">
                    <div class="quality-score" id="qualityScore">
                        <div class="grade" style="color: var(--success);">A</div>
                        <div class="score-label">Data Quality Score</div>
                    </div>
                    <div id="qualityMetrics">
                        <div class="metric-row">
                            <span class="label">Cloud Coverage</span>
                            <span class="value" style="color: var(--success);">~15%</span>
                        </div>
                        <div class="metric-row">
                            <span class="label">Temporal Coverage</span>
                            <span class="value" style="color: var(--success);">92%</span>
                        </div>
                        <div class="metric-row">
                            <span class="label">Spatial Completeness</span>
                            <span class="value" style="color: var(--success);">100%</span>
                        </div>
                        <div class="metric-row">
                            <span class="label">Data Freshness</span>
                            <span class="value">Recent</span>
                        </div>
                    </div>
                    <div id="qualityRecommendations" style="margin-top: 15px; padding: 12px; background: rgba(33,150,243,0.1); border-radius: 8px; display: none;">
                        <h4 style="color: var(--info); font-size: 0.85em; margin-bottom: 8px;">💡 Recommendations</h4>
                        <ul id="recommendationsList" style="font-size: 0.8em; padding-left: 15px; color: var(--text-secondary);">
                        </ul>
                    </div>
                </div>

                <!-- Process Graph Tab -->
                <div class="tab-panel" id="tab-process">
                    <h4 style="margin-bottom: 10px; font-size: 0.9em;">Current Process Graph</h4>
                    <div class="process-graph-view" id="processGraphView">
                        <div style="color: var(--text-secondary); font-style: italic;">
                            No process graph generated yet. Start a query to see the workflow.
                        </div>
                    </div>
                    <button class="btn btn-secondary" style="width: 100%; margin-top: 10px;" onclick="downloadProcessGraph()">
                        📥 Download JSON
                    </button>
                    <button class="btn btn-secondary" style="width: 100%; margin-top: 8px;" onclick="copyProcessGraph()">
                        📋 Copy to Clipboard
                    </button>
                </div>

                <!-- Export Tab -->
                <div class="tab-panel" id="tab-export">
                    <div class="export-option" onclick="exportNotebook()">
                        <span class="icon">📓</span>
                        <div class="details">
                            <h4>Jupyter Notebook</h4>
                            <p>Export as reproducible notebook with code cells</p>
                        </div>
                    </div>
                    <div class="export-option" onclick="exportProcessGraph()">
                        <span class="icon">📊</span>
                        <div class="details">
                            <h4>Process Graph JSON</h4>
                            <p>OpenEO-compatible process graph</p>
                        </div>
                    </div>
                    <div class="export-option" onclick="exportMarkdown()">
                        <span class="icon">📝</span>
                        <div class="details">
                            <h4>Markdown Report</h4>
                            <p>Analysis summary with methodology</p>
                        </div>
                    </div>
                    <div class="export-option" onclick="generateCitation()">
                        <span class="icon">📚</span>
                        <div class="details">
                            <h4>Citation</h4>
                            <p>Generate BibTeX for publications</p>
                        </div>
                    </div>
                </div>

                <!-- Sustainability Tab -->
                <div class="tab-panel" id="tab-eco">
                    <div class="eco-score">
                        <div class="leaf">🌱</div>
                        <div class="carbon" id="carbonEstimate">~0.02 kg CO₂</div>
                        <div class="label">Estimated Carbon Footprint</div>
                    </div>
                    <div class="metric-row">
                        <span class="label">Data Transferred</span>
                        <span class="value" id="dataTransferred">0 MB</span>
                    </div>
                    <div class="metric-row">
                        <span class="label">Compute Time</span>
                        <span class="value" id="computeTime">0s</span>
                    </div>
                    <div class="metric-row">
                        <span class="label">Backend Region</span>
                        <span class="value">EU-Central</span>
                    </div>
                    <p style="font-size: 0.75em; color: var(--text-secondary); margin-top: 15px; padding: 10px; background: var(--bg-darker); border-radius: 8px;">
                        💡 <strong>Tip:</strong> Reduce spatial extent or use temporal aggregation to minimize data processing and carbon footprint.
                    </p>
                </div>
            </div>
        </aside>
    </div>

    <script>
        // State Management
        let ws = null;
        let sessionId = null;
        let currentProcessGraph = null;
        let workflowHistory = [];
        let currentQualityMetrics = null;
        let messageHistory = [];
        let mapCounter = 0;
        let activeMaps = {};
        let activeCharts = {};
        let computeStartTime = null;
        let totalDataTransferred = 0;

        // Basemaps
        const BASEMAPS = {
            'CartoDB Dark': 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            'CartoDB Light': 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
            'OpenStreetMap': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            'Satellite': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        };

        // Initialize WebSocket Connection
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                console.log('Connected to server');
                updateConnectionStatus('connected');
            };

            ws.onclose = () => {
                console.log('Disconnected from server');
                updateConnectionStatus('disconnected');
                setTimeout(connect, 3000);
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                updateConnectionStatus('error');
            };

            ws.onmessage = (event) => {
                handleMessage(JSON.parse(event.data));
            };
        }

        function updateConnectionStatus(status) {
            const statusEl = document.getElementById('connectionStatus');
            if (status === 'connected') {
                statusEl.innerHTML = '<span class="status-indicator connected"></span>Connected';
            } else if (status === 'disconnected') {
                statusEl.innerHTML = '<span class="status-indicator error"></span>Reconnecting...';
            } else {
                statusEl.innerHTML = '<span class="status-indicator error"></span>Error';
            }
        }

        // Message Handling
        function handleMessage(data) {
            console.log('Received:', data);

            switch (data.type) {
                case 'session':
                    sessionId = data.session_id;
                    break;

                case 'text':
                    addMessage(data.content, 'assistant');
                    hideLoading();
                    break;

                case 'tool_start':
                    showToolCall(data.tool_name, data.tool_input);
                    break;

                case 'tool_result':
                    updateToolResult(data.tool_name, data.result);
                    break;

                case 'visualization':
                    addVisualization(data.visualization);
                    break;

                case 'quality_metrics':
                    updateQualityMetrics(data.metrics);
                    break;

                case 'process_graph':
                    updateProcessGraph(data.graph);
                    break;

                case 'error':
                    addMessage(`Error: ${data.content}`, 'assistant error');
                    hideLoading();
                    break;

                case 'done':
                    hideLoading();
                    updateComputeTime();
                    addToHistory();
                    break;
            }
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();

            if (!message || !ws || ws.readyState !== WebSocket.OPEN) return;

            addMessage(message, 'user');
            messageHistory.push({ role: 'user', content: message });
            showLoading();
            computeStartTime = Date.now();

            ws.send(JSON.stringify({
                type: 'message',
                content: message,
                session_id: sessionId
            }));

            input.value = '';
            input.style.height = 'auto';
        }

        function addMessage(content, role) {
            const messagesDiv = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = `message ${role}`;

            const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            div.innerHTML = `
                <div class="message-content">${formatContent(content)}</div>
                <div class="message-meta">${time}</div>
            `;

            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function formatContent(content) {
            // Convert markdown-like formatting
            return content
                .replace(/\\n/g, '<br>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/`(.*?)`/g, '<code>$1</code>');
        }

        function showLoading() {
            const messagesDiv = document.getElementById('messages');
            const loadingDiv = document.createElement('div');
            loadingDiv.id = 'loadingIndicator';
            loadingDiv.className = 'message assistant';
            loadingDiv.innerHTML = `
                <div class="loading">
                    <div class="loading-dots">
                        <span></span><span></span><span></span>
                    </div>
                    <span>Processing your request...</span>
                </div>
            `;
            messagesDiv.appendChild(loadingDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;

            document.getElementById('sendButton').disabled = true;
        }

        function hideLoading() {
            const loading = document.getElementById('loadingIndicator');
            if (loading) loading.remove();
            document.getElementById('sendButton').disabled = false;
        }

        function showToolCall(toolName, toolInput) {
            const messagesDiv = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = 'tool-call';
            div.innerHTML = `
                <span class="tool-name">🔧 ${toolName}</span>
                <span style="color: var(--text-secondary); font-size: 0.9em;">
                    ${JSON.stringify(toolInput).substring(0, 100)}...
                </span>
            `;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function updateToolResult(toolName, result) {
            // Update data transferred estimate
            totalDataTransferred += (JSON.stringify(result).length / 1024);
            document.getElementById('dataTransferred').textContent =
                totalDataTransferred > 1024
                    ? `${(totalDataTransferred / 1024).toFixed(1)} MB`
                    : `${totalDataTransferred.toFixed(0)} KB`;
        }

        // Visualization Handling
        function addVisualization(viz) {
            const messagesDiv = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = 'message assistant';

            if (viz.type === 'map' && viz.spec) {
                const mapId = 'map-' + (++mapCounter);
                const spec = viz.spec;

                div.innerHTML = `
                    <div class="message-content">
                        <strong>🗺️ ${spec.title || 'Map Result'}</strong>
                        <div id="${mapId}" class="map-container"></div>
                        <div class="map-controls">
                            <div class="map-control">
                                <select onchange="changeBasemap('${mapId}', this.value)">
                                    <option value="CartoDB Dark">Dark</option>
                                    <option value="CartoDB Light">Light</option>
                                    <option value="Satellite">Satellite</option>
                                    <option value="OpenStreetMap">OSM</option>
                                </select>
                            </div>
                            <div class="map-control">
                                <select onchange="changeColormap('${mapId}', this.value)">
                                    <option value="viridis">Viridis</option>
                                    <option value="plasma">Plasma</option>
                                    <option value="ndvi">NDVI</option>
                                    <option value="terrain">Terrain</option>
                                </select>
                            </div>
                            <button class="map-control" onclick="downloadMap('${mapId}')">📥 Download</button>
                        </div>
                    </div>
                `;

                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                setTimeout(() => initializeMap(mapId, spec), 100);

            } else if (viz.type === 'chart' && viz.spec) {
                const chartId = 'chart-' + (++mapCounter);
                const spec = viz.spec;

                div.innerHTML = `
                    <div class="message-content">
                        <strong>📊 ${spec.title || 'Chart'}</strong>
                        <div class="chart-container">
                            <canvas id="${chartId}"></canvas>
                        </div>
                        <button class="map-control" onclick="downloadChart('${chartId}')">📥 Download</button>
                    </div>
                `;

                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                setTimeout(() => initializeChart(chartId, spec), 100);

            } else if (viz.type === 'quality_dashboard' && viz.spec) {
                const spec = viz.spec;
                updateQualityMetrics(spec);

                // Also show inline quality summary
                div.innerHTML = `
                    <div class="message-content">
                        <strong>📊 Data Quality Assessment</strong>
                        <div style="display: flex; align-items: center; gap: 15px; margin-top: 10px;">
                            <div style="
                                background: ${getGradeColor(spec.grade)};
                                color: white;
                                padding: 15px 25px;
                                border-radius: 12px;
                                text-align: center;
                            ">
                                <div style="font-size: 2em; font-weight: bold;">${spec.grade}</div>
                                <div style="font-size: 0.8em; opacity: 0.9;">${spec.score}%</div>
                            </div>
                            <div style="flex: 1;">
                                <p style="margin-bottom: 8px;">See the <strong>Quality</strong> tab on the right for detailed metrics.</p>
                            </div>
                        </div>
                    </div>
                `;
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

            } else {
                if (viz.spec) {
                    const pre = document.createElement('pre');
                    pre.textContent = JSON.stringify(viz.spec, null, 2).substring(0, 500);
                    div.innerHTML = '<div class="message-content"></div>';
                    div.querySelector('.message-content').appendChild(pre);
                }
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }

        function getGradeColor(grade) {
            const colors = { 'A': '#4CAF50', 'B': '#8BC34A', 'C': '#FFC107', 'D': '#FF5722', 'F': '#F44336' };
            return colors[grade] || '#9E9E9E';
        }

        // Map Functions
        function initializeMap(mapId, spec) {
            const map = L.map(mapId, {
                zoomControl: true,
                attributionControl: false
            }).setView(spec.center || [0, 0], spec.zoom || 10);

            const basemapLayer = L.tileLayer(BASEMAPS['CartoDB Dark'], {
                maxZoom: 19
            }).addTo(map);

            activeMaps[mapId] = {
                map: map,
                basemapLayer: basemapLayer,
                imageLayer: null,
                spec: spec
            };

            if (spec.layers && spec.layers.length > 0) {
                const layer = spec.layers[0];
                if (layer.type === 'raster' && layer.url && layer.bounds) {
                    const imageLayer = L.imageOverlay(layer.url, layer.bounds, {
                        opacity: layer.opacity || 0.8
                    }).addTo(map);
                    activeMaps[mapId].imageLayer = imageLayer;
                    map.fitBounds(layer.bounds);
                }
            }
        }

        function changeBasemap(mapId, basemap) {
            const mapData = activeMaps[mapId];
            if (mapData) {
                mapData.basemapLayer.setUrl(BASEMAPS[basemap]);
            }
        }

        async function changeColormap(mapId, colormap) {
            const mapData = activeMaps[mapId];
            if (mapData && mapData.spec.layers?.[0]?.source) {
                try {
                    const response = await fetch(`/render-raster?path=${encodeURIComponent(mapData.spec.layers[0].source)}&colormap=${colormap}`);
                    const data = await response.json();
                    if (data.url && mapData.imageLayer) {
                        mapData.imageLayer.setUrl(data.url);
                    }
                } catch (e) {
                    console.error('Failed to change colormap:', e);
                }
            }
        }

        // Chart Functions
        function initializeChart(chartId, spec) {
            const ctx = document.getElementById(chartId).getContext('2d');

            const chartConfig = {
                type: spec.chart_type || 'line',
                data: {
                    labels: spec.data?.x || [],
                    datasets: [{
                        label: spec.data?.series_name || 'Data',
                        data: spec.data?.y || [],
                        borderColor: '#4ecdc4',
                        backgroundColor: 'rgba(78, 205, 196, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: { display: true, text: spec.title || '', color: '#e4e4e4' },
                        legend: { labels: { color: '#e4e4e4' } }
                    },
                    scales: {
                        x: {
                            title: { display: true, text: spec.xaxis?.title || '', color: '#888' },
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.1)' }
                        },
                        y: {
                            title: { display: true, text: spec.yaxis?.title || '', color: '#888' },
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.1)' }
                        }
                    }
                }
            };

            activeCharts[chartId] = new Chart(ctx, chartConfig);
        }

        // Quality Metrics
        function updateQualityMetrics(metrics) {
            currentQualityMetrics = metrics;

            // Update quality score display
            const gradeEl = document.querySelector('#qualityScore .grade');
            const grade = metrics.grade || metrics.quality_grade || 'N/A';
            gradeEl.textContent = grade;
            gradeEl.style.color = getGradeColor(grade);

            // Update metrics
            const metricsEl = document.getElementById('qualityMetrics');
            const cloud = metrics.cloud_coverage || metrics.sections?.find(s => s.title === 'Cloud Coverage')?.content || {};
            const temporal = metrics.temporal_coverage || metrics.sections?.find(s => s.title === 'Temporal Coverage')?.content || {};

            metricsEl.innerHTML = `
                <div class="metric-row">
                    <span class="label">Cloud Coverage</span>
                    <span class="value" style="color: ${cloud.color || 'inherit'};">
                        ~${cloud.estimated_cloud_cover_pct || cloud.value || 'N/A'}%
                    </span>
                </div>
                <div class="metric-row">
                    <span class="label">Temporal Coverage</span>
                    <span class="value" style="color: ${temporal.color || 'inherit'};">
                        ${temporal.coverage_percentage || temporal.value || 'N/A'}%
                    </span>
                </div>
                <div class="metric-row">
                    <span class="label">Usable Scenes</span>
                    <span class="value">${cloud.usable_scenes_estimate || 'N/A'}/${cloud.total_scenes_estimate || 'N/A'}</span>
                </div>
                <div class="metric-row">
                    <span class="label">Quality Grade</span>
                    <span class="value">${grade} (${metrics.score || metrics.overall_quality_score || 'N/A'}%)</span>
                </div>
            `;

            // Show recommendations
            const recs = metrics.recommendations || [];
            const recsEl = document.getElementById('qualityRecommendations');
            const recsList = document.getElementById('recommendationsList');

            if (recs.length > 0) {
                recsEl.style.display = 'block';
                recsList.innerHTML = recs.map(r => `<li>${r}</li>`).join('');
            } else {
                recsEl.style.display = 'none';
            }
        }

        // Process Graph
        function updateProcessGraph(graph) {
            currentProcessGraph = graph;
            const view = document.getElementById('processGraphView');

            if (!graph) {
                view.innerHTML = '<div style="color: var(--text-secondary);">No process graph generated yet.</div>';
                return;
            }

            let html = '';
            for (const [nodeId, node] of Object.entries(graph)) {
                html += `
                    <div class="process-node">
                        <span class="node-id">${nodeId}</span>
                        <span class="node-process">→ ${node.process_id || 'unknown'}</span>
                    </div>
                `;
            }

            view.innerHTML = html || '<div style="color: var(--text-secondary);">Empty process graph.</div>';
        }

        // Tab Switching
        function switchTab(tabId) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

            document.querySelector(`.tab[onclick="switchTab('${tabId}')"]`).classList.add('active');
            document.getElementById(`tab-${tabId}`).classList.add('active');
        }

        // Utility Functions
        function useSuggestion(query) {
            document.getElementById('messageInput').value = query;
            sendMessage();
        }

        function handleKeyDown(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        function clearChat() {
            if (confirm('Clear chat history?')) {
                document.getElementById('messages').innerHTML = '';
                messageHistory = [];
                currentProcessGraph = null;
                updateProcessGraph(null);
            }
        }

        function addToHistory() {
            const lastUserMsg = messageHistory.filter(m => m.role === 'user').pop();
            if (lastUserMsg) {
                workflowHistory.unshift({
                    query: lastUserMsg.content,
                    time: new Date(),
                    grade: currentQualityMetrics?.grade || currentQualityMetrics?.quality_grade || 'N/A',
                    processGraph: currentProcessGraph
                });
                updateHistoryList();
            }
        }

        function updateHistoryList() {
            const list = document.getElementById('historyList');
            list.innerHTML = workflowHistory.slice(0, 10).map((h, i) => `
                <div class="history-item" onclick="replayWorkflow(${i})">
                    <div class="query">${h.query.substring(0, 50)}...</div>
                    <div class="meta">
                        <span>${getTimeAgo(h.time)}</span>
                        <span class="grade grade-${h.grade}">${h.grade}</span>
                    </div>
                </div>
            `).join('');
        }

        function getTimeAgo(date) {
            const diff = (new Date() - date) / 1000;
            if (diff < 60) return 'Just now';
            if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
            if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
            return `${Math.floor(diff / 86400)} days ago`;
        }

        function replayWorkflow(index) {
            const workflow = workflowHistory[index];
            if (workflow) {
                document.getElementById('messageInput').value = workflow.query;
            }
        }

        function updateComputeTime() {
            if (computeStartTime) {
                const elapsed = (Date.now() - computeStartTime) / 1000;
                document.getElementById('computeTime').textContent = `${elapsed.toFixed(1)}s`;

                // Estimate carbon footprint (very rough: ~0.0001 kg CO2 per second of cloud compute)
                const carbon = elapsed * 0.0001;
                document.getElementById('carbonEstimate').textContent = `~${carbon.toFixed(4)} kg CO₂`;
            }
        }

        // Export Functions
        function exportNotebook() {
            const notebook = {
                cells: [],
                metadata: {
                    kernelspec: { display_name: "Python 3", language: "python", name: "python3" },
                    language_info: { name: "python", version: "3.11" }
                },
                nbformat: 4,
                nbformat_minor: 5
            };

            // Add header
            notebook.cells.push({
                cell_type: "markdown",
                metadata: {},
                source: [
                    "# OpenEO Analysis Export\\n",
                    `Generated: ${new Date().toISOString()}\\n`,
                    "\\n",
                    "This notebook was generated by OpenEO AI Assistant."
                ]
            });

            // Add process graph if available
            if (currentProcessGraph) {
                notebook.cells.push({
                    cell_type: "code",
                    metadata: {},
                    source: [
                        "import openeo\\n",
                        "\\n",
                        "# Connect to openEO backend\\n",
                        "connection = openeo.connect('http://localhost:8000/openeo/1.1.0')\\n",
                        "\\n",
                        "# Process graph from AI Assistant\\n",
                        `process_graph = ${JSON.stringify(currentProcessGraph, null, 2)}\\n`,
                        "\\n",
                        "# Execute\\n",
                        "job = connection.create_job(process_graph)\\n",
                        "job.start_and_wait()"
                    ],
                    outputs: []
                });
            }

            // Download
            const blob = new Blob([JSON.stringify(notebook, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `openeo_analysis_${Date.now()}.ipynb`;
            a.click();
            URL.revokeObjectURL(url);
        }

        function exportProcessGraph() {
            if (!currentProcessGraph) {
                alert('No process graph available to export.');
                return;
            }
            downloadProcessGraph();
        }

        function downloadProcessGraph() {
            if (!currentProcessGraph) return;
            const blob = new Blob([JSON.stringify(currentProcessGraph, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `process_graph_${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);
        }

        function copyProcessGraph() {
            if (currentProcessGraph) {
                navigator.clipboard.writeText(JSON.stringify(currentProcessGraph, null, 2))
                    .then(() => alert('Process graph copied to clipboard!'));
            }
        }

        function exportMarkdown() {
            let md = `# OpenEO Analysis Report\\n\\n`;
            md += `**Generated:** ${new Date().toISOString()}\\n\\n`;
            md += `## Conversation\\n\\n`;

            messageHistory.forEach(m => {
                md += `**${m.role === 'user' ? 'User' : 'Assistant'}:** ${m.content}\\n\\n`;
            });

            if (currentQualityMetrics) {
                md += `## Quality Metrics\\n\\n`;
                md += `- Grade: ${currentQualityMetrics.grade || currentQualityMetrics.quality_grade}\\n`;
                md += `- Score: ${currentQualityMetrics.score || currentQualityMetrics.overall_quality_score}%\\n`;
            }

            const blob = new Blob([md], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `analysis_report_${Date.now()}.md`;
            a.click();
            URL.revokeObjectURL(url);
        }

        function generateCitation() {
            const citation = `@misc{openeo_ai_${Date.now()},
    title = {Earth Observation Analysis via OpenEO AI Assistant},
    author = {OpenEO AI Assistant},
    year = {${new Date().getFullYear()}},
    note = {Analysis generated using federated Earth Observation processing},
    howpublished = {OpenEO API v1.1.0}
}`;
            navigator.clipboard.writeText(citation)
                .then(() => alert('BibTeX citation copied to clipboard!'));
        }

        function downloadMap(mapId) {
            const mapData = activeMaps[mapId];
            if (mapData?.imageLayer?._url) {
                const a = document.createElement('a');
                a.href = mapData.imageLayer._url;
                a.download = `map_${mapId}.png`;
                a.click();
            }
        }

        function downloadChart(chartId) {
            const chart = activeCharts[chartId];
            if (chart) {
                const a = document.createElement('a');
                a.href = chart.toBase64Image();
                a.download = `chart_${chartId}.png`;
                a.click();
            }
        }

        function showHelp() {
            addMessage(`
**OpenEO AI Assistant Help**

I can help you with Earth Observation data analysis:

**Data Discovery:**
- "List available collections"
- "What bands are in Sentinel-2?"

**Analysis:**
- "Calculate NDVI for [location] in [time period]"
- "Compare vegetation between 2020 and 2024"
- "Show elevation map for [region]"

**Quality Assessment:**
- "What's the cloud cover for [location] in [month]?"
- "Estimate data quality for this query"

**Tips:**
- Use location names (Mumbai, Kerala, Alps) - I'll resolve them
- Use natural dates (last summer, monsoon 2024)
- Check the Quality tab for data reliability
- Export your work as Jupyter notebooks
            `, 'assistant');
        }

        function showTutorial() {
            addMessage(`
**Quick Tutorial**

1. **Start with a question:** "Show NDVI for Mumbai in June 2024"

2. **I'll automatically:**
   - Resolve "Mumbai" to coordinates
   - Convert "June 2024" to dates
   - Check data quality
   - Generate the process graph
   - Create a visualization

3. **Check the sidebars:**
   - Left: Workflow history & suggestions
   - Right: Quality metrics & export options

4. **Export your work:**
   - Jupyter Notebook for reproducibility
   - Process Graph JSON for openEO
   - Markdown report for documentation

Ready to start? Try a suggestion or type your question!
            `, 'assistant');
        }

        // Initialize
        connect();
        document.getElementById('toolCount').textContent = '18 available';
    </script>
</body>
</html>
"""


# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def get_interface():
    """Serve the enhanced chat interface."""
    return HTML_TEMPLATE


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    connection_id = str(uuid.uuid4())
    connections[connection_id] = websocket
    print(f"[WS] Client connected: {connection_id}")

    # Send session info — frontend may override with stored session_id
    session_id = str(uuid.uuid4())
    await websocket.send_json({
        "type": "session",
        "session_id": session_id
    })

    try:
        client = OpenEOAIClient()

        while True:
            data = await websocket.receive_json()

            # Session restore: frontend sends stored session_id to resume
            if data.get("type") == "restore_session":
                old_session_id = data.get("session_id")
                if old_session_id:
                    session_id = old_session_id
                    # Check if SDK session exists for resume
                    _sdk_backend = os.environ.get("OPENEO_SDK_BACKEND", "anthropic")
                    has_sdk_session = False
                    if _sdk_backend == "claude_sdk" and hasattr(app.state, "sdk_bridge"):
                        stored = app.state.sdk_bridge._session_manager.get_sdk_session_id(old_session_id)
                        has_sdk_session = stored is not None
                    await websocket.send_json({
                        "type": "session_restored",
                        "session_id": session_id,
                        "has_history": has_sdk_session,
                    })
                    print(f"[WS] Session restored: {session_id[:12]}... (SDK resume: {has_sdk_session})")
                continue

            # Clarification response: frontend answers Claude's question
            if data.get("type") == "clarification_response":
                _sdk_backend = os.environ.get("OPENEO_SDK_BACKEND", "anthropic")
                if _sdk_backend == "claude_sdk" and hasattr(app.state, "sdk_bridge"):
                    answers = data.get("answers", {})
                    app.state.sdk_bridge.resolve_clarification(session_id, answers)
                continue

            # Direct load of a saved job (no AI roundtrip)
            if data.get("type") == "load_saved_job":
                _save_id = data.get("save_id")
                if _save_id:
                    from .storage.job_archive import get_job as _get_saved_job
                    _job = _get_saved_job(_save_id)
                    if _job:
                        _cmap = _job.get("colormap", "viridis")
                        await websocket.send_json({
                            "type": "visualization",
                            "visualization": {
                                "type": "map",
                                "data": {
                                    "type": "raster",
                                    "url": f"/render-raster?path={_job['result_path']}&colormap={_cmap}",
                                    "bounds": _job.get("bounds"),
                                    "colormap": _cmap,
                                    "opacity": 0.8,
                                    "vmin": _job.get("vmin"),
                                    "vmax": _job.get("vmax"),
                                    "source": _job["result_path"],
                                },
                                "title": _job["title"],
                            }
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Saved job '{_save_id}' not found"
                        })
                continue

            if data.get("type") == "message":
                message = data.get("content", "")
                session_id = data.get("session_id") or "default"

                print(f"[WS] Received message: {message[:50]}...")

                # Cleanup expired sessions periodically
                import time as _time
                _cleanup_expired_sessions()

                # Get or create session
                if session_id not in sessions:
                    sessions[session_id] = {"messages": [], "last_active": _time.monotonic()}
                sessions[session_id]["last_active"] = _time.monotonic()

                # Enforce max session count (evict oldest)
                if len(sessions) > _SESSION_MAX_COUNT:
                    oldest = min(sessions, key=lambda s: sessions[s].get("last_active", 0))
                    del sessions[oldest]
                    print(f"[Session cleanup] Evicted oldest session, {len(sessions)} remaining")

                # Run query as background task, listen for stop concurrently
                stop_event = asyncio.Event()
                query_task = asyncio.create_task(
                    _run_query(message, session_id, websocket, client, app.state, stop_event)
                )

                # Poll for stop messages while query runs
                while not query_task.done():
                    try:
                        stop_data = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)
                        if stop_data.get("type") == "stop":
                            print(f"[WS] Stop requested for session {session_id}")
                            stop_event.set()
                            try:
                                # Give bridge time to drain the SDK response pipe
                                await asyncio.wait_for(query_task, timeout=8.0)
                            except asyncio.TimeoutError:
                                query_task.cancel()
                                # If drain timed out, disconnect the SDK session
                                # so a fresh client is created on the next query
                                _sdk_backend = os.environ.get("OPENEO_SDK_BACKEND", "anthropic")
                                if _sdk_backend == "claude_sdk" and hasattr(app.state, "sdk_bridge"):
                                    await app.state.sdk_bridge.disconnect_session(session_id)
                                    print(f"[WS] SDK session {session_id} disconnected after stop timeout")
                            await websocket.send_json({"type": "done"})
                            break
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        break

                if not query_task.done():
                    query_task.cancel()
                elif not query_task.cancelled():
                    try:
                        await query_task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        print(f"[WS] Query task error: {e}")
                        import traceback
                        traceback.print_exc()

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {connection_id}")
    except Exception as e:
        print(f"[WS] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if connection_id in connections:
            del connections[connection_id]


async def execute_tool(client: OpenEOAIClient, tool_name: str, tool_input: dict) -> Any:
    """Execute a tool and return the result."""
    if tool_name in client.tools:
        result = await client.tools[tool_name](tool_input)
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list) and len(content) > 0:
                first_item = content[0]
                # Handle visualization content (from viz_tools)
                if first_item.get("type") == "visualization" and "component" in first_item:
                    return first_item["component"]
                # Handle text content
                text_content = first_item.get("text", "")
                if text_content:
                    try:
                        return json.loads(text_content)
                    except json.JSONDecodeError:
                        return text_content
        return result
    return {"error": f"Unknown tool: {tool_name}"}


# Extracted to sdk/viz_extractor.py to avoid circular imports with SDK bridge
from .sdk.viz_extractor import extract_visualization


@app.head("/render-raster")
async def render_raster_head(path: str, colormap: str = "viridis"):
    """Handle HEAD request for render-raster (used by Leaflet to probe images)."""
    from fastapi.responses import Response
    # Return empty response with correct content-type for HEAD request
    return Response(content=b"", media_type="image/png", headers={"Content-Length": "0"})


@app.get("/render-raster")
async def render_raster(path: str, colormap: str = "viridis"):
    """Re-render a raster with a different colormap and return the actual image."""
    import base64
    from fastapi.responses import Response

    print(f"[render-raster] GET request: path={path}, colormap={colormap}")

    try:
        map_component = MapComponent()

        result = await map_component.create_raster_map(
            geotiff_path=path,
            colormap=colormap
        )

        if result and "spec" in result:
            layers = result["spec"].get("layers", [])
            if layers and "url" in layers[0]:
                data_url = layers[0]["url"]
                # Extract base64 data from data URL
                if data_url.startswith("data:image/png;base64,"):
                    base64_data = data_url.split(",")[1]
                    image_bytes = base64.b64decode(base64_data)
                    print(f"[render-raster] Returning PNG image: {len(image_bytes)} bytes")
                    return Response(content=image_bytes, media_type="image/png")
                return JSONResponse({"url": data_url})

        print("[render-raster] Failed to render: no layers found")
        return JSONResponse({"error": "Failed to render"}, status_code=500)

    except Exception as e:
        print(f"[render-raster] Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/saved-jobs")
async def list_saved_jobs(limit: int = 50):
    """List permanently saved job results for the frontend."""
    from .storage.job_archive import list_jobs
    jobs = list_jobs(limit=limit)
    return {"jobs": jobs, "count": len(jobs)}


@app.delete("/saved-jobs/{save_id}")
async def delete_saved_job(save_id: str):
    """Delete a permanently saved job result."""
    from .storage.job_archive import delete_job
    success = delete_job(save_id)
    if success:
        return {"deleted": True, "save_id": save_id}
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.get("/health")
async def health_check():
    """Health check endpoint with detailed system information."""
    now = datetime.utcnow()
    uptime_seconds = (now - _SERVER_START_TIME).total_seconds()

    # Determine model name from config if possible
    model_name = "unknown"
    try:
        from .sdk.client import OpenEOAIConfig
        model_name = OpenEOAIConfig().model
    except Exception:
        model_name = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    return {
        "status": "healthy",
        "uptime_seconds": round(uptime_seconds, 1),
        "active_sessions": len(sessions),
        "active_connections": len(connections),
        "model": model_name,
        "version": "0.2.0",
        "tools_count": len(TOOL_DEFINITIONS),
    }


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the enhanced web server."""
    print(f"\n{'='*60}")
    print("OpenEO AI Enhanced Web Interface")
    print(f"{'='*60}")
    print(f"\n🌍 Open your browser at: http://localhost:{port}")
    print(f"\nFeatures:")
    print(f"  • Natural language query processing")
    print(f"  • Interactive maps and charts")
    print(f"  • Quality metrics dashboard")
    print(f"  • Workflow history")
    print(f"  • Export to Jupyter notebooks")
    print(f"\nAvailable tools: {len(TOOL_DEFINITIONS)}")
    print(f"\n{'='*60}\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenEO AI Enhanced Web Interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)
