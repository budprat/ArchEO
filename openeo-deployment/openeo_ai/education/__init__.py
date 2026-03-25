"""
OpenEO AI Education module.

ABOUTME: Educational resources for Earth Observation concepts and OpenEO workflows.
Provides knowledge base, tutorials, and guided learning for users.
"""

from .knowledge_base import KnowledgeBase, EOConcept, SpectralIndex
from .tutorials import TutorialManager, Tutorial, TutorialStep

__all__ = [
    "KnowledgeBase",
    "EOConcept",
    "SpectralIndex",
    "TutorialManager",
    "Tutorial",
    "TutorialStep",
]
