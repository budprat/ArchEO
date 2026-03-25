"""Custom exception hierarchy for OpenEO processing.

Provides specific exception types for better error handling and
user-friendly error messages.
"""


class ProcessingError(Exception):
    """Base class for all OpenEO processing errors.

    All custom exceptions inherit from this class, making it easy
    to catch any processing-related error.
    """

    def __init__(self, message: str, details: dict = None):
        """Initialize with message and optional details.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class DataSourceUnavailableError(ProcessingError):
    """Raised when STAC query returns no items.

    This typically happens when:
    - The spatial/temporal extent doesn't match any data
    - The collection doesn't have data for the requested area
    - Network issues prevent accessing the STAC catalog
    """

    def __init__(self, message: str, query: dict = None):
        super().__init__(message, details={"query": query} if query else None)
        self.query = query


class STACQueryError(ProcessingError):
    """Raised when STAC API query fails.

    This happens when:
    - The STAC catalog is unreachable
    - The collection ID doesn't exist
    - Invalid query parameters are provided
    """

    def __init__(self, message: str, catalog_url: str = None, collection_id: str = None):
        details = {}
        if catalog_url:
            details["catalog_url"] = catalog_url
        if collection_id:
            details["collection_id"] = collection_id
        super().__init__(message, details=details)
        self.catalog_url = catalog_url
        self.collection_id = collection_id


class BandSelectionError(ProcessingError):
    """Raised when requested bands are not found in the collection.

    This happens when:
    - Band names don't match the collection's band names
    - Band mapping fails (e.g., wrong band name format)
    - The collection doesn't have the requested bands
    """

    def __init__(self, message: str, requested_bands: list = None, available_bands: list = None):
        details = {}
        if requested_bands:
            details["requested_bands"] = requested_bands
        if available_bands:
            details["available_bands"] = available_bands
        super().__init__(message, details=details)
        self.requested_bands = requested_bands
        self.available_bands = available_bands


class ExtentValidationError(ProcessingError):
    """Raised when spatial or temporal extent is invalid.

    This happens when:
    - Spatial extent is too large (global queries)
    - Temporal extent is too long (>1 year)
    - Invalid coordinate values
    """

    def __init__(self, message: str, extent_type: str = None, provided_extent: dict = None):
        details = {}
        if extent_type:
            details["extent_type"] = extent_type
        if provided_extent:
            details["provided_extent"] = provided_extent
        super().__init__(message, details=details)
        self.extent_type = extent_type
        self.provided_extent = provided_extent


class JobExecutionError(ProcessingError):
    """Raised when job execution fails.

    This is a general error for job processing failures that
    don't fit into more specific categories.
    """

    def __init__(self, message: str, job_id: str = None, process_id: str = None):
        details = {}
        if job_id:
            details["job_id"] = job_id
        if process_id:
            details["process_id"] = process_id
        super().__init__(message, details=details)
        self.job_id = job_id
        self.process_id = process_id


class DimensionError(ProcessingError):
    """Raised when dimension operations fail.

    This happens when:
    - Trying to reduce a dimension that doesn't exist
    - Dimension mismatch in merge operations
    - Invalid dimension labels
    """

    def __init__(self, message: str, dimension: str = None, available_dims: list = None):
        details = {}
        if dimension:
            details["dimension"] = dimension
        if available_dims:
            details["available_dimensions"] = available_dims
        super().__init__(message, details=details)
        self.dimension = dimension
        self.available_dims = available_dims


class OutputFormatError(ProcessingError):
    """Raised when result cannot be saved in the requested format.

    This happens when:
    - Unsupported output format requested
    - Data incompatible with format (e.g., 4D data to GeoTIFF)
    - Missing CRS for geospatial formats
    """

    def __init__(self, message: str, format: str = None, reason: str = None):
        details = {}
        if format:
            details["format"] = format
        if reason:
            details["reason"] = reason
        super().__init__(message, details=details)
        self.format = format
        self.reason = reason


# Error classification for user-friendly messages
ERROR_CLASSIFICATIONS = {
    DataSourceUnavailableError: {
        "user_message": "No data found for the specified area and time range. "
                       "Try expanding the spatial or temporal extent.",
        "http_status": 404,
    },
    STACQueryError: {
        "user_message": "Failed to query the data catalog. "
                       "Please check the collection ID and try again.",
        "http_status": 502,
    },
    BandSelectionError: {
        "user_message": "The requested bands are not available in this collection. "
                       "Check the collection metadata for available bands.",
        "http_status": 400,
    },
    ExtentValidationError: {
        "user_message": "The spatial or temporal extent is invalid or too large. "
                       "Try using a smaller area or shorter time range.",
        "http_status": 400,
    },
    JobExecutionError: {
        "user_message": "Job execution failed. Please check the logs for details.",
        "http_status": 500,
    },
}


def classify_error(error: Exception) -> dict:
    """Classify an error and return user-friendly information.

    Args:
        error: The exception to classify

    Returns:
        Dictionary with user_message, http_status, and error details
    """
    error_class = type(error)

    if error_class in ERROR_CLASSIFICATIONS:
        classification = ERROR_CLASSIFICATIONS[error_class]
        return {
            "user_message": classification["user_message"],
            "http_status": classification["http_status"],
            "error_type": error_class.__name__,
            "technical_message": str(error),
            "details": error.details if hasattr(error, "details") else {},
        }

    # Default for unknown errors
    return {
        "user_message": "An unexpected error occurred. Please try again.",
        "http_status": 500,
        "error_type": error_class.__name__,
        "technical_message": str(error),
        "details": {},
    }
