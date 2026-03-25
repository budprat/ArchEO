"""
Tests for OpenEO AI Education module.

ABOUTME: Tests knowledge base, spectral indices, concepts, and tutorials.
Follows TDD principles.
"""

import pytest
from openeo_ai.education import (
    KnowledgeBase,
    EOConcept,
    SpectralIndex,
    TutorialManager,
    Tutorial,
    TutorialStep,
)
from openeo_ai.education.knowledge_base import ConceptCategory
from openeo_ai.education.tutorials import TutorialDifficulty, StepType


class TestSpectralIndex:
    """Tests for SpectralIndex dataclass."""

    def test_spectral_index_creation(self):
        """Test creating a spectral index."""
        idx = SpectralIndex(
            name="Test Index",
            abbreviation="TI",
            formula="(a - b) / (a + b)",
            description="A test index",
            bands_required=["a", "b"],
        )

        assert idx.name == "Test Index"
        assert idx.abbreviation == "TI"
        assert idx.formula == "(a - b) / (a + b)"
        assert "a" in idx.bands_required
        assert "b" in idx.bands_required

    def test_spectral_index_default_range(self):
        """Test default value range."""
        idx = SpectralIndex(
            name="Test",
            abbreviation="T",
            formula="x",
            description="Test",
            bands_required=["x"],
        )

        assert idx.value_range == (-1.0, 1.0)

    def test_get_openeo_formula_with_mapping(self):
        """Test formula band name substitution."""
        idx = SpectralIndex(
            name="Test",
            abbreviation="T",
            formula="(nir - red) / (nir + red)",
            description="Test",
            bands_required=["red", "nir"],
        )

        mapping = {"nir": "B08", "red": "B04"}
        formula = idx.get_openeo_formula(mapping)

        assert "B08" in formula
        assert "B04" in formula
        assert "nir" not in formula


class TestKnowledgeBase:
    """Tests for KnowledgeBase class."""

    @pytest.fixture
    def kb(self):
        """Create a KnowledgeBase instance."""
        return KnowledgeBase()

    def test_knowledge_base_initialization(self, kb):
        """Test knowledge base initializes with content."""
        assert len(kb._indices) > 0
        assert len(kb._concepts) > 0

    def test_get_index_by_name(self, kb):
        """Test getting index by name."""
        ndvi = kb.get_index("ndvi")

        assert ndvi is not None
        assert ndvi.abbreviation == "NDVI"
        assert "nir" in ndvi.bands_required
        assert "red" in ndvi.bands_required

    def test_get_index_by_abbreviation(self, kb):
        """Test getting index by abbreviation."""
        ndvi = kb.get_index("NDVI")

        assert ndvi is not None
        assert "vegetation" in ndvi.name.lower()

    def test_get_index_case_insensitive(self, kb):
        """Test case insensitive index lookup."""
        ndvi1 = kb.get_index("ndvi")
        ndvi2 = kb.get_index("NDVI")
        ndvi3 = kb.get_index("Ndvi")

        assert ndvi1 == ndvi2 == ndvi3

    def test_get_unknown_index(self, kb):
        """Test getting unknown index returns None."""
        result = kb.get_index("unknown_index")
        assert result is None

    def test_list_indices(self, kb):
        """Test listing all indices."""
        indices = kb.list_indices()

        assert len(indices) >= 5  # Should have at least NDVI, NDWI, EVI, etc.
        names = [idx.abbreviation for idx in indices]
        assert "NDVI" in names
        assert "NDWI" in names

    def test_list_indices_by_category(self, kb):
        """Test filtering indices by application category."""
        veg_indices = kb.list_indices(category="vegetation")

        assert len(veg_indices) > 0
        for idx in veg_indices:
            assert any("vegetation" in app.lower() for app in idx.applications)

    def test_get_concept(self, kb):
        """Test getting a concept by ID."""
        concept = kb.get_concept("atmospheric_correction")

        assert concept is not None
        assert "atmospheric" in concept.title.lower()
        assert concept.category == ConceptCategory.ATMOSPHERIC

    def test_get_unknown_concept(self, kb):
        """Test getting unknown concept returns None."""
        result = kb.get_concept("nonexistent_concept")
        assert result is None

    def test_list_concepts(self, kb):
        """Test listing concepts."""
        concepts = kb.list_concepts()

        assert len(concepts) > 0

    def test_list_concepts_by_category(self, kb):
        """Test filtering concepts by category."""
        processing_concepts = kb.list_concepts(
            category=ConceptCategory.DATA_PROCESSING
        )

        for concept in processing_concepts:
            assert concept.category == ConceptCategory.DATA_PROCESSING

    def test_list_concepts_by_difficulty(self, kb):
        """Test filtering concepts by difficulty."""
        beginner_concepts = kb.list_concepts(difficulty="beginner")

        for concept in beginner_concepts:
            assert concept.difficulty == "beginner"

    def test_get_band_mapping(self, kb):
        """Test getting band mapping for collection."""
        mapping = kb.get_band_mapping("sentinel-2-l2a")

        assert "red" in mapping
        assert "nir" in mapping
        assert mapping["red"] == "red"

    def test_get_band_mapping_unknown_collection(self, kb):
        """Test band mapping for unknown collection."""
        mapping = kb.get_band_mapping("unknown-collection")
        assert mapping == {}

    def test_explain_index(self, kb):
        """Test generating index explanation."""
        explanation = kb.explain_index("NDVI")

        assert "Normalized Difference Vegetation Index" in explanation
        assert "NDVI" in explanation
        assert "formula" in explanation.lower()

    def test_explain_unknown_index(self, kb):
        """Test explaining unknown index."""
        explanation = kb.explain_index("UNKNOWN")
        assert "Unknown index" in explanation

    def test_search_finds_indices(self, kb):
        """Test searching finds relevant indices."""
        results = kb.search("vegetation")

        assert len(results["indices"]) > 0
        # NDVI should be in results
        abbreviations = [idx.abbreviation for idx in results["indices"]]
        assert "NDVI" in abbreviations

    def test_search_finds_concepts(self, kb):
        """Test searching finds relevant concepts."""
        results = kb.search("cloud")

        assert len(results["concepts"]) > 0


class TestEOConcept:
    """Tests for EOConcept dataclass."""

    def test_concept_creation(self):
        """Test creating an EO concept."""
        concept = EOConcept(
            id="test_concept",
            title="Test Concept",
            category=ConceptCategory.DATA_PROCESSING,
            summary="A test concept",
            detailed_explanation="Detailed explanation here",
            examples=["Example 1"],
            tags=["test"],
        )

        assert concept.id == "test_concept"
        assert concept.title == "Test Concept"
        assert concept.category == ConceptCategory.DATA_PROCESSING
        assert len(concept.examples) == 1
        assert concept.difficulty == "beginner"  # Default


class TestTutorialStep:
    """Tests for TutorialStep dataclass."""

    def test_step_creation(self):
        """Test creating a tutorial step."""
        step = TutorialStep(
            id="step1",
            title="First Step",
            step_type=StepType.EXPLANATION,
            content="This is the first step.",
        )

        assert step.id == "step1"
        assert step.step_type == StepType.EXPLANATION
        assert step.hints == []  # Default empty

    def test_step_with_code(self):
        """Test step with code example."""
        step = TutorialStep(
            id="step2",
            title="Code Step",
            step_type=StepType.CODE_EXAMPLE,
            content="Here's some code",
            code="print('hello')",
        )

        assert step.code == "print('hello')"

    def test_step_to_dict(self):
        """Test step serialization."""
        step = TutorialStep(
            id="step1",
            title="Test",
            step_type=StepType.EXPLANATION,
            content="Content",
            hints=["Hint 1"],
        )

        data = step.to_dict()

        assert data["id"] == "step1"
        assert data["step_type"] == "explanation"
        assert "Hint 1" in data["hints"]


class TestTutorial:
    """Tests for Tutorial dataclass."""

    @pytest.fixture
    def tutorial(self):
        """Create a sample tutorial."""
        return Tutorial(
            id="test_tutorial",
            title="Test Tutorial",
            description="A test tutorial",
            difficulty=TutorialDifficulty.BEGINNER,
            estimated_minutes=10,
            steps=[
                TutorialStep(
                    id="step1",
                    title="Step 1",
                    step_type=StepType.EXPLANATION,
                    content="First step",
                ),
                TutorialStep(
                    id="step2",
                    title="Step 2",
                    step_type=StepType.CODE_EXAMPLE,
                    content="Second step",
                    code="x = 1",
                ),
            ],
            tags=["test"],
        )

    def test_tutorial_creation(self, tutorial):
        """Test tutorial creation."""
        assert tutorial.id == "test_tutorial"
        assert tutorial.total_steps == 2
        assert tutorial.difficulty == TutorialDifficulty.BEGINNER

    def test_get_step_by_id(self, tutorial):
        """Test getting step by ID."""
        step = tutorial.get_step("step1")

        assert step is not None
        assert step.title == "Step 1"

    def test_get_step_by_index(self, tutorial):
        """Test getting step by index."""
        step = tutorial.get_step_by_index(0)

        assert step is not None
        assert step.id == "step1"

    def test_get_step_out_of_range(self, tutorial):
        """Test getting step with invalid index."""
        step = tutorial.get_step_by_index(99)
        assert step is None

    def test_tutorial_to_dict(self, tutorial):
        """Test tutorial serialization."""
        data = tutorial.to_dict()

        assert data["id"] == "test_tutorial"
        assert data["total_steps"] == 2
        assert data["difficulty"] == "beginner"
        assert len(data["steps"]) == 2


class TestTutorialManager:
    """Tests for TutorialManager class."""

    @pytest.fixture
    def manager(self):
        """Create a TutorialManager instance."""
        return TutorialManager()

    def test_manager_initialization(self, manager):
        """Test manager initializes with tutorials."""
        tutorials = manager.list_tutorials()
        assert len(tutorials) > 0

    def test_list_tutorials(self, manager):
        """Test listing all tutorials."""
        tutorials = manager.list_tutorials()

        assert len(tutorials) >= 2
        ids = [t.id for t in tutorials]
        assert "ndvi_basics" in ids

    def test_list_tutorials_by_difficulty(self, manager):
        """Test filtering tutorials by difficulty."""
        beginner = manager.list_tutorials(difficulty=TutorialDifficulty.BEGINNER)

        for tutorial in beginner:
            assert tutorial.difficulty == TutorialDifficulty.BEGINNER

    def test_list_tutorials_by_tag(self, manager):
        """Test filtering tutorials by tag."""
        ndvi_tutorials = manager.list_tutorials(tag="ndvi")

        assert len(ndvi_tutorials) > 0
        for tutorial in ndvi_tutorials:
            assert "ndvi" in tutorial.tags

    def test_get_tutorial(self, manager):
        """Test getting a tutorial by ID."""
        tutorial = manager.get_tutorial("ndvi_basics")

        assert tutorial is not None
        assert "NDVI" in tutorial.title

    def test_get_unknown_tutorial(self, manager):
        """Test getting unknown tutorial returns None."""
        result = manager.get_tutorial("nonexistent")
        assert result is None

    def test_start_tutorial(self, manager):
        """Test starting a tutorial."""
        progress = manager.start_tutorial("ndvi_basics", "user123")

        assert progress["tutorial_id"] == "ndvi_basics"
        assert progress["current_step"] == 0
        assert progress["completed"] is False

    def test_start_unknown_tutorial_raises(self, manager):
        """Test starting unknown tutorial raises error."""
        with pytest.raises(ValueError):
            manager.start_tutorial("nonexistent", "user123")

    def test_advance_step(self, manager):
        """Test advancing through tutorial steps."""
        manager.start_tutorial("ndvi_basics", "user123")
        progress = manager.advance_step("ndvi_basics", "user123")

        assert progress["current_step"] == 1
        assert 0 in progress["completed_steps"]

    def test_get_progress(self, manager):
        """Test getting tutorial progress."""
        manager.start_tutorial("ndvi_basics", "user123")

        progress = manager.get_progress("ndvi_basics", "user123")

        assert progress is not None
        assert progress["tutorial_id"] == "ndvi_basics"

    def test_get_progress_not_started(self, manager):
        """Test getting progress for non-started tutorial."""
        progress = manager.get_progress("ndvi_basics", "new_user")
        assert progress is None

    def test_complete_tutorial(self, manager):
        """Test completing a tutorial."""
        manager.start_tutorial("ndvi_basics", "user123")
        tutorial = manager.get_tutorial("ndvi_basics")

        # Advance through all steps
        for _ in range(tutorial.total_steps):
            progress = manager.advance_step("ndvi_basics", "user123")

        assert progress["completed"] is True
