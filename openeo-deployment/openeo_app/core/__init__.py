"""Core utilities and base classes for OpenEO FastAPI."""

from .exceptions import (
    ProcessingError,
    DataSourceUnavailableError,
    STACQueryError,
    BandSelectionError,
    ExtentValidationError,
    JobExecutionError,
)

__all__ = [
    "ProcessingError",
    "DataSourceUnavailableError",
    "STACQueryError",
    "BandSelectionError",
    "ExtentValidationError",
    "JobExecutionError",
]
