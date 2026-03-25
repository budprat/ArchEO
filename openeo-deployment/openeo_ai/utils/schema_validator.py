# ABOUTME: Schema-based validation for tool inputs and process graphs.
# Provides pre-execution validation using JSON Schema with OpenEO-specific rules.

"""
Schema validator for OpenEO AI Assistant.

Provides:
- JSON Schema validation for tool inputs
- Deep validation of OpenEO process graphs
- Custom validators for geospatial data
- Pre-execution checks to prevent errors
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

logger = logging.getLogger(__name__)


# Try to import jsonschema, fall back to simple validation if not available
try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError as JsonSchemaValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    logger.warning("jsonschema not installed; using basic validation")


@dataclass
class SchemaValidationError:
    """A single validation error."""
    path: str
    message: str
    value: Any = None
    schema_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "message": self.message,
            "value": self.value,
            "schema_path": self.schema_path,
        }


@dataclass
class SchemaValidationResult:
    """Result of schema validation."""
    valid: bool
    errors: List[SchemaValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    normalized_data: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
        }

    def to_user_message(self) -> str:
        """Format as user-friendly message."""
        if self.valid:
            msg = "Validation passed."
            if self.warnings:
                msg += f"\n**Warnings:**\n" + "\n".join(f"- {w}" for w in self.warnings)
            return msg

        parts = ["**Validation Failed:**"]
        for error in self.errors:
            parts.append(f"- {error.path}: {error.message}")
        if self.warnings:
            parts.append("\n**Warnings:**")
            parts.extend(f"- {w}" for w in self.warnings)
        return "\n".join(parts)


# OpenEO Process Graph Schema
PROCESS_GRAPH_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "additionalProperties": {
        "type": "object",
        "required": ["process_id", "arguments"],
        "properties": {
            "process_id": {"type": "string", "minLength": 1},
            "arguments": {"type": "object"},
            "result": {"type": "boolean"},
            "description": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

# Spatial extent schema
SPATIAL_EXTENT_SCHEMA = {
    "type": "object",
    "required": ["west", "south", "east", "north"],
    "properties": {
        "west": {"type": "number", "minimum": -180, "maximum": 180},
        "south": {"type": "number", "minimum": -90, "maximum": 90},
        "east": {"type": "number", "minimum": -180, "maximum": 180},
        "north": {"type": "number", "minimum": -90, "maximum": 90},
        "crs": {"type": "string"},
    },
    "additionalProperties": False,
}

# Temporal extent schema
TEMPORAL_EXTENT_SCHEMA = {
    "type": "array",
    "items": {"type": ["string", "null"]},
    "minItems": 2,
    "maxItems": 2,
}

# Tool input schemas
TOOL_SCHEMAS = {
    "openeo_generate_graph": {
        "type": "object",
        "required": ["description", "collection", "spatial_extent", "temporal_extent"],
        "properties": {
            "description": {"type": "string", "minLength": 1},
            "collection": {"type": "string", "minLength": 1},
            "spatial_extent": SPATIAL_EXTENT_SCHEMA,
            "temporal_extent": TEMPORAL_EXTENT_SCHEMA,
            "output_format": {"type": "string", "enum": ["GTiff", "netCDF", "JSON", "PNG"]},
        },
    },
    "openeo_create_job": {
        "type": "object",
        "required": ["title", "process_graph"],
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "process_graph": PROCESS_GRAPH_SCHEMA,
            "description": {"type": "string"},
        },
    },
    "openeo_validate_graph": {
        "type": "object",
        "required": ["process_graph"],
        "properties": {
            "process_graph": PROCESS_GRAPH_SCHEMA,
        },
    },
    "viz_show_map": {
        "type": "object",
        "required": ["geotiff_path"],
        "properties": {
            "geotiff_path": {"type": "string", "minLength": 1},
            "title": {"type": "string"},
            "colormap": {"type": "string"},
        },
    },
    "openeo_resolve_location": {
        "type": "object",
        "required": ["location"],
        "properties": {
            "location": {"type": "string", "minLength": 1},
            "buffer_degrees": {"type": "number", "minimum": 0, "maximum": 10},
        },
    },
    "openeo_estimate_extent": {
        "type": "object",
        "required": ["spatial_extent"],
        "properties": {
            "spatial_extent": SPATIAL_EXTENT_SCHEMA,
            "temporal_extent": TEMPORAL_EXTENT_SCHEMA,
            "collection": {"type": "string"},
            "bands": {"type": "array", "items": {"type": "string"}},
        },
    },
}

# Valid OpenEO processes
VALID_PROCESSES = {
    "load_collection", "load_stac", "save_result",
    "filter_bbox", "filter_bands", "filter_temporal", "filter_spatial",
    "reduce_dimension", "add_dimension", "rename_dimension",
    "apply", "apply_dimension", "apply_kernel",
    "aggregate_temporal", "aggregate_temporal_period", "aggregate_spatial",
    "resample_cube_spatial", "resample_cube_temporal",
    "merge_cubes", "mask", "mask_polygon",
    "ndvi", "normalized_difference", "linear_scale_range",
    "add", "subtract", "multiply", "divide", "power", "sqrt", "absolute",
    "min", "max", "sum", "mean", "median", "sd", "variance", "count",
    "and", "or", "not", "xor", "if",
    "eq", "neq", "gt", "gte", "lt", "lte", "between",
    "array_element", "array_create", "first", "last",
    "run_udf", "inspect",
}

# Valid collection IDs
VALID_COLLECTIONS = {
    "sentinel-2-l2a", "sentinel-2-l1c",
    "sentinel-1-grd",
    "landsat-c2-l2",
    "cop-dem-glo-30", "cop-dem-glo-90",
    "naip",
}

# Valid band names per collection
COLLECTION_BANDS = {
    "sentinel-2-l2a": {
        "blue", "green", "red", "rededge1", "rededge2", "rededge3",
        "nir", "nir08", "nir09", "swir16", "swir22", "scl", "coastal"
    },
    "sentinel-2-l1c": {
        "blue", "green", "red", "rededge1", "rededge2", "rededge3",
        "nir", "nir08", "nir09", "swir16", "swir22", "coastal"
    },
    "landsat-c2-l2": {
        "blue", "green", "red", "nir08", "swir16", "swir22", "lwir11", "qa_pixel"
    },
    "cop-dem-glo-30": {"data"},
    "cop-dem-glo-90": {"data"},
}


class SchemaValidator:
    """
    Schema-based validator for tool inputs and process graphs.

    Usage:
        validator = SchemaValidator()

        # Validate tool input
        result = validator.validate_tool_input("openeo_create_job", input_data)

        # Validate process graph
        result = validator.validate_process_graph(process_graph)

        # Deep validation with semantic checks
        result = validator.deep_validate(process_graph)
    """

    def __init__(
        self,
        custom_schemas: Optional[Dict[str, Dict]] = None,
        custom_processes: Optional[Set[str]] = None,
        custom_collections: Optional[Set[str]] = None,
    ):
        """Initialize validator with optional custom schemas."""
        self.schemas = {**TOOL_SCHEMAS}
        if custom_schemas:
            self.schemas.update(custom_schemas)

        self.valid_processes = VALID_PROCESSES.copy()
        if custom_processes:
            self.valid_processes.update(custom_processes)

        self.valid_collections = VALID_COLLECTIONS.copy()
        if custom_collections:
            self.valid_collections.update(custom_collections)

    def validate_tool_input(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> SchemaValidationResult:
        """
        Validate tool input against its schema.

        Args:
            tool_name: Name of the tool
            tool_input: Input to validate

        Returns:
            SchemaValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        # Get schema for tool
        schema = self.schemas.get(tool_name)
        if not schema:
            # No schema defined; basic validation
            if not isinstance(tool_input, dict):
                errors.append(SchemaValidationError(
                    path="$",
                    message="Tool input must be an object",
                    value=type(tool_input).__name__
                ))
            return SchemaValidationResult(valid=len(errors) == 0, errors=errors)

        # Validate against JSON schema
        if HAS_JSONSCHEMA:
            validator = Draft7Validator(schema)
            for error in validator.iter_errors(tool_input):
                errors.append(SchemaValidationError(
                    path="$." + ".".join(str(p) for p in error.absolute_path),
                    message=error.message,
                    value=error.instance if not isinstance(error.instance, dict) else None,
                    schema_path=".".join(str(p) for p in error.absolute_schema_path),
                ))
        else:
            # Basic validation without jsonschema
            errors.extend(self._basic_validate(tool_input, schema))

        # Add tool-specific semantic validation
        if tool_name == "openeo_generate_graph":
            warnings.extend(self._validate_generate_graph_input(tool_input))
        elif tool_name == "openeo_create_job":
            pg = tool_input.get("process_graph", {})
            pg_result = self.validate_process_graph(pg)
            errors.extend(pg_result.errors)
            warnings.extend(pg_result.warnings)

        return SchemaValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_process_graph(
        self,
        process_graph: Dict[str, Any]
    ) -> SchemaValidationResult:
        """
        Validate an OpenEO process graph.

        Args:
            process_graph: The process graph to validate

        Returns:
            SchemaValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        if not isinstance(process_graph, dict):
            errors.append(SchemaValidationError(
                path="$",
                message="Process graph must be an object",
                value=type(process_graph).__name__
            ))
            return SchemaValidationResult(valid=False, errors=errors)

        if len(process_graph) == 0:
            errors.append(SchemaValidationError(
                path="$",
                message="Process graph is empty"
            ))
            return SchemaValidationResult(valid=False, errors=errors)

        # Check structure of each node
        result_nodes = []
        node_ids = set(process_graph.keys())

        for node_id, node in process_graph.items():
            if not isinstance(node, dict):
                errors.append(SchemaValidationError(
                    path=f"$.{node_id}",
                    message="Node must be an object",
                    value=type(node).__name__
                ))
                continue

            # Check required fields
            if "process_id" not in node:
                errors.append(SchemaValidationError(
                    path=f"$.{node_id}",
                    message="Missing required field 'process_id'"
                ))
            elif node["process_id"] not in self.valid_processes:
                warnings.append(
                    f"Unknown process '{node['process_id']}' at {node_id}. "
                    "May be a user-defined process (UDP)."
                )

            if "arguments" not in node:
                errors.append(SchemaValidationError(
                    path=f"$.{node_id}",
                    message="Missing required field 'arguments'"
                ))

            # Track result nodes
            if node.get("result", False):
                result_nodes.append(node_id)

            # Validate from_node references
            self._validate_references(node, node_id, node_ids, errors)

        # Check for exactly one result node
        if len(result_nodes) == 0:
            errors.append(SchemaValidationError(
                path="$",
                message="No result node found. Mark one node with 'result': true"
            ))
        elif len(result_nodes) > 1:
            errors.append(SchemaValidationError(
                path="$",
                message=f"Multiple result nodes found: {result_nodes}. Only one is allowed."
            ))

        # Check for cycles
        cycle = self._detect_cycle(process_graph)
        if cycle:
            errors.append(SchemaValidationError(
                path="$",
                message=f"Circular reference detected: {' -> '.join(cycle)}"
            ))

        return SchemaValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def deep_validate(
        self,
        process_graph: Dict[str, Any]
    ) -> SchemaValidationResult:
        """
        Perform deep validation including semantic checks.

        Includes:
        - Basic structure validation
        - Band name validation
        - Collection ID validation
        - Temporal format validation
        - Extent size warnings

        Args:
            process_graph: The process graph to validate

        Returns:
            SchemaValidationResult with comprehensive checks
        """
        # Start with basic validation
        result = self.validate_process_graph(process_graph)
        errors = list(result.errors)
        warnings = list(result.warnings)

        if not result.valid and any(e.message.startswith("Process graph") for e in errors):
            # Critical structural error; skip deep validation
            return result

        # Semantic validation for each node
        for node_id, node in process_graph.items():
            if not isinstance(node, dict):
                continue

            process_id = node.get("process_id", "")
            args = node.get("arguments", {})

            # Validate load_collection
            if process_id == "load_collection":
                collection_id = args.get("id", "")

                # Check collection exists
                if collection_id and collection_id not in self.valid_collections:
                    warnings.append(
                        f"Unknown collection '{collection_id}' at {node_id}. "
                        f"Valid collections: {', '.join(sorted(self.valid_collections))}"
                    )

                # Check bands
                bands = args.get("bands", [])
                if bands and collection_id in COLLECTION_BANDS:
                    valid_bands = COLLECTION_BANDS[collection_id]
                    invalid = set(bands) - valid_bands
                    if invalid:
                        errors.append(SchemaValidationError(
                            path=f"$.{node_id}.arguments.bands",
                            message=f"Invalid bands: {invalid}. Valid: {sorted(valid_bands)}",
                            value=list(invalid)
                        ))

                # Check temporal format
                temporal = args.get("temporal_extent", [])
                for i, date_str in enumerate(temporal):
                    if date_str is not None:
                        if not self._is_valid_date(date_str):
                            errors.append(SchemaValidationError(
                                path=f"$.{node_id}.arguments.temporal_extent[{i}]",
                                message=f"Invalid date format: '{date_str}'. Use ISO format (YYYY-MM-DD).",
                                value=date_str
                            ))

                # Check extent size
                spatial = args.get("spatial_extent", {})
                if spatial:
                    width = abs(spatial.get("east", 0) - spatial.get("west", 0))
                    height = abs(spatial.get("north", 0) - spatial.get("south", 0))
                    if width > 1 or height > 1:
                        warnings.append(
                            f"Large spatial extent ({width:.2f}° x {height:.2f}°) at {node_id}. "
                            "Consider reducing for faster processing."
                        )

            # Validate reduce_dimension
            elif process_id == "reduce_dimension":
                dimension = args.get("dimension", "")
                valid_dims = {"time", "bands", "latitude", "longitude", "x", "y", "t"}
                if dimension and dimension not in valid_dims:
                    warnings.append(
                        f"Unusual dimension name '{dimension}' at {node_id}. "
                        f"Common names: {', '.join(sorted(valid_dims))}"
                    )

        return SchemaValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_references(
        self,
        node: Dict[str, Any],
        node_id: str,
        valid_nodes: Set[str],
        errors: List[SchemaValidationError]
    ):
        """Recursively validate from_node references."""
        def check(obj: Any, path: str):
            if isinstance(obj, dict):
                if "from_node" in obj:
                    ref = obj["from_node"]
                    if ref not in valid_nodes:
                        errors.append(SchemaValidationError(
                            path=path + ".from_node",
                            message=f"References unknown node '{ref}'",
                            value=ref
                        ))
                for key, value in obj.items():
                    if key != "from_parameter":
                        check(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check(item, f"{path}[{i}]")

        check(node.get("arguments", {}), f"$.{node_id}.arguments")

    def _detect_cycle(self, process_graph: Dict[str, Any]) -> Optional[List[str]]:
        """Detect cycles in the process graph. Returns cycle path if found."""
        def get_deps(node: Dict[str, Any]) -> List[str]:
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

        visited = set()
        rec_stack = set()
        path = []

        def dfs(node_id: str) -> Optional[List[str]]:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            node = process_graph.get(node_id, {})
            for dep in get_deps(node):
                if dep not in visited:
                    result = dfs(dep)
                    if result:
                        return result
                elif dep in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep)
                    return path[cycle_start:] + [dep]

            path.pop()
            rec_stack.remove(node_id)
            return None

        for node_id in process_graph:
            if node_id not in visited:
                result = dfs(node_id)
                if result:
                    return result
        return None

    def _validate_generate_graph_input(self, tool_input: Dict[str, Any]) -> List[str]:
        """Additional validation for generate_graph input."""
        warnings = []

        spatial = tool_input.get("spatial_extent", {})
        if spatial:
            # Check extent isn't reversed
            if spatial.get("west", 0) > spatial.get("east", 0):
                warnings.append("West > East in spatial_extent; coordinates may be swapped")
            if spatial.get("south", 0) > spatial.get("north", 0):
                warnings.append("South > North in spatial_extent; coordinates may be swapped")

            # Check reasonable extent size
            width = abs(spatial.get("east", 0) - spatial.get("west", 0))
            height = abs(spatial.get("north", 0) - spatial.get("south", 0))
            if width > 5 or height > 5:
                warnings.append(
                    f"Very large extent ({width:.1f}° x {height:.1f}°) may timeout. "
                    "Consider < 1° x 1° for testing."
                )

        # Check collection
        collection = tool_input.get("collection", "")
        if collection and collection not in self.valid_collections:
            warnings.append(
                f"Unknown collection '{collection}'. "
                f"Valid: {', '.join(sorted(self.valid_collections))}"
            )

        return warnings

    def _basic_validate(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str = "$"
    ) -> List[SchemaValidationError]:
        """Basic validation without jsonschema library."""
        errors = []
        schema_type = schema.get("type")

        if schema_type == "object":
            if not isinstance(data, dict):
                errors.append(SchemaValidationError(
                    path=path,
                    message=f"Expected object, got {type(data).__name__}",
                    value=type(data).__name__
                ))
                return errors

            # Check required fields
            for req in schema.get("required", []):
                if req not in data:
                    errors.append(SchemaValidationError(
                        path=f"{path}.{req}",
                        message=f"Missing required field '{req}'"
                    ))

            # Validate properties
            props = schema.get("properties", {})
            for key, value in data.items():
                if key in props:
                    errors.extend(self._basic_validate(value, props[key], f"{path}.{key}"))

        elif schema_type == "array":
            if not isinstance(data, list):
                errors.append(SchemaValidationError(
                    path=path,
                    message=f"Expected array, got {type(data).__name__}",
                    value=type(data).__name__
                ))

        elif schema_type == "string":
            if not isinstance(data, str):
                errors.append(SchemaValidationError(
                    path=path,
                    message=f"Expected string, got {type(data).__name__}",
                    value=type(data).__name__
                ))
            elif schema.get("minLength") and len(data) < schema["minLength"]:
                errors.append(SchemaValidationError(
                    path=path,
                    message=f"String too short (min {schema['minLength']})",
                    value=data
                ))

        elif schema_type == "number":
            if not isinstance(data, (int, float)):
                errors.append(SchemaValidationError(
                    path=path,
                    message=f"Expected number, got {type(data).__name__}",
                    value=type(data).__name__
                ))

        return errors

    def _is_valid_date(self, date_str: str) -> bool:
        """Check if a string is a valid ISO date."""
        if not isinstance(date_str, str):
            return False
        try:
            datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False


# Module-level singleton
_default_validator: Optional[SchemaValidator] = None


def get_schema_validator() -> SchemaValidator:
    """Get the default schema validator singleton."""
    global _default_validator
    if _default_validator is None:
        _default_validator = SchemaValidator()
    return _default_validator


def validate_tool_input(tool_name: str, tool_input: Dict[str, Any]) -> SchemaValidationResult:
    """
    Convenience function to validate tool input.

    Args:
        tool_name: Name of the tool
        tool_input: Input to validate

    Returns:
        SchemaValidationResult
    """
    return get_schema_validator().validate_tool_input(tool_name, tool_input)


def validate_process_graph(process_graph: Dict[str, Any]) -> SchemaValidationResult:
    """
    Convenience function to validate a process graph.

    Args:
        process_graph: The process graph to validate

    Returns:
        SchemaValidationResult
    """
    return get_schema_validator().validate_process_graph(process_graph)


def deep_validate_graph(process_graph: Dict[str, Any]) -> SchemaValidationResult:
    """
    Convenience function for deep validation of a process graph.

    Args:
        process_graph: The process graph to validate

    Returns:
        SchemaValidationResult with comprehensive checks
    """
    return get_schema_validator().deep_validate(process_graph)
