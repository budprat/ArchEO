# ABOUTME: NDWI (Normalized Difference Water Index) algorithm.
# Calculates water content index from green and NIR bands.

"""
NDWI Algorithm Implementation.

NDWI = (Green - NIR) / (Green + NIR)

Values:
- > 0: Water bodies
- < 0: Non-water features

Can also calculate MNDWI (Modified NDWI) using SWIR instead of NIR:
MNDWI = (Green - SWIR) / (Green + SWIR)
"""

from typing import Any, Dict, List

from ..base.loader import (
    AlgorithmMetadata,
    AlgorithmParameter,
    BaseAlgorithm,
    ParameterType,
)
from ..base.registry import register_algorithm


@register_algorithm
class NDWIAlgorithm(BaseAlgorithm):
    """
    NDWI (Normalized Difference Water Index) calculation.

    Detects water bodies and estimates water content in vegetation.
    """

    @property
    def metadata(self) -> AlgorithmMetadata:
        return AlgorithmMetadata(
            id="ndwi",
            name="NDWI - Normalized Difference Water Index",
            description=(
                "Calculates the Normalized Difference Water Index (NDWI) for "
                "detecting water bodies and estimating water content in vegetation. "
                "Positive values indicate water, while negative values indicate "
                "non-water features. Optionally calculates MNDWI (Modified NDWI) "
                "using SWIR band for improved water body detection."
            ),
            category="index",
            version="1.0.0",
            tags=["water", "ndwi", "mndwi", "index", "hydrology", "flood"],
            references=[
                "McFeeters, S.K., 1996. The use of the Normalized Difference Water Index (NDWI).",
                "Xu, H., 2006. Modification of NDWI to enhance open water features.",
            ],
            requires_bands=["green", "nir"],
            output_type="raster",
        )

    @property
    def parameters(self) -> List[AlgorithmParameter]:
        return [
            AlgorithmParameter(
                name="green_band",
                param_type=ParameterType.BAND,
                description="Name of the green band",
                required=False,
                default="green",
            ),
            AlgorithmParameter(
                name="nir_band",
                param_type=ParameterType.BAND,
                description="Name of the NIR band (or SWIR for MNDWI)",
                required=False,
                default="nir",
            ),
            AlgorithmParameter(
                name="use_swir",
                param_type=ParameterType.BOOLEAN,
                description="Use SWIR band instead of NIR (calculates MNDWI)",
                required=False,
                default=False,
            ),
            AlgorithmParameter(
                name="swir_band",
                param_type=ParameterType.BAND,
                description="Name of the SWIR band (if use_swir=True)",
                required=False,
                default="swir16",
            ),
            AlgorithmParameter(
                name="temporal_reducer",
                param_type=ParameterType.STRING,
                description="Temporal aggregation method",
                required=False,
                default="median",
                choices=["none", "mean", "median", "max", "min"],
            ),
            AlgorithmParameter(
                name="threshold",
                param_type=ParameterType.NUMBER,
                description="Threshold for water classification (None for continuous output)",
                required=False,
                default=None,
                min_value=-1.0,
                max_value=1.0,
            ),
        ]

    def get_required_bands(self) -> List[str]:
        """Override to include SWIR if needed."""
        # Default bands; actual bands depend on parameters
        return ["green", "nir"]

    def build_process_graph(
        self,
        params: Dict[str, Any],
        input_node: str
    ) -> Dict[str, Any]:
        """Build NDWI process graph."""
        green_band = params.get("green_band", "green")
        nir_band = params.get("nir_band", "nir")
        use_swir = params.get("use_swir", False)
        swir_band = params.get("swir_band", "swir16")
        temporal_reducer = params.get("temporal_reducer", "median")
        threshold = params.get("threshold")

        # Determine which band to use for the infrared component
        ir_band = swir_band if use_swir else nir_band

        nodes = {}

        # Use normalized_difference process
        # NDWI = (Green - NIR) / (Green + NIR)
        nodes["ndwi1"] = {
            "process_id": "normalized_difference",
            "arguments": {
                "x": {"from_node": input_node},
                "y": {"from_node": input_node},
            }
        }

        # Actually, we need to extract bands first
        nodes["green"] = {
            "process_id": "array_element",
            "arguments": {
                "data": {"from_node": input_node},
                "label": green_band,
                "dimension": "bands"
            }
        }

        nodes["ir"] = {
            "process_id": "array_element",
            "arguments": {
                "data": {"from_node": input_node},
                "label": ir_band,
                "dimension": "bands"
            }
        }

        # NDWI = (Green - IR) / (Green + IR)
        nodes["green_minus_ir"] = {
            "process_id": "subtract",
            "arguments": {
                "x": {"from_node": "green"},
                "y": {"from_node": "ir"}
            }
        }

        nodes["green_plus_ir"] = {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "green"},
                "y": {"from_node": "ir"}
            }
        }

        nodes["ndwi"] = {
            "process_id": "divide",
            "arguments": {
                "x": {"from_node": "green_minus_ir"},
                "y": {"from_node": "green_plus_ir"}
            }
        }

        current_node = "ndwi"

        # Apply temporal reducer if specified
        if temporal_reducer and temporal_reducer != "none":
            nodes["reduce_time"] = {
                "process_id": "reduce_dimension",
                "arguments": {
                    "data": {"from_node": current_node},
                    "dimension": "time",
                    "reducer": {
                        "process_graph": {
                            "reducer1": {
                                "process_id": temporal_reducer,
                                "arguments": {
                                    "data": {"from_parameter": "data"}
                                },
                                "result": True
                            }
                        }
                    }
                }
            }
            current_node = "reduce_time"

        # Apply threshold if specified
        if threshold is not None:
            nodes["threshold"] = {
                "process_id": "gte",
                "arguments": {
                    "x": {"from_node": current_node},
                    "y": threshold
                }
            }
            current_node = "threshold"

        nodes[current_node]["result"] = True
        return nodes
