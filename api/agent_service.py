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
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
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

    llm = ChatAnthropic(
        api_key=ANTHROPIC_API_KEY,
        model=ANTHROPIC_MODEL,
        streaming=True,
        max_tokens=4096,
    )
    # Filter tools to only the most useful ones (reduces prompt token count)
    # Full 118 tools exceed Claude's 200K token limit
    PRIORITY_TOOLS = {
        # Archaeology — all 27 tools
        "edge_detection_canny", "edge_detection_sobel",
        "linear_feature_detection", "geometric_pattern_analysis",
        "principal_component_analysis", "adaptive_contrast_enhancement",
        "band_ratio_calculator", "spectral_anomaly_detection",
        "texture_analysis_glcm", "systematic_grid_analysis",
        "regularity_index", "crop_mark_detector",
        "morphological_cleanup", "dem_hillshade",
        "multi_directional_hillshade", "local_relief_model",
        "sky_view_factor", "temporal_difference_map", "shape_statistics",
        "bare_soil_index", "soil_adjusted_vegetation_index",
        "moisture_index", "iron_oxide_index", "clay_mineral_index",
        "brightness_index", "redness_index", "archaeological_composite_index",
        # Analysis — spatial clustering & change detection
        "getis_ord_gi_star", "analyze_hotspot_direction",
        "threshold_segmentation", "count_above_threshold",
        # Statistics — image stats useful for analysis
        "coefficient_of_variation", "mean",
        "calc_single_image_std", "calc_single_image_min",
        "calc_single_image_max", "calc_single_image_hotspot_tif",
        "grayscale_to_colormap",
        # Perception — segmentation & counting
        "count_skeleton_contours",
        # Index — vegetation/spectral indices (multi-band)
        "calculate_ndvi", "calculate_ndwi", "calculate_ndbi", "calculate_evi",
        # Statistics — post-index analysis
        "calculate_tif_difference", "calculate_tif_average",
        "calculate_intersection_percentage",
        "get_percentile_value_from_image", "calculate_area", "subtract",
        "calc_single_image_hotspot_percentage",
        "count_pixels_satisfying_conditions", "apply_cloud_mask",
        # Index — additional spectral indices
        "calculate_nbr", "calculate_fvc",
        # Inversion — thermal analysis
        "ATI",
        # Statistics — robust stats
        "calc_single_image_median",
        # Analysis — transect analysis
        "detect_change_points",
        # Perception — feature measurement
        "calculate_bbox_area",
    }
    _tools = [t for t in _tools if t.name in PRIORITY_TOOLS]
    logger.info(f"Filtered to {len(_tools)} priority tools (from full set)")

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


def _get_original_file_path(file_id: str) -> Optional[str]:
    """Find the original uploaded file path on disk."""
    upload_dir = UPLOADS_DIR / file_id
    if not upload_dir.exists():
        return None
    originals = list(upload_dir.glob("original.*"))
    return str(originals[0]) if originals else None


def _build_user_message(message: str, file_id: Optional[str]) -> HumanMessage:
    """Build a HumanMessage, embedding the thumbnail image when available.
    Also injects the actual file path so the agent can pass it to MCP tools."""
    if not file_id:
        return HumanMessage(content=message)

    # Get the actual file path on disk for tool calls
    file_path = _get_original_file_path(file_id)
    path_instruction = ""
    if file_path:
        path_instruction = (
            f"\n\n[SYSTEM: The uploaded image is stored at: {file_path} — "
            f"use this exact path when calling any tool that requires an image_path or dem_path parameter. "
            f"Result files should use relative output paths like 'edge_result.png'.]"
        )

    b64 = encode_thumbnail(file_id)
    if not b64:
        return HumanMessage(content=message + path_instruction)

    # Multimodal content block for Anthropic vision
    return HumanMessage(
        content=[
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            },
            {"type": "text", "text": message + path_instruction},
        ]
    )


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

async def stream_agent_response(
    message: str,
    file_id: Optional[str],
    history: list[dict],
    api_key_override: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE-formatted strings."""
    global _agent, _tools

    # If client provides an API key, create a per-request agent with that key
    agent_to_use = _agent
    if api_key_override and _tools:
        from langchain_anthropic import ChatAnthropic
        from langgraph.prebuilt import create_react_agent
        temp_llm = ChatAnthropic(
            api_key=api_key_override,
            model=ANTHROPIC_MODEL,
            streaming=True,
            max_tokens=4096,
        )
        agent_to_use = create_react_agent(temp_llm, tools=_tools)

    if agent_to_use is None:
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
    _last_event_was_tool = False  # Track if we're in final answer phase

    try:
        async for event in agent_to_use.astream_events(
            {"messages": all_messages},
            version="v2",
            config={"recursion_limit": 80},
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    # Use "agent" event type for final answer (after tools ran)
                    sse_type = "agent" if _last_event_was_tool else "thinking"
                    if isinstance(content, list):
                        # Multimodal chunks
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                final_text_parts.append(block["text"])
                                yield _sse(sse_type, {"text": block["text"]})
                    else:
                        final_text_parts.append(str(content))
                        yield _sse(sse_type, {"text": str(content)})

            elif kind == "on_tool_start":
                _last_event_was_tool = False  # Reset — we're in tool execution
                tool_name = event.get("name", "unknown_tool")
                tool_input = event.get("data", {}).get("input", {})
                yield _sse("tool_call", {"tool": tool_name, "input": tool_input})

            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown_tool")
                tool_output = event.get("data", {}).get("output")
                # Get raw output BEFORE formatting (to extract file paths)
                raw_output = str(tool_output) if tool_output is not None else ""
                output_str = _extract_tool_output(tool_output)

                # Copy any result images produced in MCP_TEMP_DIR to upload results dir
                result_images: list[str] = []
                if results_dir is not None:
                    result_images = _copy_mcp_results(results_dir, tool_name)

                # Also extract image filenames from raw output text
                import re
                raw_matches = re.findall(r'([a-zA-Z0-9_-]+\.(?:tif|tiff|png))', raw_output)
                for fname in raw_matches:
                    png_name = re.sub(r'\.(tif|tiff)$', '.png', fname)
                    if png_name not in result_images and results_dir:
                        # Check if the PNG already exists in results dir
                        if (results_dir / png_name).exists():
                            result_images.append(png_name)
                        # Or try to convert the TIF from MCP_TEMP_DIR now
                        elif MCP_TEMP_DIR.exists():
                            tif_src = MCP_TEMP_DIR / fname
                            if tif_src.exists() and fname.lower().endswith(('.tif', '.tiff')):
                                try:
                                    _tif_to_png(tif_src, results_dir / png_name)
                                    result_images.append(png_name)
                                except Exception:
                                    pass
                            # Also check if it's already a PNG in temp
                            elif (MCP_TEMP_DIR / png_name).exists():
                                shutil.copy2(MCP_TEMP_DIR / png_name, results_dir / png_name)
                                result_images.append(png_name)

                # Deduplicate
                result_images = list(dict.fromkeys(result_images))

                yield _sse(
                    "tool_result",
                    {
                        "tool": tool_name,
                        "output": output_str[:500],
                        "result_images": result_images,
                    },
                )
                _last_event_was_tool = True  # Next LLM output is the final answer

    except Exception as exc:
        logger.exception("Agent stream error")
        yield _sse("error", {"message": str(exc)})
        yield _sse("done", {})
        return

    # Don't re-emit thinking text as a message — it was already streamed.
    # Just signal completion.
    yield _sse("done", {})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_tool_output(tool_output) -> str:
    """Extract clean text from LangChain tool output (strips wrapper objects)."""
    if tool_output is None:
        return ""
    # If it's a string, use directly
    if isinstance(tool_output, str):
        return _format_tool_summary(tool_output)
    # If it has .content attribute (ToolMessage)
    if hasattr(tool_output, "content"):
        content = tool_output.content
        if isinstance(content, str):
            return _format_tool_summary(content)
        if isinstance(content, list):
            # Extract text blocks from content list
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            return _format_tool_summary(" ".join(texts))
    # If it's a dict (direct tool return)
    if isinstance(tool_output, dict):
        return _format_tool_summary(json.dumps(tool_output, default=str))
    return _format_tool_summary(str(tool_output))


def _format_tool_summary(raw: str) -> str:
    """Format tool output to be concise — hide large arrays, show summaries."""
    if not raw:
        return ""
    # Try to parse as JSON/dict and summarize
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parts = []
            for k, v in parsed.items():
                if isinstance(v, list) and len(v) > 5:
                    parts.append(f"{k}: {len(v)} items")
                elif isinstance(v, list) and len(v) <= 5:
                    formatted = [f"{x:.2f}" if isinstance(x, float) else str(x) for x in v]
                    parts.append(f"{k}: [{', '.join(formatted)}]")
                elif isinstance(v, float):
                    parts.append(f"{k}: {v:.4f}")
                elif isinstance(v, str) and "/" in v:
                    parts.append(f"{k}: {v.split('/')[-1]}")
                else:
                    parts.append(f"{k}: {v}")
            return "\n".join(parts)
    except (json.JSONDecodeError, TypeError):
        pass
    # Clean file paths
    import re
    cleaned = re.sub(r'/[^\s\'",\]]*\/([^\s\'",\]]+)', r'\1', raw)
    # Truncate very long output
    if len(cleaned) > 500:
        cleaned = cleaned[:500] + "..."
    return cleaned


def _safe_serialize(obj: object) -> object:
    """Make an object JSON-serializable by converting non-standard types to strings."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    # Fallback: convert to string representation
    return str(obj)


def _sse(event: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(_safe_serialize(data))}\n\n"


def _copy_mcp_results(results_dir: Path, tool_name: str) -> list[str]:
    """Copy new image files from MCP_TEMP_DIR to results_dir.

    GeoTIFF files are converted to PNG so browsers can display them.
    Returns list of relative filenames suitable for /api/results/{file_id}/ URLs.
    """
    copied: list[str] = []
    if not MCP_TEMP_DIR.exists():
        return copied

    for src in MCP_TEMP_DIR.rglob("*"):
        if not src.is_file():
            continue
        if src.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            dest = results_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)
                copied.append(src.name)
        elif src.suffix.lower() in {".tif", ".tiff"}:
            # Convert GeoTIFF to PNG for browser display
            png_name = src.stem + ".png"
            dest = results_dir / png_name
            if not dest.exists():
                try:
                    _tif_to_png(src, dest)
                    copied.append(png_name)
                except Exception as exc:
                    logger.warning(f"Failed to convert {src.name} to PNG: {exc}")
                    # Fallback: copy the TIF as-is
                    shutil.copy2(src, results_dir / src.name)
                    copied.append(src.name)

    return copied


def _tif_to_png(src: Path, dest: Path) -> None:
    """Convert a GeoTIFF to a PNG viewable in browsers."""
    import numpy as np
    from osgeo import gdal
    import cv2

    ds = gdal.Open(str(src))
    if ds is None:
        raise RuntimeError(f"Cannot open {src}")

    bands = ds.RasterCount
    if bands == 1:
        arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
    elif bands >= 3:
        r = ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
        g = ds.GetRasterBand(2).ReadAsArray().astype(np.float64)
        b = ds.GetRasterBand(3).ReadAsArray().astype(np.float64)
        arr = np.stack([b, g, r], axis=-1)  # BGR for OpenCV
    else:
        arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
    ds = None

    # Normalize to 0-255 using percentile stretch (2%-98%) for better contrast
    finite = arr[np.isfinite(arr)] if arr.ndim == 2 else arr[np.isfinite(arr).all(axis=-1)]
    if finite.size > 0:
        vmin = np.percentile(finite, 2)
        vmax = np.percentile(finite, 98)
    else:
        vmin, vmax = np.nanmin(arr), np.nanmax(arr)
    if vmax > vmin:
        arr = (arr - vmin) / (vmax - vmin) * 255
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    # Apply colormap for single-band images (much better than grayscale)
    if arr.ndim == 2:
        import cv2 as _cv2
        arr = _cv2.applyColorMap(arr, _cv2.COLORMAP_INFERNO)

    cv2.imwrite(str(dest), arr)
