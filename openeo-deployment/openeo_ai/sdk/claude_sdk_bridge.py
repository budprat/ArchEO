"""Bridge between Claude Agent SDK and WebSocket for the OpenEO AI chat interface.

Routes SDK messages (StreamEvent, AssistantMessage, ResultMessage) and hook
callbacks (PreToolUse, PostToolUse) to WebSocket messages matching the existing
frontend protocol.

Architecture:
    WebSocket msg → ClaudeSDKBridge.query(prompt, websocket)
        ├── ClaudeSDKClient with McpStdioServerConfig → mcp_stdio_server.py
        ├── PreToolUse hook  → tool_start + thinking + permission check
        ├── PostToolUse hook → tool_result + viz + quality WS messages
        └── StreamEvent loop → text_stream_start/delta/end WS messages
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
import uuid
from collections import Counter
from typing import Any, Dict, Optional

# Structured audit logger — writes to stderr alongside existing SDK logs
_audit_log = logging.getLogger("openeo.audit")
if not _audit_log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter(
        "[AUDIT %(asctime)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    ))
    _audit_log.addHandler(_handler)
    _audit_log.setLevel(logging.INFO)
    _audit_log.propagate = False

from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
)

from .client import OpenEOAIClient, OpenEOAIConfig, TOOL_DEFINITIONS
from .inprocess_tools import create_openeo_mcp_server
from .permissions import (
    BLOCKED_TOOLS, RATE_LIMIT_DEFAULT, RATE_LIMITS, READ_ONLY_TOOLS,
    SAFE_MODIFY_TOOLS, _validate_extent, check_suspicious_input,
)
from .sessions import SessionManager
from .viz_extractor import extract_visualization

# Session TTL: expire SDK sessions inactive for more than 30 minutes
_SDK_SESSION_TTL_SECONDS = 1800  # 30 minutes
_SDK_SESSION_MAX_COUNT = 100  # Maximum concurrent SDK sessions


def _strip_mcp_prefix(tool_name: str) -> str:
    """Strip MCP server prefix: mcp__openeo__X → X"""
    prefix = "mcp__openeo__"
    if tool_name.startswith(prefix):
        return tool_name[len(prefix):]
    return tool_name


def _tool_display_name(tool_name: str) -> str:
    """Format tool name for display: openeo_list_collections → List Collections"""
    name = tool_name
    for prefix in ("openeo_", "viz_", "geoai_", "saved_jobs_"):
        name = name.replace(prefix, "")
    return name.replace("_", " ").title()


class ClaudeSDKBridge:
    """Bridge between Claude Agent SDK and WebSocket connections.

    Manages per-session SDK clients. Each session keeps a ClaudeSDKClient alive
    for the WebSocket connection lifetime, enabling multi-turn conversation via
    client.query(). Hooks close over a mutable ws_ref dict so the websocket
    reference can be updated on reconnection.

    Sessions expire after _SDK_SESSION_TTL_SECONDS of inactivity. Cleanup runs
    on each new query. Maximum _SDK_SESSION_MAX_COUNT concurrent sessions; oldest
    evicted on overflow.
    """

    def __init__(self, config: OpenEOAIConfig):
        self.config = config
        # session_id → {"client", "ws_ref", "thinking_ids", "tools_used", "last_active", "sdk_session_id"}
        self._sessions: Dict[str, dict] = {}
        # In-process MCP server shared across all sessions (stateless tools)
        self._mcp_server_config = create_openeo_mcp_server(config)
        # SQLite session persistence for resume support
        self._session_manager = SessionManager(config.sqlite_path)
        # Pending clarification futures for AskUserQuestion (session_id → Future)
        self._pending_clarifications: Dict[str, asyncio.Future] = {}

    async def query(self, prompt: str, websocket: Any, session_id: str = "default",
                    stop_event: Optional[asyncio.Event] = None) -> None:
        """Send a query through the SDK and stream results to the WebSocket."""
        # Cleanup expired sessions on each query (matches Anthropic path pattern)
        await self._cleanup_expired_sessions()

        entry = self._sessions.get(session_id)

        if entry is None:
            # New session — check SQLite for a resumable SDK session
            stored_sdk_id = self._session_manager.get_sdk_session_id(session_id)
            ws_ref = {"ws": websocket}
            thinking_ids: Dict[str, str] = {}
            session_tools_used: list = []
            session_tool_counts: Counter = Counter()
            options = self._build_options(
                ws_ref, thinking_ids, session_tools_used,
                session_id=session_id,
                resume_session_id=stored_sdk_id,
                tool_call_counts=session_tool_counts,
            )
            client = ClaudeSDKClient(options)
            self._sessions[session_id] = {
                "client": client,
                "ws_ref": ws_ref,
                "thinking_ids": thinking_ids,
                "tools_used": session_tools_used,
                "last_active": time.monotonic(),
                "sdk_session_id": stored_sdk_id,
                "tool_call_counts": session_tool_counts,
            }
            # connect() initializes the subprocess; query() sends the prompt
            await client.connect()
            await client.query(prompt, session_id=session_id)
            if stored_sdk_id:
                print(f"[SDK Bridge] Resumed SDK session {stored_sdk_id[:12]}...", file=sys.stderr)
        else:
            # Existing session — update websocket reference, send new query
            client = entry["client"]
            entry["ws_ref"]["ws"] = websocket
            entry["tools_used"].clear()  # Reset for new query
            entry.setdefault("tool_call_counts", Counter()).clear()  # Reset rate limiter
            entry["last_active"] = time.monotonic()
            session_tools_used = entry["tools_used"]
            thinking_ids = entry["thinking_ids"]
            ws_ref = entry["ws_ref"]
            await client.query(prompt, session_id=session_id)

        # Streaming state
        text_streaming = False
        text_buffer = ""
        last_flush = time.monotonic()
        current_block_type = None  # "text" | "tool_use" | None
        first_turn = True
        analyzing_id = str(uuid.uuid4())
        tools_used = session_tools_used  # Shared with hooks — populated by post_tool_use

        stopped = False  # Set after interrupt — drain remaining messages silently

        try:
            # Send analyzing indicator on first turn
            if first_turn:
                await websocket.send_json({
                    "type": "thinking",
                    "thinking_id": analyzing_id,
                    "thinking_type": "analyzing",
                    "content": "Understanding your request..."
                })

            async for msg in client.receive_response():
                # Check for stop signal — interrupt once, then drain silently
                if not stopped and stop_event and stop_event.is_set():
                    try:
                        await client.interrupt()
                    except Exception:
                        pass
                    if text_streaming:
                        if text_buffer:
                            await websocket.send_json({"type": "text_delta", "content": text_buffer})
                            text_buffer = ""
                        await websocket.send_json({"type": "text_stream_end"})
                        text_streaming = False
                    stopped = True
                    continue  # Keep consuming to drain the pipe

                # After interrupt, silently consume until ResultMessage
                if stopped:
                    if isinstance(msg, ResultMessage):
                        break  # Pipe fully drained, client is in clean state
                    continue

                if isinstance(msg, SystemMessage):
                    continue

                elif isinstance(msg, StreamEvent):
                    event = msg.event
                    event_type = event.get("type", "")

                    if event_type == "content_block_start":
                        block = event.get("content_block", {})
                        block_type = block.get("type", "")

                        if block_type == "text":
                            current_block_type = "text"
                            # Complete analyzing thinking on first text block
                            if first_turn:
                                first_turn = False
                                await websocket.send_json({
                                    "type": "thinking",
                                    "thinking_id": analyzing_id,
                                    "thinking_type": "analyzing",
                                    "content": "Understanding your request...",
                                    "thinking_completed": True
                                })
                            # Start text stream
                            if not text_streaming:
                                await websocket.send_json({"type": "text_stream_start"})
                                text_streaming = True

                        elif block_type == "tool_use":
                            current_block_type = "tool_use"
                            # End any active text stream before tool execution
                            if text_streaming:
                                if text_buffer:
                                    await websocket.send_json({"type": "text_delta", "content": text_buffer})
                                    text_buffer = ""
                                await websocket.send_json({"type": "text_stream_end"})
                                text_streaming = False

                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        delta_type = delta.get("type", "")

                        if delta_type == "text_delta" and current_block_type == "text":
                            text_buffer += delta.get("text", "")
                            now = time.monotonic()
                            if now - last_flush >= 0.05:  # Flush every 50ms
                                if text_buffer:
                                    await websocket.send_json({"type": "text_delta", "content": text_buffer})
                                    text_buffer = ""
                                last_flush = now

                    elif event_type == "content_block_stop":
                        if current_block_type == "text":
                            # Flush remaining text buffer
                            if text_buffer:
                                await websocket.send_json({"type": "text_delta", "content": text_buffer})
                                text_buffer = ""
                        current_block_type = None

                    elif event_type == "message_stop":
                        # End of a turn — close text stream if active
                        if text_streaming:
                            if text_buffer:
                                await websocket.send_json({"type": "text_delta", "content": text_buffer})
                                text_buffer = ""
                            await websocket.send_json({"type": "text_stream_end"})
                            text_streaming = False

                elif isinstance(msg, AssistantMessage):
                    # Complete message for this turn — text was already streamed via
                    # StreamEvents. Just ensure text stream is closed.
                    if text_streaming:
                        if text_buffer:
                            await websocket.send_json({"type": "text_delta", "content": text_buffer})
                            text_buffer = ""
                        await websocket.send_json({"type": "text_stream_end"})
                        text_streaming = False

                elif isinstance(msg, ResultMessage):
                    # Capture SDK session ID for resume support
                    sdk_sid = getattr(msg, "session_id", None)
                    if sdk_sid:
                        entry = self._sessions.get(session_id)
                        if entry:
                            entry["sdk_session_id"] = sdk_sid
                        # Persist to SQLite for cross-refresh resume
                        try:
                            self._session_manager.ensure_session(session_id)
                            self._session_manager.set_sdk_session_id(session_id, sdk_sid)
                        except Exception as e:
                            print(f"[SDK Bridge] Failed to persist SDK session: {e}", file=sys.stderr)

                    # Final result — close any open stream and send done/error
                    if text_streaming:
                        if text_buffer:
                            await websocket.send_json({"type": "text_delta", "content": text_buffer})
                            text_buffer = ""
                        await websocket.send_json({"type": "text_stream_end"})
                        text_streaming = False

                    # Complete analyzing if still pending (e.g., error on first turn)
                    if first_turn:
                        first_turn = False
                        await websocket.send_json({
                            "type": "thinking",
                            "thinking_id": analyzing_id,
                            "thinking_type": "analyzing",
                            "content": "Understanding your request...",
                            "thinking_completed": True
                        })

                    if msg.is_error:
                        await websocket.send_json({
                            "type": "error",
                            "content": msg.result or "An error occurred"
                        })
                    else:
                        # Send contextual suggestions before done
                        suggestions = _generate_suggestions(tools_used, prompt)
                        if suggestions:
                            await websocket.send_json({
                                "type": "suggestions",
                                "suggestions": suggestions,
                            })
                        await websocket.send_json({"type": "done"})
                    break

        except Exception as e:
            print(f"[SDK Bridge] Error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

            # Clean up streaming state
            if text_streaming:
                try:
                    await websocket.send_json({"type": "text_stream_end"})
                except Exception:
                    pass

            try:
                await websocket.send_json({
                    "type": "error",
                    "content": str(e)
                })
            except Exception:
                pass

    def _build_options(
        self,
        ws_ref: Dict[str, Any],
        thinking_ids: Dict[str, str],
        session_tools_used: list,
        session_id: str = "default",
        resume_session_id: Optional[str] = None,
        tool_call_counts: Optional[Counter] = None,
    ) -> ClaudeAgentOptions:
        """Build SDK options with hooks that send messages to the WebSocket.

        Args:
            ws_ref: Mutable dict {"ws": websocket} so hooks always see current WS.
            thinking_ids: Shared dict {tool_use_id: thinking_uuid} between pre/post hooks.
            session_tools_used: Mutable list of tool names — populated by post_tool_use.
            session_id: Session ID for this connection (for pending clarifications).
            resume_session_id: SDK session ID to resume (from previous conversation).
            tool_call_counts: Mutable Counter for rate limiting (reset each query).
        """
        # In-process MCP server (shared instance, no subprocess overhead)
        mcp_servers = {"openeo": self._mcp_server_config}

        # Only allow our MCP tools (excludes all built-in tools)
        allowed_tools = [f"mcp__openeo__{td['name']}" for td in TOOL_DEFINITIONS]
        allowed_tools.append("mcp__openeo__AskUserQuestion")

        # --- can_use_tool: intercept AskUserQuestion to route to frontend ---
        bridge_ref = self  # Capture self for closure

        async def can_use_tool(
            tool_name: str, input_data: dict, context: ToolPermissionContext
        ):
            if _strip_mcp_prefix(tool_name) == "AskUserQuestion":
                ws = ws_ref["ws"]
                questions = input_data.get("questions", [])
                if not questions:
                    return PermissionResultAllow(updated_input=input_data)

                # Send clarification request to frontend
                future = asyncio.get_event_loop().create_future()
                bridge_ref._pending_clarifications[session_id] = future
                try:
                    await ws.send_json({
                        "type": "clarification",
                        "questions": questions,
                    })
                    # Wait for user response (120s timeout)
                    answers = await asyncio.wait_for(future, timeout=120)
                    return PermissionResultAllow(
                        updated_input={**input_data, "answers": answers}
                    )
                except asyncio.TimeoutError:
                    bridge_ref._pending_clarifications.pop(session_id, None)
                    return PermissionResultDeny(
                        message="User did not respond to clarification within 120 seconds."
                    )
                except Exception as e:
                    bridge_ref._pending_clarifications.pop(session_id, None)
                    print(f"[SDK Bridge] AskUserQuestion error: {e}", file=sys.stderr)
                    return PermissionResultDeny(
                        message=f"Clarification failed: {e}"
                    )

            # All other tools: allow without modification
            return PermissionResultAllow(updated_input=input_data)

        # --- Hook callbacks ---

        # Mutable container to share last job title between pre/post hooks
        _last_job_title = {"value": ""}
        # Rate-limit counters — shared with session entry, reset each query()
        _tool_call_counts: Counter = tool_call_counts if tool_call_counts is not None else Counter()

        def _deny(tool_name: str, reason: str) -> dict:
            """Build a deny hook response and log audit event."""
            _audit_log.info(
                "DENY session=%s tool=%s reason=%s", session_id, tool_name, reason
            )
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }

        async def pre_tool_use(hook_input, tool_use_id_param, context):
            """Check permissions, then send tool_start and thinking to WebSocket.

            Security layers (in order):
            1. Blocked-tool deny list
            2. Input sanitisation (path traversal, shell metacharacters)
            3. Rate limiting (per-tool and global per-query)
            4. Spatial extent validation
            5. Audit logging of every decision
            """
            ws = ws_ref["ws"]
            tool_name = _strip_mcp_prefix(hook_input.get("tool_name", ""))
            tool_input_data = hook_input.get("tool_input", {})
            t_use_id = hook_input.get("tool_use_id", tool_use_id_param or "")
            display_name = _tool_display_name(tool_name)

            # --- Layer 1: Blocked tools ---
            if tool_name in BLOCKED_TOOLS:
                return _deny(tool_name, (
                    f"Tool '{tool_name}' is blocked for safety. "
                    "Bulk-delete operations are not permitted."
                ))

            # --- Layer 2: Input sanitisation ---
            suspicious = check_suspicious_input(tool_input_data)
            if suspicious:
                return _deny(tool_name, (
                    f"Input rejected for tool '{tool_name}': {suspicious}"
                ))

            # --- Layer 3: Rate limiting ---
            _tool_call_counts[tool_name] += 1
            total_calls = sum(_tool_call_counts.values())

            # Per-tool limit
            per_tool_limit = RATE_LIMITS.get(tool_name)
            if per_tool_limit is not None and _tool_call_counts[tool_name] > per_tool_limit:
                return _deny(tool_name, (
                    f"Rate limit exceeded for '{tool_name}': "
                    f"{_tool_call_counts[tool_name]}/{per_tool_limit} calls this query."
                ))

            # Global limit
            if total_calls > RATE_LIMIT_DEFAULT:
                return _deny(tool_name, (
                    f"Global rate limit exceeded: {total_calls}/{RATE_LIMIT_DEFAULT} "
                    "tool calls this query."
                ))

            # --- Layer 4: Spatial extent validation ---
            if tool_name in SAFE_MODIFY_TOOLS:
                extent_result = _validate_extent(tool_input_data)
                if extent_result is False:
                    return _deny(tool_name, (
                        "Spatial extent is too large (>50 degrees). "
                        "Please use a smaller area."
                    ))
                if isinstance(extent_result, dict):
                    msg = extent_result.get("message", "Large spatial extent detected")
                    return _deny(tool_name, msg)

            # --- All checks passed — audit ALLOW and proceed ---
            _audit_log.info(
                "ALLOW session=%s tool=%s call#=%d",
                session_id, tool_name, _tool_call_counts[tool_name],
            )

            # Capture job title for naming saved results
            if tool_name == "openeo_create_job":
                _last_job_title["value"] = tool_input_data.get("title", "")

            tid = str(uuid.uuid4())
            thinking_ids[t_use_id] = tid

            try:
                await ws.send_json({
                    "type": "thinking",
                    "thinking_id": tid,
                    "thinking_type": "executing",
                    "content": f"Running {display_name}..."
                })
                await ws.send_json({
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "tool_input": tool_input_data,
                })
            except Exception as e:
                print(f"[SDK Bridge] PreToolUse WS error: {e}", file=sys.stderr)

            return {}  # Empty SyncHookJSONOutput = approve and continue

        async def post_tool_use(hook_input, tool_use_id_param, context):
            """Send tool_result, thinking_completed, viz, quality, graph to WebSocket."""
            ws = ws_ref["ws"]
            tool_name = _strip_mcp_prefix(hook_input.get("tool_name", ""))
            tool_response = hook_input.get("tool_response", "")
            t_use_id = hook_input.get("tool_use_id", tool_use_id_param or "")

            # Track tool usage for contextual suggestions
            session_tools_used.append(tool_name)

            # Parse tool response — may be JSON string or MCP content format
            tool_result = _parse_tool_response(tool_response)

            try:
                # 1. Send tool_result
                result_payload = tool_result if isinstance(tool_result, (dict, list, str, int, float, bool)) else str(tool_result)
                await ws.send_json({
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": result_payload,
                })

                # 2. Send thinking completed
                tid = thinking_ids.pop(t_use_id, None)
                if tid:
                    await ws.send_json({
                        "type": "thinking",
                        "thinking_id": tid,
                        "thinking_type": "executing",
                        "content": f"Running {_tool_display_name(tool_name)}...",
                        "thinking_completed": True
                    })

                # 3. Extract and send visualization
                viz = extract_visualization(tool_name, tool_result, title_hint=_last_job_title["value"])
                if viz:
                    await ws.send_json({
                        "type": "visualization",
                        "visualization": viz,
                    })

                # 4. Send quality_metrics (additional message for dashboard)
                if tool_name == "openeo_quality_metrics":
                    await ws.send_json({
                        "type": "quality_metrics",
                        "metrics": tool_result,
                    })

                # 5. Send process_graph (additional message for graph panel)
                if tool_name == "openeo_generate_graph":
                    await ws.send_json({
                        "type": "process_graph",
                        "graph": tool_result,
                    })

            except Exception as e:
                print(f"[SDK Bridge] PostToolUse WS error: {e}", file=sys.stderr)

            return {}  # Continue normally

        hooks = {
            "PreToolUse": [
                HookMatcher(matcher=".*", hooks=[pre_tool_use])
            ],
            "PostToolUse": [
                HookMatcher(matcher=".*", hooks=[post_tool_use])
            ],
        }

        opts = ClaudeAgentOptions(
            system_prompt=OpenEOAIClient.SYSTEM_PROMPT,
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            permission_mode="default",
            max_turns=10,
            model=self.config.model,
            include_partial_messages=True,
            hooks=hooks,
            can_use_tool=can_use_tool,
        )
        if resume_session_id:
            opts.resume = resume_session_id
        return opts

    async def _cleanup_expired_sessions(self) -> None:
        """Remove SDK sessions that have been inactive beyond the TTL.

        Also evicts the oldest sessions if count exceeds _SDK_SESSION_MAX_COUNT.
        Called at the start of each query() call.
        """
        now = time.monotonic()
        expired = [
            sid for sid, entry in self._sessions.items()
            if now - entry.get("last_active", 0) > _SDK_SESSION_TTL_SECONDS
        ]
        for sid in expired:
            print(f"[SDK Bridge] Expiring idle session {sid}", file=sys.stderr)
            entry = self._sessions.pop(sid, None)
            if entry:
                try:
                    await entry["client"].disconnect()
                except Exception as e:
                    print(f"[SDK Bridge] Cleanup disconnect error for {sid}: {e}", file=sys.stderr)

        # Evict oldest if over max count
        if len(self._sessions) > _SDK_SESSION_MAX_COUNT:
            sorted_sessions = sorted(
                self._sessions.items(),
                key=lambda item: item[1].get("last_active", 0),
            )
            to_evict = sorted_sessions[:len(self._sessions) - _SDK_SESSION_MAX_COUNT]
            for sid, entry in to_evict:
                print(f"[SDK Bridge] Evicting session {sid} (over max count)", file=sys.stderr)
                self._sessions.pop(sid, None)
                try:
                    await entry["client"].disconnect()
                except Exception:
                    pass

    async def disconnect_session(self, session_id: str) -> None:
        """Disconnect and clean up a session's SDK client."""
        entry = self._sessions.pop(session_id, None)
        if entry:
            try:
                await entry["client"].disconnect()
            except Exception as e:
                print(f"[SDK Bridge] Disconnect error for {session_id}: {e}", file=sys.stderr)

    async def disconnect_all(self) -> None:
        """Disconnect all SDK clients (e.g., on server shutdown)."""
        for sid in list(self._sessions.keys()):
            await self.disconnect_session(sid)

    def resolve_clarification(self, session_id: str, answers: Dict[str, Any]) -> None:
        """Resolve a pending AskUserQuestion clarification with user answers.

        Called by the WebSocket handler when the frontend sends
        a clarification_response message.
        """
        future = self._pending_clarifications.pop(session_id, None)
        if future and not future.done():
            future.set_result(answers)
        else:
            print(f"[SDK Bridge] No pending clarification for {session_id}", file=sys.stderr)


def _parse_tool_response(tool_response: Any) -> Any:
    """Parse raw tool response from SDK hook into usable result dict.

    The tool_response from PostToolUse hook may be:
    - A JSON string
    - A dict with MCP "content" format: {"content": [{"type": "text", "text": "..."}]}
    - A bare list of MCP content items: [{"type": "text", "text": "..."}]
    - A plain string
    - A dict/list already
    """
    result = tool_response

    # Parse JSON string
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result

    # Unwrap MCP content format — bare list: [{"type": "text", "text": "..."}]
    if isinstance(result, list) and len(result) > 0:
        first = result[0]
        if isinstance(first, dict) and first.get("type") == "text":
            text = first.get("text", "")
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text

    # Unwrap MCP content format — dict wrapper: {"content": [{"type": "text", "text": "..."}]}
    if isinstance(result, dict) and "content" in result:
        content_items = result.get("content", [])
        if isinstance(content_items, list) and len(content_items) > 0:
            first = content_items[0]
            if isinstance(first, dict) and first.get("type") == "text":
                text = first.get("text", "")
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return text

    return result


def _generate_suggestions(tools_used: list, prompt: str) -> list:
    """Generate contextual follow-up suggestions based on tools used during the query."""
    unique_tools = list(dict.fromkeys(tools_used))  # Deduplicate, preserve order
    suggestions = []

    has_viz = any(t.startswith("viz_") for t in unique_tools)
    has_job = "openeo_create_job" in unique_tools or "openeo_get_results" in unique_tools
    has_graph = "openeo_generate_graph" in unique_tools
    has_collections = "openeo_list_collections" in unique_tools
    has_quality = "openeo_quality_metrics" in unique_tools
    has_ndvi = "ndvi" in prompt.lower()
    has_temporal = "openeo_parse_temporal" in unique_tools

    if has_job and has_viz:
        suggestions.append("Compare this result with a different time period")
        suggestions.append("Calculate statistics for this area")
        suggestions.append("Export the result as GeoTIFF")
        suggestions.append("Run the same analysis for a nearby region")
    elif has_job:
        suggestions.append("Show the result on the map")
        suggestions.append("Run the same analysis for a different area")
        suggestions.append("Check the quality metrics for this job")
    elif has_graph:
        suggestions.append("Run this process graph as a job")
        suggestions.append("Validate and optimize the process graph")
        suggestions.append("Modify the graph to add cloud masking")
    elif has_collections:
        suggestions.append("Show NDVI using one of these collections")
        suggestions.append("What bands are available in Sentinel-2?")
        suggestions.append("Compare two collections for my area")
    elif has_quality:
        suggestions.append("Proceed with the analysis")
        suggestions.append("Try a different time period with less cloud cover")
        suggestions.append("Show available data for this region")

    if not suggestions:
        # Generic follow-ups based on what happened
        if has_temporal:
            suggestions.append("Run the analysis for this time period")
        suggestions.append("Show available collections for this area")
        suggestions.append("Calculate NDVI for a different region")
        suggestions.append("Analyze land cover changes over time")

    if has_ndvi and has_job:
        suggestions.insert(0, "Compare NDVI between two seasons")

    return suggestions[:4]
