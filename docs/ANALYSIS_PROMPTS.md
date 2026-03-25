# ArchEO-Agent: Optimized Analysis Prompts for Peru Desert Archaeology

Comprehensive prompt library for detecting archaeological sites in Peru's coastal desert using the ArchEO-Agent platform. All parameters are calibrated for Sentinel-2 imagery at 10m resolution in hyper-arid environments (annual rainfall <25mm).

---

## Table of Contents

1. [Nazca Lines Detection](#1-nazca-lines-detection)
2. [Caral/Supe Valley Ruins](#2-caralsupe-valley-ruins)
3. [General Peru Desert Archaeological Survey](#3-general-peru-desert-archaeological-survey)
4. [Quick Analysis Prompts](#4-quick-analysis-prompts)
5. [Parameter Reference](#5-parameter-reference)
6. [Sentinel-2 Band Reference](#6-sentinel-2-band-reference)

---

## 1. Nazca Lines Detection

### Context

The Nazca Lines are geoglyphs created by removing the reddish-brown iron oxide-coated pebbles (desert varnish / desert pavement) from the pampa surface to reveal the lighter ground beneath. They range from simple straight lines hundreds of meters long to complex zoomorphic figures 50-300m across. At 10m Sentinel-2 resolution, the major lines and large figures are detectable as subtle albedo and texture differences against the homogeneous desert pavement.

### 1.1 Optimal BSI Threshold for Desert Pavement vs Cleared Lines

**Rationale:** The Nazca pampa is almost entirely bare soil. BSI values will be uniformly high across the scene. Geoglyph lines, where darker varnished pebbles have been removed, show *slightly lower* BSI because the exposed lighter substrate has different SWIR/NIR/Red/Blue ratios. The key is detecting relative BSI anomalies, not absolute bare soil.

- **BSI threshold for bare soil detection:** > 0.0 (entire pampa is bare soil)
- **BSI threshold for high-confidence bare soil:** > 0.2
- **Geoglyph detection strategy:** Look for BSI *anomalies* below the scene mean -- cleared lines will have BSI ~0.05-0.15 lower than surrounding desert pavement (BSI ~0.25-0.40)

### 1.2 Canny Edge Parameters for Faint Geoglyphs

**Rationale:** Geoglyph edges are extremely subtle at 10m resolution -- only 1-3 DN difference in reflectance. Standard Canny thresholds (100/200) will miss them entirely. Low thresholds capture faint gradient boundaries but need pre-processing (CLAHE or PCA) to boost contrast first.

- **low_threshold:** 20 (captures very faint edges)
- **high_threshold:** 60 (connects faint edges into continuous features)
- **gaussian_sigma:** 1.5 (suppresses sensor noise without blurring 1-2 pixel features)

**Why these values:** At 10m resolution, a geoglyph line 5m wide may occupy only part of a pixel, producing very low contrast. The 20/60 combination with a 3:1 ratio (rather than the standard 1:2) captures more weak-but-connected edges while still filtering noise.

### 1.3 Hough Line Parameters for Straight Lines

**Rationale:** Many Nazca geoglyphs include long straight lines (some >1km). At 10m resolution, a 500m line = 50 pixels. The key challenge is connecting line segments broken by noise.

- **min_line_length:** 5 (= 50m at 10m/px -- minimum meaningful archaeological line)
- **max_line_gap:** 3 (= 30m -- bridges gaps caused by noise or slight curvature)
- **hough_threshold:** 50 (default; lower to 30 for very faint lines, raise to 80 for confident-only)

**Why these values:** Real Nazca lines are continuous features 50m to 10km+ in length. minLineLength=5 pixels filters out noise while keeping the smallest meaningful features. max_line_gap=3 handles the reality that desert surface is not perfectly homogeneous, so line edges have small discontinuities.

### 1.4 Gi* Weight Matrix for Geoglyph-Scale Features

**Rationale:** Geoglyph figures are typically 50-300m across (5-30 pixels at 10m). A 3x3 queen matrix captures local anomalies at the 30m scale; a 5x5 captures broader patterns at the 50m scale.

- **Local features (individual lines):** 3x3 queen `[[1,1,1],[1,0,1],[1,1,1]]`
- **Figure-scale features (zoomorphic shapes):** 5x5 queen matrix
- **Large-scale patterns (line complexes):** 7x7 queen matrix

### 1.5 Complete Prompt: Nazca Lines Detection

```
I have a Sentinel-2 multi-band image of the Nazca pampa in southern Peru. I need to detect geoglyph lines and figures. Please run the following analysis pipeline:

STEP 1 - SPECTRAL INDICES:
- Compute the Bare Soil Index (BSI) with red_band=4, blue_band=2, nir_band=8, swir1_band=11. Save as "nazca/bsi.tif".
- Compute the Brightness Index with red_band=4, nir_band=8. Save as "nazca/bi.tif".
- Compute the Iron Oxide Index (IOI) with red_band=4, blue_band=2. Save as "nazca/ioi.tif". The Nazca pampa has iron oxide desert varnish; cleared lines have LESS iron oxide.

STEP 2 - PCA:
- Run PCA on the multi-band image with n_components=3, output_prefix="nazca/pca". PC2 and PC3 often reveal subtle surface disturbances invisible in individual bands.

STEP 3 - CONTRAST ENHANCEMENT:
- Apply CLAHE to the PCA PC1 output with clip_limit=3.0, grid_size=8. Save as "nazca/clahe_pc1.tif".
- Apply CLAHE to PCA PC2 output with clip_limit=3.0, grid_size=8. Save as "nazca/clahe_pc2.tif".

STEP 4 - EDGE DETECTION (on enhanced images):
- Run Canny edge detection on the CLAHE-enhanced PC1 with low_threshold=20, high_threshold=60, gaussian_sigma=1.5. Save as "nazca/edges_pc1.tif".
- Run Canny edge detection on the CLAHE-enhanced PC2 with low_threshold=20, high_threshold=60, gaussian_sigma=1.5. Save as "nazca/edges_pc2.tif".

STEP 5 - LINEAR FEATURE DETECTION:
- Run linear feature detection on the PC1 edges with min_line_length=5, max_line_gap=3, hough_threshold=50. Save as "nazca/lines_pc1.tif".
- Run linear feature detection on the PC2 edges with min_line_length=5, max_line_gap=3, hough_threshold=30. Save as "nazca/lines_pc2.tif". Use lower threshold for PC2 since it captures subtler features.

STEP 6 - SHAPE ANALYSIS:
- Run geometric pattern analysis on the PC1 edges with min_area=10. Save as "nazca/shapes.tif". Look for contours with low circularity (lines) and high circularity (zoomorphic figures).

STEP 7 - SPATIAL CLUSTERING:
- Compute Getis-Ord Gi* on the BSI image with weight_matrix=[[1,1,1],[1,0,1],[1,1,1]]. Save as "nazca/gi_star_bsi.tif". Cold spots (negative Gi*) indicate areas where desert pavement has been cleared.

STEP 8 - TEXTURE ANALYSIS:
- Run GLCM texture analysis on the image with distances=[1,3,5], angles=[0, 0.785, 1.571, 2.356], and save texture map to "nazca/texture.tif". Geoglyph areas should show lower contrast and higher homogeneity than undisturbed pampa.

STEP 9 - GRID ANALYSIS:
- Run systematic grid analysis with grid_size=10. Save as "nazca/grid_aps.tif". This identifies the tiles with highest archaeological potential for targeted follow-up.

After all steps, summarize:
1. How many linear features were detected and their dominant orientations?
2. Which grid tiles scored highest for archaeological potential?
3. Where are the BSI cold spots (potential cleared areas)?
4. What do the GLCM metrics suggest about surface texture variation?
```

### Expected Output

- **BSI map:** Uniformly high (0.2-0.4) across pampa; geoglyph lines show as subtle depressions (0.1-0.25)
- **PCA PC2/PC3:** Bright/dark patterns tracing geoglyph outlines
- **Edge maps:** Networks of faint linear and curvilinear edges
- **Hough lines:** Dominant orientations at ~0, ~45, ~90, ~135 degrees (Nazca lines follow cardinal and diagonal orientations)
- **Gi* cold spots:** Clusters of below-average BSI marking cleared areas
- **Grid APS:** High scores in tiles containing geoglyph concentrations

### Interpretation Tips

- **Lines at consistent orientations** (0/90/45/135 degrees) are strong geoglyph candidates -- natural erosion channels tend to follow drainage patterns, not cardinal directions
- **PC2 is your best friend** -- it separates the primary brightness signal (PC1 = albedo) from the secondary variation that often captures subtle surface disturbances
- **GLCM homogeneity** should be *higher* within geoglyphs (uniform cleared surface) than on undisturbed desert pavement (irregular pebble surface)
- **Gi* cold spots on BSI** indicate areas where the spectral signature departs from typical desert pavement -- these are your highest-probability geoglyph areas

---

## 2. Caral/Supe Valley Ruins

### Context

Caral (also called Caral-Supe) is a 5000-year-old city with monumental mudbrick (adobe) pyramids, sunken circular plazas, and residential compounds in the Supe River Valley, ~200km north of Lima. The site sits in a narrow river valley with irrigated agriculture adjacent to desert terraces. Architecture is mudbrick (sun-dried adobe) which has similar but not identical spectral properties to natural alluvial soil. Key detection strategy: exploit differences in clay mineral content, iron oxide signatures, and geometric regularity between architectural remains and natural terrain.

### 2.1 IOI Threshold for Mudbrick vs Natural Soil

**Rationale:** Mudbrick contains processed clay with elevated iron oxide from the firing/weathering process. Natural alluvial soil has lower, more variable iron oxide concentrations.

- **IOI > 0.15:** High iron oxide -- consistent with mudbrick architectural remains or pottery-rich midden deposits
- **IOI 0.05-0.15:** Moderate iron oxide -- could be natural laterite or low-density archaeological deposits
- **IOI < 0.05:** Low iron oxide -- typical alluvial soil, agricultural fields

**Why 0.15:** Mudbrick concentrates iron-bearing clays during manufacture. The 0.15 threshold separates processed clay (mudbrick) from typical Supe Valley alluvial deposits (IOI ~0.05-0.12). This is conservative to reduce false positives from natural iron-rich outcrops.

### 2.2 Clay Mineral Index Thresholds

**Rationale:** CMI = (SWIR1 - SWIR2) / (SWIR1 + SWIR2) detects clay minerals. Adobe architecture concentrates clay compared to surrounding sandy alluvium.

- **CMI > 0.1:** High clay content -- strong indicator of mudbrick structures, pottery production areas, or puddled clay floors
- **CMI 0.05-0.1:** Moderate clay -- could be natural clay-rich soil or degraded adobe
- **CMI < 0.05:** Low clay -- sandy alluvium, bedrock, or non-clay soils

**Why 0.1:** The Supe Valley alluvium is predominantly sandy with CMI ~0.03-0.07. Intact mudbrick structures concentrate enough clay to push CMI above 0.1. Degraded adobe that has partially eroded back into the soil matrix may fall in the 0.05-0.1 range.

### 2.3 SAVI L-Factor for Hyper-Arid

**Rationale:** Standard SAVI uses L=0.5 (moderate vegetation). In hyper-arid coastal Peru, vegetation is almost entirely confined to irrigated river valleys. The L-factor must be increased to minimize soil brightness influence.

- **L = 1.0** for the desert terraces (virtually no vegetation)
- **L = 0.5** for the irrigated river valley floor (moderate vegetation)
- **L = 0.25** for dense agricultural areas (if present)

**Why L=1.0:** In hyper-arid regions where NDVI < 0.1, the standard L=0.5 still allows too much soil brightness influence, producing noisy SAVI values. L=1.0 maximally suppresses soil effects, giving cleaner differentiation between truly bare soil and the sparse xerophytic vegetation that may mark ancient water management features.

### 2.4 Grid Analysis Tile Sizes

**Rationale:** Caral's monumental structures span 50-200m. At 10m resolution, appropriate grid sizes must balance detail against computational cost.

- **grid_size=20:** Each tile covers ~50x50 pixels (~500x500m) -- captures individual monumental structures. Best for site-scale prospection.
- **grid_size=10:** Each tile covers ~100x100 pixels (~1x1km) -- captures site complexes. Best for valley-scale survey.
- **grid_size=5:** Each tile covers ~200x200 pixels (~2x2km) -- captures settlement clusters. Best for regional reconnaissance.

### 2.5 Complete Prompt: Caral/Supe Valley Ruins Detection

```
I have a Sentinel-2 multi-band image of the Supe Valley in Peru, covering the area around the Caral archaeological site. I need to detect mudbrick architectural remains. Please run the following analysis:

STEP 1 - SOIL AND MINERAL INDICES:
- Compute the Iron Oxide Index (IOI) with red_band=4, blue_band=2. Save as "caral/ioi.tif". Mudbrick shows IOI > 0.15.
- Compute the Clay Mineral Index (CMI) with swir1_band=11, swir2_band=12. Save as "caral/cmi.tif". Adobe structures show CMI > 0.1.
- Compute the Bare Soil Index (BSI) with red_band=4, blue_band=2, nir_band=8, swir1_band=11. Save as "caral/bsi.tif".
- Compute the Brightness Index with red_band=4, nir_band=8. Save as "caral/bi.tif".
- Compute the Redness Index with red_band=4, green_band=3, blue_band=2. Save as "caral/ri.tif". High redness indicates iron-rich mudbrick.

STEP 2 - VEGETATION ANALYSIS (moisture anomalies):
- Compute SAVI with nir_band=8, red_band=4, L=1.0. Save as "caral/savi.tif". Use L=1.0 for hyper-arid correction.
- Compute the Moisture Index (NDMI) with nir_band=8, swir1_band=11. Save as "caral/ndmi.tif". Buried walls create drainage anomalies detectable as moisture differences.

STEP 3 - ARCHAEOLOGICAL COMPOSITE:
- Compute the Archaeological Composite Index (ACI) with red_band=4, blue_band=2, green_band=3, nir_band=8, swir1_band=11, w_bsi=0.25, w_ndbi=0.20, w_ndvi=0.25, w_ioi=0.30. Save as "caral/aci.tif". Increase IOI weight because mudbrick detection is IOI-dependent.

STEP 4 - PCA AND ENHANCEMENT:
- Run PCA with n_components=3, output_prefix="caral/pca".
- Apply CLAHE to PC1 with clip_limit=2.5, grid_size=8. Save as "caral/clahe_pc1.tif".

STEP 5 - STRUCTURAL DETECTION:
- Run Canny edge detection on CLAHE PC1 with low_threshold=20, high_threshold=60, gaussian_sigma=1.5. Save as "caral/edges.tif".
- Run linear feature detection on the edges with min_line_length=5, max_line_gap=3, hough_threshold=50. Save as "caral/lines.tif".
- Run geometric pattern analysis on the edges with min_area=10. Save as "caral/shapes.tif". Archaeological structures show high aspect ratios (~1.0 for plazas, >2.0 for walls) and moderate circularity.

STEP 6 - REGULARITY ANALYSIS:
- Run the regularity index on the image with window_size=15. Save as "caral/regularity.tif". Man-made structures show HIGH regularity (low LBP entropy) compared to natural terrain.

STEP 7 - SPATIAL ANALYSIS:
- Compute Getis-Ord Gi* on the IOI output with weight_matrix=[[1,1,1],[1,0,1],[1,1,1]]. Save as "caral/gi_star_ioi.tif". Hot spots indicate iron oxide concentrations = potential mudbrick structures.
- Compute Getis-Ord Gi* on the CMI output with weight_matrix=[[1,1,1,1,1],[1,1,1,1,1],[1,1,0,1,1],[1,1,1,1,1],[1,1,1,1,1]]. Save as "caral/gi_star_cmi.tif". Use 5x5 matrix for broader clay concentration patterns matching building complexes.

STEP 8 - GRID SURVEY:
- Run systematic grid analysis with grid_size=20. Save as "caral/grid_aps.tif". grid_size=20 gives ~500m tiles matching individual monumental structures at Caral.

STEP 9 - TEXTURE:
- Run GLCM texture analysis with distances=[1,3,5], angles=[0, 0.785, 1.571, 2.356], and texture map output at "caral/texture.tif".

After analysis, summarize:
1. Where are the IOI hotspots (IOI > 0.15) that could indicate mudbrick?
2. Where do clay concentrations (CMI > 0.1) overlap with IOI hotspots?
3. Which grid tiles scored highest on the APS?
4. Do the high-regularity areas correspond to known or suspected structural remains?
5. What orientations dominate the detected linear features?
```

### Expected Output

- **IOI map:** Valley floor ~0.05-0.12; mudbrick structures ~0.15-0.30; natural rock outcrops variable
- **CMI map:** Sandy alluvium ~0.02-0.06; adobe remains ~0.10-0.20
- **ACI map:** Natural terrain <0.4; archaeological structures >0.5
- **Regularity map:** Natural terrain ~0.3-0.5; architectural remains ~0.6-0.9
- **Grid APS:** High scores clustered around monumental architecture areas
- **Gi* IOI hot spots:** Clustered positive values marking mudbrick concentration

### Interpretation Tips

- **IOI + CMI overlap** is the strongest indicator of mudbrick -- natural iron-rich soils rarely also have high clay, but processed adobe has both
- **Regularity index > 0.7** strongly suggests man-made features -- natural desert terrain is texturally irregular
- **SAVI with L=1.0** will show near-zero values everywhere except irrigated fields and any vegetation marking ancient canals or water features
- **Dominant orientations at ~0/90 degrees** (cardinal alignment) are strong architectural indicators -- Caral's structures are roughly cardinally aligned
- **Gi* hot spots on 5x5 CMI** capture building-complex-scale clay concentrations that individual pixel analysis would miss

---

## 3. General Peru Desert Archaeological Survey

### 3.1 Full Pipeline Prompt (Multi-Band Sentinel-2)

This is the comprehensive "run everything" prompt for unknown areas where you do not know what type of site to expect. It follows the optimal pipeline order: indices, PCA, enhancement, edges, spatial clustering, grid analysis.

```
I have a Sentinel-2 multi-band image of an unexplored area in the Peruvian coastal desert. I need a comprehensive archaeological prospection survey. Run the full analysis pipeline:

PHASE 1 - SPECTRAL INDICES (characterize the surface):
1. Compute BSI (red_band=4, blue_band=2, nir_band=8, swir1_band=11). Save as "survey/bsi.tif".
2. Compute IOI (red_band=4, blue_band=2). Save as "survey/ioi.tif".
3. Compute CMI (swir1_band=11, swir2_band=12). Save as "survey/cmi.tif".
4. Compute SAVI (nir_band=8, red_band=4, L=1.0). Save as "survey/savi.tif".
5. Compute Moisture Index NDMI (nir_band=8, swir1_band=11). Save as "survey/ndmi.tif".
6. Compute Brightness Index (red_band=4, nir_band=8). Save as "survey/bi.tif".
7. Compute Redness Index (red_band=4, green_band=3, blue_band=2). Save as "survey/ri.tif".
8. Compute ACI (red_band=4, blue_band=2, green_band=3, nir_band=8, swir1_band=11). Save as "survey/aci.tif".

PHASE 2 - DIMENSIONALITY REDUCTION:
9. Run PCA with n_components=3, output_prefix="survey/pca". Report explained variance ratios.

PHASE 3 - ENHANCEMENT:
10. Apply CLAHE to PC1 (clip_limit=2.5, grid_size=8). Save as "survey/clahe_pc1.tif".
11. Apply CLAHE to PC2 (clip_limit=3.0, grid_size=8). Save as "survey/clahe_pc2.tif".

PHASE 4 - EDGE AND STRUCTURE DETECTION:
12. Canny edges on CLAHE PC1 (low_threshold=20, high_threshold=60, gaussian_sigma=1.5). Save as "survey/edges_pc1.tif".
13. Canny edges on CLAHE PC2 (low_threshold=20, high_threshold=60, gaussian_sigma=1.5). Save as "survey/edges_pc2.tif".
14. Linear feature detection on PC1 edges (min_line_length=5, max_line_gap=3, hough_threshold=50). Save as "survey/lines.tif".
15. Geometric pattern analysis on PC1 edges (min_area=10). Save as "survey/shapes.tif".

PHASE 5 - SPATIAL CLUSTERING:
16. Getis-Ord Gi* on BSI with 3x3 queen weight_matrix=[[1,1,1],[1,0,1],[1,1,1]]. Save as "survey/gi_star_bsi.tif".
17. Getis-Ord Gi* on IOI with 3x3 queen weight_matrix=[[1,1,1],[1,0,1],[1,1,1]]. Save as "survey/gi_star_ioi.tif".

PHASE 6 - TEXTURE AND REGULARITY:
18. GLCM texture analysis (distances=[1,3,5], angles=[0, 0.785, 1.571, 2.356], output_path="survey/texture.tif").
19. Regularity index (window_size=15). Save as "survey/regularity.tif".
20. Shape statistics on the edges (min_area=10). Save as "survey/shape_stats.tif".

PHASE 7 - GRID SURVEY:
21. Systematic grid analysis (grid_size=10). Save as "survey/grid_aps.tif".

PHASE 8 - ANOMALY DETECTION:
22. Spectral anomaly detection with threshold_sigma=2.5. Save as "survey/anomalies.tif".
23. Crop mark detector with window_size=25. Save as "survey/cropmarks.tif".

After completing all phases, provide a synthesis report:
1. List the top 5 grid tiles by APS score and what makes each one interesting.
2. Identify areas where multiple indicators overlap (IOI hotspots + CMI hotspots + high regularity + high APS).
3. Distinguish between potential geoglyph sites (BSI cold spots + linear features) and potential structural sites (IOI + CMI hotspots + regularity).
4. Note any spectral anomalies and their potential archaeological significance.
5. Report the dominant orientations of detected linear features -- cardinal alignments suggest architecture, drainage-pattern alignments suggest natural features.
```

### 3.2 Multi-Band vs RGB-Only Prompts

#### When You Have Full Multi-Band Sentinel-2 (13 bands)

Use the full pipeline above. All indices (BSI, CMI, NDMI, SAVI, ACI) are available.

#### When You Only Have RGB (3 bands)

Many tools adapt automatically to 3-band input. Here is the RGB-only prompt:

```
I have a 3-band RGB image of an area in the Peruvian coastal desert. I need archaeological analysis using only visible bands. Please run:

STEP 1 - RGB-COMPATIBLE INDICES:
- Compute IOI with red_band=1, blue_band=3. Save as "rgb_survey/ioi.tif". IOI works with any image that has Red and Blue channels.
- Compute Brightness Index. Save as "rgb_survey/bi.tif". For RGB, it uses BI = sqrt((R^2 + G^2 + B^2) / 3) automatically.
- Compute Redness Index with red_band=1, green_band=2, blue_band=3. Save as "rgb_survey/ri.tif".

STEP 2 - PCA ON RGB:
- Run PCA with n_components=3, output_prefix="rgb_survey/pca". With 3 bands, all 3 PCs will be computed.

STEP 3 - ENHANCEMENT AND EDGES:
- Apply CLAHE to PC1 (clip_limit=3.0, grid_size=8). Save as "rgb_survey/clahe_pc1.tif".
- Canny edges on CLAHE output (low_threshold=20, high_threshold=60, gaussian_sigma=1.5). Save as "rgb_survey/edges.tif".
- Linear feature detection (min_line_length=5, max_line_gap=3, hough_threshold=50). Save as "rgb_survey/lines.tif".
- Geometric pattern analysis (min_area=10). Save as "rgb_survey/shapes.tif".

STEP 4 - TEXTURE AND REGULARITY:
- GLCM texture analysis (distances=[1,3,5], angles=[0, 0.785, 1.571, 2.356], output_path="rgb_survey/texture.tif").
- Regularity index (window_size=15). Save as "rgb_survey/regularity.tif".

STEP 5 - SPATIAL AND GRID:
- Gi* on IOI with weight_matrix=[[1,1,1],[1,0,1],[1,1,1]]. Save as "rgb_survey/gi_star_ioi.tif".
- Spectral anomaly detection (threshold_sigma=2.5). Save as "rgb_survey/anomalies.tif".
- Grid analysis (grid_size=10). Save as "rgb_survey/grid_aps.tif".

Note: Without SWIR bands, BSI, CMI, NDMI, SAVI, and full ACI are NOT available. The analysis relies on visible-band indices (IOI, BI, RI), texture, regularity, and spatial statistics. Results will be less definitive for soil composition but still effective for structural detection and geoglyph identification.
```

### 3.3 Temporal Change Detection (Two Dates)

When you have imagery from two different dates, temporal differencing can reveal archaeological features that vary seasonally (e.g., crop marks appear during dry season, moisture marks during wet season).

```
I have two Sentinel-2 multi-band images of the same area in the Peruvian coastal desert, taken at different dates. I need temporal change analysis to detect archaeological features that vary seasonally.

STEP 1 - TEMPORAL DIFFERENCING:
- Run temporal difference map (Change Vector Analysis) between the two images. Use match_histograms=true to correct for radiometric differences. Save as "temporal/cva_magnitude.tif".

STEP 2 - PER-DATE INDICES:
- Compute BSI for date 1 (red_band=4, blue_band=2, nir_band=8, swir1_band=11). Save as "temporal/bsi_date1.tif".
- Compute BSI for date 2 (same params). Save as "temporal/bsi_date2.tif".
- Compute SAVI for date 1 (nir_band=8, red_band=4, L=1.0). Save as "temporal/savi_date1.tif".
- Compute SAVI for date 2 (same params). Save as "temporal/savi_date2.tif".
- Compute NDMI for date 1 (nir_band=8, swir1_band=11). Save as "temporal/ndmi_date1.tif".
- Compute NDMI for date 2 (same params). Save as "temporal/ndmi_date2.tif".

STEP 3 - SPATIAL ANALYSIS ON CHANGE MAP:
- Gi* on the CVA magnitude with weight_matrix=[[1,1,1],[1,0,1],[1,1,1]]. Save as "temporal/gi_star_change.tif". Hot spots indicate areas with maximum spectral change -- potential crop marks or moisture anomalies over buried features.
- Threshold segmentation on CVA magnitude to isolate high-change pixels (use threshold based on the mean_change + 2*std from the CVA results). Save as "temporal/change_mask.tif".
- Grid analysis on the CVA magnitude (grid_size=10). Save as "temporal/grid_change.tif".

STEP 4 - CROP MARK ANALYSIS:
- Run crop mark detector on date 1 image (window_size=25). Save as "temporal/cropmarks_date1.tif".
- Run crop mark detector on date 2 image (window_size=25). Save as "temporal/cropmarks_date2.tif".

After analysis, report:
1. Which areas show the most temporal change?
2. Do the change hot spots correlate with crop mark anomalies?
3. Are there areas that changed from low SAVI to high SAVI (or vice versa) -- these could be crop marks over buried walls/ditches?
4. How many pixels exceeded the change threshold, and what percentage of the scene do they represent?
```

### Expected Output for Temporal Analysis

- **CVA magnitude map:** Most of the desert should show near-zero change; areas over buried features may show change values 2-3x above the mean
- **Gi* change hot spots:** Clustered areas of maximum temporal difference
- **Crop mark differences:** Positive z-scores in one date but not the other indicate seasonal crop marks

### Interpretation Tips for Temporal Analysis

- **Ideal date pairs:** One image from the wet season (Jan-Mar for Peru's coast, though rainfall is minimal) and one from peak dry season (Jul-Sep). Even small moisture differences are amplified over buried structures.
- **CVA magnitude > mean + 2*std** is a reasonable threshold for significant change, but adjust based on the reported changed_pixel_count
- **Crop marks are most visible** when vegetation stress coincides with buried architecture: walls create dry spots (negative z-score), ditches create wet spots (positive z-score)

---

## 4. Quick Analysis Prompts

These are streamlined prompts using 3-5 tools each for rapid assessment of specific archaeological signatures.

### 4.1 Quick Structural Detection

**Purpose:** Rapidly identify potential man-made structures through edge regularity and geometric analysis. Best when you suspect architectural remains.

**Tools used:** 4 (CLAHE, Canny, geometric_pattern_analysis, regularity_index)

```
I need a quick structural assessment of this image for potential archaeological architecture. Run:

1. Apply CLAHE (clip_limit=2.5, grid_size=8). Save as "quick/clahe.tif".
2. Canny edge detection on the CLAHE output (low_threshold=20, high_threshold=60, gaussian_sigma=1.5). Save as "quick/edges.tif".
3. Geometric pattern analysis on the edges (min_area=10). Save as "quick/shapes.tif".
4. Regularity index on the original image (window_size=15). Save as "quick/regularity.tif".

Report: How many shapes were detected? What are the mean circularity and aspect ratio? What percentage of the image shows high regularity (>0.7)? Man-made structures typically show aspect ratios ~1.0-3.0, moderate circularity (0.3-0.8), and regularity above 0.7.
```

**Expected runtime:** ~30 seconds
**What to look for:** High regularity zones (>0.7), shapes with aspect ratios near 1.0 (plazas/rooms) or >3.0 (walls/roads), circularity 0.3-0.8 (rectangular to rounded structures)

### 4.2 Quick Soil Composition

**Purpose:** Rapidly assess soil mineral composition to identify mudbrick, pottery, or other anthropogenic soil modifications. Requires multi-band (SWIR) imagery.

**Tools used:** 4 (BSI, IOI, CMI, Gi*)

```
I need a quick soil composition assessment for archaeological indicators. Run:

1. Compute BSI (red_band=4, blue_band=2, nir_band=8, swir1_band=11). Save as "quick/bsi.tif".
2. Compute IOI (red_band=4, blue_band=2). Save as "quick/ioi.tif".
3. Compute CMI (swir1_band=11, swir2_band=12). Save as "quick/cmi.tif".
4. Compute Gi* on IOI with weight_matrix=[[1,1,1],[1,0,1],[1,1,1]]. Save as "quick/gi_star_ioi.tif".

Report: What percentage of pixels show BSI > 0.2 (bare soil), IOI > 0.15 (high iron / potential mudbrick), and CMI > 0.1 (high clay)? Where do IOI hot spots cluster? Areas where IOI > 0.15 AND CMI > 0.1 are highest priority for mudbrick detection.
```

**Expected runtime:** ~20 seconds
**What to look for:** Overlap zones where both IOI and CMI are elevated. Natural soils rarely show both high iron AND high clay simultaneously; processed mudbrick does.

### 4.3 Quick Vegetation Anomaly

**Purpose:** Detect buried features through their effect on surface and subsurface moisture, visible as vegetation anomalies. Best for areas near rivers or with seasonal vegetation.

**Tools used:** 3 (SAVI, crop_mark_detector, NDMI)

```
I need a quick vegetation anomaly scan for potential buried archaeological features. Run:

1. Compute SAVI (nir_band=8, red_band=4, L=1.0). Save as "quick/savi.tif". L=1.0 for hyper-arid Peru desert.
2. Compute NDMI (nir_band=8, swir1_band=11). Save as "quick/ndmi.tif".
3. Run crop mark detector (window_size=25). Save as "quick/cropmarks.tif".

Report: How many positive anomalies (potential ditches/water channels) and negative anomalies (potential walls/compacted surfaces) were detected? What is the mean SAVI value? Any SAVI anomalies in otherwise barren areas could indicate subsurface water features from ancient irrigation.
```

**Expected runtime:** ~15 seconds
**What to look for:**
- Positive crop mark z-scores (>1.5) = enhanced vegetation over buried ditches/canals
- Negative crop mark z-scores (<-1.5) = suppressed vegetation over buried walls/compacted floors
- NDMI anomalies in otherwise uniform desert

### 4.4 Quick Spatial Clustering

**Purpose:** Identify statistically significant spatial clusters in any pre-computed index map. Use this AFTER computing indices to find where anomalies concentrate.

**Tools used:** 3 (Gi* at two scales, analyze_hotspot_direction)

```
I need spatial clustering analysis on my index results to find where archaeological indicators concentrate. Run:

1. Compute Gi* on the target index image with 3x3 queen matrix weight_matrix=[[1,1,1],[1,0,1],[1,1,1]]. Save as "quick/gi_star_3x3.tif". This finds local clusters at the 30m scale.
2. Compute Gi* on the same index with 5x5 queen matrix weight_matrix=[[1,1,1,1,1],[1,1,1,1,1],[1,1,0,1,1],[1,1,1,1,1],[1,1,1,1,1]]. Save as "quick/gi_star_5x5.tif". This finds broader patterns at the 50m scale.
3. Run threshold segmentation on the 3x3 Gi* result with threshold=1.96. Save as "quick/hotspot_mask.tif". Gi* > 1.96 corresponds to p < 0.05 significance.
4. Analyze hotspot direction on the threshold mask. This tells you where hotspots concentrate (N/S/E/W).

Report: How many pixels are statistically significant hot spots (Gi* > 1.96)? What is the dominant direction of clustering? Do 3x3 and 5x5 results agree on hot spot locations?
```

**Expected runtime:** ~20 seconds
**What to look for:**
- Gi* > 1.96 = statistically significant hot spot at p < 0.05
- Gi* > 2.58 = highly significant hot spot at p < 0.01
- Gi* < -1.96 = statistically significant cold spot
- Agreement between 3x3 and 5x5 scales strengthens confidence

### 4.5 Quick Line Detection

**Purpose:** Rapidly find linear features (roads, walls, canals, geoglyph lines). No spectral indices needed -- works on any single image.

**Tools used:** 3 (Canny, linear_feature_detection, shape_statistics)

```
I need to quickly scan for linear archaeological features in this image. Run:

1. Canny edge detection (low_threshold=20, high_threshold=60, gaussian_sigma=1.5). Save as "quick/edges.tif".
2. Linear feature detection on edges (min_line_length=5, max_line_gap=3, hough_threshold=40). Save as "quick/lines.tif". Use lower hough_threshold=40 to catch fainter lines.
3. Shape statistics on edges (min_area=10). Save as "quick/shape_stats.tif".

Report: How many lines were detected? What are the dominant orientations? Lines at cardinal orientations (0, 90 degrees) or diagonal (45, 135 degrees) are more likely archaeological. What does the orientation histogram show?
```

**Expected runtime:** ~10 seconds
**What to look for:**
- Peaks in the orientation histogram at 0, 45, 90, 135 degrees suggest man-made features
- Broad, uniform orientation distributions suggest natural drainage or erosion
- Long lines (many pixels) are more reliable than short fragments

---

## 5. Parameter Reference

### Edge Detection Parameters

| Parameter | Value | Physical Meaning |
|-----------|-------|-----------------|
| Canny low_threshold | 20 | Captures gradient > ~8% of max range -- needed for faint geoglyph edges |
| Canny high_threshold | 60 | Connects edges > ~24% of max range -- filters noise while keeping subtle features |
| Canny gaussian_sigma | 1.5 | Smooths at ~15m scale -- suppresses single-pixel noise without blurring 2-3 pixel features |
| Hough min_line_length | 5 | = 50m at 10m/px -- minimum meaningful archaeological linear feature |
| Hough max_line_gap | 3 | = 30m -- bridges gaps from noise or slight irregularities |
| Hough threshold | 50 | Standard sensitivity; use 30 for maximum sensitivity, 80 for high confidence only |
| Sobel ksize | 3 | Standard 3x3 kernel; use 5 for smoother gradients |

### Spectral Index Thresholds (Hyper-Arid Peru)

| Index | Threshold | Meaning |
|-------|-----------|---------|
| BSI > 0.0 | Bare soil present | Entire Nazca pampa exceeds this |
| BSI > 0.2 | High-confidence bare soil | Undisturbed desert pavement |
| IOI > 0.15 | High iron oxide | Mudbrick, pottery, burnt earth |
| IOI > 0.20 | Very high iron | Strong archaeological indicator |
| CMI > 0.10 | High clay minerals | Adobe structures, processed clay |
| CMI > 0.15 | Very high clay | Intact mudbrick, pottery kilns |
| SAVI L=1.0 | Hyper-arid correction | Maximally suppresses soil brightness |
| NDMI < -0.1 | Dry surface | Normal for hyper-arid; watch for local anomalies |
| ACI > 0.5 | High archaeological potential | Multiple indicators align |

### GLCM Texture Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| distances | [1, 3, 5] | Multi-scale: 10m, 30m, 50m captures fine to coarse texture |
| angles | [0, pi/4, pi/2, 3pi/4] | All 4 directions for isotropic texture characterization |
| levels | 32 | Internal quantization -- balance between discrimination and computation |

### Spatial Statistics Parameters

| Parameter | Value | Use Case |
|-----------|-------|----------|
| 3x3 queen weight | [[1,1,1],[1,0,1],[1,1,1]] | Local clusters, individual features |
| 5x5 queen weight | [[1,1,1,1,1],[1,1,1,1,1],[1,1,0,1,1],[1,1,1,1,1],[1,1,1,1,1]] | Building complex scale |
| 7x7 queen weight | 7x7 matrix with center=0 | Large-scale settlement patterns |
| Gi* > 1.96 | p < 0.05 | Statistically significant cluster |
| Gi* > 2.58 | p < 0.01 | Highly significant cluster |
| Gi* < -1.96 | p < 0.05 cold spot | Significant low-value cluster |

### Grid Analysis Parameters

| grid_size | Tile Size (at 1000x1000 px image) | Best For |
|-----------|-----------------------------------|----------|
| 5 | ~200x200 px = 2x2 km | Regional reconnaissance |
| 10 | ~100x100 px = 1x1 km | Valley-scale survey |
| 20 | ~50x50 px = 500x500 m | Site-scale prospection |
| 40 | ~25x25 px = 250x250 m | Fine-scale feature mapping |

### Archaeological Composite Index Weights

| Weight Set | w_bsi | w_ndbi | w_ndvi | w_ioi | Best For |
|------------|-------|--------|--------|-------|----------|
| Default | 0.30 | 0.25 | 0.25 | 0.20 | General survey |
| Mudbrick emphasis | 0.25 | 0.20 | 0.25 | 0.30 | Adobe architecture (Caral) |
| Desert pavement | 0.40 | 0.20 | 0.20 | 0.20 | Geoglyph detection (Nazca) |
| Vegetation marks | 0.20 | 0.20 | 0.40 | 0.20 | Crop/moisture marks |

---

## 6. Sentinel-2 Band Reference

All prompts in this document assume Sentinel-2 MSI band numbering:

| Band | Name | Central Wavelength | Resolution | Band Index (1-based) |
|------|------|-------------------|------------|---------------------|
| B1 | Coastal Aerosol | 443 nm | 60m | 1 |
| B2 | Blue | 490 nm | 10m | 2 |
| B3 | Green | 560 nm | 10m | 3 |
| B4 | Red | 665 nm | 10m | 4 |
| B5 | Red Edge 1 | 705 nm | 20m | 5 |
| B6 | Red Edge 2 | 740 nm | 20m | 6 |
| B7 | Red Edge 3 | 783 nm | 20m | 7 |
| B8 | NIR | 842 nm | 10m | 8 |
| B8A | NIR Narrow | 865 nm | 20m | 9 |
| B9 | Water Vapor | 945 nm | 60m | 10 |
| B11 | SWIR 1 | 1610 nm | 20m | 11 |
| B12 | SWIR 2 | 2190 nm | 20m | 12 |

**Note on band ordering:** The band indices used in these prompts (e.g., red_band=4, nir_band=8) assume Sentinel-2 bands are stored in the standard order above. If your multi-band image uses a different band order (e.g., only 4 bands as R/G/B/NIR), adjust the band indices accordingly. The tool descriptions note when defaults differ (e.g., SAVI defaults to nir_band=4, red_band=3 for 4-band images).

**Resolution note:** SWIR bands (B11, B12) are natively 20m resolution. When using them alongside 10m bands, the tools handle the mixed resolution internally, but results for SWIR-dependent indices (BSI, CMI, NDMI) will reflect the coarser 20m resolution.
