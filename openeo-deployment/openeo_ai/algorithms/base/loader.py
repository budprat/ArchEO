# ABOUTME: Base algorithm class for modular algorithm implementations.
# Defines the interface for algorithms that generate OpenEO process graphs.

"""
Base algorithm class for OpenEO AI.

Provides:
- BaseAlgorithm abstract class
- AlgorithmParameter for defining inputs
- AlgorithmMetadata for algorithm descriptions
- Composition pattern: loader + algorithm → process graph
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

logger = logging.getLogger(__name__)


class ParameterType(Enum):
    """Types of algorithm parameters."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    BAND = "band"
    COLLECTION = "collection"
    SPATIAL_EXTENT = "spatial_extent"
    TEMPORAL_EXTENT = "temporal_extent"


@dataclass
class AlgorithmParameter:
    """Definition of an algorithm parameter."""
    name: str
    param_type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    choices: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate a parameter value."""
        if value is None:
            if self.required and self.default is None:
                return False, f"Parameter '{self.name}' is required"
            return True, None

        # Type validation
        if self.param_type == ParameterType.STRING:
            if not isinstance(value, str):
                return False, f"Parameter '{self.name}' must be a string"
        elif self.param_type in (ParameterType.NUMBER, ParameterType.INTEGER):
            if not isinstance(value, (int, float)):
                return False, f"Parameter '{self.name}' must be a number"
            if self.min_value is not None and value < self.min_value:
                return False, f"Parameter '{self.name}' must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Parameter '{self.name}' must be <= {self.max_value}"
        elif self.param_type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return False, f"Parameter '{self.name}' must be a boolean"
        elif self.param_type == ParameterType.ARRAY:
            if not isinstance(value, list):
                return False, f"Parameter '{self.name}' must be an array"
        elif self.param_type == ParameterType.OBJECT:
            if not isinstance(value, dict):
                return False, f"Parameter '{self.name}' must be an object"

        # Choice validation
        if self.choices and value not in self.choices:
            return False, f"Parameter '{self.name}' must be one of: {self.choices}"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "type": self.param_type.value,
            "description": self.description,
            "required": self.required,
            "default": self.default,
            "choices": self.choices,
        }


@dataclass
class AlgorithmMetadata:
    """Metadata describing an algorithm."""
    id: str
    name: str
    description: str
    category: str
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    requires_bands: List[str] = field(default_factory=list)
    output_type: str = "raster"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "references": self.references,
            "requires_bands": self.requires_bands,
            "output_type": self.output_type,
        }


class BaseAlgorithm(ABC):
    """
    Base class for algorithm implementations.

    Algorithms generate OpenEO process graphs from parameters.
    They follow a composition pattern: loader → algorithm → saver.

    Usage:
        class NDVIAlgorithm(BaseAlgorithm):
            @property
            def metadata(self):
                return AlgorithmMetadata(...)

            @property
            def parameters(self):
                return [AlgorithmParameter(...), ...]

            def build_process_graph(self, params, input_node):
                return {...}  # Process graph dict

        # Use the algorithm
        algo = NDVIAlgorithm()
        graph = algo.generate_full_graph(
            collection="sentinel-2-l2a",
            spatial_extent={...},
            temporal_extent=[...],
            **params
        )
    """

    @property
    @abstractmethod
    def metadata(self) -> AlgorithmMetadata:
        """Get algorithm metadata."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> List[AlgorithmParameter]:
        """Get algorithm parameters."""
        pass

    @abstractmethod
    def build_process_graph(
        self,
        params: Dict[str, Any],
        input_node: str
    ) -> Dict[str, Any]:
        """
        Build the algorithm-specific process graph.

        Args:
            params: Validated parameters
            input_node: Name of the input data node (typically from load_collection)

        Returns:
            Dictionary of process graph nodes (without load_collection and save_result)
        """
        pass

    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate all parameters.

        Args:
            params: Parameter values

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        for param in self.parameters:
            value = params.get(param.name, param.default)
            valid, error = param.validate(value)
            if not valid:
                errors.append(error)
        return len(errors) == 0, errors

    def get_required_bands(self) -> List[str]:
        """Get list of bands required by this algorithm."""
        return self.metadata.requires_bands

    def generate_full_graph(
        self,
        collection: str,
        spatial_extent: Dict[str, float],
        temporal_extent: List[str],
        output_format: str = "GTiff",
        **params
    ) -> Dict[str, Any]:
        """
        Generate a complete process graph including load_collection and save_result.

        Args:
            collection: Collection ID
            spatial_extent: Bounding box {west, south, east, north}
            temporal_extent: Date range [start, end]
            output_format: Output format (GTiff, netCDF, etc.)
            **params: Algorithm-specific parameters

        Returns:
            Complete process graph ready for execution
        """
        # Validate parameters
        valid, errors = self.validate_parameters(params)
        if not valid:
            raise ValueError(f"Invalid parameters: {errors}")

        # Build load_collection node
        process_graph = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": collection,
                    "spatial_extent": spatial_extent,
                    "temporal_extent": temporal_extent,
                    "bands": self.get_required_bands() or None,
                }
            }
        }

        # Remove None values from load_collection arguments
        process_graph["load1"]["arguments"] = {
            k: v for k, v in process_graph["load1"]["arguments"].items()
            if v is not None
        }

        # Apply default values to params
        full_params = {}
        for param in self.parameters:
            full_params[param.name] = params.get(param.name, param.default)

        # Build algorithm-specific nodes
        algo_nodes = self.build_process_graph(full_params, "load1")
        process_graph.update(algo_nodes)

        # Find the result node from algorithm
        result_node = None
        for node_id, node in algo_nodes.items():
            if node.get("result", False):
                result_node = node_id
                # Remove result flag; we'll add save_result
                node["result"] = False
                break

        if result_node is None:
            # Use last node if no result specified
            result_node = list(algo_nodes.keys())[-1] if algo_nodes else "load1"

        # Add save_result node
        process_graph["save1"] = {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": result_node},
                "format": output_format
            },
            "result": True
        }

        logger.debug(f"Generated process graph for {self.metadata.id}: {len(process_graph)} nodes")
        return process_graph

    def describe(self) -> Dict[str, Any]:
        """Get full algorithm description."""
        return {
            "metadata": self.metadata.to_dict(),
            "parameters": [p.to_dict() for p in self.parameters],
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.metadata.id})>"


class CompositeAlgorithm(BaseAlgorithm):
    """
    Algorithm that composes multiple sub-algorithms.

    Useful for creating pipelines like: load → preprocess → analyze → postprocess → save
    """

    def __init__(self, *algorithms: BaseAlgorithm):
        """
        Initialize with a sequence of algorithms.

        Args:
            *algorithms: Algorithms to compose in order
        """
        self._algorithms = list(algorithms)

    @property
    def metadata(self) -> AlgorithmMetadata:
        """Combined metadata from all algorithms."""
        if not self._algorithms:
            return AlgorithmMetadata(
                id="composite",
                name="Composite Algorithm",
                description="Empty composite",
                category="composite"
            )

        primary = self._algorithms[0].metadata
        return AlgorithmMetadata(
            id=f"composite_{primary.id}",
            name=f"Composite: {primary.name}",
            description=f"Composite of: {', '.join(a.metadata.name for a in self._algorithms)}",
            category="composite",
            requires_bands=self._get_all_required_bands(),
        )

    @property
    def parameters(self) -> List[AlgorithmParameter]:
        """Combined parameters from all algorithms."""
        params = []
        seen = set()
        for algo in self._algorithms:
            for param in algo.parameters:
                if param.name not in seen:
                    params.append(param)
                    seen.add(param.name)
        return params

    def _get_all_required_bands(self) -> List[str]:
        """Get all required bands from all algorithms."""
        bands = []
        for algo in self._algorithms:
            bands.extend(algo.get_required_bands())
        return list(set(bands))

    def build_process_graph(
        self,
        params: Dict[str, Any],
        input_node: str
    ) -> Dict[str, Any]:
        """Build composite process graph."""
        all_nodes = {}
        current_input = input_node

        for i, algo in enumerate(self._algorithms):
            # Build sub-graph
            nodes = algo.build_process_graph(params, current_input)

            # Prefix node names to avoid conflicts
            prefixed_nodes = {}
            for node_id, node in nodes.items():
                new_id = f"algo{i}_{node_id}"
                prefixed_nodes[new_id] = self._rewrite_references(
                    node, nodes.keys(), f"algo{i}_", current_input
                )

            all_nodes.update(prefixed_nodes)

            # Find output node for next algorithm
            for node_id, node in prefixed_nodes.items():
                if node.get("result", False):
                    current_input = node_id
                    node["result"] = False  # Clear intermediate results
                    break

        # Mark last node as result
        if all_nodes:
            last_node = list(all_nodes.keys())[-1]
            all_nodes[last_node]["result"] = True

        return all_nodes

    def _rewrite_references(
        self,
        node: Dict[str, Any],
        old_names: set,
        prefix: str,
        input_node: str
    ) -> Dict[str, Any]:
        """Rewrite from_node references with prefix."""
        import copy
        result = copy.deepcopy(node)

        def rewrite(obj):
            if isinstance(obj, dict):
                if "from_node" in obj:
                    ref = obj["from_node"]
                    if ref in old_names:
                        obj["from_node"] = f"{prefix}{ref}"
                for value in obj.values():
                    rewrite(value)
            elif isinstance(obj, list):
                for item in obj:
                    rewrite(item)

        rewrite(result)
        return result
