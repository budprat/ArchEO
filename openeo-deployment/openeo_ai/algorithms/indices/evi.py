# ABOUTME: EVI (Enhanced Vegetation Index) algorithm.
# Calculates vegetation index with atmospheric correction.

"""
EVI Algorithm Implementation.

EVI = G * ((NIR - Red) / (NIR + C1 * Red - C2 * Blue + L))

Where:
- G = 2.5 (gain factor)
- C1 = 6 (coefficient for aerosol resistance)
- C2 = 7.5 (coefficient for aerosol resistance)
- L = 1 (canopy background adjustment)

EVI improves on NDVI by:
- Reducing atmospheric effects
- Reducing saturation in dense vegetation
- Accounting for canopy background
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
class EVIAlgorithm(BaseAlgorithm):
    """
    EVI (Enhanced Vegetation Index) calculation.

    Improves on NDVI with atmospheric correction and reduced saturation.
    """

    @property
    def metadata(self) -> AlgorithmMetadata:
        return AlgorithmMetadata(
            id="evi",
            name="EVI - Enhanced Vegetation Index",
            description=(
                "Calculates the Enhanced Vegetation Index (EVI), which improves "
                "upon NDVI by reducing atmospheric influences and correcting for "
                "canopy background. EVI is particularly useful in areas of dense "
                "vegetation where NDVI tends to saturate. Values typically range "
                "from -1 to 1."
            ),
            category="index",
            version="1.0.0",
            tags=["vegetation", "evi", "index", "atmospheric-correction", "dense-vegetation"],
            references=[
                "Huete et al., 2002. Overview of the radiometric and biophysical "
                "performance of the MODIS vegetation indices.",
            ],
            requires_bands=["blue", "red", "nir"],
            output_type="raster",
        )

    @property
    def parameters(self) -> List[AlgorithmParameter]:
        return [
            AlgorithmParameter(
                name="blue_band",
                param_type=ParameterType.BAND,
                description="Name of the blue band",
                required=False,
                default="blue",
            ),
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
                name="gain",
                param_type=ParameterType.NUMBER,
                description="Gain factor (G)",
                required=False,
                default=2.5,
                min_value=0.1,
                max_value=10.0,
            ),
            AlgorithmParameter(
                name="c1",
                param_type=ParameterType.NUMBER,
                description="Coefficient C1 for aerosol resistance",
                required=False,
                default=6.0,
            ),
            AlgorithmParameter(
                name="c2",
                param_type=ParameterType.NUMBER,
                description="Coefficient C2 for aerosol resistance",
                required=False,
                default=7.5,
            ),
            AlgorithmParameter(
                name="l",
                param_type=ParameterType.NUMBER,
                description="Canopy background adjustment (L)",
                required=False,
                default=1.0,
            ),
            AlgorithmParameter(
                name="temporal_reducer",
                param_type=ParameterType.STRING,
                description="Temporal aggregation method",
                required=False,
                default="median",
                choices=["none", "mean", "median", "max", "min"],
            ),
        ]

    def build_process_graph(
        self,
        params: Dict[str, Any],
        input_node: str
    ) -> Dict[str, Any]:
        """Build EVI process graph."""
        blue_band = params.get("blue_band", "blue")
        red_band = params.get("red_band", "red")
        nir_band = params.get("nir_band", "nir")
        gain = params.get("gain", 2.5)
        c1 = params.get("c1", 6.0)
        c2 = params.get("c2", 7.5)
        l_value = params.get("l", 1.0)
        temporal_reducer = params.get("temporal_reducer", "median")

        nodes = {}

        # Extract bands
        nodes["nir"] = {
            "process_id": "array_element",
            "arguments": {
                "data": {"from_node": input_node},
                "label": nir_band,
                "dimension": "bands"
            }
        }

        nodes["red"] = {
            "process_id": "array_element",
            "arguments": {
                "data": {"from_node": input_node},
                "label": red_band,
                "dimension": "bands"
            }
        }

        nodes["blue"] = {
            "process_id": "array_element",
            "arguments": {
                "data": {"from_node": input_node},
                "label": blue_band,
                "dimension": "bands"
            }
        }

        # EVI = G * ((NIR - Red) / (NIR + C1*Red - C2*Blue + L))

        # Numerator: NIR - Red
        nodes["nir_minus_red"] = {
            "process_id": "subtract",
            "arguments": {
                "x": {"from_node": "nir"},
                "y": {"from_node": "red"}
            }
        }

        # Denominator parts: C1 * Red
        nodes["c1_red"] = {
            "process_id": "multiply",
            "arguments": {
                "x": {"from_node": "red"},
                "y": c1
            }
        }

        # C2 * Blue
        nodes["c2_blue"] = {
            "process_id": "multiply",
            "arguments": {
                "x": {"from_node": "blue"},
                "y": c2
            }
        }

        # NIR + C1*Red
        nodes["nir_plus_c1red"] = {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "nir"},
                "y": {"from_node": "c1_red"}
            }
        }

        # (NIR + C1*Red) - C2*Blue
        nodes["sub_c2blue"] = {
            "process_id": "subtract",
            "arguments": {
                "x": {"from_node": "nir_plus_c1red"},
                "y": {"from_node": "c2_blue"}
            }
        }

        # Denominator: add L
        nodes["denominator"] = {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "sub_c2blue"},
                "y": l_value
            }
        }

        # Division
        nodes["fraction"] = {
            "process_id": "divide",
            "arguments": {
                "x": {"from_node": "nir_minus_red"},
                "y": {"from_node": "denominator"}
            }
        }

        # Multiply by gain
        nodes["evi"] = {
            "process_id": "multiply",
            "arguments": {
                "x": {"from_node": "fraction"},
                "y": gain
            }
        }

        current_node = "evi"

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

        nodes[current_node]["result"] = True
        return nodes
