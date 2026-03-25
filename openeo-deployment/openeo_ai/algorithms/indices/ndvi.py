# ABOUTME: NDVI (Normalized Difference Vegetation Index) algorithm.
# Calculates vegetation health index from red and NIR bands.

"""
NDVI Algorithm Implementation.

NDVI = (NIR - Red) / (NIR + Red)

Values range from -1 to 1:
- < 0: Water, snow, clouds
- 0-0.1: Bare soil
- 0.2-0.4: Sparse vegetation
- 0.4-0.6: Moderate vegetation
- 0.6-1.0: Dense vegetation
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
class NDVIAlgorithm(BaseAlgorithm):
    """
    NDVI (Normalized Difference Vegetation Index) calculation.

    Calculates vegetation health from red and NIR bands.
    Optionally applies temporal aggregation and scaling.
    """

    @property
    def metadata(self) -> AlgorithmMetadata:
        return AlgorithmMetadata(
            id="ndvi",
            name="NDVI - Normalized Difference Vegetation Index",
            description=(
                "Calculates the Normalized Difference Vegetation Index (NDVI) "
                "from satellite imagery. NDVI is the most widely used vegetation "
                "index for monitoring plant health, biomass, and phenology. "
                "Values range from -1 to 1, with higher values indicating denser vegetation."
            ),
            category="index",
            version="1.0.0",
            tags=["vegetation", "ndvi", "index", "phenology", "agriculture"],
            references=[
                "Rouse et al., 1974. Monitoring vegetation systems in the Great Plains.",
                "Tucker, C. J., 1979. Red and photographic infrared linear combinations."
            ],
            requires_bands=["red", "nir"],
            output_type="raster",
        )

    @property
    def parameters(self) -> List[AlgorithmParameter]:
        return [
            AlgorithmParameter(
                name="red_band",
                param_type=ParameterType.BAND,
                description="Name of the red band",
                required=False,
                default="red",
            ),
            AlgorithmParameter(
                name="nir_band",
                param_type=ParameterType.BAND,
                description="Name of the NIR band",
                required=False,
                default="nir",
            ),
            AlgorithmParameter(
                name="temporal_reducer",
                param_type=ParameterType.STRING,
                description="Temporal aggregation method (none, mean, median, max, min)",
                required=False,
                default="median",
                choices=["none", "mean", "median", "max", "min"],
            ),
            AlgorithmParameter(
                name="scale_output",
                param_type=ParameterType.BOOLEAN,
                description="Scale output to 0-255 for visualization",
                required=False,
                default=False,
            ),
        ]

    def build_process_graph(
        self,
        params: Dict[str, Any],
        input_node: str
    ) -> Dict[str, Any]:
        """Build NDVI process graph."""
        red_band = params.get("red_band", "red")
        nir_band = params.get("nir_band", "nir")
        temporal_reducer = params.get("temporal_reducer", "median")
        scale_output = params.get("scale_output", False)

        nodes = {}

        # Use built-in NDVI process
        nodes["ndvi1"] = {
            "process_id": "ndvi",
            "arguments": {
                "data": {"from_node": input_node},
                "nir": nir_band,
                "red": red_band,
            }
        }

        current_node = "ndvi1"

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

        # Scale output if requested
        if scale_output:
            nodes["scale1"] = {
                "process_id": "linear_scale_range",
                "arguments": {
                    "x": {"from_node": current_node},
                    "inputMin": -1,
                    "inputMax": 1,
                    "outputMin": 0,
                    "outputMax": 255,
                }
            }
            current_node = "scale1"

        # Mark the last node as result
        nodes[current_node]["result"] = True

        return nodes
