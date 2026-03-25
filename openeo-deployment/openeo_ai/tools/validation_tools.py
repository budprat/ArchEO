# ABOUTME: Process graph validation with educational feedback and suggestions.
# Validates structure, processes, data flow, band names, and spatial extents.

"""
Process graph validation tools with educational feedback.

Validates OpenEO process graphs and provides helpful suggestions
for optimization and best practices.
"""

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


# Known processes with their required arguments
PROCESS_SPECS = {
    "load_collection": {
        "required": ["id"],
        "optional": ["spatial_extent", "temporal_extent", "bands", "properties"]
    },
    "ndvi": {
        "required": ["data"],
        "optional": ["nir", "red", "target_band"]
    },
    "normalized_difference": {
        "required": ["x", "y"],
        "optional": []
    },
    "reduce_dimension": {
        "required": ["data", "dimension", "reducer"],
        "optional": ["context"]
    },
    "filter_bands": {
        "required": ["data", "bands"],
        "optional": []
    },
    "filter_bbox": {
        "required": ["data", "extent"],
        "optional": []
    },
    "filter_temporal": {
        "required": ["data", "extent"],
        "optional": []
    },
    "save_result": {
        "required": ["data", "format"],
        "optional": ["options"]
    },
    "mask": {
        "required": ["data", "mask"],
        "optional": ["replacement"]
    },
    "add": {"required": ["x", "y"], "optional": []},
    "subtract": {"required": ["x", "y"], "optional": []},
    "multiply": {"required": ["x", "y"], "optional": []},
    "divide": {"required": ["x", "y"], "optional": []},
}

# Band mappings for validation
COLLECTION_BANDS = {
    "sentinel-2-l2a": [
        "blue", "green", "red", "rededge1", "rededge2", "rededge3",
        "nir", "nir08", "nir09", "swir16", "swir22", "scl"
    ],
    "sentinel-2-l1c": [
        "blue", "green", "red", "rededge1", "rededge2", "rededge3",
        "nir", "nir08", "nir09", "swir16", "swir22"
    ],
    "landsat-c2-l2": [
        "blue", "green", "red", "nir08", "swir16", "swir22"
    ],
    "cop-dem-glo-30": ["data"],
    "cop-dem-glo-90": ["data"],
}

# Common band name corrections
BAND_CORRECTIONS = {
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B05": "rededge1",
    "B06": "rededge2",
    "B07": "rededge3",
    "B08": "nir",
    "B8A": "nir08",
    "B09": "nir09",
    "B11": "swir16",
    "B12": "swir22",
}


@dataclass
class ValidationResult:
    """Result of process graph validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    resource_estimate: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "resource_estimate": self.resource_estimate
        }


class ValidationTools:
    """Validate process graphs before execution."""

    async def validate(self, process_graph: Any) -> Dict[str, Any]:
        """
        Run all validation checks on a process graph.

        Args:
            process_graph: OpenEO process graph dict

        Returns:
            ValidationResult as dict
        """
        errors = []
        warnings = []
        suggestions = []

        # Handle non-dict input
        if not isinstance(process_graph, dict):
            return ValidationResult(
                valid=False,
                errors=["Process graph must be a dictionary"]
            ).to_dict()

        # 1. Structural validation
        errors.extend(self._validate_structure(process_graph))

        # 2. Process validation
        errors.extend(self._validate_processes(process_graph))

        # Add warnings for unknown processes (could be UDPs)
        for node_id, process_id in getattr(self, '_unknown_processes', []):
            warnings.append(
                f"Unknown process '{process_id}' in node '{node_id}'. "
                "This may be a user-defined process (UDP)."
            )

        # 3. Data flow validation
        errors.extend(self._validate_data_flow(process_graph))

        # 4. Band validation
        band_issues = self._validate_bands(process_graph)
        # Band issues can be errors or warnings
        for issue in band_issues:
            if "not available" in issue.lower():
                errors.append(issue)
            else:
                warnings.append(issue)

        # 5. Extent validation
        warnings.extend(self._validate_extents(process_graph))

        # 6. Check for temporal formats
        errors.extend(self._validate_temporal_format(process_graph))

        # 7. Generate suggestions
        suggestions.extend(self._generate_suggestions(process_graph))

        # 8. Estimate resources
        estimate = self._estimate_resources(process_graph)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            resource_estimate=estimate
        ).to_dict()

    def _validate_structure(self, pg: Dict[str, Any]) -> List[str]:
        """Validate basic structure."""
        errors = []

        if len(pg) == 0:
            errors.append("Process graph is empty")
            return errors

        # Check for result node
        result_nodes = [
            node_id for node_id, node in pg.items()
            if isinstance(node, dict) and node.get("result", False)
        ]

        if len(result_nodes) == 0:
            errors.append("No result node found. Mark one node with 'result': true")
        elif len(result_nodes) > 1:
            errors.append(f"Multiple result nodes found: {result_nodes}. Only one is allowed.")

        return errors

    def _validate_processes(self, pg: Dict[str, Any]) -> List[str]:
        """Validate process IDs and arguments."""
        errors = []
        self._unknown_processes = []  # Track unknown processes for warnings

        for node_id, node in pg.items():
            if not isinstance(node, dict):
                continue

            process_id = node.get("process_id")
            if not process_id:
                errors.append(f"Node '{node_id}' missing process_id")
                continue

            # Check required arguments for known processes
            if process_id in PROCESS_SPECS:
                spec = PROCESS_SPECS[process_id]
                args = node.get("arguments", {})

                for req_arg in spec["required"]:
                    if req_arg not in args:
                        errors.append(
                            f"Node '{node_id}' ({process_id}): "
                            f"missing required argument '{req_arg}'"
                        )
            else:
                # Track unknown processes (could be UDPs)
                self._unknown_processes.append((node_id, process_id))

        return errors

    def _validate_data_flow(self, pg: Dict[str, Any]) -> List[str]:
        """Validate node references and detect cycles."""
        errors = []
        node_ids = set(pg.keys())

        # Check all from_node references
        for node_id, node in pg.items():
            if not isinstance(node, dict):
                continue

            args = node.get("arguments", {})
            self._check_references(args, node_ids, node_id, errors)

        # Check for cycles
        cycle_errors = self._detect_cycles(pg)
        errors.extend(cycle_errors)

        return errors

    def _check_references(
        self,
        obj: Any,
        valid_nodes: set,
        current_node: str,
        errors: List[str]
    ):
        """Recursively check from_node references."""
        if isinstance(obj, dict):
            if "from_node" in obj:
                ref = obj["from_node"]
                if ref not in valid_nodes:
                    errors.append(
                        f"Node '{current_node}' references unknown node '{ref}'"
                    )
            # Don't check from_parameter - that's for nested process graphs
            for key, value in obj.items():
                if key != "from_parameter":
                    self._check_references(value, valid_nodes, current_node, errors)
        elif isinstance(obj, list):
            for item in obj:
                self._check_references(item, valid_nodes, current_node, errors)

    def _detect_cycles(self, pg: Dict[str, Any]) -> List[str]:
        """Detect circular dependencies in process graph."""
        errors = []

        # Build dependency graph
        deps = {}
        for node_id, node in pg.items():
            if not isinstance(node, dict):
                continue
            deps[node_id] = self._get_dependencies(node)

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for dep in deps.get(node, []):
                if dep not in visited:
                    if dfs(dep, path + [dep]):
                        return True
                elif dep in rec_stack:
                    cycle = path[path.index(dep):] + [dep]
                    errors.append(f"Circular reference detected: {' -> '.join(cycle)}")
                    return True

            rec_stack.remove(node)
            return False

        for node in pg.keys():
            if node not in visited:
                dfs(node, [node])

        return errors

    def _get_dependencies(self, node: Dict[str, Any]) -> List[str]:
        """Extract from_node dependencies from a node."""
        deps = []

        def extract(obj):
            if isinstance(obj, dict):
                if "from_node" in obj:
                    deps.append(obj["from_node"])
                for value in obj.values():
                    extract(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)

        extract(node.get("arguments", {}))
        return deps

    def _validate_bands(self, pg: Dict[str, Any]) -> List[str]:
        """Validate band names against collection capabilities."""
        issues = []

        for node_id, node in pg.items():
            if not isinstance(node, dict):
                continue

            if node.get("process_id") != "load_collection":
                continue

            args = node.get("arguments", {})
            collection_id = args.get("id", "")
            bands = args.get("bands", [])

            if collection_id in COLLECTION_BANDS and bands:
                available = set(COLLECTION_BANDS[collection_id])
                requested = set(bands)
                invalid = requested - available

                if invalid:
                    # Check if they're using old-style band names
                    corrections = []
                    for band in invalid:
                        if band in BAND_CORRECTIONS:
                            corrections.append(
                                f"'{band}' should be '{BAND_CORRECTIONS[band]}'"
                            )

                    if corrections:
                        issues.append(
                            f"Node '{node_id}': Band name corrections needed: "
                            f"{', '.join(corrections)}. "
                            f"Use AWS Earth Search band names (e.g., 'red', 'nir')."
                        )
                    else:
                        issues.append(
                            f"Node '{node_id}': bands {invalid} not available "
                            f"in {collection_id}. Available: {sorted(available)}"
                        )

        return issues

    def _validate_extents(self, pg: Dict[str, Any]) -> List[str]:
        """Check spatial/temporal extents for warnings."""
        warnings = []

        for node_id, node in pg.items():
            if not isinstance(node, dict):
                continue

            if node.get("process_id") != "load_collection":
                continue

            args = node.get("arguments", {})

            # Check spatial extent
            spatial = args.get("spatial_extent", {})
            if spatial:
                width = abs(spatial.get("east", 0) - spatial.get("west", 0))
                height = abs(spatial.get("north", 0) - spatial.get("south", 0))

                if width > 1 or height > 1:
                    warnings.append(
                        f"Large spatial extent ({width:.2f}° x {height:.2f}°). "
                        "Consider reducing for faster processing."
                    )

                if width > 5 or height > 5:
                    warnings.append(
                        f"Very large extent may timeout or fail. "
                        "Recommend < 1° x 1° for testing."
                    )

            # Check temporal extent
            temporal = args.get("temporal_extent", [])
            if len(temporal) >= 2 and temporal[0] and temporal[1]:
                try:
                    start = datetime.fromisoformat(temporal[0].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(temporal[1].replace("Z", "+00:00"))
                    days = (end - start).days

                    if days > 365:
                        warnings.append(
                            f"Long temporal range ({days} days). "
                            "Consider reducing for faster processing."
                        )
                except ValueError:
                    pass  # Will be caught by temporal format validation

        return warnings

    def _validate_temporal_format(self, pg: Dict[str, Any]) -> List[str]:
        """Validate temporal extent date formats."""
        errors = []

        for node_id, node in pg.items():
            if not isinstance(node, dict):
                continue

            if node.get("process_id") != "load_collection":
                continue

            temporal = node.get("arguments", {}).get("temporal_extent", [])
            if temporal:
                for i, date_str in enumerate(temporal):
                    if date_str is None:
                        continue
                    try:
                        # Try parsing the date
                        if isinstance(date_str, str):
                            datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except ValueError:
                        errors.append(
                            f"Node '{node_id}': Invalid date format at position {i}: "
                            f"'{date_str}'. Use ISO format (YYYY-MM-DD)."
                        )

        return errors

    def _generate_suggestions(self, pg: Dict[str, Any]) -> List[str]:
        """Generate optimization suggestions."""
        suggestions = []

        # Check for cloud masking with Sentinel
        has_cloud_mask = any(
            node.get("process_id") in ["mask", "mask_polygon"]
            for node in pg.values() if isinstance(node, dict)
        )

        has_sentinel = any(
            "sentinel" in str(node.get("arguments", {}).get("id", "")).lower()
            for node in pg.values() if isinstance(node, dict)
        )

        if has_sentinel and not has_cloud_mask:
            suggestions.append(
                "Consider adding cloud masking for Sentinel data. "
                "Use the SCL band to filter cloudy pixels."
            )

        # Check for time reduction
        has_temporal = any(
            node.get("arguments", {}).get("temporal_extent")
            for node in pg.values()
            if isinstance(node, dict) and node.get("process_id") == "load_collection"
        )

        has_reduce_time = any(
            node.get("process_id") == "reduce_dimension" and
            node.get("arguments", {}).get("dimension") in ["time", "t"]
            for node in pg.values() if isinstance(node, dict)
        )

        if has_temporal and not has_reduce_time:
            suggestions.append(
                "Consider adding reduce_dimension over time if you need "
                "a single composite image (e.g., mean, median)."
            )

        # Check for NDVI without NIR band
        has_ndvi = any(
            node.get("process_id") in ["ndvi", "normalized_difference"]
            for node in pg.values() if isinstance(node, dict)
        )

        if has_ndvi:
            # Check if NIR band is loaded
            for node in pg.values():
                if isinstance(node, dict) and node.get("process_id") == "load_collection":
                    bands = node.get("arguments", {}).get("bands", [])
                    if bands and "nir" not in bands:
                        suggestions.append(
                            "NDVI calculation requires NIR band. "
                            "Make sure to include 'nir' in the bands argument."
                        )

        return suggestions

    def _estimate_resources(self, pg: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate processing resources needed."""
        # Calculate based on extent, temporal range, bands
        total_pixels = 0
        complexity = "low"

        for node in pg.values():
            if isinstance(node, dict) and node.get("process_id") == "load_collection":
                args = node.get("arguments", {})

                spatial = args.get("spatial_extent", {})
                if spatial:
                    width = abs(spatial.get("east", 0) - spatial.get("west", 0))
                    height = abs(spatial.get("north", 0) - spatial.get("south", 0))
                    # Rough estimate: 10m resolution for Sentinel-2
                    pixels = (width * 111000 / 10) * (height * 111000 / 10)
                    total_pixels += pixels

                    if width > 0.5 or height > 0.5:
                        complexity = "medium"
                    if width > 2 or height > 2:
                        complexity = "high"
                    if width > 5 or height > 5:
                        complexity = "very_high"

        return {
            "estimated_size_mb": "unknown",
            "estimated_time_seconds": "unknown",
            "complexity": complexity,
            "estimated_pixels": int(total_pixels) if total_pixels else "unknown"
        }


async def validate_graph_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone tool function for validating process graphs."""
    tools = ValidationTools()
    result = await tools.validate(args.get("process_graph", {}))
    return {
        "content": [{"type": "text", "text": json.dumps(result)}]
    }
