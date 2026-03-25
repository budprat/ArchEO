# ABOUTME: Permission callbacks controlling tool access and validation.
# Blocks dangerous operations, validates spatial extent sizes,
# enforces rate limits, and detects suspicious input patterns.

"""
Permission callbacks for OpenEO AI tools.

Defines which tools require user confirmation and validates
tool arguments before execution. Also provides rate-limit
configuration and input sanitisation patterns.
"""

import re
from typing import Any, Dict, List, Union

# Read-only tools that don't require confirmation
READ_ONLY_TOOLS = {
    "openeo_list_collections",
    "openeo_get_collection_info",
    "openeo_validate_graph",
    "openeo_generate_graph",
    "openeo_get_job_status",
    "openeo_list_jobs",
    "openeo_resolve_location",
    "openeo_parse_temporal",
    "openeo_estimate_extent",
    "openeo_quality_metrics",
    "openeo_validate_geospatial",
    "viz_show_map",
    "viz_show_time_series",
    "saved_jobs_list",
    "saved_jobs_load",
}

# Tools that modify state but are generally safe
SAFE_MODIFY_TOOLS = {
    "openeo_create_job",
    "openeo_start_job",
    "openeo_get_results",
    "geoai_segment",
    "geoai_detect_change",
    "geoai_estimate_canopy_height",
    "saved_jobs_delete",
}

# Tools that are blocked by default
BLOCKED_TOOLS = {
    "openeo_delete_all_jobs",
    "openeo_delete_all_graphs",
}

# Maximum allowed spatial extent (degrees)
MAX_SPATIAL_EXTENT = 10.0  # 10 degrees in any direction

# --- Rate Limiting Configuration ---
# Per-query limits: {tool_name_suffix: max_calls_per_query}
RATE_LIMITS: Dict[str, int] = {
    "openeo_create_job": 5,       # Max 5 job creations per query
    "openeo_start_job": 5,        # Max 5 job starts per query
    "openeo_delete_all_jobs": 0,  # Redundant with BLOCKED_TOOLS, belt-and-suspenders
    "geoai_segment": 3,           # Expensive GPU ops
    "geoai_detect_change": 3,
    "geoai_estimate_canopy_height": 3,
}
RATE_LIMIT_DEFAULT = 50  # Max total tool calls per query (any tool)

# --- Suspicious Input Patterns ---
# Regex patterns that should never appear in tool inputs.
# Matched against all string values in the tool input dict (recursive).
SUSPICIOUS_PATTERNS: List[re.Pattern] = [
    re.compile(r"\.\./"),                          # Path traversal
    re.compile(r"\.\\.\\"),                        # Windows path traversal
    re.compile(r"^/(?:etc|proc|sys|dev|root)/"),   # Absolute system paths
    re.compile(r"[;|&`$]"),                        # Shell metacharacters
    re.compile(r"<script", re.IGNORECASE),         # XSS attempt
    re.compile(r"\bexec\s*\("),                    # Code injection
    re.compile(r"\beval\s*\("),                    # Code injection
    re.compile(r"__import__"),                     # Python import injection
]


def check_suspicious_input(args: Dict[str, Any]) -> str | None:
    """Recursively scan tool input for suspicious patterns.

    Returns the matched pattern description if found, None if clean.
    """
    def _scan(value: Any) -> str | None:
        if isinstance(value, str):
            for pattern in SUSPICIOUS_PATTERNS:
                if pattern.search(value):
                    return f"Suspicious pattern matched: {pattern.pattern!r}"
        elif isinstance(value, dict):
            for v in value.values():
                hit = _scan(v)
                if hit:
                    return hit
        elif isinstance(value, (list, tuple)):
            for v in value:
                hit = _scan(v)
                if hit:
                    return hit
        return None

    return _scan(args)


def openeo_permission_callback(
    tool_name: str,
    args: Dict[str, Any]
) -> Union[bool, Dict[str, Any]]:
    """
    Permission callback for OpenEO AI tools.

    Determines whether a tool call should be:
    - Allowed immediately (return True)
    - Blocked (return False)
    - Require confirmation (return dict with confirmation request)

    Args:
        tool_name: Name of the tool being called
        args: Arguments passed to the tool

    Returns:
        True if allowed, False if blocked, or dict for confirmation
    """
    # Block dangerous operations
    if tool_name in BLOCKED_TOOLS:
        return False

    # Allow read-only tools
    if tool_name in READ_ONLY_TOOLS:
        return True

    # For modification tools, check arguments
    if tool_name in SAFE_MODIFY_TOOLS:
        # Check for large spatial extent in process graphs
        validation_result = _validate_extent(args)
        if validation_result is not True:
            return validation_result

        return True

    # Unknown tools - block by default
    return False


def _validate_extent(args: Dict[str, Any]) -> Union[bool, Dict[str, Any]]:
    """
    Validate spatial extent in tool arguments.

    Args:
        args: Tool arguments

    Returns:
        True if valid, or dict with warning/confirmation request
    """
    # Check for process_graph in args
    process_graph = args.get("process_graph", {})
    if isinstance(process_graph, dict) and "process_graph" in process_graph:
        process_graph = process_graph["process_graph"]

    if not isinstance(process_graph, dict):
        return True

    # Find load_collection nodes and check extents
    for node_id, node in process_graph.items():
        if not isinstance(node, dict):
            continue

        if node.get("process_id") != "load_collection":
            continue

        spatial_extent = node.get("arguments", {}).get("spatial_extent", {})
        if not spatial_extent:
            continue

        # Calculate extent size
        width = abs(spatial_extent.get("east", 0) - spatial_extent.get("west", 0))
        height = abs(spatial_extent.get("north", 0) - spatial_extent.get("south", 0))

        # Check if extent is very large
        if width > MAX_SPATIAL_EXTENT or height > MAX_SPATIAL_EXTENT:
            return {
                "type": "confirmation_required",
                "message": f"Large spatial extent detected ({width:.1f}° x {height:.1f}°). "
                           f"This may be slow or timeout. Continue?",
                "severity": "warning"
            }

        # Check if extent is extremely large (likely error)
        if width > 50 or height > 50:
            return False  # Block global queries

    return True
