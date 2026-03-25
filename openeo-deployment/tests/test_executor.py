"""Tests for openeo_app/execution/executor.py.

Verifies process registry building, simple math graph execution, and
chained operations. External data loading is mocked to avoid network access.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from openeo_ai.utils.extent_validator import ExtentValidator


# ---------------------------------------------------------------------------
# Process discovery and registry building
# ---------------------------------------------------------------------------


class TestProcessDiscovery:
    """Tests for process discovery and registry building."""

    def test_import_processes_returns_dict(self):
        """_import_processes should return a dict of process_id -> callable."""
        from openeo_app.execution.executor import _import_processes

        process_map = _import_processes()

        assert isinstance(process_map, dict)
        assert len(process_map) > 0

    def test_import_processes_has_basic_math(self):
        """Basic math processes should always be available."""
        from openeo_app.execution.executor import _import_processes

        process_map = _import_processes()

        for name in ["add", "subtract", "multiply", "divide"]:
            assert name in process_map, f"Missing basic math process: {name}"

    def test_import_processes_has_save_result(self):
        """save_result should always be available (fallback exists)."""
        from openeo_app.execution.executor import _import_processes

        process_map = _import_processes()
        assert "save_result" in process_map

    def test_import_processes_has_load_collection(self):
        """load_collection should be available (custom override)."""
        from openeo_app.execution.executor import _import_processes

        process_map = _import_processes()
        assert "load_collection" in process_map

    def test_reserved_words_mapped(self):
        """Python reserved words should be mapped (min, max, sum, etc.)."""
        from openeo_app.execution.executor import _import_processes

        process_map = _import_processes()

        for name in ["min", "max", "sum", "and", "or", "not"]:
            assert name in process_map, f"Missing reserved word mapping: {name}"
        # Underscore versions should NOT remain
        for name in ["_min", "_max", "_sum", "_and", "_or", "_not"]:
            assert name not in process_map, f"Internal name should be removed: {name}"

    def test_process_count_minimum(self):
        """At least 100 processes should be discovered."""
        from openeo_app.execution.executor import _import_processes

        process_map = _import_processes()
        assert len(process_map) >= 100, (
            f"Expected 100+ processes, found {len(process_map)}"
        )

    def test_skip_modules_excluded(self):
        """Experimental and ML modules should be excluded."""
        from openeo_app.execution.executor import _import_processes

        process_map = _import_processes()

        # These would only be present if experimental modules loaded
        # (they require Linux-only dependencies)
        # We just check the skip logic didn't crash
        assert isinstance(process_map, dict)


# ---------------------------------------------------------------------------
# ProcessGraphExecutor initialization
# ---------------------------------------------------------------------------


class TestProcessGraphExecutorInit:
    """Tests for ProcessGraphExecutor initialization."""

    def test_executor_initializes(self):
        """ProcessGraphExecutor should initialize without errors."""
        from openeo_app.execution.executor import ProcessGraphExecutor

        executor = ProcessGraphExecutor(
            stac_api_url="https://earth-search.aws.element84.com/v1/"
        )

        assert executor.stac_api_url == "https://earth-search.aws.element84.com/v1/"
        assert len(executor._process_registry) > 0

    def test_get_available_processes(self):
        """get_available_processes should return a list of strings."""
        from openeo_app.execution.executor import ProcessGraphExecutor

        executor = ProcessGraphExecutor(
            stac_api_url="https://example.com"
        )

        procs = executor.get_available_processes()
        assert isinstance(procs, list)
        assert len(procs) > 100
        assert "add" in procs

    def test_has_process(self):
        """has_process should correctly check for process existence."""
        from openeo_app.execution.executor import ProcessGraphExecutor

        executor = ProcessGraphExecutor(stac_api_url="https://example.com")

        assert executor.has_process("add") is True
        assert executor.has_process("nonexistent_process_xyz") is False


# ---------------------------------------------------------------------------
# Simple math graph execution
# ---------------------------------------------------------------------------


class TestSimpleMathExecution:
    """Tests for executing simple math process graphs."""

    @pytest.fixture
    def executor(self):
        """Create a ProcessGraphExecutor."""
        from openeo_app.execution.executor import ProcessGraphExecutor

        return ProcessGraphExecutor(stac_api_url="https://example.com")

    def test_add(self, executor):
        """Execute add(3, 5) = 8."""
        graph = {
            "add1": {
                "process_id": "add",
                "arguments": {"x": 3, "y": 5},
                "result": True,
            }
        }
        result = executor.execute(graph)
        assert result == 8

    def test_subtract(self, executor):
        """Execute subtract(10, 3) = 7."""
        graph = {
            "sub1": {
                "process_id": "subtract",
                "arguments": {"x": 10, "y": 3},
                "result": True,
            }
        }
        result = executor.execute(graph)
        assert result == 7

    def test_multiply(self, executor):
        """Execute multiply(4, 7) = 28."""
        graph = {
            "mul1": {
                "process_id": "multiply",
                "arguments": {"x": 4, "y": 7},
                "result": True,
            }
        }
        result = executor.execute(graph)
        assert result == 28

    def test_divide(self, executor):
        """Execute divide(20, 4) = 5."""
        graph = {
            "div1": {
                "process_id": "divide",
                "arguments": {"x": 20, "y": 4},
                "result": True,
            }
        }
        result = executor.execute(graph)
        assert result == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Chained operations
# ---------------------------------------------------------------------------


class TestChainedOperations:
    """Tests for graphs with multiple chained operations."""

    @pytest.fixture
    def executor(self):
        """Create a ProcessGraphExecutor."""
        from openeo_app.execution.executor import ProcessGraphExecutor

        return ProcessGraphExecutor(stac_api_url="https://example.com")

    def test_add_then_multiply(self, executor):
        """Execute (3 + 5) * 2 = 16."""
        graph = {
            "add1": {
                "process_id": "add",
                "arguments": {"x": 3, "y": 5},
            },
            "mul1": {
                "process_id": "multiply",
                "arguments": {
                    "x": {"from_node": "add1"},
                    "y": 2,
                },
                "result": True,
            },
        }
        result = executor.execute(graph)
        assert result == 16

    def test_subtract_then_divide(self, executor):
        """Execute (20 - 10) / 2 = 5."""
        graph = {
            "sub1": {
                "process_id": "subtract",
                "arguments": {"x": 20, "y": 10},
            },
            "div1": {
                "process_id": "divide",
                "arguments": {
                    "x": {"from_node": "sub1"},
                    "y": 2,
                },
                "result": True,
            },
        }
        result = executor.execute(graph)
        assert result == pytest.approx(5.0)

    def test_three_step_chain(self, executor):
        """Execute ((2 + 3) * 4) - 10 = 10."""
        graph = {
            "add1": {
                "process_id": "add",
                "arguments": {"x": 2, "y": 3},
            },
            "mul1": {
                "process_id": "multiply",
                "arguments": {
                    "x": {"from_node": "add1"},
                    "y": 4,
                },
            },
            "sub1": {
                "process_id": "subtract",
                "arguments": {
                    "x": {"from_node": "mul1"},
                    "y": 10,
                },
                "result": True,
            },
        }
        result = executor.execute(graph)
        assert result == 10


# ---------------------------------------------------------------------------
# Wrapped process graph format
# ---------------------------------------------------------------------------


class TestWrappedGraphFormat:
    """Tests for the {process_graph: {...}} wrapper format."""

    @pytest.fixture
    def executor(self):
        """Create a ProcessGraphExecutor."""
        from openeo_app.execution.executor import ProcessGraphExecutor

        return ProcessGraphExecutor(stac_api_url="https://example.com")

    def test_wrapped_format(self, executor):
        """Process graph wrapped in {process_graph: ...} should work."""
        graph = {
            "process_graph": {
                "add1": {
                    "process_id": "add",
                    "arguments": {"x": 1, "y": 1},
                    "result": True,
                }
            }
        }
        result = executor.execute(graph)
        assert result == 2


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestExecutionErrors:
    """Tests for error handling during graph execution."""

    @pytest.fixture
    def executor(self):
        """Create a ProcessGraphExecutor."""
        from openeo_app.execution.executor import ProcessGraphExecutor

        return ProcessGraphExecutor(stac_api_url="https://example.com")

    def test_missing_process_raises(self, executor):
        """Graph referencing a non-existent process should raise ValueError."""
        graph = {
            "bad1": {
                "process_id": "nonexistent_process_xyz",
                "arguments": {"x": 1},
                "result": True,
            }
        }
        with pytest.raises(ValueError, match="Missing process"):
            executor.execute(graph)


# ---------------------------------------------------------------------------
# Custom process registration
# ---------------------------------------------------------------------------


class TestCustomProcessRegistration:
    """Tests for registering custom process implementations."""

    def test_register_process(self):
        """Registered custom process should be available."""
        from openeo_app.execution.executor import ProcessGraphExecutor

        executor = ProcessGraphExecutor(stac_api_url="https://example.com")

        def my_custom_process(x, **kwargs):
            return x * 100

        executor.register_process("my_custom", my_custom_process)

        assert executor.has_process("my_custom")


# ---------------------------------------------------------------------------
# ProcessRegistrySingleton
# ---------------------------------------------------------------------------


class TestProcessRegistrySingleton:
    """Tests for the ProcessRegistrySingleton."""

    def test_singleton_returns_same_registry(self):
        """Multiple calls should return the same registry object."""
        from openeo_app.execution.process_registry_singleton import (
            ProcessRegistrySingleton,
        )

        r1 = ProcessRegistrySingleton.get_registry()
        r2 = ProcessRegistrySingleton.get_registry()

        assert r1 is r2

    def test_singleton_is_initialized(self):
        """After get_registry, is_initialized should return True."""
        from openeo_app.execution.process_registry_singleton import (
            ProcessRegistrySingleton,
        )

        ProcessRegistrySingleton.get_registry()
        assert ProcessRegistrySingleton.is_initialized() is True

    def test_singleton_process_count(self):
        """Process count should match registry length."""
        from openeo_app.execution.process_registry_singleton import (
            ProcessRegistrySingleton,
        )

        registry = ProcessRegistrySingleton.get_registry()
        assert ProcessRegistrySingleton.get_process_count() == len(registry)
