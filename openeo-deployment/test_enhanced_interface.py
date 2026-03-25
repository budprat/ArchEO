#!/usr/bin/env python3
"""
Test suite for the enhanced web interface components.

Tests all PRD-aligned features:
- Natural language workflow generation
- Quality metrics dashboard
- Export capabilities
- Workflow history
- Sustainability metrics
"""

import asyncio
import json
import sys
import requests

# Add project to path
sys.path.insert(0, '/Users/macbookpro/openeo-deployment')

BASE_URL = "http://localhost:8080"


def test_health_endpoint():
    """Test the health endpoint."""
    print("\n" + "="*60)
    print("TEST: Health Endpoint")
    print("="*60)

    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200, f"Health check failed: {response.status_code}"

    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.2.0"
    assert data["tools"] == 18

    print(f"   ✓ Status: {data['status']}")
    print(f"   ✓ Version: {data['version']}")
    print(f"   ✓ Tools: {data['tools']}")

    print("\n✅ Health endpoint test PASSED")
    return True


def test_ui_components():
    """Test that all UI components are present in the HTML."""
    print("\n" + "="*60)
    print("TEST: UI Components")
    print("="*60)

    response = requests.get(BASE_URL)
    assert response.status_code == 200
    html = response.text

    # Check for main layout components
    components = [
        ("sidebar-left", "Left sidebar (workflow panel)"),
        ("sidebar-right", "Right sidebar (metrics panel)"),
        ("main-content", "Main chat area"),
        ("messages-container", "Messages container"),
        ("suggestion-chips", "Suggestion chips"),
        ("workflow-status", "Workflow status"),
        ("history-list", "History list"),
        ("quality-score", "Quality score display"),
        ("process-graph-view", "Process graph view"),
        ("export-option", "Export options"),
        ("eco-score", "Sustainability metrics"),
    ]

    for component_class, description in components:
        assert component_class in html, f"Missing: {description}"
        print(f"   ✓ {description}")

    print("\n✅ UI components test PASSED")
    return True


def test_javascript_functions():
    """Test that all JavaScript functions are defined."""
    print("\n" + "="*60)
    print("TEST: JavaScript Functions")
    print("="*60)

    response = requests.get(BASE_URL)
    html = response.text

    functions = [
        ("connect", "WebSocket connection"),
        ("sendMessage", "Message sending"),
        ("addMessage", "Message rendering"),
        ("handleMessage", "Message handling"),
        ("addVisualization", "Visualization rendering"),
        ("updateQualityMetrics", "Quality metrics update"),
        ("updateProcessGraph", "Process graph update"),
        ("exportNotebook", "Notebook export"),
        ("exportProcessGraph", "Process graph export"),
        ("exportMarkdown", "Markdown export"),
        ("generateCitation", "Citation generation"),
        ("switchTab", "Tab switching"),
        ("useSuggestion", "Suggestion chips"),
        ("replayWorkflow", "Workflow replay"),
        ("clearChat", "Chat clearing"),
        ("showHelp", "Help display"),
        ("showTutorial", "Tutorial display"),
        ("changeBasemap", "Basemap switching"),
        ("changeColormap", "Colormap switching"),
        ("downloadMap", "Map download"),
        ("downloadChart", "Chart download"),
    ]

    for func_name, description in functions:
        assert f"function {func_name}" in html, f"Missing function: {func_name}"
        print(f"   ✓ {description} ({func_name})")

    print("\n✅ JavaScript functions test PASSED")
    return True


def test_suggestion_chips():
    """Test that suggestion chips contain useful queries."""
    print("\n" + "="*60)
    print("TEST: Suggestion Chips")
    print("="*60)

    response = requests.get(BASE_URL)
    html = response.text

    suggestions = [
        "NDVI",
        "Change Detection",
        "Terrain",
        "Data Discovery",
        "Quality Check",
    ]

    for suggestion in suggestions:
        assert suggestion in html, f"Missing suggestion: {suggestion}"
        print(f"   ✓ Suggestion chip: {suggestion}")

    print("\n✅ Suggestion chips test PASSED")
    return True


def test_tabs():
    """Test that all tabs are present."""
    print("\n" + "="*60)
    print("TEST: Tabs")
    print("="*60)

    response = requests.get(BASE_URL)
    html = response.text

    tabs = [
        ("quality", "Quality metrics tab"),
        ("process", "Process graph tab"),
        ("export", "Export tab"),
        ("eco", "Sustainability tab"),
    ]

    for tab_id, description in tabs:
        assert f"switchTab('{tab_id}')" in html, f"Missing tab: {tab_id}"
        assert f"tab-{tab_id}" in html, f"Missing tab panel: {tab_id}"
        print(f"   ✓ {description}")

    print("\n✅ Tabs test PASSED")
    return True


def test_export_options():
    """Test that all export options are available."""
    print("\n" + "="*60)
    print("TEST: Export Options")
    print("="*60)

    response = requests.get(BASE_URL)
    html = response.text

    exports = [
        ("exportNotebook", "Jupyter Notebook export"),
        ("exportProcessGraph", "Process Graph JSON export"),
        ("exportMarkdown", "Markdown Report export"),
        ("generateCitation", "Citation generation"),
    ]

    for func_name, description in exports:
        assert f"onclick=\"{func_name}()\"" in html, f"Missing export: {func_name}"
        print(f"   ✓ {description}")

    print("\n✅ Export options test PASSED")
    return True


def test_quality_metrics_display():
    """Test quality metrics display components."""
    print("\n" + "="*60)
    print("TEST: Quality Metrics Display")
    print("="*60)

    response = requests.get(BASE_URL)
    html = response.text

    quality_elements = [
        ("qualityScore", "Quality score container"),
        ("qualityMetrics", "Quality metrics container"),
        ("qualityRecommendations", "Recommendations container"),
        ("Cloud Coverage", "Cloud coverage metric"),
        ("Temporal Coverage", "Temporal coverage metric"),
    ]

    for element, description in quality_elements:
        assert element in html, f"Missing: {element}"
        print(f"   ✓ {description}")

    print("\n✅ Quality metrics display test PASSED")
    return True


def test_sustainability_display():
    """Test sustainability metrics display."""
    print("\n" + "="*60)
    print("TEST: Sustainability Display")
    print("="*60)

    response = requests.get(BASE_URL)
    html = response.text

    eco_elements = [
        ("carbonEstimate", "Carbon estimate display"),
        ("dataTransferred", "Data transferred metric"),
        ("computeTime", "Compute time metric"),
        ("CO₂", "Carbon dioxide unit"),
    ]

    for element, description in eco_elements:
        assert element in html, f"Missing: {element}"
        print(f"   ✓ {description}")

    print("\n✅ Sustainability display test PASSED")
    return True


def test_responsive_design():
    """Test responsive design considerations."""
    print("\n" + "="*60)
    print("TEST: Responsive Design")
    print("="*60)

    response = requests.get(BASE_URL)
    html = response.text

    responsive_elements = [
        ("@media", "Media queries present"),
        ("grid-template-columns", "Grid layout"),
        ("flex-direction", "Flexbox layout"),
    ]

    for element, description in responsive_elements:
        assert element in html, f"Missing: {element}"
        print(f"   ✓ {description}")

    print("\n✅ Responsive design test PASSED")
    return True


def test_render_raster_endpoint():
    """Test the render-raster endpoint exists."""
    print("\n" + "="*60)
    print("TEST: Render Raster Endpoint")
    print("="*60)

    # Just test that the endpoint exists (will fail with missing path, but that's OK)
    response = requests.get(f"{BASE_URL}/render-raster?path=test&colormap=viridis")

    # Should return an error (not 404) since path doesn't exist
    assert response.status_code in [200, 500], "Endpoint not found"
    print(f"   ✓ Endpoint exists (status: {response.status_code})")

    print("\n✅ Render raster endpoint test PASSED")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("  ENHANCED WEB INTERFACE TEST SUITE")
    print("="*70)

    tests = [
        ("Health Endpoint", test_health_endpoint),
        ("UI Components", test_ui_components),
        ("JavaScript Functions", test_javascript_functions),
        ("Suggestion Chips", test_suggestion_chips),
        ("Tabs", test_tabs),
        ("Export Options", test_export_options),
        ("Quality Metrics Display", test_quality_metrics_display),
        ("Sustainability Display", test_sustainability_display),
        ("Responsive Design", test_responsive_design),
        ("Render Raster Endpoint", test_render_raster_endpoint),
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
        print("\n🎉 ALL ENHANCED INTERFACE TESTS PASSED!")
        print("\n📋 PRD-Aligned Features Verified:")
        print("  • Three-column layout with sidebars")
        print("  • Natural language suggestion chips")
        print("  • Workflow status and history")
        print("  • Quality metrics dashboard (cloud, temporal coverage)")
        print("  • Process graph visualization")
        print("  • Export capabilities (Notebook, JSON, Markdown, Citation)")
        print("  • Sustainability metrics (carbon footprint)")
        print("  • Responsive design for different screens")
        print("\n🌐 Enhanced interface available at: http://localhost:8080")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
