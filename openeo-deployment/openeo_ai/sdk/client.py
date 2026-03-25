# ABOUTME: Claude SDK client for conversational Earth Observation analysis.
# Implements agentic chat loop with custom OpenEO, GeoAI, and visualization tools.

"""
Claude SDK client for OpenEO AI Assistant.

Uses the Anthropic SDK with custom tools for Earth Observation
data processing and analysis.
"""

import os
import json
import asyncio
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Any, Optional, Dict, List

import anthropic

from .sessions import SessionManager
from .permissions import openeo_permission_callback

logger = logging.getLogger(__name__)


# Module-level query function for mockability in tests
async def query(
    client: "OpenEOAIClient",
    prompt: str,
    user_id: str,
    session_id: Optional[str] = None,
    messages: Optional[List[dict]] = None
) -> AsyncIterator[Any]:
    """
    Query the Claude API and yield responses.

    This is a module-level function to enable easy mocking in tests.

    Args:
        client: The OpenEOAIClient instance
        prompt: User's message
        user_id: Authenticated user ID
        session_id: Optional session ID
        messages: Message history

    Yields:
        Response objects from Claude API
    """
    if messages is None:
        messages = []

    messages.append({"role": "user", "content": prompt})

    # Call Claude API (with prompt caching for system prompt)
    response = await client.client.messages.create(
        model=client.config.model,
        max_tokens=client.config.max_tokens,
        system=[{
            "type": "text",
            "text": client.SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        tools=TOOL_DEFINITIONS,
        messages=messages
    )

    # Yield response blocks as response objects
    for block in response.content:
        result = type('Response', (), {
            'text': block.text if hasattr(block, 'text') and block.type == 'text' else None,
            'tool_result': None,
            'tool_name': block.name if hasattr(block, 'name') and block.type == 'tool_use' else None,
            'tool_input': block.input if hasattr(block, 'input') and block.type == 'tool_use' else None,
            'tool_use_id': block.id if hasattr(block, 'id') and block.type == 'tool_use' else None,
            'visualization': None,
            'session_id': session_id,
            'stop_reason': response.stop_reason
        })()
        yield result


@dataclass
class OpenEOAIConfig:
    """Configuration for OpenEO AI Assistant."""

    model: str = "claude-sonnet-4-20250514"
    max_turns: int = 15
    max_tokens: int = 4096
    openeo_url: str = field(
        default_factory=lambda: os.environ.get(
            "OPENEO_URL", "http://localhost:8000/openeo/1.1.0"
        )
    )
    sqlite_path: str = field(
        default_factory=lambda: os.environ.get(
            "OPENEO_AI_DB", "data/openeo_ai.db"
        )
    )
    geoai_models_path: str = field(
        default_factory=lambda: os.environ.get(
            "GEOAI_MODELS_PATH", "models/"
        )
    )
    stac_api_url: str = field(
        default_factory=lambda: os.environ.get(
            "STAC_API_URL", "https://earth-search.aws.element84.com/v1/"
        )
    )
    api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )


# Tool definitions for Claude API
TOOL_DEFINITIONS = [
    {
        "name": "openeo_list_collections",
        "description": "List available Earth Observation data collections from the STAC catalog. Returns collection IDs, titles, and descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "openeo_get_collection_info",
        "description": "Get detailed information about a specific collection including available bands, spatial/temporal extent, and metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "The collection identifier (e.g., 'sentinel-2-l2a', 'landsat-c2-l2')"
                }
            },
            "required": ["collection_id"]
        }
    },
    {
        "name": "openeo_validate_graph",
        "description": "Validate an OpenEO process graph for errors, warnings, and suggestions. Checks structure, process IDs, arguments, data flow, band names, and extent sizes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_graph": {
                    "type": "object",
                    "description": "The OpenEO process graph to validate"
                }
            },
            "required": ["process_graph"]
        }
    },
    {
        "name": "openeo_generate_graph",
        "description": "Generate an OpenEO process graph from a natural language description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of the desired analysis"
                },
                "collection": {
                    "type": "string",
                    "description": "Collection ID to use"
                },
                "spatial_extent": {
                    "type": "object",
                    "description": "Bounding box with west, south, east, north coordinates",
                    "properties": {
                        "west": {"type": "number"},
                        "south": {"type": "number"},
                        "east": {"type": "number"},
                        "north": {"type": "number"}
                    },
                    "required": ["west", "south", "east", "north"]
                },
                "temporal_extent": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Start and end dates [start, end] in ISO format"
                },
                "output_format": {
                    "type": "string",
                    "description": "Output format (GTiff, netCDF, etc.)",
                    "default": "GTiff"
                }
            },
            "required": ["description", "collection", "spatial_extent", "temporal_extent"]
        }
    },
    {
        "name": "openeo_list_jobs",
        "description": "ALWAYS use this tool when the user asks to 'list jobs', 'list all jobs', 'show jobs', 'show all jobs', 'what jobs exist', or 'check job status'. Lists ALL batch jobs (running, queued, finished, error, created) with their ID, title, status, and creation date. Can filter by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of jobs to return (default 50)"
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status: finished, error, running, queued, created. Omit to show all.",
                    "enum": ["finished", "error", "running", "queued", "created"]
                }
            },
            "required": []
        }
    },
    {
        "name": "openeo_create_job",
        "description": "Create, start, and monitor a batch processing job. Automatically starts the job after creation and polls status every 10 seconds until complete (up to 120s). Returns final status with job ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Job title"
                },
                "process_graph": {
                    "type": "object",
                    "description": "The OpenEO process graph to execute"
                },
                "description": {
                    "type": "string",
                    "description": "Optional job description"
                }
            },
            "required": ["title", "process_graph"]
        }
    },
    {
        "name": "openeo_start_job",
        "description": "Start a queued batch job.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID to start"
                }
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "openeo_get_job_status",
        "description": "Get the current status of a batch job.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID to check"
                }
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "openeo_get_results",
        "description": "Get the results of a completed batch job.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID to get results for"
                }
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "geoai_segment",
        "description": "Run semantic segmentation on satellite imagery to classify land cover types.",
        "input_schema": {
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Path to input GeoTIFF file"
                },
                "model": {
                    "type": "string",
                    "description": "Model name (default: segmentation_default)",
                    "default": "segmentation_default"
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional output path for results"
                }
            },
            "required": ["input_path"]
        }
    },
    {
        "name": "geoai_detect_change",
        "description": "Detect changes between two satellite images from different times.",
        "input_schema": {
            "type": "object",
            "properties": {
                "before_path": {
                    "type": "string",
                    "description": "Path to before image GeoTIFF"
                },
                "after_path": {
                    "type": "string",
                    "description": "Path to after image GeoTIFF"
                },
                "model": {
                    "type": "string",
                    "description": "Model name (default: change_default)",
                    "default": "change_default"
                }
            },
            "required": ["before_path", "after_path"]
        }
    },
    {
        "name": "geoai_estimate_canopy_height",
        "description": "Estimate tree canopy height from RGB satellite imagery.",
        "input_schema": {
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Path to input RGB GeoTIFF file"
                }
            },
            "required": ["input_path"]
        }
    },
    {
        "name": "viz_show_map",
        "description": "Create an interactive map visualization of raster data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "geotiff_path": {
                    "type": "string",
                    "description": "Path to GeoTIFF file to display"
                },
                "title": {
                    "type": "string",
                    "description": "Map title"
                },
                "colormap": {
                    "type": "string",
                    "description": "Colormap name (viridis, plasma, ndvi, terrain)",
                    "default": "viridis"
                }
            },
            "required": ["geotiff_path"]
        }
    },
    {
        "name": "viz_show_time_series",
        "description": "Create a time series chart from temporal data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of date strings"
                },
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of values corresponding to dates"
                },
                "title": {
                    "type": "string",
                    "description": "Chart title"
                },
                "y_label": {
                    "type": "string",
                    "description": "Y-axis label"
                }
            },
            "required": ["dates", "values"]
        }
    },
    {
        "name": "openeo_resolve_location",
        "description": "Resolve a place name, city, region, or coordinates to a geographic bounding box for spatial queries. Use this when the user mentions a location by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Location name (e.g., 'Mumbai', 'Kerala', 'Amazon rainforest') or coordinates ('28.6139, 77.2090')"
                },
                "buffer_degrees": {
                    "type": "number",
                    "description": "Buffer in degrees to add around point locations (default: 0.1, ~11km)",
                    "default": 0.1
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "openeo_parse_temporal",
        "description": "Parse natural language temporal expressions to ISO date ranges. Use this when the user mentions time periods like 'last summer', 'monsoon 2024', 'past 3 months'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Temporal expression (e.g., 'last summer', '2020-2023', 'monsoon', 'past 6 months')"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "openeo_estimate_extent",
        "description": "Estimate data size and validate extent before processing. Use this to check if a query will produce too much data and warn the user about large requests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spatial_extent": {
                    "type": "object",
                    "description": "Bounding box {west, south, east, north}",
                    "properties": {
                        "west": {"type": "number"},
                        "south": {"type": "number"},
                        "east": {"type": "number"},
                        "north": {"type": "number"}
                    },
                    "required": ["west", "south", "east", "north"]
                },
                "temporal_extent": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Date range [start, end] in ISO format"
                },
                "collection": {
                    "type": "string",
                    "description": "Collection ID (default: sentinel-2-l2a)"
                },
                "bands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bands to use"
                }
            },
            "required": ["spatial_extent"]
        }
    },
    {
        "name": "openeo_quality_metrics",
        "description": "Get comprehensive data quality metrics including estimated cloud coverage, temporal coverage, and data completeness. Use this to inform users about expected data quality before processing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spatial_extent": {
                    "type": "object",
                    "description": "Bounding box {west, south, east, north}",
                    "properties": {
                        "west": {"type": "number"},
                        "south": {"type": "number"},
                        "east": {"type": "number"},
                        "north": {"type": "number"}
                    },
                    "required": ["west", "south", "east", "north"]
                },
                "temporal_extent": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Date range [start, end] in ISO format"
                },
                "collection": {
                    "type": "string",
                    "description": "Collection ID (default: sentinel-2-l2a)"
                },
                "bands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bands to use"
                }
            },
            "required": ["spatial_extent"]
        }
    },
    {
        "name": "openeo_validate_geospatial",
        "description": "Validate geospatial extent including CRS validation, antimeridian handling, and coordinate bounds. Use this to check if coordinates are valid before processing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spatial_extent": {
                    "type": "object",
                    "description": "Bounding box {west, south, east, north}",
                    "properties": {
                        "west": {"type": "number"},
                        "south": {"type": "number"},
                        "east": {"type": "number"},
                        "north": {"type": "number"}
                    },
                    "required": ["west", "south", "east", "north"]
                },
                "crs": {
                    "type": "string",
                    "description": "Coordinate Reference System (default: EPSG:4326)",
                    "default": "EPSG:4326"
                }
            },
            "required": ["spatial_extent"]
        }
    },
    {
        "name": "saved_jobs_list",
        "description": "List permanently saved result files (GeoTIFFs archived from completed jobs). Use ONLY when the user asks about 'saved results', 'saved files', 'archived results', or 'downloaded results'. Do NOT use for general 'list jobs' queries — use openeo_list_jobs instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of jobs to return (default 20)"
                }
            },
            "required": []
        }
    },
    {
        "name": "saved_jobs_load",
        "description": "Load a saved/finished job result onto the map for visualization. Takes a save_id from saved_jobs_list. Use when the user asks to show, load, or display a previous result on the map.",
        "input_schema": {
            "type": "object",
            "properties": {
                "save_id": {
                    "type": "string",
                    "description": "The save_id of the job to load (from saved_jobs_list)"
                }
            },
            "required": ["save_id"]
        }
    },
    {
        "name": "saved_jobs_delete",
        "description": "Permanently delete a saved job result. Removes both the file and manifest entry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "save_id": {
                    "type": "string",
                    "description": "The save_id of the job to delete"
                }
            },
            "required": ["save_id"]
        }
    }
]


class OpenEOAIClient:
    """
    OpenEO AI Assistant using Claude SDK.

    Provides conversational interface for:
    - Natural language → Process graph generation
    - Process graph validation
    - Batch job management
    - Result visualization
    - GeoAI model inference
    """

    SYSTEM_PROMPT = """You are an expert Earth Observation assistant powered by OpenEO.

Capabilities: Collection discovery, process graph generation/validation, batch job management, result visualization, GeoAI inference (segmentation, change detection), and EO education.

Workflow for user queries:
1. If the message starts with [Bounding box: west=W, south=S, east=E, north=N], use those exact coordinates as the spatial_extent (west, south, east, north) — skip openeo_resolve_location for spatial extent. Still resolve place names if user also mentions a location name for context.
2. Otherwise, resolve locations with openeo_resolve_location (for place names like "Mumbai", "Kerala")
3. Parse temporal expressions with openeo_parse_temporal (e.g. "last summer", "monsoon 2024"). If no date specified, default to a recent period (e.g. last 30 days or a recent month with good data).
4. Check data size with openeo_estimate_extent — if severity is "warning" or "error", inform the user and suggest reducing extent or limiting bands
5. Assess quality with openeo_quality_metrics — if quality grade is C or below, suggest cloud masking or a longer time range
6. Generate graph with openeo_generate_graph, then validate with openeo_validate_graph
7. Create job with openeo_create_job (it auto-starts and polls until finished), then get results with openeo_get_results and visualize with viz_show_map

Available collections: sentinel-2-l2a, sentinel-2-l1c, landsat-c2-l2, cop-dem-glo-30, cop-dem-glo-90

Backend rules:
- Dimension names: "time", "latitude", "longitude", "bands" (use these exact names in reduce_dimension)
- Use built-in "ndvi" process (NOT filter_bands + normalized_difference)
- Sentinel-2 bands: blue, green, red, nir, nir08, swir16, swir22, scl
- Common indices: NDVI=(nir-red)/(nir+red), NDWI=(green-nir)/(green+nir), EVI=2.5*((nir-red)/(nir+6*red-7.5*blue+1))
- Use openeo_validate_geospatial to check for CRS issues and antimeridian crossing
- Result paths: /tmp/openeo_results/results/{job_id}/result.tif — always use the FULL path from openeo_get_results
- Colormaps: viridis, plasma, inferno, ndvi, terrain, coolwarm, grayscale

Job listing: When the user asks to "list jobs", "show all jobs", or "check job status", ALWAYS call openeo_list_jobs. This shows all batch jobs (running, queued, finished, error).
Saved results: Completed results are auto-archived as files. Use saved_jobs_list ONLY when user asks about "saved results" or "archived files". Use saved_jobs_load to display a saved result on the map.

Always explain your actions clearly and warn about large or slow queries."""

    def __init__(self, config: Optional[OpenEOAIConfig] = None):
        """Initialize the OpenEO AI Client."""
        self.config = config or OpenEOAIConfig()
        self.session_manager = SessionManager(db_path=self.config.sqlite_path)
        self.tools = self._create_tools()
        self._client = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            if not self.config.api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is required. "
                    "Set it with: export ANTHROPIC_API_KEY=your-key"
                )
            self._client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
        return self._client

    def _create_tools(self) -> Dict[str, Any]:
        """Create and register all custom tools."""
        from ..tools.openeo_tools import create_openeo_tools
        from ..tools.job_tools import create_job_tools
        from ..tools.geoai_tools import create_geoai_tools
        from ..tools.viz_tools import create_viz_tools

        tools = {}
        tools.update(create_openeo_tools(self.config))
        tools.update(create_job_tools(self.config))
        tools.update(create_geoai_tools(self.config))
        tools.update(create_viz_tools(self.config))

        from ..tools.saved_jobs_tools import create_saved_jobs_tools
        tools.update(create_saved_jobs_tools(self.config))

        return tools

    async def chat(
        self,
        prompt: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> AsyncIterator[dict]:
        """
        Chat with the OpenEO AI Assistant.

        Args:
            prompt: User's message
            user_id: Authenticated user ID (from OIDC)
            session_id: Optional session to resume

        Yields:
            Response messages with text, tool results, or visualizations
        """
        # Get or create session
        if session_id:
            session = self.session_manager.get_session(session_id)
            if session:
                # Messages are stored in context.messages
                context = session.get("context", {})
                messages = context.get("messages", [])
                # Limit conversation history to prevent token overflow
                # Keep last 20 messages (10 turns) to stay under token limits
                if len(messages) > 20:
                    messages = messages[-20:]
            else:
                session_id = self.session_manager.create_session(user_id)
                messages = []
        else:
            session_id = self.session_manager.create_session(user_id)
            messages = []

        # Agentic loop - continues until Claude stops using tools
        turn = 0
        current_prompt = prompt

        while turn < self.config.max_turns:
            turn += 1
            tool_calls_this_turn = []
            should_continue = False

            try:
                # Add user message on first turn
                if turn == 1:
                    messages.append({"role": "user", "content": current_prompt})

                # Call Claude API (with prompt caching for system prompt)
                response = await self.client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=[{
                        "type": "text",
                        "text": self.SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"}
                    }],
                    tools=TOOL_DEFINITIONS,
                    messages=messages
                )

                # Build assistant message content
                assistant_content = []

                # Process each content block
                for block in response.content:
                    if block.type == "text":
                        yield {"type": "text", "content": block.text}
                        assistant_content.append({"type": "text", "text": block.text})

                    elif block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        assistant_content.append({
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": tool_name,
                            "input": tool_input
                        })

                        # Check permission
                        if not openeo_permission_callback(tool_name, tool_input):
                            tool_result = {"error": f"Permission denied for tool: {tool_name}"}
                            yield {
                                "type": "tool_blocked",
                                "tool": tool_name,
                                "reason": "Permission denied"
                            }
                        else:
                            # Execute tool
                            try:
                                tool_result = await self._execute_tool(tool_name, tool_input)

                                # Check if result is a visualization
                                is_viz = (
                                    isinstance(tool_result, dict) and (
                                        tool_result.get("type") == "visualization" or
                                        tool_result.get("type") in ("map", "comparison_slider", "chart") or
                                        (tool_result.get("component", {}).get("type") in ("map", "comparison_slider", "chart"))
                                    )
                                )
                                if is_viz:
                                    # Extract the actual visualization component
                                    viz_content = tool_result.get("component", tool_result)
                                    yield {
                                        "type": "visualization",
                                        "content": viz_content
                                    }
                                else:
                                    yield {
                                        "type": "tool_result",
                                        "tool": tool_name,
                                        "result": tool_result
                                    }
                            except Exception as e:
                                logger.error(f"Tool execution error: {e}")
                                tool_result = {"error": str(e)}
                                yield {
                                    "type": "tool_error",
                                    "tool": tool_name,
                                    "error": str(e)
                                }

                        tool_calls_this_turn.append({
                            "tool_use_id": tool_use_id,
                            "result": tool_result
                        })

                # Add assistant message
                messages.append({"role": "assistant", "content": assistant_content})

                # If there were tool calls, add tool results and continue
                if tool_calls_this_turn:
                    tool_results_content = []
                    for tc in tool_calls_this_turn:
                        # Truncate large tool results to prevent token overflow
                        result_str = json.dumps(tc["result"]) if isinstance(tc["result"], (dict, list)) else str(tc["result"])
                        if len(result_str) > 2000:
                            result_str = result_str[:2000] + "... [truncated]"
                        tool_results_content.append({
                            "type": "tool_result",
                            "tool_use_id": tc["tool_use_id"],
                            "content": result_str
                        })
                    messages.append({"role": "user", "content": tool_results_content})
                    should_continue = True

                # Check if we should stop
                if response.stop_reason == "end_turn" and not tool_calls_this_turn:
                    break

                if not should_continue:
                    break

            except anthropic.APIError as e:
                logger.error(f"Claude API error: {e}")
                yield {"type": "error", "content": f"API error: {str(e)}"}
                return
            except Exception as e:
                if "ConnectionError" in str(type(e).__name__):
                    raise
                logger.error(f"Query error: {e}")
                yield {"type": "error", "content": str(e)}
                return

        # Save session
        self.session_manager.update_context(session_id, {"messages": messages})

        # Yield session info
        yield {"type": "session", "session_id": session_id}

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute a tool and return its result."""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_func = self.tools[tool_name]

        # Call the tool function
        result = await tool_func(tool_input)

        # Extract content from Claude SDK format
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list) and len(content) > 0:
                first_item = content[0]
                if isinstance(first_item, dict) and "text" in first_item:
                    try:
                        return json.loads(first_item["text"])
                    except json.JSONDecodeError:
                        return first_item["text"]
                return first_item
            return content

        return result

    def _build_options(self, user_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Build options dict for reference."""
        return {
            "model": self.config.model,
            "system_prompt": self.SYSTEM_PROMPT,
            "allowed_tools": list(self.tools.keys()),
            "can_use_tool": openeo_permission_callback,
            "custom_tools": self.tools,
            "max_turns": self.config.max_turns,
            "resume": session_id,
        }

    async def chat_sync(
        self,
        prompt: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> List[dict]:
        """
        Synchronous chat that collects all responses.

        Args:
            prompt: User's message
            user_id: Authenticated user ID
            session_id: Optional session to resume

        Returns:
            List of all response messages
        """
        responses = []
        async for response in self.chat(prompt, user_id, session_id):
            responses.append(response)
        return responses
