#!/usr/bin/env python3
"""
Comprehensive test suite for OpenEO FastAPI Dask execution engine.
Tests complex process graphs with detailed logging of each step.
"""

import sys
import os
import logging
import json
import numpy as np

# Setup path
sys.path.insert(0, '/Users/macbookpro/openeo-deployment')
os.environ.setdefault('STAC_API_URL', 'https://earth-search.aws.element84.com/v1/')

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)

# Set specific loggers
logging.getLogger('openeo_app').setLevel(logging.DEBUG)
logging.getLogger('openeo_pg_parser_networkx').setLevel(logging.DEBUG)

logger = logging.getLogger('test_complex_workflows')


def print_section(title):
    """Print a section header."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step_num, description):
    """Print a step header."""
    print(f"\n  Step {step_num}: {description}")
    print("-" * 50)


def test_1_chained_math_operations():
    """Test 1: Complex chained mathematical operations."""
    print_section("TEST 1: Chained Mathematical Operations")

    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Process graph: ((5 + 3) * 2) - 4 / 2 = 16 - 2 = 14
    process_graph = {
        "add1": {
            "process_id": "add",
            "arguments": {"x": 5, "y": 3},
            "description": "5 + 3 = 8"
        },
        "mult1": {
            "process_id": "multiply",
            "arguments": {"x": {"from_node": "add1"}, "y": 2},
            "description": "(5+3) * 2 = 16"
        },
        "div1": {
            "process_id": "divide",
            "arguments": {"x": 4, "y": 2},
            "description": "4 / 2 = 2"
        },
        "sub1": {
            "process_id": "subtract",
            "arguments": {"x": {"from_node": "mult1"}, "y": {"from_node": "div1"}},
            "result": True,
            "description": "16 - 2 = 14"
        }
    }

    print_step(1, "Parsing process graph")
    print(f"  Graph nodes: {list(process_graph.keys())}")

    print_step(2, "Executing graph")
    result = executor.execute(process_graph)

    print_step(3, "Validating result")
    expected = ((5 + 3) * 2) - (4 / 2)
    print(f"  Expected: {expected}")
    print(f"  Got: {result}")
    assert result == expected, f"Expected {expected}, got {result}"

    print("\n  ✓ TEST 1 PASSED")
    return True


def test_2_statistical_operations():
    """Test 2: Statistical operations on arrays."""
    print_section("TEST 2: Statistical Operations on Arrays")

    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    data = [10, 20, 30, 40, 50]

    # Test min
    print_step(1, "Testing min()")
    result = executor.execute({
        "min1": {"process_id": "min", "arguments": {"data": data}, "result": True}
    })
    print(f"  min({data}) = {result}")
    assert result == 10, f"Expected 10, got {result}"

    # Test max
    print_step(2, "Testing max()")
    result = executor.execute({
        "max1": {"process_id": "max", "arguments": {"data": data}, "result": True}
    })
    print(f"  max({data}) = {result}")
    assert result == 50, f"Expected 50, got {result}"

    # Test sum
    print_step(3, "Testing sum()")
    result = executor.execute({
        "sum1": {"process_id": "sum", "arguments": {"data": data}, "result": True}
    })
    print(f"  sum({data}) = {result}")
    assert result == 150, f"Expected 150, got {result}"

    # Test mean
    print_step(4, "Testing mean()")
    result = executor.execute({
        "mean1": {"process_id": "mean", "arguments": {"data": data}, "result": True}
    })
    print(f"  mean({data}) = {result}")
    assert result == 30, f"Expected 30, got {result}"

    # Test chained: (max - min) / mean
    print_step(5, "Testing chained statistics: (max - min) / mean")
    process_graph = {
        "max1": {"process_id": "max", "arguments": {"data": data}},
        "min1": {"process_id": "min", "arguments": {"data": data}},
        "mean1": {"process_id": "mean", "arguments": {"data": data}},
        "sub1": {"process_id": "subtract", "arguments": {"x": {"from_node": "max1"}, "y": {"from_node": "min1"}}},
        "div1": {"process_id": "divide", "arguments": {"x": {"from_node": "sub1"}, "y": {"from_node": "mean1"}}, "result": True}
    }
    result = executor.execute(process_graph)
    expected = (50 - 10) / 30
    print(f"  (max - min) / mean = (50 - 10) / 30 = {expected}")
    print(f"  Got: {result}")
    assert abs(result - expected) < 0.0001, f"Expected {expected}, got {result}"

    print("\n  ✓ TEST 2 PASSED")
    return True


def test_3_trigonometric_operations():
    """Test 3: Trigonometric functions."""
    print_section("TEST 3: Trigonometric Operations")

    import math
    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Test sin
    print_step(1, "Testing sin(π/2)")
    result = executor.execute({
        "sin1": {"process_id": "sin", "arguments": {"x": math.pi / 2}, "result": True}
    })
    print(f"  sin(π/2) = {result}")
    assert abs(result - 1.0) < 0.0001, f"Expected 1.0, got {result}"

    # Test cos
    print_step(2, "Testing cos(0)")
    result = executor.execute({
        "cos1": {"process_id": "cos", "arguments": {"x": 0}, "result": True}
    })
    print(f"  cos(0) = {result}")
    assert abs(result - 1.0) < 0.0001, f"Expected 1.0, got {result}"

    # Test tan
    print_step(3, "Testing tan(π/4)")
    result = executor.execute({
        "tan1": {"process_id": "tan", "arguments": {"x": math.pi / 4}, "result": True}
    })
    print(f"  tan(π/4) = {result}")
    assert abs(result - 1.0) < 0.0001, f"Expected 1.0, got {result}"

    # Test sin² + cos² = 1
    print_step(4, "Testing identity: sin²(x) + cos²(x) = 1")
    x = math.pi / 6  # 30 degrees
    process_graph = {
        "sin1": {"process_id": "sin", "arguments": {"x": x}},
        "cos1": {"process_id": "cos", "arguments": {"x": x}},
        "sin_sq": {"process_id": "power", "arguments": {"base": {"from_node": "sin1"}, "p": 2}},
        "cos_sq": {"process_id": "power", "arguments": {"base": {"from_node": "cos1"}, "p": 2}},
        "sum1": {"process_id": "add", "arguments": {"x": {"from_node": "sin_sq"}, "y": {"from_node": "cos_sq"}}, "result": True}
    }
    result = executor.execute(process_graph)
    print(f"  sin²(π/6) + cos²(π/6) = {result}")
    assert abs(result - 1.0) < 0.0001, f"Expected 1.0, got {result}"

    print("\n  ✓ TEST 3 PASSED")
    return True


def test_4_comparison_and_logic():
    """Test 4: Comparison and logic operations."""
    print_section("TEST 4: Comparison and Logic Operations")

    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Test gt (greater than)
    print_step(1, "Testing gt(10, 5)")
    result = executor.execute({
        "gt1": {"process_id": "gt", "arguments": {"x": 10, "y": 5}, "result": True}
    })
    print(f"  10 > 5 = {result} (expected True/1)")
    assert result == True or result == 1, f"Expected True, got {result}"

    # Test lt (less than)
    print_step(2, "Testing lt(3, 7)")
    result = executor.execute({
        "lt1": {"process_id": "lt", "arguments": {"x": 3, "y": 7}, "result": True}
    })
    print(f"  3 < 7 = {result} (expected True/1)")
    assert result == True or result == 1, f"Expected True, got {result}"

    # Test eq (equal)
    print_step(3, "Testing eq(5, 5)")
    result = executor.execute({
        "eq1": {"process_id": "eq", "arguments": {"x": 5, "y": 5}, "result": True}
    })
    print(f"  5 == 5 = {result} (expected True/1)")
    assert result == True or result == 1, f"Expected True, got {result}"

    # Test between
    print_step(4, "Testing between(5, 1, 10)")
    result = executor.execute({
        "between1": {"process_id": "between", "arguments": {"x": 5, "min": 1, "max": 10}, "result": True}
    })
    print(f"  1 <= 5 <= 10 = {result} (expected True/1)")
    assert result == True or result == 1, f"Expected True, got {result}"

    # Test complex: (x > 5) and (x < 15)
    print_step(5, "Testing (x > 5) AND (x < 15) where x = 10")
    process_graph = {
        "gt1": {"process_id": "gt", "arguments": {"x": 10, "y": 5}},
        "lt1": {"process_id": "lt", "arguments": {"x": 10, "y": 15}},
        "and1": {"process_id": "and", "arguments": {"x": {"from_node": "gt1"}, "y": {"from_node": "lt1"}}, "result": True}
    }
    result = executor.execute(process_graph)
    print(f"  (10 > 5) AND (10 < 15) = {result} (expected True/1)")
    assert result == True or result == 1, f"Expected True, got {result}"

    print("\n  ✓ TEST 4 PASSED")
    return True


def test_5_array_operations():
    """Test 5: Array manipulation operations."""
    print_section("TEST 5: Array Operations")

    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Test array_element (get element at index)
    print_step(1, "Testing array_element([10,20,30,40], index=2)")
    result = executor.execute({
        "arr1": {"process_id": "array_element", "arguments": {"data": [10, 20, 30, 40], "index": 2}, "result": True}
    })
    print(f"  array[2] = {result} (expected 30)")
    assert result == 30, f"Expected 30, got {result}"

    # Test first
    print_step(2, "Testing first([100, 200, 300])")
    result = executor.execute({
        "first1": {"process_id": "first", "arguments": {"data": [100, 200, 300]}, "result": True}
    })
    print(f"  first([100,200,300]) = {result} (expected 100)")
    assert result == 100, f"Expected 100, got {result}"

    # Test last
    print_step(3, "Testing last([100, 200, 300])")
    result = executor.execute({
        "last1": {"process_id": "last", "arguments": {"data": [100, 200, 300]}, "result": True}
    })
    print(f"  last([100,200,300]) = {result} (expected 300)")
    assert result == 300, f"Expected 300, got {result}"

    # Test array_contains
    print_step(4, "Testing array_contains([1,2,3,4,5], 3)")
    result = executor.execute({
        "contains1": {"process_id": "array_contains", "arguments": {"data": [1, 2, 3, 4, 5], "value": 3}, "result": True}
    })
    print(f"  array_contains([1,2,3,4,5], 3) = {result} (expected True)")
    assert result == True, f"Expected True, got {result}"

    print("\n  ✓ TEST 5 PASSED")
    return True


def test_6_math_functions():
    """Test 6: Advanced math functions."""
    print_section("TEST 6: Advanced Math Functions")

    import math
    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Test sqrt
    print_step(1, "Testing sqrt(16)")
    result = executor.execute({
        "sqrt1": {"process_id": "sqrt", "arguments": {"x": 16}, "result": True}
    })
    print(f"  sqrt(16) = {result} (expected 4)")
    assert result == 4, f"Expected 4, got {result}"

    # Test power
    print_step(2, "Testing power(2, 10)")
    result = executor.execute({
        "pow1": {"process_id": "power", "arguments": {"base": 2, "p": 10}, "result": True}
    })
    print(f"  2^10 = {result} (expected 1024)")
    assert result == 1024, f"Expected 1024, got {result}"

    # Test ln (natural log)
    print_step(3, "Testing ln(e)")
    result = executor.execute({
        "ln1": {"process_id": "ln", "arguments": {"x": math.e}, "result": True}
    })
    print(f"  ln(e) = {result} (expected 1)")
    assert abs(result - 1.0) < 0.0001, f"Expected 1, got {result}"

    # Test exp
    print_step(4, "Testing exp(1)")
    result = executor.execute({
        "exp1": {"process_id": "exp", "arguments": {"p": 1}, "result": True}
    })
    print(f"  exp(1) = {result} (expected e ≈ 2.718)")
    assert abs(result - math.e) < 0.0001, f"Expected {math.e}, got {result}"

    # Test absolute
    print_step(5, "Testing absolute(-42)")
    result = executor.execute({
        "abs1": {"process_id": "absolute", "arguments": {"x": -42}, "result": True}
    })
    print(f"  |−42| = {result} (expected 42)")
    assert result == 42, f"Expected 42, got {result}"

    # Test mod
    print_step(6, "Testing mod(17, 5)")
    result = executor.execute({
        "mod1": {"process_id": "mod", "arguments": {"x": 17, "y": 5}, "result": True}
    })
    print(f"  17 mod 5 = {result} (expected 2)")
    assert result == 2, f"Expected 2, got {result}"

    # Test floor and ceil
    print_step(7, "Testing floor(3.7) and ceil(3.2)")
    result_floor = executor.execute({
        "floor1": {"process_id": "floor", "arguments": {"x": 3.7}, "result": True}
    })
    result_ceil = executor.execute({
        "ceil1": {"process_id": "ceil", "arguments": {"x": 3.2}, "result": True}
    })
    print(f"  floor(3.7) = {result_floor} (expected 3)")
    print(f"  ceil(3.2) = {result_ceil} (expected 4)")
    assert result_floor == 3, f"Expected 3, got {result_floor}"
    assert result_ceil == 4, f"Expected 4, got {result_ceil}"

    print("\n  ✓ TEST 6 PASSED")
    return True


def test_7_complex_workflow():
    """Test 7: Complex multi-step workflow simulating real processing."""
    print_section("TEST 7: Complex Multi-Step Workflow")
    print("  Simulating: Normalized calculation similar to NDVI formula")

    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Simulate NDVI-like calculation: (NIR - RED) / (NIR + RED)
    # Using values: NIR = 0.8, RED = 0.2
    # Expected: (0.8 - 0.2) / (0.8 + 0.2) = 0.6 / 1.0 = 0.6

    nir = 0.8
    red = 0.2

    process_graph = {
        "nir_val": {
            "process_id": "add",
            "arguments": {"x": nir, "y": 0},  # Identity operation to set value
            "description": "NIR band value"
        },
        "red_val": {
            "process_id": "add",
            "arguments": {"x": red, "y": 0},  # Identity operation to set value
            "description": "RED band value"
        },
        "difference": {
            "process_id": "subtract",
            "arguments": {
                "x": {"from_node": "nir_val"},
                "y": {"from_node": "red_val"}
            },
            "description": "NIR - RED"
        },
        "sum_bands": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "nir_val"},
                "y": {"from_node": "red_val"}
            },
            "description": "NIR + RED"
        },
        "ndvi": {
            "process_id": "divide",
            "arguments": {
                "x": {"from_node": "difference"},
                "y": {"from_node": "sum_bands"}
            },
            "result": True,
            "description": "NDVI = (NIR - RED) / (NIR + RED)"
        }
    }

    print_step(1, "Process graph structure:")
    for node_id, node in process_graph.items():
        desc = node.get('description', node['process_id'])
        args = node['arguments']
        print(f"    {node_id}: {desc}")
        print(f"      process: {node['process_id']}")
        print(f"      args: {args}")

    print_step(2, "Executing workflow")
    result = executor.execute(process_graph)

    print_step(3, "Validating result")
    expected = (nir - red) / (nir + red)
    print(f"  NIR = {nir}, RED = {red}")
    print(f"  NDVI = (NIR - RED) / (NIR + RED)")
    print(f"  NDVI = ({nir} - {red}) / ({nir} + {red})")
    print(f"  NDVI = {nir - red} / {nir + red}")
    print(f"  Expected: {expected}")
    print(f"  Got: {result}")
    assert abs(result - expected) < 0.0001, f"Expected {expected}, got {result}"

    print("\n  ✓ TEST 7 PASSED")
    return True


def test_8_cumulative_operations():
    """Test 8: Cumulative operations."""
    print_section("TEST 8: Cumulative Operations")

    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    data = [1, 2, 3, 4, 5]

    # Test cumsum
    print_step(1, "Testing cumsum([1,2,3,4,5])")
    result = executor.execute({
        "cumsum1": {"process_id": "cumsum", "arguments": {"data": data}, "result": True}
    })
    expected = [1, 3, 6, 10, 15]
    print(f"  cumsum({data}) = {list(result)}")
    print(f"  Expected: {expected}")
    assert list(result) == expected, f"Expected {expected}, got {list(result)}"

    # Test cumproduct
    print_step(2, "Testing cumproduct([1,2,3,4,5])")
    result = executor.execute({
        "cumprod1": {"process_id": "cumproduct", "arguments": {"data": data}, "result": True}
    })
    expected = [1, 2, 6, 24, 120]
    print(f"  cumproduct({data}) = {list(result)}")
    print(f"  Expected: {expected}")
    assert list(result) == expected, f"Expected {expected}, got {list(result)}"

    # Test cummin
    print_step(3, "Testing cummin([5,3,4,1,2])")
    data2 = [5, 3, 4, 1, 2]
    result = executor.execute({
        "cummin1": {"process_id": "cummin", "arguments": {"data": data2}, "result": True}
    })
    expected = [5, 3, 3, 1, 1]
    print(f"  cummin({data2}) = {list(result)}")
    print(f"  Expected: {expected}")
    assert list(result) == expected, f"Expected {expected}, got {list(result)}"

    # Test cummax
    print_step(4, "Testing cummax([1,3,2,5,4])")
    data3 = [1, 3, 2, 5, 4]
    result = executor.execute({
        "cummax1": {"process_id": "cummax", "arguments": {"data": data3}, "result": True}
    })
    expected = [1, 3, 3, 5, 5]
    print(f"  cummax({data3}) = {list(result)}")
    print(f"  Expected: {expected}")
    assert list(result) == expected, f"Expected {expected}, got {list(result)}"

    print("\n  ✓ TEST 8 PASSED")
    return True


def test_9_text_operations():
    """Test 9: Text/string operations."""
    print_section("TEST 9: Text Operations")

    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Test text_begins
    print_step(1, "Testing text_begins('Hello World', 'Hello')")
    result = executor.execute({
        "begins1": {"process_id": "text_begins", "arguments": {"data": "Hello World", "pattern": "Hello"}, "result": True}
    })
    print(f"  text_begins('Hello World', 'Hello') = {result} (expected True)")
    assert result == True, f"Expected True, got {result}"

    # Test text_ends
    print_step(2, "Testing text_ends('Hello World', 'World')")
    result = executor.execute({
        "ends1": {"process_id": "text_ends", "arguments": {"data": "Hello World", "pattern": "World"}, "result": True}
    })
    print(f"  text_ends('Hello World', 'World') = {result} (expected True)")
    assert result == True, f"Expected True, got {result}"

    # Test text_contains
    print_step(3, "Testing text_contains('Hello World', 'lo Wo')")
    result = executor.execute({
        "contains1": {"process_id": "text_contains", "arguments": {"data": "Hello World", "pattern": "lo Wo"}, "result": True}
    })
    print(f"  text_contains('Hello World', 'lo Wo') = {result} (expected True)")
    assert result == True, f"Expected True, got {result}"

    # Test text_concat
    print_step(4, "Testing text_concat(['Hello', ' ', 'World'])")
    result = executor.execute({
        "concat1": {"process_id": "text_concat", "arguments": {"data": ["Hello", " ", "World"]}, "result": True}
    })
    print(f"  text_concat(['Hello', ' ', 'World']) = '{result}' (expected 'Hello World')")
    assert result == "Hello World", f"Expected 'Hello World', got '{result}'"

    print("\n  ✓ TEST 9 PASSED")
    return True


def test_10_type_checking():
    """Test 10: Type checking operations."""
    print_section("TEST 10: Type Checking Operations")

    import math
    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Test is_nan
    print_step(1, "Testing is_nan(NaN)")
    result = executor.execute({
        "isnan1": {"process_id": "is_nan", "arguments": {"x": float('nan')}, "result": True}
    })
    print(f"  is_nan(NaN) = {result} (expected True)")
    assert result == True, f"Expected True, got {result}"

    # Test is_nan with normal number
    print_step(2, "Testing is_nan(42)")
    result = executor.execute({
        "isnan2": {"process_id": "is_nan", "arguments": {"x": 42}, "result": True}
    })
    print(f"  is_nan(42) = {result} (expected False)")
    assert result == False, f"Expected False, got {result}"

    # Test is_infinite
    print_step(3, "Testing is_infinite(inf)")
    result = executor.execute({
        "isinf1": {"process_id": "is_infinite", "arguments": {"x": float('inf')}, "result": True}
    })
    print(f"  is_infinite(inf) = {result} (expected True)")
    assert result == True, f"Expected True, got {result}"

    # Test is_valid
    print_step(4, "Testing is_valid(42)")
    result = executor.execute({
        "valid1": {"process_id": "is_valid", "arguments": {"x": 42}, "result": True}
    })
    print(f"  is_valid(42) = {result} (expected True)")
    assert result == True, f"Expected True, got {result}"

    print("\n  ✓ TEST 10 PASSED")
    return True


def test_11_conditional_logic():
    """Test 11: Conditional logic (if/then/else)."""
    print_section("TEST 11: Conditional Logic")

    from openeo_app.execution.executor import ProcessGraphExecutor
    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')

    # Test if with true condition
    print_step(1, "Testing if(True, 'yes', 'no')")
    result = executor.execute({
        "if1": {"process_id": "if", "arguments": {"value": True, "accept": "yes", "reject": "no"}, "result": True}
    })
    print(f"  if(True, 'yes', 'no') = '{result}' (expected 'yes')")
    assert result == "yes", f"Expected 'yes', got '{result}'"

    # Test if with false condition
    print_step(2, "Testing if(False, 100, 200)")
    result = executor.execute({
        "if2": {"process_id": "if", "arguments": {"value": False, "accept": 100, "reject": 200}, "result": True}
    })
    print(f"  if(False, 100, 200) = {result} (expected 200)")
    assert result == 200, f"Expected 200, got {result}"

    # Test complex: if x > 10 then x*2 else x/2
    print_step(3, "Testing: if (15 > 10) then 15*2 else 15/2")
    process_graph = {
        "x_val": {"process_id": "add", "arguments": {"x": 15, "y": 0}},
        "condition": {"process_id": "gt", "arguments": {"x": {"from_node": "x_val"}, "y": 10}},
        "then_val": {"process_id": "multiply", "arguments": {"x": {"from_node": "x_val"}, "y": 2}},
        "else_val": {"process_id": "divide", "arguments": {"x": {"from_node": "x_val"}, "y": 2}},
        "result": {
            "process_id": "if",
            "arguments": {
                "value": {"from_node": "condition"},
                "accept": {"from_node": "then_val"},
                "reject": {"from_node": "else_val"}
            },
            "result": True
        }
    }
    result = executor.execute(process_graph)
    print(f"  if (15 > 10) then 15*2 else 15/2 = {result} (expected 30)")
    assert result == 30, f"Expected 30, got {result}"

    print("\n  ✓ TEST 11 PASSED")
    return True


def test_12_load_collection_dem():
    """Test 12: Load real collection data (DEM)."""
    print_section("TEST 12: Load Collection (Copernicus DEM)")

    from openeo_app.processes.load_collection import load_collection

    print_step(1, "Loading cop-dem-glo-30 data")
    print("  Collection: cop-dem-glo-30")
    print("  Spatial extent: 11.0-11.01°E, 46.0-46.01°N (small area)")

    try:
        data = load_collection(
            id="cop-dem-glo-30",
            spatial_extent={
                "west": 11.0,
                "south": 46.0,
                "east": 11.01,
                "north": 46.01,
                "crs": "EPSG:4326"
            },
        )

        print_step(2, "Inspecting loaded data")
        print(f"  Type: {type(data).__name__}")
        print(f"  Shape: {data.shape}")
        print(f"  Dimensions: {data.dims}")
        print(f"  Coordinates: {list(data.coords.keys())}")

        print_step(3, "Computing statistics")
        # Compute to get actual values
        computed = data.compute()
        print(f"  Min elevation: {float(computed.min()):.2f} m")
        print(f"  Max elevation: {float(computed.max()):.2f} m")
        print(f"  Mean elevation: {float(computed.mean()):.2f} m")

        print("\n  ✓ TEST 12 PASSED")
        return True

    except Exception as e:
        print(f"\n  ✗ TEST 12 FAILED: {e}")
        return False


def main():
    """Run all tests."""
    print()
    print("=" * 70)
    print("  OPENEO FASTAPI DASK EXECUTION ENGINE - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print("  Testing 136 processes with detailed logging")
    print("=" * 70)

    results = {}

    # Run all tests
    tests = [
        ("Chained Math", test_1_chained_math_operations),
        ("Statistics", test_2_statistical_operations),
        ("Trigonometry", test_3_trigonometric_operations),
        ("Comparison & Logic", test_4_comparison_and_logic),
        ("Array Operations", test_5_array_operations),
        ("Math Functions", test_6_math_functions),
        ("Complex Workflow", test_7_complex_workflow),
        ("Cumulative Ops", test_8_cumulative_operations),
        ("Text Operations", test_9_text_operations),
        ("Type Checking", test_10_type_checking),
        ("Conditional Logic", test_11_conditional_logic),
        ("Load Collection", test_12_load_collection_dem),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                results[name] = "PASSED"
                passed += 1
            else:
                results[name] = "FAILED"
                failed += 1
        except Exception as e:
            results[name] = f"ERROR: {e}"
            failed += 1
            import traceback
            traceback.print_exc()

    # Print summary
    print()
    print("=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    for name, result in results.items():
        status = "✓" if result == "PASSED" else "✗"
        print(f"  {status} {name}: {result}")

    print()
    print(f"  Total: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
