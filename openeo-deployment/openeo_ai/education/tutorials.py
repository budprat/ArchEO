"""
Guided Tutorials for OpenEO AI Assistant.

ABOUTME: Interactive tutorials and guided workflows for learning OpenEO
and Earth Observation data processing.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from enum import Enum
import json


class TutorialDifficulty(Enum):
    """Tutorial difficulty levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class StepType(Enum):
    """Types of tutorial steps."""
    EXPLANATION = "explanation"
    CODE_EXAMPLE = "code_example"
    INTERACTIVE = "interactive"
    QUIZ = "quiz"
    PROCESS_GRAPH = "process_graph"


@dataclass
class TutorialStep:
    """A single step in a tutorial."""
    id: str
    title: str
    step_type: StepType
    content: str
    code: Optional[str] = None
    process_graph: Optional[Dict[str, Any]] = None
    expected_output: Optional[str] = None
    hints: List[str] = field(default_factory=list)
    validation_fn: Optional[str] = None  # Name of validation function

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "step_type": self.step_type.value,
            "content": self.content,
            "code": self.code,
            "process_graph": self.process_graph,
            "hints": self.hints,
        }


@dataclass
class Tutorial:
    """A complete tutorial with multiple steps."""
    id: str
    title: str
    description: str
    difficulty: TutorialDifficulty
    estimated_minutes: int
    steps: List[TutorialStep]
    prerequisites: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    learning_objectives: List[str] = field(default_factory=list)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    def get_step(self, step_id: str) -> Optional[TutorialStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_step_by_index(self, index: int) -> Optional[TutorialStep]:
        """Get a step by index (0-based)."""
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert tutorial to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "difficulty": self.difficulty.value,
            "estimated_minutes": self.estimated_minutes,
            "total_steps": self.total_steps,
            "prerequisites": self.prerequisites,
            "tags": self.tags,
            "learning_objectives": self.learning_objectives,
            "steps": [step.to_dict() for step in self.steps],
        }


class TutorialManager:
    """
    Manages tutorials and user progress.

    Provides:
    - Tutorial discovery and browsing
    - Progress tracking
    - Step validation
    """

    def __init__(self):
        """Initialize with built-in tutorials."""
        self._tutorials = self._load_tutorials()
        self._progress: Dict[str, Dict[str, Any]] = {}

    def _load_tutorials(self) -> Dict[str, Tutorial]:
        """Load built-in tutorials."""
        return {
            "ndvi_basics": self._create_ndvi_tutorial(),
            "cloud_masking": self._create_cloud_masking_tutorial(),
            "temporal_analysis": self._create_temporal_tutorial(),
            "change_detection": self._create_change_detection_tutorial(),
        }

    def _create_ndvi_tutorial(self) -> Tutorial:
        """Create the NDVI basics tutorial."""
        return Tutorial(
            id="ndvi_basics",
            title="Calculate Your First NDVI",
            description="Learn how to calculate the Normalized Difference Vegetation Index (NDVI) from Sentinel-2 data.",
            difficulty=TutorialDifficulty.BEGINNER,
            estimated_minutes=15,
            learning_objectives=[
                "Understand what NDVI measures",
                "Load Sentinel-2 data with OpenEO",
                "Apply band math to calculate indices",
                "Visualize results",
            ],
            tags=["ndvi", "vegetation", "sentinel-2", "indices"],
            steps=[
                TutorialStep(
                    id="intro",
                    title="What is NDVI?",
                    step_type=StepType.EXPLANATION,
                    content="""
**Normalized Difference Vegetation Index (NDVI)** is one of the most widely used
vegetation indices in remote sensing.

NDVI measures vegetation health by comparing:
- **NIR (Near-Infrared)**: Healthy vegetation strongly reflects NIR light
- **Red**: Vegetation absorbs red light for photosynthesis

The formula is: `NDVI = (NIR - Red) / (NIR + Red)`

**NDVI Values:**
- -1 to 0: Water, snow, clouds, bare soil
- 0 to 0.2: Sparse vegetation or stressed plants
- 0.2 to 0.5: Moderate vegetation
- 0.5 to 1: Dense, healthy vegetation
                    """,
                ),
                TutorialStep(
                    id="load_data",
                    title="Load Sentinel-2 Data",
                    step_type=StepType.PROCESS_GRAPH,
                    content="""
First, we need to load Sentinel-2 data with the red and NIR bands.

For Sentinel-2, the band names are:
- `red`: Red band (665nm)
- `nir`: NIR band (842nm)
                    """,
                    process_graph={
                        "load1": {
                            "process_id": "load_collection",
                            "arguments": {
                                "id": "sentinel-2-l2a",
                                "spatial_extent": {
                                    "west": 11.0,
                                    "south": 46.0,
                                    "east": 11.5,
                                    "north": 46.5,
                                },
                                "temporal_extent": ["2024-06-01", "2024-06-30"],
                                "bands": ["red", "nir"],
                            },
                        }
                    },
                    hints=[
                        "Use 'red' and 'nir' as band names for Sentinel-2",
                        "Keep the spatial extent small for faster processing",
                    ],
                ),
                TutorialStep(
                    id="calculate_ndvi",
                    title="Calculate NDVI",
                    step_type=StepType.PROCESS_GRAPH,
                    content="""
Now we apply the NDVI formula using OpenEO's normalized_difference process.

The `normalized_difference` process calculates: `(x - y) / (x + y)`
                    """,
                    process_graph={
                        "load1": {
                            "process_id": "load_collection",
                            "arguments": {
                                "id": "sentinel-2-l2a",
                                "spatial_extent": {
                                    "west": 11.0,
                                    "south": 46.0,
                                    "east": 11.5,
                                    "north": 46.5,
                                },
                                "temporal_extent": ["2024-06-01", "2024-06-30"],
                                "bands": ["red", "nir"],
                            },
                        },
                        "ndvi1": {
                            "process_id": "ndvi",
                            "arguments": {
                                "data": {"from_node": "load1"},
                                "nir": "nir",
                                "red": "red",
                            },
                        },
                        "save1": {
                            "process_id": "save_result",
                            "arguments": {
                                "data": {"from_node": "ndvi1"},
                                "format": "GTiff",
                            },
                            "result": True,
                        },
                    },
                ),
                TutorialStep(
                    id="interpret",
                    title="Interpret the Results",
                    step_type=StepType.EXPLANATION,
                    content="""
**Congratulations!** You've calculated your first NDVI image.

**What the colors mean:**
- 🔵 Blue/Purple (< 0): Water bodies
- 🟤 Brown (0 - 0.2): Bare soil, urban areas
- 🟡 Yellow (0.2 - 0.4): Sparse vegetation, grassland
- 🟢 Green (0.4 - 0.6): Moderate vegetation
- 🌲 Dark Green (> 0.6): Dense, healthy vegetation

**Next steps:**
- Try calculating NDVI for different time periods
- Compare NDVI before and after a drought
- Calculate other indices like NDWI for water
                    """,
                ),
            ],
        )

    def _create_cloud_masking_tutorial(self) -> Tutorial:
        """Create the cloud masking tutorial."""
        return Tutorial(
            id="cloud_masking",
            title="Cloud Masking with Sentinel-2",
            description="Learn how to identify and remove cloud-contaminated pixels from your analysis.",
            difficulty=TutorialDifficulty.BEGINNER,
            estimated_minutes=20,
            learning_objectives=[
                "Understand why cloud masking is important",
                "Use the SCL band for cloud detection",
                "Apply masks to data cubes",
            ],
            tags=["clouds", "preprocessing", "sentinel-2", "quality"],
            steps=[
                TutorialStep(
                    id="intro",
                    title="Why Cloud Masking?",
                    step_type=StepType.EXPLANATION,
                    content="""
Clouds are the biggest challenge in optical remote sensing. They:
- Block the view of the Earth's surface
- Can be confused with snow or bright surfaces
- Make time series analysis unreliable

**Sentinel-2 Solution: Scene Classification Layer (SCL)**

The SCL band automatically classifies each pixel into categories:
- Cloud shadows (3)
- Vegetation (4)
- Bare soils (5)
- Water (6)
- Clouds medium probability (8)
- Clouds high probability (9)
- Thin cirrus (10)
                    """,
                ),
                TutorialStep(
                    id="load_with_scl",
                    title="Load Data with SCL Band",
                    step_type=StepType.PROCESS_GRAPH,
                    content="Load Sentinel-2 data including the SCL band for masking.",
                    process_graph={
                        "load1": {
                            "process_id": "load_collection",
                            "arguments": {
                                "id": "sentinel-2-l2a",
                                "spatial_extent": {
                                    "west": 11.0,
                                    "south": 46.0,
                                    "east": 11.2,
                                    "north": 46.2,
                                },
                                "temporal_extent": ["2024-07-01", "2024-07-31"],
                                "bands": ["red", "green", "blue", "scl"],
                            },
                        }
                    },
                ),
                TutorialStep(
                    id="apply_mask",
                    title="Apply Cloud Mask",
                    step_type=StepType.EXPLANATION,
                    content="""
**Recommended SCL values to keep (clear pixels):**
- 4: Vegetation
- 5: Bare soils / Not vegetated
- 6: Water

**Values to mask out (cloudy/bad pixels):**
- 3: Cloud shadows
- 8: Cloud medium probability
- 9: Cloud high probability
- 10: Thin cirrus

This approach keeps about 80-90% of your data on a clear day,
but removes all cloud-contaminated pixels.
                    """,
                ),
            ],
        )

    def _create_temporal_tutorial(self) -> Tutorial:
        """Create the temporal analysis tutorial."""
        return Tutorial(
            id="temporal_analysis",
            title="Time Series Analysis",
            description="Learn to analyze vegetation changes over time using monthly NDVI composites.",
            difficulty=TutorialDifficulty.INTERMEDIATE,
            estimated_minutes=25,
            learning_objectives=[
                "Create temporal composites",
                "Aggregate data over time",
                "Analyze seasonal patterns",
            ],
            tags=["time-series", "compositing", "ndvi", "seasonal"],
            prerequisites=["ndvi_basics", "cloud_masking"],
            steps=[
                TutorialStep(
                    id="intro",
                    title="Why Time Series?",
                    step_type=StepType.EXPLANATION,
                    content="""
Single images capture a moment in time. Time series analysis reveals:
- Seasonal vegetation patterns (green-up, senescence)
- Agricultural crop cycles (planting, growth, harvest)
- Disturbances (fires, floods, deforestation)
- Long-term trends (climate change impacts)

**Common Temporal Aggregations:**
- **Median**: Robust to outliers (clouds, noise)
- **Mean**: Sensitive to outliers
- **Max**: Peak values (e.g., maximum greenness)
- **Min**: Minimum values (e.g., drought detection)
                    """,
                ),
                TutorialStep(
                    id="monthly_median",
                    title="Monthly Median NDVI",
                    step_type=StepType.PROCESS_GRAPH,
                    content="Create monthly median NDVI composites for a full year.",
                    process_graph={
                        "load1": {
                            "process_id": "load_collection",
                            "arguments": {
                                "id": "sentinel-2-l2a",
                                "spatial_extent": {
                                    "west": 11.0,
                                    "south": 46.0,
                                    "east": 11.2,
                                    "north": 46.2,
                                },
                                "temporal_extent": ["2024-01-01", "2024-12-31"],
                                "bands": ["red", "nir"],
                            },
                        },
                        "ndvi1": {
                            "process_id": "ndvi",
                            "arguments": {
                                "data": {"from_node": "load1"},
                                "nir": "nir",
                                "red": "red",
                            },
                        },
                        "aggregate1": {
                            "process_id": "aggregate_temporal_period",
                            "arguments": {
                                "data": {"from_node": "ndvi1"},
                                "period": "month",
                                "reducer": {
                                    "process_graph": {
                                        "median1": {
                                            "process_id": "median",
                                            "arguments": {"data": {"from_parameter": "data"}},
                                            "result": True,
                                        }
                                    }
                                },
                            },
                            "result": True,
                        },
                    },
                ),
            ],
        )

    def _create_change_detection_tutorial(self) -> Tutorial:
        """Create the change detection tutorial."""
        return Tutorial(
            id="change_detection",
            title="Detecting Land Cover Changes",
            description="Learn to detect and map changes in land cover between two time periods.",
            difficulty=TutorialDifficulty.ADVANCED,
            estimated_minutes=30,
            learning_objectives=[
                "Compare images from different dates",
                "Calculate change indices",
                "Classify types of change",
            ],
            tags=["change-detection", "comparison", "land-cover"],
            prerequisites=["ndvi_basics", "temporal_analysis"],
            steps=[
                TutorialStep(
                    id="intro",
                    title="Change Detection Approaches",
                    step_type=StepType.EXPLANATION,
                    content="""
**Common Change Detection Methods:**

1. **Image Differencing**
   - Calculate: Image2 - Image1
   - Simple but effective for vegetation changes

2. **Ratio-based**
   - Calculate: Image2 / Image1
   - Good for relative changes

3. **Normalized Burn Ratio (dNBR)**
   - Specifically for fire/burn detection
   - dNBR = NBR_pre - NBR_post

4. **Machine Learning**
   - Train classifiers on labeled change samples
   - Can detect specific change types
                    """,
                ),
                TutorialStep(
                    id="before_after",
                    title="Load Before and After Images",
                    step_type=StepType.EXPLANATION,
                    content="""
For effective change detection:

1. **Select appropriate dates**:
   - Same season (to avoid phenological differences)
   - Cloud-free or use composites
   - Before/after a known event

2. **Use consistent preprocessing**:
   - Atmospheric correction
   - Cloud masking
   - Same bands

3. **Consider the change type**:
   - Vegetation loss: Use NDVI difference
   - Urban expansion: Use NDBI difference
   - Fire damage: Use NBR difference
                    """,
                ),
            ],
        )

    def list_tutorials(
        self,
        difficulty: TutorialDifficulty = None,
        tag: str = None
    ) -> List[Tutorial]:
        """
        List available tutorials with optional filtering.

        Args:
            difficulty: Filter by difficulty level
            tag: Filter by tag

        Returns:
            List of Tutorial objects
        """
        tutorials = list(self._tutorials.values())

        if difficulty:
            tutorials = [t for t in tutorials if t.difficulty == difficulty]

        if tag:
            tutorials = [t for t in tutorials if tag in t.tags]

        return tutorials

    def get_tutorial(self, tutorial_id: str) -> Optional[Tutorial]:
        """
        Get a tutorial by ID.

        Args:
            tutorial_id: Tutorial identifier

        Returns:
            Tutorial or None if not found
        """
        return self._tutorials.get(tutorial_id)

    def start_tutorial(self, tutorial_id: str, user_id: str) -> Dict[str, Any]:
        """
        Start a tutorial for a user.

        Args:
            tutorial_id: Tutorial to start
            user_id: User identifier

        Returns:
            Progress state for the tutorial
        """
        tutorial = self.get_tutorial(tutorial_id)
        if not tutorial:
            raise ValueError(f"Tutorial not found: {tutorial_id}")

        progress_key = f"{user_id}:{tutorial_id}"
        self._progress[progress_key] = {
            "tutorial_id": tutorial_id,
            "current_step": 0,
            "completed_steps": [],
            "started_at": None,  # Would use datetime in production
            "completed": False,
        }

        return self._progress[progress_key]

    def advance_step(self, tutorial_id: str, user_id: str) -> Dict[str, Any]:
        """
        Advance to the next step in a tutorial.

        Args:
            tutorial_id: Tutorial ID
            user_id: User ID

        Returns:
            Updated progress state
        """
        progress_key = f"{user_id}:{tutorial_id}"
        if progress_key not in self._progress:
            return self.start_tutorial(tutorial_id, user_id)

        progress = self._progress[progress_key]
        tutorial = self.get_tutorial(tutorial_id)

        if not tutorial:
            raise ValueError(f"Tutorial not found: {tutorial_id}")

        current_step = progress["current_step"]
        if current_step < tutorial.total_steps - 1:
            progress["completed_steps"].append(current_step)
            progress["current_step"] = current_step + 1
        else:
            progress["completed_steps"].append(current_step)
            progress["completed"] = True

        return progress

    def get_progress(self, tutorial_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's progress in a tutorial.

        Args:
            tutorial_id: Tutorial ID
            user_id: User ID

        Returns:
            Progress state or None if not started
        """
        progress_key = f"{user_id}:{tutorial_id}"
        return self._progress.get(progress_key)
