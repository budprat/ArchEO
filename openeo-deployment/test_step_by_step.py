#!/usr/bin/env python3
"""
Step-by-step process graph execution test with detailed logging.
Shows each processing step being executed with input/output values.
"""

import sys
import os
import logging

sys.path.insert(0, '/Users/macbookpro/openeo-deployment')
os.environ.setdefault('STAC_API_URL', 'https://earth-search.aws.element84.com/v1/')

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger('step_by_step')


class TracingExecutor:
    """Executor wrapper that traces each process execution."""

    def __init__(self):
        from openeo_app.execution.executor import ProcessGraphExecutor
        self.executor = ProcessGraphExecutor(
            stac_api_url='https://earth-search.aws.element84.com/v1/'
        )
        self.execution_trace = []

    def execute_with_tracing(self, process_graph, description=""):
        """Execute process graph and trace each step."""
        print(f"\n{'='*70}")
        print(f"  EXECUTING: {description}")
        print(f"{'='*70}")

        # Show the process graph structure
        print("\n  Process Graph:")
        for node_id, node in process_graph.items():
            process_id = node['process_id']
            args = node['arguments']
            is_result = node.get('result', False)
            result_marker = " [RESULT]" if is_result else ""

            # Format arguments
            args_str = []
            for k, v in args.items():
                if isinstance(v, dict) and 'from_node' in v:
                    args_str.append(f"{k}=<{v['from_node']}>")
                else:
                    args_str.append(f"{k}={v}")

            print(f"    {node_id}: {process_id}({', '.join(args_str)}){result_marker}")

        # Execute
        print("\n  Execution Steps:")
        print("-" * 60)

        # We'll trace execution by looking at the required processes
        from openeo_pg_parser_networkx import OpenEOProcessGraph

        if "process_graph" in process_graph:
            pg_data = process_graph["process_graph"]
        else:
            pg_data = process_graph

        pg = OpenEOProcessGraph(pg_data=pg_data)
        print(f"    Required processes: {pg.required_processes}")
        print(f"    Graph nodes: {len(pg.nodes)}")

        # Execute the graph
        result = self.executor.execute(process_graph)

        print("-" * 60)
        print(f"\n  FINAL RESULT: {result}")
        print(f"{'='*70}")

        return result


def test_chained_calculations():
    """Test chained mathematical calculations with tracing."""
    tracer = TracingExecutor()

    # Test 1: Simple chain (a + b) * c
    print("\n" + "="*70)
    print("  TEST 1: Simple Chain - (5 + 3) * 2 = 16")
    print("="*70)

    process_graph = {
        "step1_add": {
            "process_id": "add",
            "arguments": {"x": 5, "y": 3}
        },
        "step2_multiply": {
            "process_id": "multiply",
            "arguments": {"x": {"from_node": "step1_add"}, "y": 2},
            "result": True
        }
    }

    result = tracer.execute_with_tracing(process_graph, "(5 + 3) * 2")
    expected = (5 + 3) * 2
    print(f"  Expected: {expected}, Got: {result}")
    assert result == expected, f"FAILED: Expected {expected}, got {result}"
    print("  ✓ PASSED")


def test_statistics_chain():
    """Test statistical operations chain."""
    tracer = TracingExecutor()

    print("\n" + "="*70)
    print("  TEST 2: Statistics Chain - (max - min) / count")
    print("="*70)

    data = [10, 20, 30, 40, 50]

    process_graph = {
        "get_max": {
            "process_id": "max",
            "arguments": {"data": data}
        },
        "get_min": {
            "process_id": "min",
            "arguments": {"data": data}
        },
        "get_count": {
            "process_id": "count",
            "arguments": {"data": data}
        },
        "range": {
            "process_id": "subtract",
            "arguments": {
                "x": {"from_node": "get_max"},
                "y": {"from_node": "get_min"}
            }
        },
        "normalized_range": {
            "process_id": "divide",
            "arguments": {
                "x": {"from_node": "range"},
                "y": {"from_node": "get_count"}
            },
            "result": True
        }
    }

    result = tracer.execute_with_tracing(process_graph, f"(max - min) / count of {data}")
    expected = (50 - 10) / 5
    print(f"  Expected: {expected}, Got: {result}")
    assert result == expected, f"FAILED: Expected {expected}, got {result}"
    print("  ✓ PASSED")


def test_trig_identity():
    """Test trigonometric identity: sin²(x) + cos²(x) = 1."""
    import math
    tracer = TracingExecutor()

    print("\n" + "="*70)
    print("  TEST 3: Trigonometric Identity - sin²(x) + cos²(x) = 1")
    print("="*70)

    x = math.pi / 4  # 45 degrees

    process_graph = {
        "calc_sin": {
            "process_id": "sin",
            "arguments": {"x": x}
        },
        "calc_cos": {
            "process_id": "cos",
            "arguments": {"x": x}
        },
        "sin_squared": {
            "process_id": "power",
            "arguments": {"base": {"from_node": "calc_sin"}, "p": 2}
        },
        "cos_squared": {
            "process_id": "power",
            "arguments": {"base": {"from_node": "calc_cos"}, "p": 2}
        },
        "identity_sum": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "sin_squared"},
                "y": {"from_node": "cos_squared"}
            },
            "result": True
        }
    }

    result = tracer.execute_with_tracing(process_graph, f"sin²(π/4) + cos²(π/4)")
    expected = 1.0
    print(f"  Expected: {expected}, Got: {result}")
    assert abs(result - expected) < 0.0001, f"FAILED: Expected {expected}, got {result}"
    print("  ✓ PASSED")


def test_conditional_workflow():
    """Test conditional logic workflow."""
    tracer = TracingExecutor()

    print("\n" + "="*70)
    print("  TEST 4: Conditional Workflow - if x > 10 then x*2 else x/2")
    print("="*70)

    x_value = 15

    process_graph = {
        "x": {
            "process_id": "add",
            "arguments": {"x": x_value, "y": 0}  # Identity to set x
        },
        "check_condition": {
            "process_id": "gt",
            "arguments": {"x": {"from_node": "x"}, "y": 10}
        },
        "double_value": {
            "process_id": "multiply",
            "arguments": {"x": {"from_node": "x"}, "y": 2}
        },
        "halve_value": {
            "process_id": "divide",
            "arguments": {"x": {"from_node": "x"}, "y": 2}
        },
        "conditional_result": {
            "process_id": "if",
            "arguments": {
                "value": {"from_node": "check_condition"},
                "accept": {"from_node": "double_value"},
                "reject": {"from_node": "halve_value"}
            },
            "result": True
        }
    }

    result = tracer.execute_with_tracing(process_graph, f"if {x_value} > 10 then {x_value}*2 else {x_value}/2")
    expected = x_value * 2  # Since 15 > 10
    print(f"  Expected: {expected}, Got: {result}")
    assert result == expected, f"FAILED: Expected {expected}, got {result}"
    print("  ✓ PASSED")


def test_ndvi_simulation():
    """Test NDVI-like normalized difference calculation."""
    tracer = TracingExecutor()

    print("\n" + "="*70)
    print("  TEST 5: NDVI Simulation - (NIR - RED) / (NIR + RED)")
    print("="*70)

    # Simulated band values
    nir = 0.8  # Near-infrared
    red = 0.2  # Red

    process_graph = {
        "nir_band": {
            "process_id": "add",
            "arguments": {"x": nir, "y": 0}  # Identity
        },
        "red_band": {
            "process_id": "add",
            "arguments": {"x": red, "y": 0}  # Identity
        },
        "difference": {
            "process_id": "subtract",
            "arguments": {
                "x": {"from_node": "nir_band"},
                "y": {"from_node": "red_band"}
            }
        },
        "sum": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "nir_band"},
                "y": {"from_node": "red_band"}
            }
        },
        "ndvi": {
            "process_id": "divide",
            "arguments": {
                "x": {"from_node": "difference"},
                "y": {"from_node": "sum"}
            },
            "result": True
        }
    }

    result = tracer.execute_with_tracing(process_graph, f"NDVI = ({nir} - {red}) / ({nir} + {red})")
    expected = (nir - red) / (nir + red)
    print(f"  Expected: {expected}, Got: {result}")
    assert abs(result - expected) < 0.0001, f"FAILED: Expected {expected}, got {result}"
    print("  ✓ PASSED")


def test_array_processing():
    """Test array processing workflow."""
    tracer = TracingExecutor()

    print("\n" + "="*70)
    print("  TEST 6: Array Processing - first + last + mean")
    print("="*70)

    data = [100, 200, 300, 400, 500]

    process_graph = {
        "get_first": {
            "process_id": "first",
            "arguments": {"data": data}
        },
        "get_last": {
            "process_id": "last",
            "arguments": {"data": data}
        },
        "get_mean": {
            "process_id": "mean",
            "arguments": {"data": data}
        },
        "sum_first_last": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "get_first"},
                "y": {"from_node": "get_last"}
            }
        },
        "total": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "sum_first_last"},
                "y": {"from_node": "get_mean"}
            },
            "result": True
        }
    }

    result = tracer.execute_with_tracing(process_graph, f"first + last + mean of {data}")
    expected = 100 + 500 + 300  # first=100, last=500, mean=300
    print(f"  Expected: {expected}, Got: {result}")
    assert result == expected, f"FAILED: Expected {expected}, got {result}"
    print("  ✓ PASSED")


def test_complex_math():
    """Test complex mathematical expression."""
    tracer = TracingExecutor()

    print("\n" + "="*70)
    print("  TEST 7: Complex Math - sqrt(16) * ln(e) + abs(-5)")
    print("="*70)

    import math

    process_graph = {
        "sqrt_16": {
            "process_id": "sqrt",
            "arguments": {"x": 16}
        },
        "ln_e": {
            "process_id": "ln",
            "arguments": {"x": math.e}
        },
        "abs_neg5": {
            "process_id": "absolute",
            "arguments": {"x": -5}
        },
        "sqrt_times_ln": {
            "process_id": "multiply",
            "arguments": {
                "x": {"from_node": "sqrt_16"},
                "y": {"from_node": "ln_e"}
            }
        },
        "final_result": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "sqrt_times_ln"},
                "y": {"from_node": "abs_neg5"}
            },
            "result": True
        }
    }

    result = tracer.execute_with_tracing(process_graph, "sqrt(16) * ln(e) + |−5|")
    expected = 4 * 1 + 5  # sqrt(16)=4, ln(e)=1, abs(-5)=5
    print(f"  Expected: {expected}, Got: {result}")
    assert result == expected, f"FAILED: Expected {expected}, got {result}"
    print("  ✓ PASSED")


def test_comparison_chain():
    """Test chained comparisons."""
    tracer = TracingExecutor()

    print("\n" + "="*70)
    print("  TEST 8: Comparison Chain - (x > 5) AND (x < 15) AND (x != 10)")
    print("="*70)

    x_value = 12

    process_graph = {
        "x": {"process_id": "add", "arguments": {"x": x_value, "y": 0}},
        "gt_5": {
            "process_id": "gt",
            "arguments": {"x": {"from_node": "x"}, "y": 5}
        },
        "lt_15": {
            "process_id": "lt",
            "arguments": {"x": {"from_node": "x"}, "y": 15}
        },
        "neq_10": {
            "process_id": "neq",
            "arguments": {"x": {"from_node": "x"}, "y": 10}
        },
        "and_1": {
            "process_id": "and",
            "arguments": {
                "x": {"from_node": "gt_5"},
                "y": {"from_node": "lt_15"}
            }
        },
        "and_2": {
            "process_id": "and",
            "arguments": {
                "x": {"from_node": "and_1"},
                "y": {"from_node": "neq_10"}
            },
            "result": True
        }
    }

    result = tracer.execute_with_tracing(process_graph, f"({x_value} > 5) AND ({x_value} < 15) AND ({x_value} != 10)")
    # 12 > 5 = True, 12 < 15 = True, 12 != 10 = True → True AND True AND True = True
    print(f"  Expected: True (1), Got: {result}")
    assert result == True or result == 1, f"FAILED: Expected True, got {result}"
    print("  ✓ PASSED")


def main():
    """Run all step-by-step tests."""
    print("\n" + "="*70)
    print("  OPENEO PROCESS GRAPH STEP-BY-STEP EXECUTION TEST")
    print("  Testing complex workflows with detailed tracing")
    print("="*70)

    tests = [
        ("Chained Calculations", test_chained_calculations),
        ("Statistics Chain", test_statistics_chain),
        ("Trigonometric Identity", test_trig_identity),
        ("Conditional Workflow", test_conditional_workflow),
        ("NDVI Simulation", test_ndvi_simulation),
        ("Array Processing", test_array_processing),
        ("Complex Math", test_complex_math),
        ("Comparison Chain", test_comparison_chain),
    ]

    passed = 0
    failed = 0
    results = {}

    for name, test_func in tests:
        try:
            test_func()
            results[name] = "PASSED"
            passed += 1
        except Exception as e:
            results[name] = f"FAILED: {e}"
            failed += 1
            import traceback
            traceback.print_exc()

    # Summary
    print("\n" + "="*70)
    print("  FINAL SUMMARY")
    print("="*70)
    for name, status in results.items():
        symbol = "✓" if status == "PASSED" else "✗"
        print(f"  {symbol} {name}: {status}")
    print()
    print(f"  Total: {passed} passed, {failed} failed")
    print("="*70)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
