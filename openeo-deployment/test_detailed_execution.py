#!/usr/bin/env python3
"""
Detailed execution test showing each node being processed.
Patches the executor to log each step with input/output values.
"""

import sys
import os
sys.path.insert(0, '/Users/macbookpro/openeo-deployment')
os.environ.setdefault('STAC_API_URL', 'https://earth-search.aws.element84.com/v1/')

from functools import wraps


def trace_execution(process_graph, executor):
    """Execute with detailed tracing of each node."""
    from openeo_pg_parser_networkx import OpenEOProcessGraph

    print("\n" + "="*70)
    print("  DETAILED NODE-BY-NODE EXECUTION TRACE")
    print("="*70)

    # Parse the graph
    if "process_graph" in process_graph:
        pg_data = process_graph["process_graph"]
    else:
        pg_data = process_graph

    pg = OpenEOProcessGraph(pg_data=pg_data)

    print(f"\n  Total nodes: {len(pg.nodes)}")
    print(f"  Required processes: {pg.required_processes}")

    # Get the topological order of nodes
    print("\n  Process Graph Structure:")
    print("-" * 60)

    for node_id, node in pg_data.items():
        process_id = node['process_id']
        args = node['arguments']
        is_result = node.get('result', False)

        print(f"\n  Node: {node_id}")
        print(f"    Process: {process_id}")
        print(f"    Arguments:")
        for arg_name, arg_val in args.items():
            if isinstance(arg_val, dict) and 'from_node' in arg_val:
                print(f"      {arg_name}: <from {arg_val['from_node']}>")
            else:
                print(f"      {arg_name}: {arg_val}")
        if is_result:
            print(f"    [FINAL RESULT NODE]")

    print("\n" + "-" * 60)
    print("  EXECUTION LOG:")
    print("-" * 60)

    # Now we'll patch the process implementations to log their execution
    original_registry = executor._process_registry.copy()
    execution_log = []

    def make_traced_impl(process_id, original_impl):
        @wraps(original_impl)
        def traced(*args, **kwargs):
            # Remove named_parameters for cleaner logging
            log_kwargs = {k: v for k, v in kwargs.items() if k != 'named_parameters'}

            print(f"\n  >> Executing: {process_id}")
            print(f"     Inputs: {log_kwargs}")

            result = original_impl(*args, **kwargs)

            # Format result for display
            if hasattr(result, 'shape'):
                result_str = f"<array shape={result.shape}>"
            elif isinstance(result, (list, tuple)) and len(result) > 5:
                result_str = f"{result[:3]}...{result[-1]}"
            else:
                result_str = str(result)

            print(f"     Output: {result_str}")
            execution_log.append({
                'process': process_id,
                'inputs': log_kwargs,
                'output': result
            })
            return result
        return traced

    # Patch all processes
    from openeo_pg_parser_networkx.process_registry import Process
    for process_id, process_obj in executor._process_registry.items():
        traced_impl = make_traced_impl(process_id, process_obj.implementation)
        executor._process_registry[process_id] = Process(
            spec=process_obj.spec,
            implementation=traced_impl
        )

    # Execute
    print("\n  Starting execution...")
    result = executor.execute(process_graph)

    # Restore original
    executor._process_registry = original_registry

    print("\n" + "-" * 60)
    print(f"\n  FINAL RESULT: {result}")
    print("="*70)

    return result, execution_log


def main():
    """Run detailed execution tests."""
    from openeo_app.execution.executor import ProcessGraphExecutor

    print("="*70)
    print("  OPENEO PROCESS GRAPH - DETAILED EXECUTION TRACE")
    print("="*70)

    executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')
    print(f"  Executor initialized with {len(executor.get_available_processes())} processes")

    # Test 1: Complex calculation
    print("\n\n" + "="*70)
    print("  TEST 1: Complex Calculation")
    print("  Formula: ((10 + 5) * 2 - 8) / 2 = 11")
    print("="*70)

    process_graph = {
        "add1": {
            "process_id": "add",
            "arguments": {"x": 10, "y": 5}
        },
        "mult1": {
            "process_id": "multiply",
            "arguments": {"x": {"from_node": "add1"}, "y": 2}
        },
        "sub1": {
            "process_id": "subtract",
            "arguments": {"x": {"from_node": "mult1"}, "y": 8}
        },
        "div1": {
            "process_id": "divide",
            "arguments": {"x": {"from_node": "sub1"}, "y": 2},
            "result": True
        }
    }

    result, log = trace_execution(process_graph, executor)
    expected = ((10 + 5) * 2 - 8) / 2
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"\n  ✓ TEST 1 PASSED: {result} == {expected}")

    # Test 2: Statistics with conditional
    print("\n\n" + "="*70)
    print("  TEST 2: Statistics with Conditional")
    print("  If mean > 25 then max else min")
    print("="*70)

    data = [10, 20, 30, 40, 50]

    process_graph = {
        "calc_mean": {
            "process_id": "mean",
            "arguments": {"data": data}
        },
        "calc_max": {
            "process_id": "max",
            "arguments": {"data": data}
        },
        "calc_min": {
            "process_id": "min",
            "arguments": {"data": data}
        },
        "check_threshold": {
            "process_id": "gt",
            "arguments": {"x": {"from_node": "calc_mean"}, "y": 25}
        },
        "conditional_result": {
            "process_id": "if",
            "arguments": {
                "value": {"from_node": "check_threshold"},
                "accept": {"from_node": "calc_max"},
                "reject": {"from_node": "calc_min"}
            },
            "result": True
        }
    }

    result, log = trace_execution(process_graph, executor)
    # mean=30 > 25, so result should be max=50
    expected = 50
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"\n  ✓ TEST 2 PASSED: {result} == {expected}")

    # Test 3: Trig + Math combo
    print("\n\n" + "="*70)
    print("  TEST 3: Trigonometry + Math Combination")
    print("  sin(π/6) + cos(π/3) + sqrt(4) = 0.5 + 0.5 + 2 = 3")
    print("="*70)

    import math

    process_graph = {
        "sin_val": {
            "process_id": "sin",
            "arguments": {"x": math.pi / 6}  # sin(30°) = 0.5
        },
        "cos_val": {
            "process_id": "cos",
            "arguments": {"x": math.pi / 3}  # cos(60°) = 0.5
        },
        "sqrt_val": {
            "process_id": "sqrt",
            "arguments": {"x": 4}  # sqrt(4) = 2
        },
        "sum1": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "sin_val"},
                "y": {"from_node": "cos_val"}
            }
        },
        "sum2": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "sum1"},
                "y": {"from_node": "sqrt_val"}
            },
            "result": True
        }
    }

    result, log = trace_execution(process_graph, executor)
    expected = 0.5 + 0.5 + 2  # = 3
    assert abs(result - expected) < 0.0001, f"Expected {expected}, got {result}"
    print(f"\n  ✓ TEST 3 PASSED: {result} ≈ {expected}")

    # Summary
    print("\n\n" + "="*70)
    print("  ALL DETAILED EXECUTION TESTS PASSED!")
    print("="*70)
    print("  Each processing step was logged with:")
    print("    - Process name")
    print("    - Input values")
    print("    - Output values")
    print("="*70)


if __name__ == "__main__":
    main()
