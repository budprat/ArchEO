# OpenEO AI Assistant - Implementation Next Steps

**Based on PRD v1.0 Analysis**
**Date:** February 5, 2026
**Current Phase:** Alpha (Q1 2026)

---

## Current Status Summary

### Completed (P0)
| Feature | Status | Notes |
|---------|--------|-------|
| F2: Sequential Tool-Use | ✅ Complete | 16 tools registered, multi-turn working |
| F3: Interactive Maps | ✅ Complete | Leaflet, colormaps, controls |
| F3: Colormap Switching | ✅ Complete | Dynamic re-rendering via `/render-raster` |
| F4: Schema Validation | ✅ Complete | Process graph validation |
| F1: NLP Query - Location | ✅ Complete | Nominatim geocoding + predefined regions |
| F1: NLP Query - Temporal | ✅ Complete | dateparser + regional seasons |
| F2: Error Recovery | ✅ Complete | Retry with backoff + circuit breaker |
| F3: Time Series Charts | ✅ Complete | Chart.js integration |
| F4: Extent Warnings | ✅ Complete | Size estimation with thresholds |
| F3: Comparison Slider | ✅ Complete | Before/after visualization |

### Recently Completed (Feb 5, 2026)
Steps 1-6 from this implementation plan have been completed:
- `openeo_ai/utils/geocoding.py` - Location resolution with Nominatim
- `openeo_ai/utils/temporal.py` - Temporal expression parser
- `openeo_ai/utils/retry.py` - Retry with exponential backoff
- `openeo_ai/utils/extent_validator.py` - Size estimation and validation
- Chart.js integration in web_interface.py
- Comparison slider support in MapComponent

**Additional Features (Feb 5, 2026 - High Priority Recommendations):**
- `openeo_ai/utils/geospatial.py` - CRS validation, antimeridian handling
- `openeo_ai/utils/quality_metrics.py` - Cloud coverage & temporal coverage estimation
- `openeo_ai/visualization/quality_dashboard.py` - Quality metrics dashboard UI
- Tools: `openeo_quality_metrics`, `openeo_validate_geospatial`
- 18 tools now registered

**Enhanced Web Interface (Feb 5, 2026 - PRD Implementation):**
- `openeo_ai/web_interface.py` - Complete UI overhaul (v0.2.0)
- Three-column layout: Workflow sidebar | Chat | Metrics sidebar
- Natural language suggestion chips for common queries
- Workflow history with replay capability
- Quality metrics dashboard with A-F grading
- Process graph visualization panel
- Export capabilities: Jupyter Notebook, JSON, Markdown, BibTeX
- Sustainability metrics (carbon footprint, compute time)
- Interactive maps with basemap/colormap switching
- Chart.js time series with download

### Completed (P0 & P1)
| Feature | Status | Notes |
|---------|--------|-------|
| F5: Quality Metrics | ✅ Complete | Cloud %, temporal coverage, quality grades (A-F) |
| Geospatial Validation | ✅ Complete | CRS, antimeridian, coordinate validation |
| F9: Notebook Export | ✅ Complete | Export to .ipynb with process graphs |
| Enhanced UI | ✅ Complete | Three-column PRD-aligned interface |
| Sustainability Metrics | ✅ Complete | Carbon footprint estimation |
| Workflow History | ✅ Complete | Replay and track previous analyses |

### In Progress (P2 - Future)
| Feature | Status | Remaining Work |
|---------|--------|----------------|
| UDF Support | 🔄 Planned | Custom Python/R scripts in workflows |
| Multi-backend Routing | 🔄 Planned | Federated backend selection |

---

## Immediate Next Steps (Week 1-2)

### Step 1: Enhanced NLP Location Parsing
**Priority:** P0-Critical | **Effort:** 3 days

```yaml
Goal: Resolve place names to bounding boxes automatically

Implementation:
  1. Add geocoding service integration (Nominatim - free, no API key)
  2. Create location_resolver.py utility
  3. Update system prompt with location resolution instructions
  4. Add tool: openeo_resolve_location

Files to Create/Modify:
  - openeo_ai/utils/geocoding.py (new)
  - openeo_ai/sdk/client.py (update system prompt)
  - openeo_ai/tools/openeo_tools.py (add tool)

Example Usage:
  User: "Show NDVI for Mumbai"
  Agent: Resolves → {"west": 72.77, "south": 18.89, "east": 72.98, "north": 19.27}
```

### Step 2: Temporal Expression Parser
**Priority:** P0-Critical | **Effort:** 2 days

```yaml
Goal: Parse natural language dates into ISO format

Implementation:
  1. Use dateparser library for flexible parsing
  2. Handle relative expressions ("last month", "summer 2025")
  3. Detect seasonal references (monsoon, winter, etc.)
  4. Add regional calendar awareness

Files to Create/Modify:
  - openeo_ai/utils/temporal.py (new)
  - openeo_ai/sdk/client.py (update system prompt)

Example Mappings:
  "last summer" → ["2025-06-01", "2025-08-31"]
  "monsoon 2025" → ["2025-06-01", "2025-09-30"]
  "past 3 months" → ["2025-11-05", "2026-02-05"]
```

### Step 3: Time Series Visualization
**Priority:** P0-High | **Effort:** 2 days

```yaml
Goal: Display temporal data as interactive charts

Implementation:
  1. Add Chart.js to frontend
  2. Create ChartComponent in visualization module
  3. Add viz_show_time_series tool handler
  4. Support line, bar, area chart types

Files to Create/Modify:
  - openeo_ai/visualization/charts.py (enhance)
  - openeo_ai/web_interface.py (add Chart.js)
  - openeo_ai/tools/viz_tools.py (enhance handler)

Chart Spec:
  {
    "type": "chart",
    "spec": {
      "chartType": "line",
      "title": "NDVI Time Series",
      "xAxis": {"label": "Date", "values": [...]},
      "yAxis": {"label": "NDVI", "range": [-1, 1]},
      "series": [{"name": "Mean NDVI", "values": [...]}]
    }
  }
```

---

## Short-term Steps (Week 3-4)

### Step 4: Error Recovery & Retry Logic
**Priority:** P0-High | **Effort:** 3 days

```yaml
Goal: Graceful handling of API failures with automatic recovery

Implementation:
  1. Add retry decorator with exponential backoff
  2. Implement backend health checks
  3. Create fallback strategies per error type
  4. Add user-friendly error messages

Error Handling Matrix:
  | Error | Retries | Fallback |
  |-------|---------|----------|
  | 429 Rate Limit | 3x backoff | Queue request |
  | 500 Backend | 2x | Try alternate backend |
  | Timeout | 1x | Offer background job |
  | 401 Auth | 0 | Prompt re-auth |

Files to Modify:
  - openeo_ai/sdk/client.py (add retry logic)
  - openeo_ai/tools/openeo_tools.py (error handlers)
```

### Step 5: Extent Size Warnings
**Priority:** P0-High | **Effort:** 2 days

```yaml
Goal: Warn users before processing large areas

Implementation:
  1. Calculate estimated data size from extent + resolution
  2. Add warning thresholds (>1GB, >10GB, >100GB)
  3. Suggest alternatives (smaller extent, lower resolution)
  4. Show cost/time estimates

Estimation Formula:
  pixels = (extent_width / resolution) × (extent_height / resolution)
  bytes_per_band = pixels × 4 (float32)
  total_bytes = bytes_per_band × num_bands × num_timesteps

Warning Levels:
  - Info: < 1GB
  - Warning: 1-10GB (suggest chunking)
  - Error: > 10GB (require confirmation)

Files to Modify:
  - openeo_ai/tools/openeo_tools.py (add validation)
  - openeo_ai/sdk/client.py (system prompt warnings)
```

### Step 6: Comparison Slider Visualization
**Priority:** P0-Medium | **Effort:** 2 days

```yaml
Goal: Before/after image comparison in chat

Implementation:
  1. Add Leaflet side-by-side plugin
  2. Implement viz_compare_images tool
  3. Support synchronized pan/zoom
  4. Add split position control

Files to Modify:
  - openeo_ai/web_interface.py (add comparison UI)
  - openeo_ai/visualization/maps.py (enhance)
  - openeo_ai/tools/viz_tools.py (ensure handler works)
```

---

## Medium-term Steps (Week 5-8) - Beta Prep

### Step 7: Quality Metrics Dashboard (F5)
**Priority:** P1-High | **Effort:** 5 days

```yaml
Goal: Show data quality alongside results

Metrics to Display:
  - Cloud coverage percentage
  - Temporal coverage (dates available vs requested)
  - Valid pixel percentage
  - Data source consistency

Implementation:
  1. Extract quality metrics from STAC metadata
  2. Create QualityComponent in visualization
  3. Add quality info to job results
  4. Display as collapsible panel in UI
```

### Step 8: Jupyter Notebook Export (F9)
**Priority:** P1-Medium | **Effort:** 4 days

```yaml
Goal: Export conversation as reproducible notebook

Implementation:
  1. Track all tool calls and parameters
  2. Generate nbformat notebook structure
  3. Include process graphs as code cells
  4. Add markdown documentation cells
  5. Provide download button in UI
```

### Step 9: UDF Support Foundation (F6)
**Priority:** P1-Medium | **Effort:** 5 days

```yaml
Goal: Allow custom Python code in workflows

Implementation:
  1. Add UDF editor component to UI
  2. Create sandboxed execution environment
  3. Validate UDF input/output schemas
  4. Integrate with openEO run_udf process
```

---

## Implementation Checklist

### Week 1 ✅ COMPLETE
- [x] Create `openeo_ai/utils/geocoding.py` with Nominatim integration
- [x] Add `openeo_resolve_location` tool
- [x] Create `openeo_ai/utils/temporal.py` with dateparser
- [x] Update system prompt with location/temporal instructions
- [x] Test location parsing: "Mumbai", "Kerala", "Amazon rainforest"
- [x] Test temporal parsing: "last summer", "2020-2023", "monsoon"

### Week 2 ✅ COMPLETE
- [x] Add Chart.js to web_interface.py
- [x] Enhance `ChartComponent` in charts.py
- [x] Implement time series data extraction from datacubes
- [x] Create interactive chart with zoom/pan
- [ ] Add chart export (PNG, CSV) - Future enhancement

### Week 3 ✅ COMPLETE
- [x] Implement retry decorator with backoff
- [x] Add circuit breaker for cascading failure prevention
- [x] Create error message templates (ErrorRecoveryStrategy)
- [x] Test failure scenarios (timeout, 500, 429)
- [x] Add extent size calculator (ExtentValidator)
- [x] Implement warning thresholds (info/warning/error)

### Week 4 ✅ COMPLETE
- [x] Add comparison slider support
- [x] Test before/after slider structure
- [x] Integration testing of all P0 features
- [x] Update SYSTEM_PROMPT with extent estimation guidance
- [x] Update documentation

### Week 5-6 (Beta Prep)
- [ ] Quality metrics extraction
- [ ] Quality dashboard UI
- [ ] Notebook export foundation
- [ ] User feedback collection mechanism

### Week 7-8 (Beta Prep)
- [ ] UDF editor component
- [ ] Sandboxed execution
- [ ] Performance optimization
- [ ] Load testing

---

## Technical Debt to Address

| Item | Priority | Effort |
|------|----------|--------|
| Add unit tests for tools | High | 3 days |
| Improve error logging | Medium | 1 day |
| Add request/response caching | Medium | 2 days |
| Optimize large raster rendering | Medium | 2 days |
| Add TypeScript types for frontend | Low | 2 days |

---

## Dependencies to Install

```bash
# For geocoding
pip install geopy

# For temporal parsing
pip install dateparser python-dateutil

# For notebook export
pip install nbformat nbconvert

# For UDF sandboxing (future)
pip install restrictedpython
```

---

## Success Criteria for Alpha Completion

- [ ] 80% query success rate (location + temporal parsing)
- [ ] All P0 features functional
- [ ] 10 internal testers onboarded
- [ ] Core workflows documented
- [ ] No critical bugs in issue tracker

---

## Next PRD Update Items

1. Add geocoding service selection to Technical Architecture
2. Update Requirements Traceability with completion dates
3. Add Alpha testing results to Appendix E
4. Document discovered edge cases in validation rules
