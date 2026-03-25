# OpenEO Deployment - Claude Agent SDK Feature Gap Analysis

> **Date**: 2026-02-07
> **Analyzed by**: 4-agent parallel team (sdk-feature-analyst, mcp-analyst, websocket-analyst, frontend-analyst)
> **SDK Version**: claude-agent-sdk==0.1.31
> **Reference**: Claude-SDK.md (comprehensive SDK docs, 2913 lines)

---

## Executive Summary

Our OpenEO webapp uses **~35% of available Claude Agent SDK features**. The current integration successfully implements core streaming, hooks, MCP tools, and interrupt support. However, there are **critical security gaps**, a **memory leak**, **~1,460 lines of dead/replaceable code**, and **12 high-value unused SDK features** that could significantly improve UX, reliability, and cost efficiency.

### Key Numbers

| Metric | Value |
|--------|-------|
| SDK features USED | 14/40 (35%) |
| SDK features PARTIALLY USED | 7/40 (18%) |
| SDK features NOT USED | 19/40 (47%) |
| High-priority opportunities | 6 |
| Critical bugs found | 2 (session leak, permissions bypass) |
| Dead code removable | ~1,460 lines |

---

## Critical Issues (Fix Immediately)

### 1. Security: Permissions Not Enforced in SDK Path

**Severity**: HIGH
**Location**: `claude_sdk_bridge.py:419`

```python
permission_mode="bypassPermissions"  # ALL permission checks bypassed
```

`permissions.py` defines `BLOCKED_TOOLS`, `READ_ONLY_TOOLS`, and extent validation (`_validate_extent` blocks >50-degree queries). **None of this is enforced in the SDK path.** It only works in the legacy Anthropic API path.

**Fix**: Wire permissions into the existing `PreToolUse` hook:

```python
async def pre_tool_use(hook_input, tool_use_id_param, context):
    tool_name = _strip_mcp_prefix(hook_input.get("tool_name", ""))
    tool_input = hook_input.get("tool_input", {})

    # Check blocked tools
    if tool_name in BLOCKED_TOOLS:
        return {'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': f'Tool {tool_name} is blocked'
        }}

    # Validate spatial extent
    result = _validate_extent(tool_input)
    if result is not True:
        return {'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': str(result)
        }}

    # ... existing thinking/tool_start logic ...
    return {}
```

Then change `permission_mode` to `"default"`.

**Effort**: Low (1-2 hours)

---

### 2. Memory Leak: SDK Sessions Never Expire

**Severity**: HIGH
**Location**: `claude_sdk_bridge.py:74`

`ClaudeSDKBridge._sessions` dict has **no TTL cleanup**. If a user opens a browser tab, sends one query, and closes the tab, the `ClaudeSDKClient` + MCP subprocess leak forever until server restart.

The Anthropic path has 30-min TTL cleanup in `web_interface.py:55`. The SDK path has nothing.

Also: `disconnect_all()` exists but is **never registered** as a server shutdown handler.

**Fix**:
1. Add periodic TTL cleanup (mirror Anthropic path's 30-min expiry)
2. Register `disconnect_all()` on server shutdown
3. Track `last_active` timestamp per session

**Effort**: Low (2-3 hours)

---

## SDK Feature Usage Matrix

### Currently USED Features

| Feature | Location | Notes |
|---------|----------|-------|
| `ClaudeSDKClient` | `claude_sdk_bridge.py:24,87` | Per-session instances |
| `client.connect()` / `disconnect()` | `:90` / `:432` | Manual lifecycle |
| `client.query(prompt, session_id=)` | `:91,97` | Multi-turn with session IDs |
| `client.receive_response()` | `:120` | Async message iteration |
| `client.interrupt()` | `:124` | Stop button support |
| `StreamEvent` handling | `:145-208` | Full text streaming (start/delta/end) |
| `SystemMessage` / `AssistantMessage` / `ResultMessage` | `:26,142,210,220` | All major types handled |
| `include_partial_messages=True` | `:422` | Enables real-time streaming |
| `PreToolUse` hook | `:314-344` | Sends thinking + tool_start to WS |
| `PostToolUse` hook | `:346-404` | Sends tool_result + viz + quality |
| `HookMatcher` | `:408,411` | `matcher=".*"` for all tools |
| `McpStdioServerConfig` | `:297-304` | stdio transport to MCP subprocess |
| `allowed_tools` | `:307,418` | Restricted to `mcp__openeo__*` |
| `max_turns=10` | `:420` | Turn limit guard |

### PARTIALLY USED Features

| Feature | Current Use | What's Missing |
|---------|-------------|----------------|
| Message type handling | Handles 5 types | Ignores `ToolResultMessage`, `ResultMessage.subtype` granularity |
| Hook system | PreToolUse + PostToolUse | Missing: `UserPromptSubmit`, `Stop`, `PreCompact`, hook deny/modify |
| Permissions | `bypassPermissions` + `allowed_tools` | Not using `canUseTool` callback or hook-based denial |
| Session management | Manual `_sessions` dict | Not capturing SDK session IDs, no persistence |
| Error handling | `msg.is_error` boolean | Not using `ResultMessage.subtype` (error_during_execution vs max_turns vs cancelled) |

### NOT USED Features (Opportunities)

| Feature | Priority | Impact | Effort |
|---------|----------|--------|--------|
| `create_sdk_mcp_server()` (in-process tools) | P0 | Perf + Simplicity | Medium |
| `AskUserQuestion` + `canUseTool` callback | P0 | UX Quality | Medium |
| Hook-based security (deny/modify) | P0 | Security | Low |
| SDK-native `resume` sessions | P1 | Reliability | Medium |
| `output_format` (Structured Outputs) | P1 | Frontend Reliability | Medium |
| Plan Mode for expensive queries | P1 | UX + Cost Savings | High |
| Subagents + cost-optimized routing | P2 | Cost Optimization | High |
| Extended Thinking | P2 | Query Quality | Low |
| Auto-Compaction | P2 | Long Conversations | Low |
| `fork_session` | P3 | "What-if" Analysis | Medium |
| Streaming input mode | P3 | Mid-turn corrections | High |
| Artifacts (HTML Components) | P3 | Custom Visualizations | High |

---

## Detailed Recommendations

### P0: In-Process MCP Server (`create_sdk_mcp_server`)

**What it does**: Replaces the subprocess-based `mcp_stdio_server.py` with an in-process MCP server using `@tool` decorator.

**Why it matters**:
- Eliminates subprocess spawning overhead per session
- Removes JSON-RPC serialization/deserialization latency
- Replaces ~700 lines of code (185-line stdio server + 440-line manual `TOOL_DEFINITIONS`)
- Auto-generates tool schemas from type hints

**Implementation sketch**:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("list_collections", "List available EO data collections",
      {"query": str, "limit": int})
async def list_collections(args: dict) -> dict:
    result = await _list_collections_handler(args)
    return {"content": [{"type": "text", "text": json.dumps(result)}]}

# ... repeat for all 22 tools ...

openeo_server = create_sdk_mcp_server(
    name="openeo", version="1.0.0",
    tools=[list_collections, get_collection_info, ...]  # All 22
)

# In ClaudeSDKBridge._build_options():
options = ClaudeAgentOptions(
    mcp_servers={"openeo": openeo_server},  # No subprocess!
    ...
)
```

**Files affected**: `claude_sdk_bridge.py`, new `sdk/tools.py`, delete `mcp_stdio_server.py`
**Lines removed**: ~700 | **Lines added**: ~200
**Effort**: 1-2 days

---

### P0: Interactive Clarification (`AskUserQuestion`)

**What it does**: Enables Claude to ask the user multiple-choice questions before executing (e.g., "Which collection?", "Apply cloud masking?").

**Why it matters**: Currently Claude guesses parameters. Wrong guesses waste expensive STAC queries (>120s each).

**Requirements**:
1. Enable `canUseTool` callback in SDK options to route `AskUserQuestion` to WebSocket
2. Add new WS message type `clarification` (backend -> frontend)
3. Add `clarification_response` (frontend -> backend)
4. Frontend: new `ClarificationCard` component with radio buttons

**Implementation sketch**:

```python
# In ClaudeSDKBridge
async def can_use_tool(tool_name, input_data, context):
    if tool_name == "AskUserQuestion":
        # Send questions to frontend via WebSocket
        await ws.send_json({
            "type": "clarification",
            "questions": input_data["questions"]
        })
        # Wait for frontend response
        response = await self._wait_for_clarification(session_id)
        return PermissionResultAllow(
            updated_input={"questions": input_data["questions"],
                           "answers": response}
        )
    return PermissionResultAllow(updated_input=input_data)
```

**Effort**: 2-3 days (backend + frontend)

---

### P1: SDK-Native Session Resume

**What it does**: Persists conversation state across page refreshes and server restarts using SDK's built-in `resume=session_id`.

**Why it matters**: Currently closing a browser tab loses all conversation history. The SQLite `SessionManager` in `sdk/sessions.py` already exists but is **completely orphaned** (never referenced).

**Implementation**:
1. Extract `session_id` from `SystemMessage(subtype="init")` in the streaming loop
2. Store in SQLite via existing `SessionManager`
3. On reconnect, pass `resume=session_id` in `ClaudeAgentOptions`
4. Frontend sends stored `session_id` on WebSocket connect

**Effort**: 1-2 days

---

### P1: Structured Outputs

**What it does**: Forces Claude's final response to match a JSON schema, with automatic retries on validation failure.

**Why it matters**: Frontend's `ToolResultCard.tsx` uses 14 specialized renderers with heavy `as any` casting. Typed responses would eliminate runtime rendering failures.

**Implementation**:

```python
from pydantic import BaseModel

class OpenEOResponse(BaseModel):
    summary: str
    data_type: str  # "collection_info" | "analysis_result" | "job_status" | ...
    result: dict
    visualization_hint: str | None  # "map" | "chart" | "table"
    suggestions: list[str]

options = ClaudeAgentOptions(
    output_format={
        "type": "json_schema",
        "schema": OpenEOResponse.model_json_schema()
    }
)
```

**Effort**: 1-2 days

---

### P1: Plan Mode for Expensive Queries

**What it does**: Shows execution plan before running expensive operations. User approves/modifies/cancels.

**Why it matters**: STAC queries can take >120s. Users should see what will happen before committing.

**Frontend changes**:
- New `PlanPreviewCard` component with execution steps, estimated time/cost
- "Execute" / "Modify" / "Cancel" buttons
- New message types: `plan_preview`, `plan_approval`

**Effort**: 3-4 days (significant frontend + backend)

---

### P2: Subagents with Cost-Optimized Routing

**What it does**: Specialized sub-agents with different models for different task types.

**Proposed agents**:

| Agent | Model | Tools | Use Case |
|-------|-------|-------|----------|
| `data-explorer` | haiku | list_collections, get_collection_info, search | Fast data discovery (~$0.25/M tokens) |
| `graph-builder` | sonnet | generate_graph, validate_graph, estimate_extent | Process graph construction (~$3/M tokens) |
| `analyst` | sonnet | execute, get_results, visualize | Analysis + visualization |
| `job-manager` | haiku | create_job, start_job, job_status, get_results | Job lifecycle management |

**Cost impact**: ~40-60% reduction for queries that are mostly data discovery.

**Effort**: 2-3 days

---

### P2: Extended Thinking

**What it does**: Gives Claude up to 31,999 extra tokens for internal reasoning before responding.

**Why it matters**: Complex multi-step geospatial workflows (compare NDVI across years with cloud masking and seasonal correction) benefit from upfront planning. Currently Claude sometimes makes 5-6 iterative tool calls when 3-4 well-planned ones would suffice.

**Implementation**:

```python
options = ClaudeAgentOptions(
    env={"MAX_THINKING_TOKENS": "10000"},
    ...
)
```

**Effort**: 30 minutes (config change + optional frontend thinking display)

---

### P2: Auto-Compaction

**What it does**: SDK automatically summarizes conversation history at ~95% context capacity instead of hard-cutting.

**Why it matters**: Current SDK path has no token budget tracking (unlike Anthropic path's 80K limit). Auto-compaction handles long conversations gracefully.

**Implementation**:

```python
options = ClaudeAgentOptions(
    env={"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "80"},  # Compact at 80%
    hooks={
        "PreCompact": [HookMatcher(hooks=[log_compaction])],
        ...
    }
)
```

**Effort**: 1 hour

---

## Dead Code Inventory

| File | Lines | Status | Recommendation |
|------|-------|--------|---------------|
| `sdk/mcp_server.py` | 477 | **Unused** - OOP MCP abstraction, superseded by mcp_stdio_server.py | Delete |
| `sdk/mcp_lifecycle.py` | 360 | **Unused** - monitoring not integrated | Integrate into hooks OR delete |
| `sdk/sessions.py` | ~120 | **Orphaned** - SQLite SessionManager, never referenced | Wire into SDK session resume OR delete |
| `TOOL_DEFINITIONS` in `client.py` | ~440 | **Redundant** if using `@tool` decorator | Replace with `@tool` |
| `mcp_stdio_server.py` | 185 | **Replaceable** with `create_sdk_mcp_server()` | Replace |
| **Total** | **~1,460** | | |

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)

| Task | Effort | Impact |
|------|--------|--------|
| Wire permissions into PreToolUse hook | 2h | Security |
| Add session TTL cleanup to SDK bridge | 3h | Memory leak |
| Register `disconnect_all()` on shutdown | 30m | Resource cleanup |
| Enable auto-compaction (config change) | 1h | Stability |
| Enable extended thinking (config change) | 30m | Quality |
| Differentiate ResultMessage subtypes | 2h | Error UX |

### Phase 2: Architecture Improvements (Week 2)

| Task | Effort | Impact |
|------|--------|--------|
| Replace stdio MCP with `create_sdk_mcp_server()` | 2d | Performance + -700 lines |
| Implement SDK session resume with SessionManager | 2d | Reliability |
| Add audit logging hook | 2h | Observability |
| Delete dead code (mcp_server.py, mcp_lifecycle.py) | 1h | Maintenance |

### Phase 3: UX Features (Week 3-4)

| Task | Effort | Impact |
|------|--------|--------|
| AskUserQuestion + canUseTool callback | 3d | UX Quality |
| Structured outputs + typed frontend | 2d | Frontend Reliability |
| Plan mode for expensive queries | 4d | UX + Cost |
| Subagents with cost-optimized routing | 3d | Cost (-40-60%) |

### Phase 4: Advanced Features (Future)

| Task | Effort | Impact |
|------|--------|--------|
| Fork session ("what-if" branches) | 2d | Advanced UX |
| Artifacts (custom HTML visualizations) | 3d | Visualization |
| Streaming input (mid-turn corrections) | 3d | Power Users |
| File checkpointing (process graph undo) | 2d | Workflow |

---

## Appendix: New WebSocket Message Types Needed

| Message | Direction | Purpose | Required For |
|---------|-----------|---------|--------------|
| `clarification` | backend -> frontend | Multi-choice questions from Claude | AskUserQuestion |
| `clarification_response` | frontend -> backend | User's answers | AskUserQuestion |
| `plan_preview` | backend -> frontend | Execution plan with cost estimate | Plan Mode |
| `plan_approval` | frontend -> backend | User approve/modify/cancel | Plan Mode |
| `structured_result` | backend -> frontend | Validated JSON matching schema | Structured Outputs |
| `stopped` | backend -> frontend | User-initiated stop (not error) | Error differentiation |
| `compaction` | backend -> frontend | Conversation summarized | Auto-Compaction |
| `subagent_start/end` | backend -> frontend | Parallel agent progress | Subagents |
| `artifact` | backend -> frontend | Custom HTML component | Artifacts |

---

*Generated by 4-agent parallel analysis team on 2026-02-07*
