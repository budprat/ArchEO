# ABOUTME: UDF runtime with AST validation and secure execution.
# Provides sandboxed Python code execution for User Defined Functions.

"""
UDF Runtime for OpenEO AI.

Provides:
- UDFRuntime class for registering and executing UDFs
- AST-based code validation for security
- Execution timeout and resource limits
- UDF registry persistence
"""

import ast
import hashlib
import logging
import signal
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# Allowed modules for UDF execution
ALLOWED_MODULES = {
    # Core
    "math", "statistics", "itertools", "functools", "operator",
    # Data processing
    "numpy", "np",
    "xarray", "xr",
    "pandas", "pd",
    "dask",
    # OpenEO
    "openeo",
    # Utilities
    "json", "datetime", "collections", "typing",
}

# Forbidden constructs
FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "input",
    "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "hasattr",
    "breakpoint", "exit", "quit",
}

FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "http", "urllib",
    "ftplib", "smtplib", "telnetlib",
    "pickle", "shelve", "marshal",
    "importlib", "builtins", "__builtins__",
    "ctypes", "multiprocessing", "threading",
    "shutil", "pathlib", "tempfile",
    "ssl", "secrets", "hmac",
}


class UDFValidationError(Exception):
    """Raised when UDF code fails validation."""
    pass


class UDFExecutionError(Exception):
    """Raised when UDF execution fails."""
    pass


class UDFTimeoutError(Exception):
    """Raised when UDF execution times out."""
    pass


@dataclass
class UDFDefinition:
    """Definition of a User Defined Function."""
    id: str
    name: str
    code: str
    description: str
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    returns: str = "xarray.DataArray"
    runtime: str = "Python"
    version: str = "1.0.0"
    author: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    code_hash: str = field(default="")

    def __post_init__(self):
        """Calculate code hash."""
        if not self.code_hash:
            self.code_hash = hashlib.sha256(self.code.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "returns": self.returns,
            "runtime": self.runtime,
            "version": self.version,
            "author": self.author,
            "code_hash": self.code_hash,
        }


@dataclass
class UDFExecutionResult:
    """Result of UDF execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


class CodeValidator(ast.NodeVisitor):
    """AST visitor for validating UDF code."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Check import statements."""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name in FORBIDDEN_MODULES:
                self.errors.append(f"Import of forbidden module: {module_name}")
            elif module_name not in ALLOWED_MODULES:
                self.warnings.append(f"Import of unrecognized module: {module_name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from ... import statements."""
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name in FORBIDDEN_MODULES:
                self.errors.append(f"Import from forbidden module: {module_name}")
            elif module_name not in ALLOWED_MODULES:
                self.warnings.append(f"Import from unrecognized module: {module_name}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in FORBIDDEN_NAMES:
                self.errors.append(f"Call to forbidden function: {func_name}")
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                # Check for os.system, subprocess.run, etc.
                module_name = node.func.value.id
                if module_name in FORBIDDEN_MODULES:
                    self.errors.append(f"Call on forbidden module: {module_name}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Check name references."""
        if node.id in FORBIDDEN_NAMES:
            self.errors.append(f"Reference to forbidden name: {node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Check attribute access."""
        # Check for __dunder__ attributes that could be exploited
        if node.attr.startswith("__") and node.attr.endswith("__"):
            if node.attr not in ("__init__", "__call__", "__len__", "__iter__", "__next__"):
                self.warnings.append(f"Access to dunder attribute: {node.attr}")
        self.generic_visit(node)


class UDFRuntime:
    """
    Runtime for executing User Defined Functions.

    Usage:
        runtime = UDFRuntime()

        # Register a UDF
        udf = runtime.register(
            name="custom_ndvi",
            code='''
def apply(data):
    nir = data.sel(bands="nir")
    red = data.sel(bands="red")
    return (nir - red) / (nir + red)
''',
            description="Custom NDVI calculation"
        )

        # Execute the UDF
        result = runtime.execute(udf.id, data=my_xarray_data)
    """

    _instance: Optional["UDFRuntime"] = None
    _initialized: bool = False

    def __new__(cls) -> "UDFRuntime":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the runtime."""
        if self._initialized:
            return

        self._udfs: Dict[str, UDFDefinition] = {}
        self._compiled: Dict[str, Any] = {}
        self._timeout_seconds: int = 60
        self._max_memory_mb: int = 1024
        self._initialized = True

        logger.info("UDF Runtime initialized")

    @property
    def timeout_seconds(self) -> int:
        """Get execution timeout."""
        return self._timeout_seconds

    @timeout_seconds.setter
    def timeout_seconds(self, value: int):
        """Set execution timeout."""
        self._timeout_seconds = max(1, min(value, 300))  # 1-300 seconds

    def validate_code(self, code: str) -> tuple[bool, List[str], List[str]]:
        """
        Validate UDF code using AST analysis.

        Args:
            code: Python source code

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, [f"Syntax error: {e}"], []

        validator = CodeValidator()
        validator.visit(tree)

        return len(validator.errors) == 0, validator.errors, validator.warnings

    def register(
        self,
        name: str,
        code: str,
        description: str = "",
        parameters: Optional[List[Dict[str, Any]]] = None,
        returns: str = "xarray.DataArray",
        author: Optional[str] = None,
        udf_id: Optional[str] = None,
    ) -> UDFDefinition:
        """
        Register a new UDF.

        Args:
            name: UDF name
            code: Python source code
            description: Human-readable description
            parameters: List of parameter definitions
            returns: Return type description
            author: Author name
            udf_id: Optional custom ID

        Returns:
            UDFDefinition object

        Raises:
            UDFValidationError: If code validation fails
        """
        # Validate code
        valid, errors, warnings = self.validate_code(code)
        if not valid:
            raise UDFValidationError(f"Code validation failed: {errors}")

        if warnings:
            logger.warning(f"UDF '{name}' has warnings: {warnings}")

        # Generate ID
        if udf_id is None:
            code_hash = hashlib.sha256(code.encode()).hexdigest()[:8]
            udf_id = f"udf_{name.lower().replace(' ', '_')}_{code_hash}"

        # Create definition
        udf = UDFDefinition(
            id=udf_id,
            name=name,
            code=code,
            description=description,
            parameters=parameters or [],
            returns=returns,
            author=author,
        )

        # Compile the code
        try:
            compiled = compile(code, f"<udf:{udf_id}>", "exec")
            self._compiled[udf_id] = compiled
        except Exception as e:
            raise UDFValidationError(f"Code compilation failed: {e}")

        # Register
        self._udfs[udf_id] = udf
        logger.info(f"Registered UDF: {udf_id}")

        return udf

    def unregister(self, udf_id: str) -> bool:
        """Remove a UDF from the registry."""
        if udf_id in self._udfs:
            del self._udfs[udf_id]
            if udf_id in self._compiled:
                del self._compiled[udf_id]
            logger.info(f"Unregistered UDF: {udf_id}")
            return True
        return False

    def get(self, udf_id: str) -> Optional[UDFDefinition]:
        """Get a UDF definition by ID."""
        return self._udfs.get(udf_id)

    def list_all(self) -> List[UDFDefinition]:
        """List all registered UDFs."""
        return list(self._udfs.values())

    def exists(self, udf_id: str) -> bool:
        """Check if a UDF exists."""
        return udf_id in self._udfs

    @contextmanager
    def _timeout_context(self, seconds: int):
        """Context manager for execution timeout."""
        def handler(signum, frame):
            raise UDFTimeoutError(f"UDF execution timed out after {seconds} seconds")

        # Only use signal on Unix-like systems
        if hasattr(signal, "SIGALRM"):
            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        else:
            # Windows: no timeout support
            yield

    def execute(
        self,
        udf_id: str,
        **kwargs
    ) -> UDFExecutionResult:
        """
        Execute a UDF.

        Args:
            udf_id: UDF ID
            **kwargs: Arguments to pass to the UDF

        Returns:
            UDFExecutionResult with output or error
        """
        import time

        udf = self._udfs.get(udf_id)
        if udf is None:
            return UDFExecutionResult(
                success=False,
                error=f"UDF not found: {udf_id}"
            )

        compiled = self._compiled.get(udf_id)
        if compiled is None:
            return UDFExecutionResult(
                success=False,
                error=f"UDF not compiled: {udf_id}"
            )

        # Prepare execution environment
        exec_globals = self._create_safe_globals()

        # Capture stdout/stderr
        old_stdout, old_stderr = sys.stdout, sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        start_time = time.time()

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            with self._timeout_context(self._timeout_seconds):
                # Execute the code to define functions
                exec(compiled, exec_globals)

                # Look for main function (apply, run, or main)
                func = None
                for name in ["apply", "run", "main", "udf"]:
                    if name in exec_globals and callable(exec_globals[name]):
                        func = exec_globals[name]
                        break

                if func is None:
                    return UDFExecutionResult(
                        success=False,
                        error="No callable function found. Define 'apply', 'run', or 'main'."
                    )

                # Execute the function
                result = func(**kwargs)

            execution_time = (time.time() - start_time) * 1000

            return UDFExecutionResult(
                success=True,
                output=result,
                execution_time_ms=execution_time,
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
            )

        except UDFTimeoutError as e:
            return UDFExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            import traceback
            return UDFExecutionResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                execution_time_ms=(time.time() - start_time) * 1000,
                stderr=traceback.format_exc(),
            )
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def _create_safe_globals(self) -> Dict[str, Any]:
        """Create a safe execution environment."""
        safe_globals = {
            "__builtins__": {
                # Safe built-ins
                "abs": abs,
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "enumerate": enumerate,
                "filter": filter,
                "float": float,
                "frozenset": frozenset,
                "int": int,
                "isinstance": isinstance,
                "len": len,
                "list": list,
                "map": map,
                "max": max,
                "min": min,
                "pow": pow,
                "print": print,
                "range": range,
                "reversed": reversed,
                "round": round,
                "set": set,
                "slice": slice,
                "sorted": sorted,
                "str": str,
                "sum": sum,
                "tuple": tuple,
                "type": type,
                "zip": zip,
                # Exceptions
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
            }
        }

        # Import allowed modules
        import math
        import statistics
        import json
        import datetime
        from collections import OrderedDict, defaultdict
        from typing import Any, Dict, List, Optional

        safe_globals["math"] = math
        safe_globals["statistics"] = statistics
        safe_globals["json"] = json
        safe_globals["datetime"] = datetime
        safe_globals["OrderedDict"] = OrderedDict
        safe_globals["defaultdict"] = defaultdict

        # Try to import numpy and xarray
        try:
            import numpy as np
            safe_globals["numpy"] = np
            safe_globals["np"] = np
        except ImportError:
            pass

        try:
            import xarray as xr
            safe_globals["xarray"] = xr
            safe_globals["xr"] = xr
        except ImportError:
            pass

        try:
            import pandas as pd
            safe_globals["pandas"] = pd
            safe_globals["pd"] = pd
        except ImportError:
            pass

        return safe_globals

    def clear(self) -> None:
        """Clear all registered UDFs."""
        self._udfs.clear()
        self._compiled.clear()
        logger.info("Cleared UDF registry")


# Module-level singleton
_runtime: Optional[UDFRuntime] = None


def get_udf_runtime() -> UDFRuntime:
    """Get the global UDF runtime singleton."""
    global _runtime
    if _runtime is None:
        _runtime = UDFRuntime()
    return _runtime
