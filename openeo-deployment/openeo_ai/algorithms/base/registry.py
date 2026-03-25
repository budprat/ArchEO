# ABOUTME: Algorithm registry for discovering and managing algorithms.
# Provides singleton registry for algorithm lookup and instantiation.

"""
Algorithm registry for OpenEO AI.

Provides:
- Singleton AlgorithmRegistry
- Auto-discovery of algorithms
- Lookup by ID, category, or tags
"""

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type

from .loader import BaseAlgorithm, AlgorithmMetadata

logger = logging.getLogger(__name__)


class AlgorithmRegistry:
    """
    Singleton registry for algorithm discovery and management.

    Usage:
        registry = AlgorithmRegistry()

        # Discover algorithms in a package
        registry.discover("openeo_ai.algorithms.indices")

        # Register an algorithm class
        registry.register(NDVIAlgorithm)

        # Get algorithm by ID
        algo = registry.get("ndvi")

        # List all algorithms
        all_algos = registry.list_all()

        # Find by category
        indices = registry.find_by_category("index")
    """

    _instance: Optional["AlgorithmRegistry"] = None
    _initialized: bool = False

    def __new__(cls) -> "AlgorithmRegistry":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the registry."""
        if self._initialized:
            return

        self._algorithms: Dict[str, Type[BaseAlgorithm]] = {}
        self._metadata_cache: Dict[str, AlgorithmMetadata] = {}
        self._initialized = True

        # Auto-discover built-in algorithms
        self._discover_builtin()

    def _discover_builtin(self):
        """Discover built-in algorithms."""
        try:
            self.discover("openeo_ai.algorithms.indices")
        except Exception as e:
            logger.debug(f"No built-in algorithms found: {e}")

    def register(self, algorithm_class: Type[BaseAlgorithm]) -> None:
        """
        Register an algorithm class.

        Args:
            algorithm_class: Class that inherits from BaseAlgorithm
        """
        # Instantiate to get metadata
        try:
            instance = algorithm_class()
            metadata = instance.metadata
            algo_id = metadata.id

            if algo_id in self._algorithms:
                logger.warning(f"Overwriting existing algorithm: {algo_id}")

            self._algorithms[algo_id] = algorithm_class
            self._metadata_cache[algo_id] = metadata
            logger.debug(f"Registered algorithm: {algo_id}")

        except Exception as e:
            logger.error(f"Failed to register algorithm {algorithm_class}: {e}")
            raise

    def unregister(self, algo_id: str) -> bool:
        """
        Unregister an algorithm.

        Args:
            algo_id: Algorithm ID to remove

        Returns:
            True if removed, False if not found
        """
        if algo_id in self._algorithms:
            del self._algorithms[algo_id]
            del self._metadata_cache[algo_id]
            logger.debug(f"Unregistered algorithm: {algo_id}")
            return True
        return False

    def discover(self, package_name: str) -> int:
        """
        Discover and register algorithms from a package.

        Args:
            package_name: Python package name to scan

        Returns:
            Number of algorithms discovered
        """
        count = 0
        try:
            package = importlib.import_module(package_name)
        except ImportError as e:
            logger.warning(f"Could not import package {package_name}: {e}")
            return 0

        # Get package path
        if not hasattr(package, "__path__"):
            # Single module, not a package
            count += self._scan_module(package)
            return count

        # Iterate through submodules
        for importer, modname, ispkg in pkgutil.walk_packages(
            package.__path__,
            prefix=package_name + "."
        ):
            if ispkg:
                continue  # Skip subpackages

            try:
                module = importlib.import_module(modname)
                count += self._scan_module(module)
            except Exception as e:
                logger.warning(f"Error importing {modname}: {e}")

        logger.info(f"Discovered {count} algorithms in {package_name}")
        return count

    def _scan_module(self, module) -> int:
        """Scan a module for algorithm classes."""
        count = 0
        for name in dir(module):
            obj = getattr(module, name)

            # Skip non-classes and the base class itself
            if not isinstance(obj, type):
                continue
            if obj is BaseAlgorithm:
                continue
            if not issubclass(obj, BaseAlgorithm):
                continue

            # Skip abstract classes
            try:
                instance = obj()
                _ = instance.metadata  # Verify it's concrete
                self.register(obj)
                count += 1
            except (TypeError, NotImplementedError):
                # Abstract class or incomplete implementation
                pass
            except Exception as e:
                logger.debug(f"Skipping {name}: {e}")

        return count

    def get(self, algo_id: str) -> Optional[BaseAlgorithm]:
        """
        Get an algorithm instance by ID.

        Args:
            algo_id: Algorithm ID

        Returns:
            Algorithm instance or None if not found
        """
        algorithm_class = self._algorithms.get(algo_id)
        if algorithm_class:
            return algorithm_class()
        return None

    def get_class(self, algo_id: str) -> Optional[Type[BaseAlgorithm]]:
        """
        Get an algorithm class by ID.

        Args:
            algo_id: Algorithm ID

        Returns:
            Algorithm class or None if not found
        """
        return self._algorithms.get(algo_id)

    def exists(self, algo_id: str) -> bool:
        """Check if an algorithm exists."""
        return algo_id in self._algorithms

    def list_all(self) -> List[AlgorithmMetadata]:
        """List metadata for all registered algorithms."""
        return list(self._metadata_cache.values())

    def list_ids(self) -> List[str]:
        """List all algorithm IDs."""
        return list(self._algorithms.keys())

    def find_by_category(self, category: str) -> List[AlgorithmMetadata]:
        """
        Find algorithms by category.

        Args:
            category: Category to filter by

        Returns:
            List of matching algorithm metadata
        """
        return [
            m for m in self._metadata_cache.values()
            if m.category.lower() == category.lower()
        ]

    def find_by_tag(self, tag: str) -> List[AlgorithmMetadata]:
        """
        Find algorithms by tag.

        Args:
            tag: Tag to search for

        Returns:
            List of matching algorithm metadata
        """
        tag_lower = tag.lower()
        return [
            m for m in self._metadata_cache.values()
            if any(t.lower() == tag_lower for t in m.tags)
        ]

    def search(self, query: str) -> List[AlgorithmMetadata]:
        """
        Search algorithms by name, description, or tags.

        Args:
            query: Search query

        Returns:
            List of matching algorithm metadata
        """
        query_lower = query.lower()
        results = []

        for metadata in self._metadata_cache.values():
            # Search in name
            if query_lower in metadata.name.lower():
                results.append(metadata)
                continue

            # Search in description
            if query_lower in metadata.description.lower():
                results.append(metadata)
                continue

            # Search in tags
            if any(query_lower in tag.lower() for tag in metadata.tags):
                results.append(metadata)
                continue

        return results

    def get_categories(self) -> List[str]:
        """Get list of all categories."""
        return list(set(m.category for m in self._metadata_cache.values()))

    def get_tags(self) -> List[str]:
        """Get list of all tags."""
        tags = set()
        for m in self._metadata_cache.values():
            tags.update(m.tags)
        return sorted(tags)

    def to_dict(self) -> Dict[str, Dict]:
        """Export registry as dictionary."""
        return {
            algo_id: metadata.to_dict()
            for algo_id, metadata in self._metadata_cache.items()
        }

    def clear(self) -> None:
        """Clear all registered algorithms."""
        self._algorithms.clear()
        self._metadata_cache.clear()
        logger.debug("Cleared algorithm registry")

    def __len__(self) -> int:
        return len(self._algorithms)

    def __contains__(self, algo_id: str) -> bool:
        return algo_id in self._algorithms

    def __iter__(self):
        return iter(self._algorithms.keys())


# Module-level singleton accessor
_registry: Optional[AlgorithmRegistry] = None


def get_algorithm_registry() -> AlgorithmRegistry:
    """Get the global algorithm registry singleton."""
    global _registry
    if _registry is None:
        _registry = AlgorithmRegistry()
    return _registry


def register_algorithm(algorithm_class: Type[BaseAlgorithm]) -> Type[BaseAlgorithm]:
    """
    Decorator to register an algorithm class.

    Usage:
        @register_algorithm
        class MyAlgorithm(BaseAlgorithm):
            ...
    """
    get_algorithm_registry().register(algorithm_class)
    return algorithm_class
