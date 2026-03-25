# ABOUTME: GeoAI tools wrapping inference engine for Claude SDK integration.
# Provides segmentation, change detection, and canopy height tools.

"""
GeoAI tools for Claude SDK.

Provides tools for semantic segmentation, change detection,
and canopy height estimation using local models.
"""

import json
from typing import Any, Dict


def create_geoai_tools(config) -> Dict[str, Any]:
    """
    Create GeoAI tools dict for Claude SDK.

    Tools are registered following the Claude SDK tool format:
    - Each tool returns {"content": [{"type": "text|image|visualization", ...}]}
    """
    from ..geoai.inference import GeoAIInference

    # Lazy initialization - will be created on first use
    _engine = None

    def get_engine():
        nonlocal _engine
        if _engine is None:
            _engine = GeoAIInference(models_path=config.geoai_models_path)
        return _engine

    async def _segment(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run semantic segmentation on satellite imagery.

        Args:
            input_path: Path to input GeoTIFF
            model: Model name (default: "segmentation_default")
            output_path: Optional output path

        Returns:
            Claude SDK format response with segmentation results
        """
        engine = get_engine()

        result = await engine.segment(
            input_path=args["input_path"],
            model=args.get("model", "segmentation_default"),
            output_path=args.get("output_path")
        )

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result)
            }]
        }

    async def _detect_change(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect changes between two images.

        Args:
            before_path: Path to before image
            after_path: Path to after image
            model: Model name (default: "change_default")

        Returns:
            Claude SDK format response with change detection results
        """
        engine = get_engine()

        result = await engine.detect_change(
            before_path=args["before_path"],
            after_path=args["after_path"],
            model=args.get("model", "change_default")
        )

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result)
            }]
        }

    async def _estimate_canopy_height(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate canopy height from RGB imagery.

        Args:
            input_path: Path to input GeoTIFF

        Returns:
            Claude SDK format response with height estimates
        """
        engine = get_engine()

        result = await engine.estimate_canopy_height(
            input_path=args["input_path"]
        )

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result)
            }]
        }

    return {
        "geoai_segment": _segment,
        "geoai_detect_change": _detect_change,
        "geoai_estimate_canopy_height": _estimate_canopy_height,
    }


# Standalone tool functions for testing
async def segment_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone segment tool."""
    from ..geoai.inference import GeoAIInference

    engine = GeoAIInference(models_path="models/")
    result = await engine.segment(
        input_path=args["input_path"],
        model=args.get("model", "segmentation_default"),
        output_path=args.get("output_path")
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result)
        }]
    }


async def detect_change_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone change detection tool."""
    from ..geoai.inference import GeoAIInference

    engine = GeoAIInference(models_path="models/")
    result = await engine.detect_change(
        before_path=args["before_path"],
        after_path=args["after_path"],
        model=args.get("model", "change_default")
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result)
        }]
    }
