# ABOUTME: UDF (User Defined Function) package for OpenEO AI.
# Provides secure UDF execution with AST validation and sandboxing.

"""
UDF (User Defined Function) support for OpenEO AI.

Provides:
- UDFRuntime for secure code execution
- AST-based code validation
- UDF registry for storing and retrieving UDFs
"""

from .runtime import (
    UDFRuntime,
    UDFDefinition,
    UDFExecutionResult,
    UDFValidationError,
    get_udf_runtime,
)

__all__ = [
    "UDFRuntime",
    "UDFDefinition",
    "UDFExecutionResult",
    "UDFValidationError",
    "get_udf_runtime",
]
