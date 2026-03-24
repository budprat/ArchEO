# ArchEO-Agent Frontend Design Spec

## Overview

A research demo frontend for ArchEO-Agent (Earth-Agent) that lets users upload satellite/aerial imagery and converse with an AI agent to analyze images for geoglyphs, ancient structures, and other archaeological features. The agent combines GPT-5.4 vision capabilities with MCP tool servers for quantitative analysis.

**Purpose:** Research demo for showcasing capabilities at conferences/paper review
**Interaction model:** Chat-first (upload image, then converse with agent)
**LLM:** GPT-5.4 (OpenAI) with vision — deliberate choice over existing Claude integration for vision capabilities
**Architecture:** Next.js 15 full-stack + FastAPI Python backend
**Note:** Existing demos use Claude/Anthropic. This frontend intentionally uses GPT-5.4 via `langchain-openai`. The LLM is configurable via `OPENAI_API_KEY` env var.

## Architecture

```
Next.js 15 Frontend (Tailwind + shadcn/ui)
  │
  ├── Chat Panel (left ~55%) — streaming agent reasoning
  ├── Image Viewer (right ~45%) — pan/zoom uploaded & result images
  └── Upload Zone — drag-drop file upload
  │
  Next.js API Routes (/api/*) — thin proxy
  │
  ▼
FastAPI Backend (Python)
  │
  ├── LangGraph ReAct Agent (GPT-5.4 with vision)
  ├── File Processing Service (GDAL/rasterio)
  │
  └── MCP Tool Servers (5 existing + 1 new)
      ├── Index      — spectral indices (NDVI, NDWI, EVI, etc.)
      ├── Inversion  — physical parameter retrieval
      ├── Perception — classification, detection, segmentation
      ├── Analysis   — spatial statistics, hotspot analysis
      ├── Statistics  — time series, trend analysis
      └── Archaeology (NEW) — edge detection, pattern analysis, DEM hillshade
```

### Key Architecture Decisions

1. **Next.js API routes as thin proxy** — forward requests to FastAPI, stream SSE responses back. Keeps Node.js layer minimal.
2. **FastAPI runs the agent** — direct access to Python MCP tools, LangGraph, GDAL. Same pattern as existing `demo_e2e.py`.
3. **GPT-5.4 with vision** — receives the generated thumbnail (PNG, max 1024px) as base64 for initial interpretation, then orchestrates MCP tools on the original file for quantitative follow-up. The raw GeoTIFF is NOT sent to the vision API.
4. **SSE streaming** — real-time display of agent thinking, tool calls, and results.
5. **Local filesystem storage** — no database. Files stored in `uploads/{file_id}/` directory. Appropriate for demo scope.

## Frontend

### Tech Stack

- Next.js 15 (App Router)
- Tailwind CSS
- shadcn/ui components
- react-zoom-pan-pinch (image viewer)
- useReducer for state management (no Redux)

### Page Structure

Single page app at `/`. Two-panel layout:

**Left panel (~55%) — Chat Panel:**
- Message list with streaming support
- User messages (blue, right-aligned, file thumbnail attachment)
- Agent thinking (muted card, "Thinking..." with streaming text)
- Tool call cards (dark, collapsible, show tool name + params)
- Tool result cards (green-bordered, show result text + optional image)
- Agent response (left-aligned, markdown rendered, inline result images)
- Error messages (red-bordered, retry button)
- Input area with textarea + send button

**Right panel (~45%) — Image Viewer:**
- Pan/zoom image display (react-zoom-pan-pinch)
- Layer toggle tabs (original / result overlays)
- File metadata display (format, dimensions, bands, CRS)
- Drag-drop upload zone when no file loaded

### shadcn/ui Components Used

| Component | Usage |
|-----------|-------|
| `ScrollArea` | Chat message list |
| `Avatar` | User/agent message avatars |
| `Button` | Send, upload, retry actions |
| `Textarea` | Chat input |
| `Card` | Message containers, tool call cards |
| `Collapsible` | Expandable tool call details |
| `Badge` | Model indicator, file type badge |
| `Tabs` | Image layer toggle |
| `Table` | File metadata display |
| `Dialog` | Upload dialog |
| `Tooltip` | Tool parameter descriptions |
| `Skeleton` | Loading states |

### State Management

```typescript
interface AppState {
  messages: ChatMessage[];
  isStreaming: boolean;
  uploadedFile: UploadedFile | null;
  resultImages: ResultImage[];
  activeImageLayer: string; // 'original' | result image ID
}

type ChatMessage =
  | { type: 'user'; content: string; fileId?: string }
  | { type: 'thinking'; content: string }
  | { type: 'tool_call'; tool: string; params: Record<string, unknown> }
  | { type: 'tool_result'; tool: string; result: string; imageId?: string }
  | { type: 'agent'; content: string; images?: string[] }
  | { type: 'error'; message: string };

interface UploadedFile {
  id: string;
  name: string;
  format: string;
  dimensions: [number, number];
  bands: number;
  crs: string | null;
  thumbnailUrl: string;
}

interface ResultImage {
  id: string;
  tool: string;
  url: string;
  label: string;
}
```

## Backend

### FastAPI Endpoints

| Endpoint | Method | Request | Response |
|----------|--------|---------|----------|
| `/api/upload` | POST | Multipart file | `{ file_id, metadata, thumbnail_url }` |
| `/api/chat` | POST | `{ message, file_id, history: HistoryEntry[] }` | SSE stream |
| `/api/files/{id}` | GET | — | File binary (original or thumbnail) |
| `/api/results/{id}` | GET | — | Result image binary |
| `/api/health` | GET | — | `{ status, mcp_servers: {} }` |

### Chat History Format

```typescript
interface HistoryEntry {
  role: 'user' | 'assistant';
  content: string;
  fileId?: string; // only for user messages with file attachments
}
```

The backend converts these to LangGraph `HumanMessage`/`AIMessage` objects for the agent.

### SSE Stream Events

```
event: thinking
data: {"content": "I'll analyze this image for archaeological features..."}

event: tool_call
data: {"tool": "edge_detection_canny", "params": {"image_path": "...", "threshold": 50}}

event: tool_result
data: {"tool": "edge_detection_canny", "result": "14 features detected", "image_id": "result_003"}

event: message
data: {"content": "I found 14 linear features...", "images": ["result_003"]}

event: error
data: {"message": "Tool execution failed: ..."}

event: done
data: {}
```

### Agent Configuration

- **Model:** GPT-5.4 via langchain-openai
- **Pattern:** LangGraph ReAct agent (same as `demo_e2e.py`)
- **MCP servers:** Boot all 6 (5 existing + 1 new Archaeology) as stdio subprocesses on FastAPI startup
- **Recursion limit:** 30 steps
- **Temperature:** 0.1

### LangGraph Streaming Pattern

The existing `demo_e2e.py` uses `agent.ainvoke()` which returns results all at once. For SSE streaming, the backend MUST use `astream_events` (v2) to get intermediate steps:

```python
async for event in agent.astream_events(input, version="v2"):
    kind = event["event"]
    if kind == "on_chat_model_stream":
        # Token-by-token thinking → SSE "thinking" event
        yield sse_event("thinking", {"content": event["data"]["chunk"].content})
    elif kind == "on_tool_start":
        # Tool invocation → SSE "tool_call" event
        yield sse_event("tool_call", {"tool": event["name"], "params": event["data"]["input"]})
    elif kind == "on_tool_end":
        # Tool result → SSE "tool_result" event
        yield sse_event("tool_result", {"tool": event["name"], "result": event["data"]["output"]})
```

This is the key difference from the existing demo pattern and is required for real-time streaming.

### CORS Configuration

All frontend requests go through Next.js API routes (proxy pattern), so CORS is NOT needed on FastAPI. However, for direct file serving (`/api/files/{id}`, `/api/results/{id}`), these are also proxied through Next.js routes. If direct FastAPI access is ever needed during development, add `CORSMiddleware` with `allow_origins=["http://localhost:3000"]`.

**System Prompt:**

> You are ArchEO-Agent, an AI assistant specialized in archaeological analysis of satellite and aerial imagery. You combine computer vision analysis with Earth observation tools to detect geoglyphs, ancient structures, and landscape modifications. You have access to edge detection, pattern analysis, terrain analysis, spectral indices, and statistical tools via MCP. Analyze images step-by-step: first describe what you observe visually, then apply appropriate tools for quantitative analysis, then interpret results in archaeological context. Always explain your reasoning and what each tool result means.

### File Processing Service

On upload:
1. Validate file type (GDAL-supported formats)
2. Read with GDAL — extract metadata (dimensions, bands, CRS, data type)
3. Generate PNG thumbnail (normalize to uint8 for GeoTIFF)
4. Save original + thumbnail + metadata.json to `uploads/{file_id}/`
5. Return file_id and metadata to frontend

### File Storage Layout

```
uploads/
  └── {uuid}/
      ├── original.tif        # uploaded file (preserved original name in metadata)
      ├── thumbnail.png       # generated preview (max 1024px)
      ├── metadata.json       # extracted metadata
      └── results/
          ├── result_001.png  # tool output images
          ├── result_002.png
          └── ...
```

## New Archaeology MCP Server

File: `agent/tools/Archaeology.py`

Follows the exact same FastMCP pattern as the 5 existing tool servers (FastMCP + argparse for temp_dir). Imports `from utils import read_image, read_image_uint8` for consistent image reading. OpenCV-based tools use `read_image_uint8()` since OpenCV expects uint8 arrays.

### Output Path Strategy

The MCP servers use `TEMP_DIR / output_path` for saving results. On FastAPI startup, the Archaeology server (and all MCP servers) are launched with `--temp_dir` set to `uploads/{session_id}/results/`. This way tool outputs land directly in the correct upload directory. The agent provides relative paths like `edge_001.png` and the tool saves to `uploads/{session_id}/results/edge_001.png`.

### Tools

| Tool | Returns | Output |
|------|---------|--------|
| `edge_detection_canny` | image | Edge map PNG |
| `edge_detection_sobel` | image | Gradient map PNG |
| `linear_feature_detection` | image + data | Annotated image + line stats JSON |
| `geometric_pattern_analysis` | image + data | Annotated image + shape stats JSON |
| `dem_hillshade` | image | Hillshade rendering PNG |
| `texture_analysis_glcm` | data only | Texture metrics dict (no image) |

#### 1. `edge_detection_canny`
Canny edge detection with configurable thresholds. Highlights linear features like geoglyphs, ancient roads, wall foundations.

**Parameters:**
- `image_path` (str): Input image path
- `low_threshold` (float, default=50): Lower hysteresis threshold
- `high_threshold` (float, default=150): Upper hysteresis threshold
- `output_path` (str): Relative output path

**Returns:** Path to saved edge map image

**Libraries:** OpenCV

#### 2. `edge_detection_sobel`
Sobel gradient magnitude. Better for detecting subtle terrain features and gradual elevation changes.

**Parameters:**
- `image_path` (str): Input image path
- `ksize` (int, default=3): Kernel size (3, 5, or 7)
- `output_path` (str): Relative output path

**Returns:** Path to saved gradient image

**Libraries:** OpenCV

#### 3. `linear_feature_detection`
Hough line transform. Detects straight lines and measures their orientations and lengths. Useful for identifying ancient roads, geoglyph lines, field boundaries.

**Parameters:**
- `image_path` (str): Input image path (should be edge-detected)
- `min_line_length` (int, default=50): Minimum line length in pixels
- `max_line_gap` (int, default=10): Maximum gap between line segments
- `output_path` (str): Relative output path

**Returns:** Dict with `image_path` (annotated image), `lines` (list of line coords), `orientations` (list of angles), `count` (number of lines)

**Libraries:** OpenCV

#### 4. `geometric_pattern_analysis`
Contour detection + shape descriptor analysis. Identifies geometric shapes (circles, rectangles, triangles) and measures properties like circularity, rectangularity, and symmetry. Useful for detecting man-made ground markings.

**Parameters:**
- `image_path` (str): Input binary/edge image path
- `min_area` (int, default=100): Minimum contour area in pixels
- `output_path` (str): Relative output path

**Returns:** Dict with `image_path` (annotated image), `shapes` (list of detected shapes with properties), `count` (number of shapes)

**Libraries:** OpenCV, scikit-image

#### 5. `dem_hillshade`
Hillshade rendering from DEM GeoTIFF. Simulates illumination at configurable sun angle and azimuth to reveal subtle terrain relief — critical for detecting earthworks, mounds, and leveled structures.

**Parameters:**
- `dem_path` (str): Path to DEM GeoTIFF
- `azimuth` (float, default=315): Sun azimuth in degrees
- `altitude` (float, default=45): Sun altitude in degrees
- `output_path` (str): Relative output path

**Returns:** Path to saved hillshade image

**Libraries:** GDAL, numpy

#### 6. `texture_analysis_glcm`
Gray-Level Co-occurrence Matrix texture analysis. Computes texture descriptors (contrast, homogeneity, entropy, correlation) that help distinguish natural terrain from man-made features.

**Parameters:**
- `image_path` (str): Input grayscale image path
- `distances` (list[int], default=[1]): Pixel distances for GLCM
- `angles` (list[float], default=[0]): Angles in radians for GLCM

**Returns:** Dict with texture metrics (contrast, homogeneity, entropy, correlation, energy)

**Libraries:** scikit-image

## Error Handling

| Error | Handling |
|-------|----------|
| Invalid file format | Frontend: check extension. Backend: GDAL validation, return 422 |
| File too large (>50MB) | Frontend rejects before upload |
| MCP tool crash | Agent receives error, tries alternative tool or reports gracefully |
| GPT-5.4 API timeout | SSE error event, frontend shows retry button |
| SSE connection drop | `use-chat.ts` hook auto-reconnects with exponential backoff (max 3 retries) |
| MCP server not running | `/api/health` check on page load, warning banner |
| GDAL can't read file | Return 422 with descriptive error message |

## Data Flow

```
1. User drops file on UploadZone
   → Frontend validates type (tif/png/jpg), shows loading
   → POST /api/upload (multipart)
   → FastAPI: GDAL reads, extracts metadata, generates thumbnail
   → Returns { file_id, metadata, thumbnail_url }
   → Frontend: displays in ImageViewer + metadata panel

2. User types analysis request + sends
   → POST /api/chat { message, file_id, history[] }
   → FastAPI constructs LangGraph agent
   → GPT-5.4 receives system prompt + image (base64 vision) + user message
   → Agent ReAct loop:
     a. THINK → SSE "thinking" event → frontend renders thinking card
     b. TOOL CALL → SSE "tool_call" event → frontend renders tool card
        → MCP server executes tool → result saved to uploads/{id}/results/
     c. TOOL RESULT → SSE "tool_result" event → frontend renders result card
     d. Repeat until final answer
   → FINAL ANSWER → SSE "message" event → frontend renders agent response
   → SSE "done" event → frontend enables input

3. User can click result images to view in ImageViewer
   → activeImageLayer switches to show result overlay
```

## Directory Structure (New Files)

```
ArchEO-Agent/
├── frontend/                    # Next.js app
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── components.json          # shadcn config
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Main single-page app
│   │   ├── globals.css
│   │   └── api/
│   │       ├── upload/route.ts
│   │       ├── chat/route.ts
│   │       ├── files/[id]/route.ts
│   │       └── results/[id]/route.ts
│   ├── components/
│   │   ├── chat-panel.tsx
│   │   ├── chat-message.tsx
│   │   ├── tool-call-card.tsx
│   │   ├── image-viewer.tsx
│   │   ├── image-layer-toggle.tsx
│   │   ├── upload-zone.tsx
│   │   ├── file-metadata.tsx
│   │   └── header.tsx
│   ├── lib/
│   │   ├── types.ts             # TypeScript interfaces
│   │   ├── api.ts               # API client functions
│   │   ├── use-chat.ts          # Chat hook with SSE
│   │   └── utils.ts
│   └── ui/                      # shadcn/ui generated components
│       └── ...
├── api/                         # FastAPI backend
│   ├── main.py                  # FastAPI app, endpoints, startup
│   ├── agent_service.py         # LangGraph agent setup + execution
│   ├── file_service.py          # Upload processing, GDAL metadata
│   ├── requirements.txt         # Backend-specific deps
│   └── config.py                # Settings (API keys, paths)
├── agent/tools/
│   └── Archaeology.py           # NEW MCP server (6 tools)
└── uploads/                     # File storage (gitignored)
```

## Running the Demo

```bash
# Terminal 1: Start FastAPI backend
cd api && pip install -r requirements.txt
uvicorn main:app --port 8000

# Terminal 2: Start Next.js frontend
cd frontend && npm install && npm run dev
# → http://localhost:3000
```

## Out of Scope

- Authentication / user accounts
- Database / persistent storage beyond filesystem
- Deployment / containerization
- Multi-user concurrent sessions
- Mobile responsive design
- Internationalization
