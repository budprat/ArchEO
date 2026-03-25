# ABOUTME: Enhanced error handler with classification, recovery suggestions, and human oversight.
# Provides structured error handling for tool execution with actionable feedback.

"""
Enhanced error handler for OpenEO AI Assistant.

Provides:
- Error classification by type (validation, permission, execution, data_quality, network)
- Recovery suggestions based on error type and context
- Human oversight prompts for risky operations
- Integration with tool execution pipeline
"""

import logging
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of error types."""
    VALIDATION = "validation"
    PERMISSION = "permission"
    EXECUTION = "execution"
    DATA_QUALITY = "data_quality"
    NETWORK = "network"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class Severity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class RecoverySuggestion:
    """A suggestion for recovering from an error."""
    action: str
    description: str
    auto_recoverable: bool = False
    code_example: Optional[str] = None


@dataclass
class ErrorContext:
    """Context information about where an error occurred."""
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    operation: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class HandledError:
    """Structured error response with classification and recovery options."""
    error_type: ErrorType
    severity: Severity
    message: str
    original_exception: Optional[Exception] = None
    suggestions: List[RecoverySuggestion] = field(default_factory=list)
    context: Optional[ErrorContext] = None
    requires_human_oversight: bool = False
    oversight_reason: Optional[str] = None
    stack_trace: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_type": self.error_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "suggestions": [
                {
                    "action": s.action,
                    "description": s.description,
                    "auto_recoverable": s.auto_recoverable,
                    "code_example": s.code_example
                }
                for s in self.suggestions
            ],
            "context": {
                "tool_name": self.context.tool_name if self.context else None,
                "operation": self.context.operation if self.context else None,
            } if self.context else None,
            "requires_human_oversight": self.requires_human_oversight,
            "oversight_reason": self.oversight_reason,
        }

    def to_user_message(self) -> str:
        """Format as user-friendly message."""
        parts = [f"**{self.error_type.value.title()} Error**: {self.message}"]

        if self.suggestions:
            parts.append("\n**Suggestions:**")
            for i, s in enumerate(self.suggestions, 1):
                parts.append(f"{i}. {s.action}: {s.description}")
                if s.code_example:
                    parts.append(f"   ```\n   {s.code_example}\n   ```")

        if self.requires_human_oversight:
            parts.append(f"\n⚠️ **Human Review Required**: {self.oversight_reason}")

        return "\n".join(parts)


# Error pattern matchers for classification
ERROR_PATTERNS = {
    ErrorType.VALIDATION: [
        "missing required",
        "invalid argument",
        "validation failed",
        "invalid format",
        "type error",
        "not a valid",
        "expected",
        "must be",
        "schema",
        "process_id",
        "band",
    ],
    ErrorType.PERMISSION: [
        "permission denied",
        "access denied",
        "unauthorized",
        "forbidden",
        "not allowed",
        "authentication",
        "credentials",
    ],
    ErrorType.NETWORK: [
        "connection",
        "timeout",
        "unreachable",
        "network",
        "dns",
        "ssl",
        "certificate",
        "socket",
        "refused",
        "reset",
    ],
    ErrorType.DATA_QUALITY: [
        "no data",
        "empty",
        "cloud cover",
        "quality",
        "no items",
        "not found",
        "missing data",
        "nodata",
        "nan",
    ],
    ErrorType.RESOURCE: [
        "memory",
        "disk",
        "quota",
        "limit",
        "exceeded",
        "too large",
        "out of",
        "insufficient",
    ],
    ErrorType.TIMEOUT: [
        "timed out",
        "deadline",
        "took too long",
    ],
}


# Recovery suggestions by error type
RECOVERY_SUGGESTIONS = {
    ErrorType.VALIDATION: [
        RecoverySuggestion(
            action="Validate input",
            description="Use openeo_validate_graph to check process graph structure",
            auto_recoverable=True
        ),
        RecoverySuggestion(
            action="Check band names",
            description="Use AWS Earth Search band names (red, nir, blue) instead of B04, B08",
            code_example='bands=["red", "nir", "blue"]'
        ),
        RecoverySuggestion(
            action="Check collection ID",
            description="Use openeo_list_collections to see available collections"
        ),
    ],
    ErrorType.DATA_QUALITY: [
        RecoverySuggestion(
            action="Expand temporal range",
            description="Increase date range to find more cloud-free observations",
            auto_recoverable=True
        ),
        RecoverySuggestion(
            action="Add cloud masking",
            description="Use SCL band to mask cloudy pixels before processing"
        ),
        RecoverySuggestion(
            action="Use temporal composite",
            description="Apply reduce_dimension over time with median reducer"
        ),
    ],
    ErrorType.NETWORK: [
        RecoverySuggestion(
            action="Retry request",
            description="Network errors are often temporary; retry after a short delay",
            auto_recoverable=True
        ),
        RecoverySuggestion(
            action="Check STAC API",
            description="Verify STAC catalog is accessible at configured URL"
        ),
    ],
    ErrorType.RESOURCE: [
        RecoverySuggestion(
            action="Reduce extent",
            description="Use smaller spatial extent (< 1° x 1° recommended)",
            auto_recoverable=True
        ),
        RecoverySuggestion(
            action="Reduce bands",
            description="Request fewer bands to reduce data volume"
        ),
        RecoverySuggestion(
            action="Shorten time range",
            description="Use shorter temporal extent"
        ),
    ],
    ErrorType.TIMEOUT: [
        RecoverySuggestion(
            action="Use batch job",
            description="Convert to batch processing for large requests"
        ),
        RecoverySuggestion(
            action="Reduce extent",
            description="Process smaller area for faster results",
            auto_recoverable=True
        ),
    ],
    ErrorType.PERMISSION: [
        RecoverySuggestion(
            action="Check authentication",
            description="Verify OIDC credentials are valid"
        ),
        RecoverySuggestion(
            action="Check tool permissions",
            description="Some tools require elevated permissions"
        ),
    ],
}


# Operations that require human oversight
RISKY_OPERATIONS = {
    "openeo_start_job": {
        "reason": "Starting a batch job consumes compute resources",
        "threshold": {"extent_degrees": 2.0, "temporal_days": 365}
    },
    "geoai_segment": {
        "reason": "AI inference on large images can be resource-intensive",
        "threshold": {"file_size_mb": 500}
    },
    "geoai_detect_change": {
        "reason": "Change detection requires processing two large images",
        "threshold": {"file_size_mb": 500}
    },
}


class ErrorHandler:
    """
    Enhanced error handler with classification, recovery, and oversight.

    Usage:
        handler = ErrorHandler()

        # Classify an exception
        handled = handler.handle_exception(e, context)

        # Check if operation requires oversight
        needs_oversight = handler.requires_oversight("openeo_start_job", tool_input)

        # Wrap a tool function
        @handler.wrap_tool("my_tool")
        async def my_tool(args):
            ...
    """

    def __init__(self, custom_patterns: Optional[Dict[ErrorType, List[str]]] = None):
        """Initialize with optional custom error patterns."""
        self.patterns = {**ERROR_PATTERNS}
        if custom_patterns:
            for error_type, patterns in custom_patterns.items():
                self.patterns.setdefault(error_type, []).extend(patterns)

    def classify_error(self, error: Exception) -> ErrorType:
        """Classify an exception by type."""
        error_str = str(error).lower()
        error_class = type(error).__name__.lower()

        # Check exception type first
        if "validation" in error_class or "schema" in error_class:
            return ErrorType.VALIDATION
        if "permission" in error_class or "auth" in error_class:
            return ErrorType.PERMISSION
        if "connection" in error_class or "network" in error_class:
            return ErrorType.NETWORK
        if "timeout" in error_class:
            return ErrorType.TIMEOUT
        if "memory" in error_class or "resource" in error_class:
            return ErrorType.RESOURCE

        # Check error message patterns
        for error_type, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern in error_str:
                    return error_type

        return ErrorType.UNKNOWN

    def get_severity(self, error_type: ErrorType, exception: Optional[Exception] = None) -> Severity:
        """Determine severity based on error type and context."""
        if error_type in (ErrorType.VALIDATION, ErrorType.DATA_QUALITY):
            return Severity.WARNING
        if error_type in (ErrorType.NETWORK, ErrorType.TIMEOUT):
            return Severity.ERROR
        if error_type in (ErrorType.PERMISSION, ErrorType.RESOURCE):
            return Severity.CRITICAL
        return Severity.ERROR

    def get_suggestions(self, error_type: ErrorType, context: Optional[ErrorContext] = None) -> List[RecoverySuggestion]:
        """Get recovery suggestions for error type."""
        base_suggestions = RECOVERY_SUGGESTIONS.get(error_type, [])

        # Add context-specific suggestions
        if context and context.tool_name:
            if context.tool_name == "openeo_generate_graph":
                base_suggestions = [
                    RecoverySuggestion(
                        action="Use openeo_validate_graph first",
                        description="Validate the generated graph before execution",
                        auto_recoverable=True
                    )
                ] + base_suggestions
            elif context.tool_name in ("viz_show_map", "viz_show_time_series"):
                base_suggestions = [
                    RecoverySuggestion(
                        action="Check file path",
                        description="Ensure the result file exists at the expected path"
                    )
                ] + base_suggestions

        return base_suggestions[:5]  # Limit to top 5 suggestions

    def requires_oversight(self, tool_name: str, tool_input: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Check if an operation requires human oversight."""
        if tool_name not in RISKY_OPERATIONS:
            return False, None

        config = RISKY_OPERATIONS[tool_name]
        threshold = config.get("threshold", {})

        # Check spatial extent
        spatial = tool_input.get("spatial_extent", {})
        if spatial:
            width = abs(spatial.get("east", 0) - spatial.get("west", 0))
            height = abs(spatial.get("north", 0) - spatial.get("south", 0))
            max_extent = max(width, height)
            if max_extent > threshold.get("extent_degrees", float("inf")):
                return True, f"{config['reason']} (extent {max_extent:.1f}° exceeds {threshold['extent_degrees']}°)"

        # Check temporal extent
        temporal = tool_input.get("temporal_extent", [])
        if len(temporal) >= 2 and temporal[0] and temporal[1]:
            from datetime import datetime
            try:
                start = datetime.fromisoformat(str(temporal[0]).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(temporal[1]).replace("Z", "+00:00"))
                days = (end - start).days
                if days > threshold.get("temporal_days", float("inf")):
                    return True, f"{config['reason']} (range {days} days exceeds {threshold['temporal_days']} days)"
            except ValueError:
                pass

        return False, None

    def handle_exception(
        self,
        exception: Exception,
        context: Optional[ErrorContext] = None,
        include_stack_trace: bool = False
    ) -> HandledError:
        """
        Handle an exception and return structured error response.

        Args:
            exception: The exception that occurred
            context: Optional context about where the error occurred
            include_stack_trace: Whether to include full stack trace

        Returns:
            HandledError with classification, suggestions, and user message
        """
        error_type = self.classify_error(exception)
        severity = self.get_severity(error_type, exception)
        suggestions = self.get_suggestions(error_type, context)

        # Check if operation would have required oversight
        requires_oversight = False
        oversight_reason = None
        if context and context.tool_name and context.tool_input:
            requires_oversight, oversight_reason = self.requires_oversight(
                context.tool_name, context.tool_input
            )

        stack_trace = None
        if include_stack_trace:
            stack_trace = traceback.format_exc()

        handled = HandledError(
            error_type=error_type,
            severity=severity,
            message=str(exception),
            original_exception=exception,
            suggestions=suggestions,
            context=context,
            requires_human_oversight=requires_oversight,
            oversight_reason=oversight_reason,
            stack_trace=stack_trace,
        )

        # Log the error
        log_msg = f"[{error_type.value}] {exception}"
        if context:
            log_msg = f"[{context.tool_name or 'unknown'}] {log_msg}"

        if severity == Severity.CRITICAL:
            logger.critical(log_msg)
        elif severity == Severity.ERROR:
            logger.error(log_msg)
        elif severity == Severity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return handled

    def wrap_tool(self, tool_name: str):
        """
        Decorator to wrap a tool function with error handling.

        Usage:
            @handler.wrap_tool("my_tool")
            async def my_tool(args):
                ...
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(tool_input: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
                # Check oversight requirement before execution
                needs_oversight, reason = self.requires_oversight(tool_name, tool_input)
                if needs_oversight:
                    return {
                        "requires_oversight": True,
                        "reason": reason,
                        "tool_name": tool_name,
                        "action_required": "User must confirm to proceed with this operation"
                    }

                context = ErrorContext(
                    tool_name=tool_name,
                    tool_input=tool_input
                )

                try:
                    return await func(tool_input, *args, **kwargs)
                except Exception as e:
                    handled = self.handle_exception(e, context)
                    return {
                        "error": handled.to_dict(),
                        "user_message": handled.to_user_message()
                    }

            return wrapper
        return decorator


# Module-level singleton for convenience
_default_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get the default error handler singleton."""
    global _default_handler
    if _default_handler is None:
        _default_handler = ErrorHandler()
    return _default_handler


def handle_error(
    exception: Exception,
    tool_name: Optional[str] = None,
    tool_input: Optional[Dict[str, Any]] = None,
    operation: Optional[str] = None
) -> HandledError:
    """
    Convenience function to handle an error with the default handler.

    Args:
        exception: The exception that occurred
        tool_name: Name of the tool where error occurred
        tool_input: Input that was passed to the tool
        operation: Description of the operation being performed

    Returns:
        HandledError with classification and recovery suggestions
    """
    handler = get_error_handler()
    context = ErrorContext(
        tool_name=tool_name,
        tool_input=tool_input,
        operation=operation
    )
    return handler.handle_exception(exception, context)


def check_oversight(tool_name: str, tool_input: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Check if an operation requires human oversight.

    Args:
        tool_name: Name of the tool
        tool_input: Input to be passed to the tool

    Returns:
        Tuple of (requires_oversight, reason)
    """
    handler = get_error_handler()
    return handler.requires_oversight(tool_name, tool_input)
