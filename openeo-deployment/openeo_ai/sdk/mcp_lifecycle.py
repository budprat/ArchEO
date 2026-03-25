# ABOUTME: MCP lifecycle monitoring and metrics.
# Provides hooks and tracking for tool execution lifecycle.

"""
MCP Lifecycle Monitoring.

Provides:
- Lifecycle hooks (tool_start, tool_end, tool_error, resource_access)
- Metrics tracking (total_calls, by_tool, errors, latency)
- Event logging
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class LifecycleEvent(Enum):
    """Types of lifecycle events."""
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"
    RESOURCE_ACCESS = "resource_access"
    CONNECTION_OPEN = "connection_open"
    CONNECTION_CLOSE = "connection_close"
    RATE_LIMIT = "rate_limit"


@dataclass
class ToolMetrics:
    """Metrics for a single tool."""
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    last_called: Optional[datetime] = None
    last_error: Optional[str] = None

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100

    def record_call(self, latency_ms: float, success: bool, error: str = None):
        """Record a tool call."""
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self.last_called = datetime.now()

        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
            self.last_error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.success_rate, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2) if self.min_latency_ms != float('inf') else None,
            "max_latency_ms": round(self.max_latency_ms, 2),
            "last_called": self.last_called.isoformat() if self.last_called else None,
            "last_error": self.last_error,
        }


@dataclass
class LifecycleEventData:
    """Data for a lifecycle event."""
    event_type: LifecycleEvent
    timestamp: datetime
    tool_name: Optional[str] = None
    resource_uri: Optional[str] = None
    latency_ms: Optional[float] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "resource_uri": self.resource_uri,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


# Type for lifecycle hooks
LifecycleHook = Callable[[LifecycleEventData], None]


class MCPLifecycleMonitor:
    """
    Monitor for MCP tool lifecycle.

    Usage:
        monitor = MCPLifecycleMonitor()

        # Register hooks
        monitor.on_tool_start(lambda e: print(f"Starting {e.tool_name}"))
        monitor.on_tool_end(lambda e: print(f"Finished {e.tool_name} in {e.latency_ms}ms"))

        # Track tool execution
        with monitor.track_tool("my_tool"):
            result = await execute_tool()

        # Get metrics
        metrics = monitor.get_metrics()
    """

    def __init__(self, max_events: int = 1000):
        """Initialize the monitor."""
        self._hooks: Dict[LifecycleEvent, List[LifecycleHook]] = defaultdict(list)
        self._metrics: Dict[str, ToolMetrics] = {}
        self._events: List[LifecycleEventData] = []
        self._max_events = max_events
        self._start_time = datetime.now()
        self._total_calls = 0
        self._total_errors = 0

    def on_tool_start(self, hook: LifecycleHook) -> None:
        """Register hook for tool start events."""
        self._hooks[LifecycleEvent.TOOL_START].append(hook)

    def on_tool_end(self, hook: LifecycleHook) -> None:
        """Register hook for tool end events."""
        self._hooks[LifecycleEvent.TOOL_END].append(hook)

    def on_tool_error(self, hook: LifecycleHook) -> None:
        """Register hook for tool error events."""
        self._hooks[LifecycleEvent.TOOL_ERROR].append(hook)

    def on_resource_access(self, hook: LifecycleHook) -> None:
        """Register hook for resource access events."""
        self._hooks[LifecycleEvent.RESOURCE_ACCESS].append(hook)

    def _emit_event(self, event: LifecycleEventData) -> None:
        """Emit a lifecycle event to hooks."""
        # Store event
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        # Call hooks
        for hook in self._hooks.get(event.event_type, []):
            try:
                hook(event)
            except Exception as e:
                logger.error(f"Lifecycle hook error: {e}")

    def track_tool_start(self, tool_name: str, metadata: Dict[str, Any] = None) -> float:
        """
        Record tool start.

        Args:
            tool_name: Name of the tool
            metadata: Optional metadata

        Returns:
            Start timestamp for measuring duration
        """
        self._total_calls += 1

        event = LifecycleEventData(
            event_type=LifecycleEvent.TOOL_START,
            timestamp=datetime.now(),
            tool_name=tool_name,
            metadata=metadata or {},
        )
        self._emit_event(event)

        return time.time() * 1000  # Return milliseconds

    def track_tool_end(
        self,
        tool_name: str,
        start_time: float,
        success: bool = True,
        error: str = None,
        metadata: Dict[str, Any] = None
    ) -> None:
        """
        Record tool completion.

        Args:
            tool_name: Name of the tool
            start_time: Start time from track_tool_start
            success: Whether execution succeeded
            error: Error message if failed
            metadata: Optional metadata
        """
        latency_ms = (time.time() * 1000) - start_time

        # Update metrics
        if tool_name not in self._metrics:
            self._metrics[tool_name] = ToolMetrics(name=tool_name)
        self._metrics[tool_name].record_call(latency_ms, success, error)

        if not success:
            self._total_errors += 1

        # Emit event
        event_type = LifecycleEvent.TOOL_END if success else LifecycleEvent.TOOL_ERROR
        event = LifecycleEventData(
            event_type=event_type,
            timestamp=datetime.now(),
            tool_name=tool_name,
            latency_ms=latency_ms,
            success=success,
            error=error,
            metadata=metadata or {},
        )
        self._emit_event(event)

    def track_resource_access(self, resource_uri: str, metadata: Dict[str, Any] = None) -> None:
        """Record resource access."""
        event = LifecycleEventData(
            event_type=LifecycleEvent.RESOURCE_ACCESS,
            timestamp=datetime.now(),
            resource_uri=resource_uri,
            metadata=metadata or {},
        )
        self._emit_event(event)

    class _ToolTracker:
        """Context manager for tracking tool execution."""

        def __init__(self, monitor: "MCPLifecycleMonitor", tool_name: str, metadata: Dict = None):
            self.monitor = monitor
            self.tool_name = tool_name
            self.metadata = metadata
            self.start_time = None

        def __enter__(self):
            self.start_time = self.monitor.track_tool_start(self.tool_name, self.metadata)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            success = exc_type is None
            error = str(exc_val) if exc_val else None
            self.monitor.track_tool_end(self.tool_name, self.start_time, success, error)
            return False  # Don't suppress exceptions

    def track_tool(self, tool_name: str, metadata: Dict[str, Any] = None):
        """
        Context manager for tracking tool execution.

        Usage:
            with monitor.track_tool("my_tool"):
                result = await execute()
        """
        return self._ToolTracker(self, tool_name, metadata)

    def get_tool_metrics(self, tool_name: str) -> Optional[ToolMetrics]:
        """Get metrics for a specific tool."""
        return self._metrics.get(tool_name)

    def get_all_metrics(self) -> Dict[str, ToolMetrics]:
        """Get metrics for all tools."""
        return dict(self._metrics)

    def get_recent_events(self, limit: int = 100) -> List[LifecycleEventData]:
        """Get recent events."""
        return self._events[-limit:]

    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary."""
        uptime = (datetime.now() - self._start_time).total_seconds()
        calls_per_minute = (self._total_calls / uptime * 60) if uptime > 0 else 0

        return {
            "uptime_seconds": round(uptime, 2),
            "total_calls": self._total_calls,
            "total_errors": self._total_errors,
            "error_rate": round((self._total_errors / self._total_calls * 100) if self._total_calls > 0 else 0, 2),
            "calls_per_minute": round(calls_per_minute, 2),
            "tools_tracked": len(self._metrics),
            "events_stored": len(self._events),
            "tools": {name: m.to_dict() for name, m in self._metrics.items()},
        }

    def reset(self) -> None:
        """Reset all metrics and events."""
        self._metrics.clear()
        self._events.clear()
        self._total_calls = 0
        self._total_errors = 0
        self._start_time = datetime.now()


# Module-level singleton
_monitor: Optional[MCPLifecycleMonitor] = None


def get_lifecycle_monitor() -> MCPLifecycleMonitor:
    """Get the global lifecycle monitor singleton."""
    global _monitor
    if _monitor is None:
        _monitor = MCPLifecycleMonitor()
    return _monitor


def wrap_tool_with_monitoring(
    tool_name: str,
    handler: Callable[[Dict[str, Any]], Any],
    monitor: Optional[MCPLifecycleMonitor] = None
) -> Callable[[Dict[str, Any]], Any]:
    """
    Wrap a tool handler with lifecycle monitoring.

    Args:
        tool_name: Name of the tool
        handler: Original handler function
        monitor: Optional monitor instance (uses global if not provided)

    Returns:
        Wrapped handler function
    """
    if monitor is None:
        monitor = get_lifecycle_monitor()

    async def wrapped_handler(args: Dict[str, Any]) -> Any:
        with monitor.track_tool(tool_name, {"args_keys": list(args.keys())}):
            if asyncio.iscoroutinefunction(handler):
                return await handler(args)
            else:
                return handler(args)

    return wrapped_handler
