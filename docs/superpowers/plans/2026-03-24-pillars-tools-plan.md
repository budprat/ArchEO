# Pillars of the Past Inspired Tools — Implementation Plan

## Tools to Implement (5)

### 1. temporal_difference_map (CVA)
- Change Vector Analysis on multi-band imagery
- Histogram matching before differencing
- Co-registration check
- Returns magnitude + direction of spectral change

### 2. regularity_index
- LBP entropy for local texture regularity (low entropy = man-made)
- Edge orientation histogram (0/90 peaks = man-made)
- Returns spatial regularity heatmap

### 3. crop_mark_detector
- Compute NDVI from bands 8+4
- Local z-score: (pixel - local_mean) / local_std
- Highlight positive (wet/ditch) and negative (dry/wall) anomalies
- Returns anomaly map + statistics

### 4. shape_statistics (reframed from morphology classifier)
- Report contour statistics without claiming site type classification
- Aspect ratio distribution, compactness, orientation histogram
- Note resolution limitations in description

### 5. systematic_grid_analysis
- Divide image into NxN tiles
- Per-tile Archaeological Potential Score (APS):
  - Edge density (Canny count / area)
  - Regularity (LBP entropy, inverted)
  - Spectral anomaly count
  - NDVI contrast (local std)
  - Geometric feature count
- Return ranked tiles + heatmap

## Implementation Notes
- All follow existing FastMCP + _resolve_input pattern
- Add to agent/tools/Archaeology.py
- Add to PRIORITY_TOOLS in agent_service.py
- Add tests to tests/test_archaeology.py
- Keep descriptions concise (token budget)
