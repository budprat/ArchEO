# ABOUTME: UDF tools for Claude SDK integration.
# Provides tools for registering and executing User Defined Functions.

"""
UDF Tools for OpenEO AI.

Provides Claude SDK tools for:
- udf_register: Register a new UDF
- udf_execute: Execute a registered UDF
- udf_list: List all registered UDFs
- udf_validate: Validate UDF code without registering
"""

import json
import logging
from typing import Any, Dict

from ..udf.runtime import (
    UDFRuntime,
    UDFValidationError,
    get_udf_runtime,
)

logger = logging.getLogger(__name__)


async def udf_register_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register a new User Defined Function.

    Args:
        args: {
            "name": "UDF name",
            "code": "Python code",
            "description": "Description",
            "parameters": [{"name": "...", "type": "...", "description": "..."}],
            "returns": "Return type description"
        }

    Returns:
        Registration result with UDF ID
    """
    name = args.get("name")
    code = args.get("code")
    description = args.get("description", "")
    parameters = args.get("parameters", [])
    returns = args.get("returns", "xarray.DataArray")

    if not name:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": False,
                "error": "UDF name is required"
            })}]
        }

    if not code:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": False,
                "error": "UDF code is required"
            })}]
        }

    try:
        runtime = get_udf_runtime()
        udf = runtime.register(
            name=name,
            code=code,
            description=description,
            parameters=parameters,
            returns=returns,
        )

        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": True,
                "udf_id": udf.id,
                "name": udf.name,
                "description": udf.description,
                "code_hash": udf.code_hash,
                "message": f"UDF '{name}' registered successfully with ID: {udf.id}"
            })}]
        }

    except UDFValidationError as e:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": False,
                "error": str(e),
                "error_type": "validation"
            })}]
        }
    except Exception as e:
        logger.error(f"UDF registration error: {e}")
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": False,
                "error": str(e)
            })}]
        }


async def udf_execute_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a registered User Defined Function.

    Args:
        args: {
            "udf_id": "UDF identifier",
            "data": "Input data (xarray-like)",
            "parameters": {"param1": value1, ...}
        }

    Returns:
        Execution result
    """
    udf_id = args.get("udf_id")
    data = args.get("data")
    parameters = args.get("parameters", {})

    if not udf_id:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": False,
                "error": "UDF ID is required"
            })}]
        }

    runtime = get_udf_runtime()

    if not runtime.exists(udf_id):
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": False,
                "error": f"UDF not found: {udf_id}",
                "available_udfs": [u.id for u in runtime.list_all()]
            })}]
        }

    try:
        # Execute the UDF
        kwargs = {"data": data, **parameters}
        result = runtime.execute(udf_id, **kwargs)

        if result.success:
            # Try to serialize output
            output_repr = None
            if result.output is not None:
                try:
                    if hasattr(result.output, "to_dict"):
                        output_repr = result.output.to_dict()
                    elif hasattr(result.output, "values"):
                        output_repr = {"type": "array", "shape": list(result.output.shape)}
                    else:
                        output_repr = str(result.output)[:1000]
                except Exception:
                    output_repr = str(type(result.output))

            return {
                "content": [{"type": "text", "text": json.dumps({
                    "success": True,
                    "udf_id": udf_id,
                    "execution_time_ms": result.execution_time_ms,
                    "output": output_repr,
                    "stdout": result.stdout[:500] if result.stdout else None,
                })}]
            }
        else:
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "success": False,
                    "udf_id": udf_id,
                    "error": result.error,
                    "stderr": result.stderr[:500] if result.stderr else None,
                })}]
            }

    except Exception as e:
        logger.error(f"UDF execution error: {e}")
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": False,
                "error": str(e)
            })}]
        }


async def udf_list_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List all registered User Defined Functions.

    Returns:
        List of UDF metadata
    """
    runtime = get_udf_runtime()
    udfs = runtime.list_all()

    return {
        "content": [{"type": "text", "text": json.dumps({
            "count": len(udfs),
            "udfs": [udf.to_dict() for udf in udfs]
        })}]
    }


async def udf_validate_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate UDF code without registering.

    Args:
        args: {"code": "Python code to validate"}

    Returns:
        Validation result with errors and warnings
    """
    code = args.get("code")

    if not code:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "valid": False,
                "errors": ["Code is required"]
            })}]
        }

    runtime = get_udf_runtime()
    valid, errors, warnings = runtime.validate_code(code)

    return {
        "content": [{"type": "text", "text": json.dumps({
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "message": "Code is valid" if valid else "Code has validation errors"
        })}]
    }


async def udf_delete_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete a registered UDF.

    Args:
        args: {"udf_id": "UDF identifier"}

    Returns:
        Deletion result
    """
    udf_id = args.get("udf_id")

    if not udf_id:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": False,
                "error": "UDF ID is required"
            })}]
        }

    runtime = get_udf_runtime()
    removed = runtime.unregister(udf_id)

    return {
        "content": [{"type": "text", "text": json.dumps({
            "success": removed,
            "udf_id": udf_id,
            "message": f"UDF '{udf_id}' deleted" if removed else f"UDF '{udf_id}' not found"
        })}]
    }


def create_udf_tools(config=None) -> Dict[str, Any]:
    """Create UDF tools for Claude SDK integration."""
    return {
        "udf_register": udf_register_tool,
        "udf_execute": udf_execute_tool,
        "udf_list": udf_list_tool,
        "udf_validate": udf_validate_tool,
        "udf_delete": udf_delete_tool,
    }


# Tool definitions for Claude API
UDF_TOOL_DEFINITIONS = [
    {
        "name": "udf_register",
        "description": "Register a new User Defined Function (UDF) for custom data processing. UDFs must define an 'apply' function that takes 'data' as input.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the UDF"
                },
                "code": {
                    "type": "string",
                    "description": "Python code defining the UDF. Must contain an 'apply(data)' function."
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description of what the UDF does"
                },
                "parameters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "description": {"type": "string"}
                        }
                    },
                    "description": "List of additional parameters the UDF accepts"
                }
            },
            "required": ["name", "code"]
        }
    },
    {
        "name": "udf_execute",
        "description": "Execute a registered UDF on data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "udf_id": {
                    "type": "string",
                    "description": "ID of the UDF to execute"
                },
                "parameters": {
                    "type": "object",
                    "description": "Additional parameters to pass to the UDF"
                }
            },
            "required": ["udf_id"]
        }
    },
    {
        "name": "udf_list",
        "description": "List all registered User Defined Functions.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "udf_validate",
        "description": "Validate UDF code for security and syntax without registering it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to validate"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "udf_delete",
        "description": "Delete a registered UDF.",
        "input_schema": {
            "type": "object",
            "properties": {
                "udf_id": {
                    "type": "string",
                    "description": "ID of the UDF to delete"
                }
            },
            "required": ["udf_id"]
        }
    }
]
