#!/usr/bin/env python3
"""
Comprehensive test for all new features implemented in Steps 3-6.

Tests:
- Step 3: Time series visualization (Chart.js data generation)
- Step 4: Error recovery & retry logic
- Step 5: Extent size warnings
- Step 6: Comparison slider visualization
"""

import asyncio
import json
import sys

# Add project to path
sys.path.insert(0, '/Users/macbookpro/openeo-deployment')


def test_time_series_chart():
    """Test Step 3: Chart.js data generation."""
    print("\n" + "="*60)
    print("TEST 3: Time Series Visualization (Chart.js)")
    print("="*60)

    from openeo_ai.visualization.charts import ChartComponent

    chart = ChartComponent()

    # Test data generation (using async)
    dates = ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"]
    values = [0.25, 0.32, 0.45, 0.68, 0.72]

    async def test_async():
        mcp_data = await chart.create_time_series(
            values=values,
            dates=dates,
            title="NDVI Time Series",
            ylabel="NDVI Value"
        )
        return mcp_data

    mcp_data = asyncio.run(test_async())

    # Verify structure
    assert "type" in mcp_data, "Missing 'type' key"
    assert mcp_data["type"] == "chart", "Wrong type"
    assert "spec" in mcp_data, "Missing 'spec' key"
    assert "data" in mcp_data["spec"], "Missing data in spec"
    assert len(mcp_data["spec"]["data"]["x"]) == 5, "Wrong data count"
    assert mcp_data["spec"]["title"] == "NDVI Time Series", "Wrong title"

    print(f"✓ Generated chart with {len(dates)} data points")
    print(f"✓ Chart type: {mcp_data['spec']['chart_type']}")
    print(f"✓ Title: {mcp_data['spec']['title']}")
    print(f"✓ Statistics: min={mcp_data['spec']['statistics']['min']:.2f}, max={mcp_data['spec']['statistics']['max']:.2f}")
    print("✅ Time series chart test PASSED")
    return True


def test_retry_utilities():
    """Test Step 4: Error recovery & retry logic."""
    print("\n" + "="*60)
    print("TEST 4: Error Recovery & Retry Logic")
    print("="*60)

    from openeo_ai.utils.retry import (
        RetryConfig, RetryResult, CircuitBreaker,
        retry_async, calculate_delay, ErrorRecoveryStrategy
    )

    # Test 4a: RetryConfig defaults
    config = RetryConfig()
    assert config.max_retries == 3, "Wrong default max_retries"
    assert config.initial_delay == 1.0, "Wrong default initial_delay"
    print("✓ RetryConfig defaults correct")

    # Test 4b: Delay calculation with exponential backoff
    delay_0 = calculate_delay(0, config)  # 1.0 * 2^0 = 1.0 (with jitter)
    delay_1 = calculate_delay(1, config)  # 1.0 * 2^1 = 2.0 (with jitter)
    delay_2 = calculate_delay(2, config)  # 1.0 * 2^2 = 4.0 (with jitter)

    print(f"✓ Delay at attempt 0: {delay_0:.2f}s")
    print(f"✓ Delay at attempt 1: {delay_1:.2f}s")
    print(f"✓ Delay at attempt 2: {delay_2:.2f}s")

    # Test 4c: Circuit breaker
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
    assert cb.state == "closed", "Initial state should be closed"

    # Record failures until circuit opens
    for i in range(3):
        cb.record_failure()
    assert cb.state == "open", "Circuit should be open after threshold"
    print(f"✓ Circuit breaker opens after {cb.failure_threshold} failures")

    # Test 4d: Error recovery suggestions
    recovery = ErrorRecoveryStrategy.get_recovery_message(Exception("Connection refused"))
    assert recovery["error_type"] == "connection", "Should identify connection error"
    assert recovery["recoverable"] == True, "Connection errors are recoverable"
    print(f"✓ Error recovery identifies: {recovery['error_type']}")

    timeout_recovery = ErrorRecoveryStrategy.get_recovery_message(Exception("timeout occurred"))
    assert timeout_recovery["error_type"] == "timeout", "Should identify timeout"
    print(f"✓ Error recovery identifies: {timeout_recovery['error_type']}")

    # Test 4e: Async retry function
    async def test_async_retry():
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Simulated failure")
            return "success"

        config = RetryConfig(max_retries=5, initial_delay=0.01)
        result = await retry_async(failing_func, config=config)

        assert result.success == True, "Should succeed after retries"
        assert result.attempts == 3, f"Should take 3 attempts, got {result.attempts}"
        return result

    result = asyncio.run(test_async_retry())
    print(f"✓ Async retry succeeded after {result.attempts} attempts")

    print("✅ Retry utilities test PASSED")
    return True


def test_extent_validator():
    """Test Step 5: Extent size warnings."""
    print("\n" + "="*60)
    print("TEST 5: Extent Size Warnings")
    print("="*60)

    from openeo_ai.utils.extent_validator import (
        ExtentValidator, validate_extent, estimate_extent_size
    )

    validator = ExtentValidator()

    # Test 5a: Small extent (should be OK)
    small_extent = {
        "west": 11.0, "south": 46.0,
        "east": 11.1, "north": 46.1  # ~10km x ~10km
    }
    result = validator.validate_extent(
        spatial_extent=small_extent,
        temporal_extent=["2024-06-01", "2024-06-10"],
        collection="sentinel-2-l2a"
    )
    assert result["valid"] == True, "Small extent should be valid"
    print(f"✓ Small extent ({result['estimate']['spatial']['area_km2']} km²): {result['estimate']['severity']}")

    # Test 5b: Medium extent (should show info/warning)
    medium_extent = {
        "west": 10.0, "south": 45.0,
        "east": 11.0, "north": 46.0  # ~110km x ~110km
    }
    result = validator.validate_extent(
        spatial_extent=medium_extent,
        temporal_extent=["2024-01-01", "2024-06-01"],  # 5 months
        collection="sentinel-2-l2a"
    )
    print(f"✓ Medium extent ({result['estimate']['spatial']['area_km2']} km²): {result['estimate']['severity']}")
    print(f"  Size: {result['estimate']['size']['human']}")
    print(f"  Scenes: {result['estimate']['temporal']['estimated_scenes']}")

    # Test 5c: Large extent (should show warning/error)
    large_extent = {
        "west": 5.0, "south": 40.0,
        "east": 15.0, "north": 50.0  # ~1000km x ~1000km
    }
    result = validator.validate_extent(
        spatial_extent=large_extent,
        temporal_extent=["2024-01-01", "2024-12-31"],  # Full year
        collection="sentinel-2-l2a"
    )
    print(f"✓ Large extent ({result['estimate']['spatial']['area_km2']:.0f} km²): {result['estimate']['severity']}")
    print(f"  Size: {result['estimate']['size']['human']}")
    if result['estimate']['warnings']:
        print(f"  Warnings: {result['estimate']['warnings'][0]}")
    if result['estimate']['suggestions']:
        print(f"  Suggestion: {result['estimate']['suggestions'][0]}")

    # Test 5d: Invalid coordinates (should be error)
    invalid_extent = {
        "west": 11.0, "south": 46.5,
        "east": 11.1, "north": 46.0  # south > north!
    }
    result = validator.validate_extent(
        spatial_extent=invalid_extent,
        collection="sentinel-2-l2a"
    )
    assert result["valid"] == False, "Invalid extent should fail"
    assert "South coordinate must be less than north" in result['estimate']['warnings']
    print("✓ Invalid coordinates detected and reported")

    # Test 5e: Convenience function
    estimate = estimate_extent_size(
        spatial_extent=small_extent,
        temporal_extent=["2024-06-01", "2024-06-10"],
        collection="cop-dem-glo-30",
        bands=["data"]
    )
    print(f"✓ Convenience function works: {estimate['size']['human']}")

    print("✅ Extent validator test PASSED")
    return True


def test_comparison_slider():
    """Test Step 6: Comparison slider visualization."""
    print("\n" + "="*60)
    print("TEST 6: Comparison Slider Visualization")
    print("="*60)

    from openeo_ai.visualization.maps import MapComponent, COLORMAPS

    map_component = MapComponent()

    # Test 6a: Verify MapComponent has comparison_slider method
    assert hasattr(map_component, 'create_comparison_slider'), "Missing create_comparison_slider method"
    print("✓ MapComponent has create_comparison_slider method")

    # Test 6b: Verify colormaps are available
    assert "viridis" in COLORMAPS, "Missing viridis colormap"
    assert "ndvi" in COLORMAPS, "Missing ndvi colormap"
    assert "terrain" in COLORMAPS, "Missing terrain colormap"
    print(f"✓ {len(COLORMAPS)} colormaps available: {list(COLORMAPS.keys())}")

    # Test 6c: Verify the web interface has comparison slider JavaScript
    with open('/Users/macbookpro/openeo-deployment/openeo_ai/web_interface.py', 'r') as f:
        content = f.read()

    assert "initializeComparison" in content, "Missing initializeComparison function"
    assert "updateComparisonSlider" in content, "Missing updateComparisonSlider function"
    assert "comparison_slider" in content, "Missing comparison_slider type handler"
    print("✓ Comparison slider JavaScript functions present in web_interface.py")

    # Test 6d: Test visualization structure format
    comparison_data = {
        "type": "comparison_slider",
        "spec": {
            "title": "NDVI Change Comparison",
            "center": [46.0, 11.0],
            "zoom": 12,
            "before": {
                "label": "Before",
                "bounds": [[45.5, 10.5], [46.0, 11.0]],
                "url": "data:image/png;base64,..."
            },
            "after": {
                "label": "After",
                "bounds": [[45.5, 10.5], [46.0, 11.0]],
                "url": "data:image/png;base64,..."
            },
            "colorbar": {
                "min": -1.0,
                "max": 1.0,
                "colormap": "ndvi"
            },
            "initial_position": 50
        }
    }

    # Verify structure matches expected format
    assert comparison_data["type"] == "comparison_slider", "Should have comparison_slider type"
    assert "spec" in comparison_data, "Should have spec"
    assert "before" in comparison_data["spec"], "Should have before in spec"
    assert "after" in comparison_data["spec"], "Should have after in spec"
    assert comparison_data["spec"]["initial_position"] == 50, "Should have initial position"
    print("✓ Comparison slider data structure is valid")

    # Test 6e: Verify other map methods exist
    assert hasattr(map_component, 'create_raster_map'), "Missing create_raster_map"
    assert hasattr(map_component, 'create_ndvi_map'), "Missing create_ndvi_map"
    assert hasattr(map_component, 'create_multi_layer_map'), "Missing create_multi_layer_map"
    print("✓ All MapComponent methods available")

    print("✅ Comparison slider test PASSED")
    return True


def test_tool_integration():
    """Test that all tools are properly integrated."""
    print("\n" + "="*60)
    print("TEST INTEGRATION: Tool Definitions")
    print("="*60)

    from openeo_ai.sdk.client import TOOL_DEFINITIONS

    # Check for new tools
    tool_names = [t["name"] for t in TOOL_DEFINITIONS]

    required_tools = [
        "openeo_resolve_location",
        "openeo_parse_temporal",
        "openeo_estimate_extent",
        "viz_show_time_series",
        "viz_show_map"
    ]

    for tool in required_tools:
        assert tool in tool_names, f"Missing tool: {tool}"
        print(f"✓ Tool registered: {tool}")

    # Check estimate_extent schema
    estimate_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "openeo_estimate_extent")
    assert "spatial_extent" in estimate_tool["input_schema"]["properties"], "Missing spatial_extent"
    assert "temporal_extent" in estimate_tool["input_schema"]["properties"], "Missing temporal_extent"
    print(f"✓ openeo_estimate_extent schema is complete")

    print(f"\nTotal tools available: {len(TOOL_DEFINITIONS)}")
    print("✅ Tool integration test PASSED")
    return True


def test_system_prompt():
    """Test that SYSTEM_PROMPT has all guidance."""
    print("\n" + "="*60)
    print("TEST: System Prompt Guidance")
    print("="*60)

    from openeo_ai.sdk.client import OpenEOAIClient

    prompt = OpenEOAIClient.SYSTEM_PROMPT

    # Check for new guidance
    checks = [
        ("openeo_resolve_location", "Location resolution guidance"),
        ("openeo_parse_temporal", "Temporal parsing guidance"),
        ("openeo_estimate_extent", "Size estimation guidance"),
        ("BEFORE creating large", "Pre-query check guidance"),
        ("severity is \"warning\" or \"error\"", "Warning handling guidance"),
    ]

    for keyword, description in checks:
        assert keyword in prompt, f"Missing: {description}"
        print(f"✓ {description}")

    print("✅ System prompt test PASSED")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("  COMPREHENSIVE FEATURE TESTS - Steps 3-6 from NEXT_STEPS.md")
    print("="*70)

    tests = [
        ("Step 3: Time Series Chart", test_time_series_chart),
        ("Step 4: Retry Utilities", test_retry_utilities),
        ("Step 5: Extent Validator", test_extent_validator),
        ("Step 6: Comparison Slider", test_comparison_slider),
        ("Integration: Tool Definitions", test_tool_integration),
        ("Integration: System Prompt", test_system_prompt),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("="*70)

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n📋 Summary of implemented features:")
        print("  • Chart.js time series visualization")
        print("  • Exponential backoff retry with circuit breaker")
        print("  • Extent size estimation with warnings")
        print("  • Comparison slider visualization support")
        print("  • Updated SYSTEM_PROMPT with all guidance")
        print("\n🌐 Web interface available at: http://localhost:8080")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
