#!/usr/bin/env python3
"""
Comprehensive tests for quality metrics, geospatial validation, and uncertainty indicators.

Tests:
- Geospatial validation (CRS, antimeridian, coordinates)
- Quality metrics (cloud coverage, temporal coverage)
- Quality dashboard visualization
- Integration with existing tools
"""

import asyncio
import json
import sys

# Add project to path
sys.path.insert(0, '/Users/macbookpro/openeo-deployment')


def test_geospatial_validation():
    """Test geospatial validation utilities."""
    print("\n" + "="*60)
    print("TEST: Geospatial Validation")
    print("="*60)

    from openeo_ai.utils.geospatial import (
        GeospatialValidator,
        validate_extent,
        validate_crs,
        split_antimeridian,
        get_utm_zone_for_extent,
        SUPPORTED_CRS,
    )

    validator = GeospatialValidator()

    # Test 1: Valid extent
    print("\n1. Valid extent validation:")
    result = validator.validate_extent({
        "west": 11.0, "south": 46.0,
        "east": 12.0, "north": 47.0
    })
    assert result.valid == True, "Valid extent should pass"
    print(f"   ✓ Valid extent: {result.valid}")

    # Test 2: Invalid extent (south > north)
    print("\n2. Invalid extent (south > north):")
    result = validator.validate_extent({
        "west": 11.0, "south": 47.0,
        "east": 12.0, "north": 46.0
    })
    assert result.valid == False, "Should fail when south > north"
    assert any("south" in e.lower() for e in result.errors)
    print(f"   ✓ Detected error: {result.errors[0]}")

    # Test 3: Antimeridian crossing
    print("\n3. Antimeridian crossing detection:")
    result = validator.validate_extent({
        "west": 170.0, "south": -10.0,
        "east": -170.0, "north": 10.0
    })
    assert any("antimeridian" in w.lower() for w in result.warnings)
    print(f"   ✓ Detected: {result.warnings[0]}")
    print(f"   ✓ Normalized extent: {result.normalized_extent}")

    # Test 4: Split antimeridian extent
    print("\n4. Antimeridian extent splitting:")
    extents = split_antimeridian({
        "west": 170.0, "south": -10.0,
        "east": -170.0, "north": 10.0
    })
    assert len(extents) == 2, "Should split into two extents"
    print(f"   ✓ Split into {len(extents)} extents:")
    for i, ext in enumerate(extents):
        print(f"      {i+1}. {ext}")

    # Test 5: CRS validation
    print("\n5. CRS validation:")
    crs_result = validate_crs("EPSG:4326")
    assert crs_result["valid"] == True
    print(f"   ✓ EPSG:4326 valid: {crs_result['valid']}")
    print(f"   ✓ Info: {crs_result['info']['name']}")

    crs_result = validate_crs("INVALID:1234")
    assert crs_result["valid"] == False
    print(f"   ✓ INVALID:1234 valid: {crs_result['valid']}")

    # Test 6: UTM zone detection
    print("\n6. UTM zone detection:")
    utm = get_utm_zone_for_extent({
        "west": 11.0, "south": 46.0,
        "east": 12.0, "north": 47.0
    })
    assert "EPSG:326" in utm  # Northern hemisphere
    print(f"   ✓ UTM zone for Alps region: {utm}")

    # Test 7: Area calculation
    print("\n7. Area calculation:")
    area = validator.calculate_area_km2({
        "west": 11.0, "south": 46.0,
        "east": 12.0, "north": 47.0
    })
    print(f"   ✓ Area: {area:.0f} km² (approximately 1° x 1° box)")
    assert 7000 < area < 10000, "Area should be roughly 8000-9000 km²"

    # Test 8: Polar region warning
    print("\n8. Polar region detection:")
    result = validator.validate_extent({
        "west": -180, "south": 85.0,
        "east": 180, "north": 90.0
    })
    assert any("polar" in w.lower() for w in result.warnings)
    print(f"   ✓ Polar warning: {result.warnings[0]}")

    # Test 9: Supported CRS list
    print("\n9. Supported CRS:")
    print(f"   ✓ {len(SUPPORTED_CRS)} CRS definitions available")
    for crs_id in SUPPORTED_CRS:
        print(f"      - {crs_id}: {SUPPORTED_CRS[crs_id]['name']}")

    print("\n✅ Geospatial validation tests PASSED")
    return True


def test_quality_metrics():
    """Test quality metrics calculation."""
    print("\n" + "="*60)
    print("TEST: Quality Metrics")
    print("="*60)

    from openeo_ai.utils.quality_metrics import (
        QualityMetricsCalculator,
        estimate_cloud_coverage,
        estimate_temporal_coverage,
        get_quality_metrics,
    )

    calculator = QualityMetricsCalculator()

    # Test 1: Cloud coverage estimation
    print("\n1. Cloud coverage estimation:")
    cloud = calculator.estimate_cloud_coverage(
        collection="sentinel-2-l2a",
        spatial_extent={"west": 11.0, "south": 46.0, "east": 12.0, "north": 47.0},
        temporal_extent=["2024-06-01", "2024-06-30"]
    )
    print(f"   ✓ Estimated cloud cover: {cloud.estimated_percentage*100:.1f}%")
    print(f"   ✓ Confidence: {cloud.confidence}")
    print(f"   ✓ Usable scenes: ~{cloud.usable_scenes_estimate}/{cloud.total_scenes_estimate}")
    assert 0 <= cloud.estimated_percentage <= 1

    # Test 2: Different regions have different cloud factors
    print("\n2. Regional cloud factor variation:")
    cloud_tropical = calculator.estimate_cloud_coverage(
        collection="sentinel-2-l2a",
        spatial_extent={"west": 0, "south": -5, "east": 1, "north": 5},  # Tropical
        temporal_extent=["2024-06-01", "2024-06-30"]
    )
    cloud_temperate = calculator.estimate_cloud_coverage(
        collection="sentinel-2-l2a",
        spatial_extent={"west": 11.0, "south": 46.0, "east": 12.0, "north": 47.0},  # Temperate
        temporal_extent=["2024-06-01", "2024-06-30"]
    )
    print(f"   ✓ Tropical (equator): {cloud_tropical.estimated_percentage*100:.1f}%")
    print(f"   ✓ Temperate (Alps): {cloud_temperate.estimated_percentage*100:.1f}%")
    assert cloud_tropical.regional_adjustment > cloud_temperate.regional_adjustment

    # Test 3: Temporal coverage estimation
    print("\n3. Temporal coverage estimation:")
    temporal = calculator.estimate_temporal_coverage(
        collection="sentinel-2-l2a",
        temporal_extent=["2024-01-01", "2024-06-30"],
        cloud_coverage=cloud
    )
    print(f"   ✓ Requested days: {temporal.requested_days}")
    print(f"   ✓ Expected acquisitions: {temporal.expected_acquisitions}")
    print(f"   ✓ Expected cloud-free: {temporal.expected_cloud_free}")
    print(f"   ✓ Coverage: {temporal.coverage_percentage*100:.1f}%")
    print(f"   ✓ Gaps likely: {temporal.gaps_likely}")

    # Test 4: SAR collection (no clouds)
    print("\n4. SAR collection (no cloud issues):")
    cloud_sar = calculator.estimate_cloud_coverage(
        collection="sentinel-1-grd",
        spatial_extent={"west": 11.0, "south": 46.0, "east": 12.0, "north": 47.0},
        temporal_extent=["2024-06-01", "2024-06-30"]
    )
    assert cloud_sar.estimated_percentage == 0
    print(f"   ✓ SAR cloud cover: {cloud_sar.estimated_percentage*100:.1f}% (as expected)")

    # Test 5: Comprehensive quality metrics
    print("\n5. Comprehensive quality metrics:")
    metrics = calculator.calculate_quality_metrics(
        collection="sentinel-2-l2a",
        spatial_extent={"west": 11.0, "south": 46.0, "east": 12.0, "north": 47.0},
        temporal_extent=["2024-06-01", "2024-06-30"]
    )
    print(f"   ✓ Overall score: {metrics.overall_quality_score*100:.1f}%")
    print(f"   ✓ Quality grade: {metrics.quality_grade}")
    print(f"   ✓ Data freshness: {metrics.data_freshness}")
    print(f"   ✓ Spatial completeness: {metrics.spatial_completeness*100:.1f}%")
    if metrics.recommendations:
        print(f"   ✓ Recommendations: {len(metrics.recommendations)}")
        for rec in metrics.recommendations[:3]:
            print(f"      - {rec}")

    # Test 6: Convenience functions
    print("\n6. Convenience functions:")
    result = get_quality_metrics(
        collection="landsat-c2-l2",
        spatial_extent={"west": -122.5, "south": 37.5, "east": -122.0, "north": 38.0},
        temporal_extent=["2024-01-01", "2024-03-31"]
    )
    print(f"   ✓ get_quality_metrics returns dict: {type(result) == dict}")
    print(f"   ✓ Contains quality_grade: {'quality_grade' in result}")
    print(f"   ✓ Grade: {result['quality_grade']}")

    print("\n✅ Quality metrics tests PASSED")
    return True


def test_quality_dashboard():
    """Test quality dashboard visualization."""
    print("\n" + "="*60)
    print("TEST: Quality Dashboard")
    print("="*60)

    from openeo_ai.visualization.quality_dashboard import (
        QualityDashboard,
        generate_quality_html,
    )
    from openeo_ai.utils.quality_metrics import get_quality_metrics

    dashboard = QualityDashboard()

    # Test 1: Create quality dashboard
    print("\n1. Quality dashboard creation:")
    metrics = get_quality_metrics(
        collection="sentinel-2-l2a",
        spatial_extent={"west": 11.0, "south": 46.0, "east": 12.0, "north": 47.0},
        temporal_extent=["2024-06-01", "2024-06-30"]
    )

    async def test_dashboard():
        result = await dashboard.create_quality_dashboard(metrics, "Test Dashboard")
        return result

    dash_result = asyncio.run(test_dashboard())
    assert dash_result["type"] == "quality_dashboard"
    assert "spec" in dash_result
    assert "grade" in dash_result["spec"]
    assert "sections" in dash_result["spec"]
    print(f"   ✓ Dashboard type: {dash_result['type']}")
    print(f"   ✓ Grade: {dash_result['spec']['grade']}")
    print(f"   ✓ Sections: {len(dash_result['spec']['sections'])}")

    # Test 2: Dashboard sections
    print("\n2. Dashboard sections:")
    for section in dash_result["spec"]["sections"]:
        print(f"   ✓ Section: {section['type']} - {section['title']}")

    # Test 3: Quality badge
    print("\n3. Quality badge:")
    async def test_badge():
        badge = await dashboard.create_simple_quality_badge("B", 78.5)
        return badge

    badge = asyncio.run(test_badge())
    assert badge["type"] == "badge"
    print(f"   ✓ Badge type: {badge['type']}")
    print(f"   ✓ Badge text: {badge['spec']['text']}")

    # Test 4: Cloud indicator
    print("\n4. Cloud indicator:")
    async def test_indicator():
        indicator = await dashboard.create_cloud_indicator(45.5, 8, 12)
        return indicator

    indicator = asyncio.run(test_indicator())
    assert indicator["type"] == "indicator"
    print(f"   ✓ Indicator type: {indicator['type']}")
    print(f"   ✓ Value: {indicator['spec']['value']}")
    print(f"   ✓ Severity: {indicator['spec']['severity']}")

    # Test 5: HTML generation
    print("\n5. HTML generation:")
    html = generate_quality_html(metrics)
    assert "quality-dashboard" in html
    assert "Cloud Coverage" in html
    assert "Temporal Coverage" in html
    print(f"   ✓ HTML generated: {len(html)} characters")
    print(f"   ✓ Contains dashboard class: {'quality-dashboard' in html}")

    print("\n✅ Quality dashboard tests PASSED")
    return True


def test_tool_integration():
    """Test tool integration for quality and validation features."""
    print("\n" + "="*60)
    print("TEST: Tool Integration")
    print("="*60)

    from openeo_ai.sdk.client import TOOL_DEFINITIONS, OpenEOAIClient

    # Test 1: Check new tools are registered
    print("\n1. New tool definitions:")
    tool_names = [t["name"] for t in TOOL_DEFINITIONS]

    required_tools = [
        "openeo_quality_metrics",
        "openeo_validate_geospatial",
    ]

    for tool_name in required_tools:
        assert tool_name in tool_names, f"Missing tool: {tool_name}"
        print(f"   ✓ Tool registered: {tool_name}")

    # Test 2: Check tool schemas
    print("\n2. Tool schemas:")
    quality_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "openeo_quality_metrics")
    assert "spatial_extent" in quality_tool["input_schema"]["properties"]
    assert "temporal_extent" in quality_tool["input_schema"]["properties"]
    print(f"   ✓ openeo_quality_metrics has spatial_extent: True")
    print(f"   ✓ openeo_quality_metrics has temporal_extent: True")

    geospatial_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "openeo_validate_geospatial")
    assert "crs" in geospatial_tool["input_schema"]["properties"]
    print(f"   ✓ openeo_validate_geospatial has crs: True")

    # Test 3: Check system prompt updates
    print("\n3. System prompt guidance:")
    prompt = OpenEOAIClient.SYSTEM_PROMPT
    checks = [
        ("openeo_quality_metrics", "Quality metrics tool reference"),
        ("cloud coverage", "Cloud coverage guidance"),
        ("quality grade", "Quality grade guidance"),
        ("openeo_validate_geospatial", "Geospatial validation reference"),
    ]
    for keyword, description in checks:
        assert keyword.lower() in prompt.lower(), f"Missing: {description}"
        print(f"   ✓ {description}")

    # Test 4: Total tool count
    print(f"\n4. Total tools available: {len(TOOL_DEFINITIONS)}")

    print("\n✅ Tool integration tests PASSED")
    return True


def test_web_interface():
    """Test web interface quality dashboard support."""
    print("\n" + "="*60)
    print("TEST: Web Interface Support")
    print("="*60)

    with open('/Users/macbookpro/openeo-deployment/openeo_ai/web_interface.py', 'r') as f:
        content = f.read()

    # Test 1: Quality dashboard handler
    print("\n1. Quality dashboard handler:")
    assert "quality_dashboard" in content
    print(f"   ✓ quality_dashboard type handler present")

    # Test 2: Grade colors
    print("\n2. Grade colors:")
    assert "gradeColors" in content
    print(f"   ✓ Grade color mapping present")

    # Test 3: Section rendering
    print("\n3. Section rendering:")
    assert "Cloud Coverage" in content
    assert "Temporal Coverage" in content
    print(f"   ✓ Cloud Coverage section")
    print(f"   ✓ Temporal Coverage section")

    print("\n✅ Web interface tests PASSED")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("  QUALITY METRICS & VALIDATION FEATURE TESTS")
    print("="*70)

    tests = [
        ("Geospatial Validation", test_geospatial_validation),
        ("Quality Metrics", test_quality_metrics),
        ("Quality Dashboard", test_quality_dashboard),
        ("Tool Integration", test_tool_integration),
        ("Web Interface Support", test_web_interface),
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
        print("\n🎉 ALL QUALITY TESTS PASSED!")
        print("\n📋 Implemented features:")
        print("  • Geospatial validation (CRS, antimeridian, coordinates)")
        print("  • Cloud coverage estimation")
        print("  • Temporal coverage analysis")
        print("  • Quality grade calculation (A-F)")
        print("  • Quality dashboard visualization")
        print("  • Tool integration (openeo_quality_metrics, openeo_validate_geospatial)")
        print("  • Web interface dashboard rendering")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
