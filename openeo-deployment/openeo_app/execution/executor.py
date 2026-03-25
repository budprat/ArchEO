"""Process Graph Executor for OpenEO using Dask."""

import logging
import pkgutil
import importlib
import inspect
from functools import wraps
from typing import Any, Callable, Optional

import xarray as xr

from openeo_pg_parser_networkx import OpenEOProcessGraph
from openeo_pg_parser_networkx.process_registry import Process

logger = logging.getLogger(__name__)


def _wrap_process(func: Callable) -> Callable:
    """
    Wrap a process function to accept and ignore extra keyword arguments
    like 'named_parameters' that openeo-pg-parser-networkx passes.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Remove arguments that the function doesn't expect
        kwargs.pop('named_parameters', None)
        return func(*args, **kwargs)
    return wrapper

# Processes that need special handling or custom implementations
CUSTOM_PROCESS_OVERRIDES = {
    "load_collection",  # Our custom implementation with STAC mapping
}

# Modules to skip when discovering processes (problematic dependencies)
SKIP_MODULES = {
    "experimental",  # Requires rqadeforestation (Linux-only)
    "ml",  # Requires xgboost and other ML libs
}

# Reserved word functions that start with _ but should be included
RESERVED_WORD_FUNCTIONS = {
    "_and", "_or", "_not", "_if", "_int", "_round", "_min", "_max", "_sum", "_all", "_any"
}


def _discover_processes_from_package():
    """
    Dynamically discover all process implementations from openeo_processes_dask.

    Returns a dict mapping process_id to implementation function.
    """
    process_map = {}

    try:
        from openeo_processes_dask import process_implementations
    except ImportError as e:
        logger.error(f"Could not import openeo_processes_dask: {e}")
        return process_map

    # Walk through all modules in the package
    for importer, modname, ispkg in pkgutil.walk_packages(
        process_implementations.__path__,
        prefix='openeo_processes_dask.process_implementations.'
    ):
        # Skip problematic modules
        if any(skip in modname for skip in SKIP_MODULES):
            continue

        try:
            module = importlib.import_module(modname)

            for name in dir(module):
                # Skip private names, but allow reserved word functions
                if name.startswith('_') and name not in RESERVED_WORD_FUNCTIONS:
                    continue

                obj = getattr(module, name)

                # Filter for actual functions (not classes, not exceptions)
                if not callable(obj) or inspect.isclass(obj):
                    continue

                # Check it's from process_implementations
                if not hasattr(obj, '__module__'):
                    continue
                if 'process_implementations' not in str(obj.__module__):
                    continue

                # Skip utility functions (heuristic: process names are lowercase, no underscores at start)
                if name.startswith('get_') or name.startswith('update_'):
                    continue

                # Prefer shorter module paths for duplicates (more specific imports)
                if name not in process_map:
                    # Wrap to handle extra kwargs from pg-parser-networkx
                    process_map[name] = _wrap_process(obj)

        except Exception as e:
            logger.debug(f"Could not import module {modname}: {e}")

    return process_map


def _import_processes():
    """
    Import all process implementations from openeo_processes_dask.

    Uses dynamic discovery to load all available processes, then applies
    custom overrides for processes that need special handling.

    Returns a dict mapping process_id to implementation function.
    """
    # Start with dynamically discovered processes
    process_map = _discover_processes_from_package()

    logger.info(f"Discovered {len(process_map)} processes from openeo_processes_dask")

    # Apply custom overrides

    # 1. Our custom load_collection with STAC collection mapping
    try:
        from openeo_app.processes.load_collection import load_collection
        process_map["load_collection"] = load_collection
        logger.debug("Using custom load_collection implementation")
    except ImportError as e:
        logger.warning(f"Could not import custom load_collection: {e}")

    # 1b. Our fixed reduce_dimension that doesn't have the double-argument bug
    try:
        from openeo_app.processes.reduce_dimension_fix import (
            reduce_dimension,
            aggregate_temporal,
        )
        process_map["reduce_dimension"] = reduce_dimension
        process_map["aggregate_temporal"] = aggregate_temporal
        logger.debug("Using fixed reduce_dimension implementation")
    except ImportError as e:
        logger.warning(f"Could not import fixed reduce_dimension: {e}")

    # 2. Ensure save_result has a fallback
    if "save_result" not in process_map:
        def save_result(data, format="GTiff", options=None, **kwargs):
            """Basic save_result that just returns the data."""
            kwargs.pop('named_parameters', None)
            return data
        process_map["save_result"] = save_result
        logger.debug("Using basic save_result fallback")

    # 3. Ensure basic math operations have fallbacks (with **kwargs to accept named_parameters)
    # Import stable math operations from our math_fixes module
    try:
        from openeo_app.processes.math_fixes import (
            divide_safe,
            normalized_difference_stable,
        )
        # Use stable implementations
        def _add(x, y, **kwargs): return x + y
        def _subtract(x, y, **kwargs): return x - y
        def _multiply(x, y, **kwargs): return x * y
        def _divide(x, y, **kwargs): return divide_safe(x, y)  # Safe division!

        basic_math = {
            "add": _add,
            "subtract": _subtract,
            "multiply": _multiply,
            "divide": _divide,
            "normalized_difference": normalized_difference_stable,  # Stable NDVI
        }
    except ImportError:
        logger.warning("Could not import math_fixes, using basic fallbacks")
        def _add(x, y, **kwargs): return x + y
        def _subtract(x, y, **kwargs): return x - y
        def _multiply(x, y, **kwargs): return x * y
        def _divide(x, y, **kwargs):
            # Basic safe division fallback
            import numpy as np
            if hasattr(y, "where"):
                return x / y.where(y != 0, 1e-10)
            else:
                return x / np.where(y != 0, y, 1e-10)

        basic_math = {
            "add": _add,
            "subtract": _subtract,
            "multiply": _multiply,
            "divide": _divide,
        }

    for name, impl in basic_math.items():
        if name not in process_map:
            process_map[name] = impl
            logger.debug(f"Using basic {name} fallback")

    # 4. Handle Python reserved word conflicts (and, or, not, if, etc.)
    # These are exported with LEADING underscores in openeo_processes_dask (_min, _max, etc.)
    reserved_word_map = {
        "and": "_and",
        "or": "_or",
        "not": "_not",
        "if": "_if",
        "int": "_int",
        "round": "_round",
        "min": "_min",
        "max": "_max",
        "sum": "_sum",
        "all": "_all",
        "any": "_any",
    }

    for openeo_name, python_name in reserved_word_map.items():
        if python_name in process_map:
            # Add the user-facing name
            process_map[openeo_name] = process_map[python_name]
            # Remove the internal name (users should use 'min' not '_min')
            del process_map[python_name]
            logger.debug(f"Mapped {python_name} -> {openeo_name}")

    return process_map


class ProcessGraphExecutor:
    """
    Execute OpenEO process graphs using Dask.

    This executor:
    1. Parses process graphs into NetworkX DAGs
    2. Maps process IDs to implementation functions
    3. Executes processes using the graph's to_callable() method
    4. Handles Dask lazy computation

    The execution leverages openeo-pg-parser-networkx for graph parsing
    and openeo-processes-dask for process implementations.
    """

    def __init__(
        self,
        stac_api_url: str,
        process_registry: Optional[dict] = None,
    ):
        """
        Initialize the ProcessGraphExecutor.

        Args:
            stac_api_url: URL of the STAC API for data loading
            process_registry: Optional dict mapping process_id to Process objects.
                            If not provided, builds from openeo-processes-dask.
        """
        self.stac_api_url = stac_api_url
        self._custom_process_registry = process_registry

        # Use singleton process registry for performance
        # (saves 400-500ms per job by avoiding repeated process discovery)
        from openeo_app.execution.process_registry_singleton import ProcessRegistrySingleton
        self._process_registry = ProcessRegistrySingleton.get_registry()

        logger.info(
            f"ProcessGraphExecutor initialized with {len(self._process_registry)} processes"
        )

    def _build_process_registry(self) -> dict:
        """
        Build the process registry mapping process_id to Process objects.

        Returns:
            Dict mapping process_id to Process objects with implementations
        """
        registry = {}

        # Import process implementations
        process_map = _import_processes()

        # Create Process objects for each implementation
        for process_id, impl in process_map.items():
            registry[process_id] = Process(
                spec={"id": process_id},
                implementation=impl,
            )

        logger.info(f"Built process registry with {len(registry)} processes")
        return registry

    def execute(
        self,
        process_graph: dict,
        parameters: Optional[dict] = None,
    ) -> Any:
        """
        Execute a process graph and return results.

        Args:
            process_graph: OpenEO process graph dict
            parameters: Optional parameters for the graph

        Returns:
            Computation result (xarray.DataArray or other type depending on output)
        """
        logger.info("Starting process graph execution")

        if parameters is None:
            parameters = {}

        # Handle wrapped process graph format
        if "process_graph" in process_graph:
            pg_data = process_graph["process_graph"]
        else:
            pg_data = process_graph

        logger.debug(f"Process graph nodes: {list(pg_data.keys())}")

        try:
            # Parse process graph into NetworkX DAG
            pg = OpenEOProcessGraph(pg_data=pg_data)

            logger.debug(f"Parsed graph with {len(pg.nodes)} nodes")
            logger.debug(f"Required processes: {pg.required_processes}")

            # Verify all required processes are available
            missing = pg.required_processes - set(self._process_registry.keys())
            if missing:
                raise ValueError(f"Missing process implementations: {missing}")

            # Use the graph's to_callable method for execution
            # This handles all the dependency resolution and callback handling
            callable_graph = pg.to_callable(
                process_registry=self._process_registry,
                parameters=parameters,
            )

            # Execute the callable to get the result
            result = callable_graph()

            logger.info("Process graph execution completed")

            # Trigger Dask computation if result is lazy
            if hasattr(result, "compute"):
                logger.info("Triggering Dask computation...")
                result = result.compute()
                logger.info("Dask computation completed")

            return result

        except Exception as e:
            logger.error(f"Process graph execution failed: {e}")
            raise

    def execute_lazy(
        self,
        process_graph: dict,
        parameters: Optional[dict] = None,
    ) -> Any:
        """
        Execute a process graph and return lazy (uncomputed) result.

        This is useful for building up computation graphs without
        triggering actual computation.

        Args:
            process_graph: OpenEO process graph dict
            parameters: Optional parameters for the graph

        Returns:
            Lazy computation result (Dask-backed xarray.DataArray)
        """
        logger.info("Starting lazy process graph execution")

        if parameters is None:
            parameters = {}

        # Handle wrapped process graph format
        if "process_graph" in process_graph:
            pg_data = process_graph["process_graph"]
        else:
            pg_data = process_graph

        try:
            # Parse process graph
            pg = OpenEOProcessGraph(pg_data=pg_data)

            # Verify all required processes are available
            missing = pg.required_processes - set(self._process_registry.keys())
            if missing:
                raise ValueError(f"Missing process implementations: {missing}")

            # Create callable and execute (but don't compute)
            callable_graph = pg.to_callable(
                process_registry=self._process_registry,
                parameters=parameters,
            )

            result = callable_graph()

            logger.info("Lazy process graph execution completed")
            return result

        except Exception as e:
            logger.error(f"Lazy process graph execution failed: {e}")
            raise

    def get_available_processes(self) -> list:
        """Get list of available process IDs."""
        return list(self._process_registry.keys())

    def has_process(self, process_id: str) -> bool:
        """Check if a process is available."""
        return process_id in self._process_registry

    def register_process(self, process_id: str, implementation: Callable):
        """
        Register a custom process implementation.

        Args:
            process_id: The process identifier
            implementation: The implementation function
        """
        self._process_registry[process_id] = Process(
            spec={"id": process_id},
            implementation=implementation,
        )
        logger.info(f"Registered custom process: {process_id}")
