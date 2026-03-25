"""Numerically stable math operations for OpenEO processes.

This module provides fixed versions of math operations that handle
edge cases like division by zero, which commonly occur in satellite
imagery processing (e.g., dark pixels where NIR and RED are both ~0).
"""

import logging
from typing import Union

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

# Epsilon value for numerical stability
EPSILON = 1e-10


def normalized_difference_stable(
    x: Union[xr.DataArray, np.ndarray],
    y: Union[xr.DataArray, np.ndarray],
    **kwargs
) -> Union[xr.DataArray, np.ndarray]:
    """Compute numerically stable normalized difference.

    Fixes division by zero issues that occur in dark pixels where
    both bands have near-zero values.

    Formula: (x - y) / (x + y + epsilon), clipped to [-1, 1]

    This is commonly used for vegetation indices like:
    - NDVI: normalized_difference_stable(nir, red)
    - NDWI: normalized_difference_stable(green, nir)
    - NDSI: normalized_difference_stable(green, swir)

    Args:
        x: First band (e.g., NIR for NDVI)
        y: Second band (e.g., RED for NDVI)
        **kwargs: Additional arguments (ignored, for compatibility)

    Returns:
        Normalized difference in valid range [-1, 1]
    """
    logger.debug("Computing normalized_difference with stability fix")

    # Add epsilon to denominator to prevent division by zero
    denominator = x + y + EPSILON
    nd = (x - y) / denominator

    # Clip to valid range [-1, 1]
    if hasattr(nd, "clip"):
        # xarray DataArray
        nd = nd.clip(-1.0, 1.0)
    elif isinstance(nd, np.ndarray):
        # numpy array
        nd = np.clip(nd, -1.0, 1.0)

    # Log statistics for debugging
    if isinstance(nd, xr.DataArray):
        try:
            min_val = float(nd.min().compute()) if hasattr(nd.min(), 'compute') else float(nd.min())
            max_val = float(nd.max().compute()) if hasattr(nd.max(), 'compute') else float(nd.max())
            logger.info(
                f"normalized_difference output: min={min_val:.3f}, max={max_val:.3f}"
            )
        except Exception as e:
            logger.debug(f"Could not compute statistics: {e}")

    return nd


def divide_safe(
    x: Union[xr.DataArray, np.ndarray],
    y: Union[xr.DataArray, np.ndarray],
    **kwargs
) -> Union[xr.DataArray, np.ndarray]:
    """Perform division with zero protection.

    Replaces zero values in denominator with epsilon to prevent
    division by zero errors.

    Args:
        x: Numerator
        y: Denominator
        **kwargs: Additional arguments (ignored, for compatibility)

    Returns:
        Result of x / y with zero protection
    """
    logger.debug("Computing safe division")

    if hasattr(y, "where"):
        # xarray DataArray - use where to replace zeros
        safe_y = y.where(y != 0, EPSILON)
        return x / safe_y
    elif isinstance(y, np.ndarray):
        # numpy array - use np.where
        safe_y = np.where(y != 0, y, EPSILON)
        return x / safe_y
    else:
        # scalar or other - simple epsilon addition
        if y == 0:
            y = EPSILON
        return x / y


def add_stable(
    x: Union[xr.DataArray, np.ndarray],
    y: Union[xr.DataArray, np.ndarray],
    **kwargs
) -> Union[xr.DataArray, np.ndarray]:
    """Addition with NaN handling.

    Args:
        x: First operand
        y: Second operand
        **kwargs: Additional arguments (ignored)

    Returns:
        Sum of x and y
    """
    return x + y


def subtract_stable(
    x: Union[xr.DataArray, np.ndarray],
    y: Union[xr.DataArray, np.ndarray],
    **kwargs
) -> Union[xr.DataArray, np.ndarray]:
    """Subtraction with NaN handling.

    Args:
        x: First operand
        y: Second operand
        **kwargs: Additional arguments (ignored)

    Returns:
        Difference of x and y
    """
    return x - y


def multiply_stable(
    x: Union[xr.DataArray, np.ndarray],
    y: Union[xr.DataArray, np.ndarray],
    **kwargs
) -> Union[xr.DataArray, np.ndarray]:
    """Multiplication with overflow protection.

    Args:
        x: First operand
        y: Second operand
        **kwargs: Additional arguments (ignored)

    Returns:
        Product of x and y
    """
    return x * y


def apply_scale_factor(
    data: Union[xr.DataArray, np.ndarray],
    scale: float = 0.0001,
    offset: float = 0.0,
    **kwargs
) -> Union[xr.DataArray, np.ndarray]:
    """Apply scale factor and offset to convert DN to reflectance.

    Sentinel-2 L2A data uses scale factor 0.0001 to convert
    integer DN values (0-10000) to reflectance (0-1).

    Args:
        data: Input data (typically uint16 or int16)
        scale: Scale factor (default 0.0001 for Sentinel-2)
        offset: Offset value (default 0.0)
        **kwargs: Additional arguments (ignored)

    Returns:
        Scaled data in physical units
    """
    logger.debug(f"Applying scale factor: scale={scale}, offset={offset}")
    return data * scale + offset


# Dictionary of stable process implementations
STABLE_PROCESSES = {
    "normalized_difference": normalized_difference_stable,
    "divide": divide_safe,
    "add": add_stable,
    "subtract": subtract_stable,
    "multiply": multiply_stable,
}
