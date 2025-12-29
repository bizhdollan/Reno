"""
Session-level cache for database objects.

Prevents redundant DB queries within the same conversation session.
Cache is cleared at the end of each conversation turn or when explicitly cleared.
"""

from typing import Dict, Any, Optional
from uuid import UUID


class SessionCache:
    """
    In-memory cache for database objects during a conversation session.

    This cache prevents redundant DB queries by storing objects that have
    already been fetched. It should be cleared at the end of each conversation
    or when the state is persisted.

    Usage:
        cache = SessionCache()

        # Try cache first, then DB
        analysis = cache.get_image_analysis(image_id)
        if not analysis:
            analysis = await db.query(ImageAnalysis).get(image_id)
            cache.set_image_analysis(image_id, analysis)
    """

    def __init__(self):
        """Initialize empty caches for each entity type."""
        self._image_analysis: Dict[UUID, Any] = {}
        self._image_metadata: Dict[UUID, Any] = {}
        self._generation_history: Dict[UUID, Any] = {}
        self._critical_elements: Dict[UUID, Any] = {}
        self._budget_context: Dict[UUID, Any] = {}
        self._correction_history: Dict[UUID, list] = {}  # List per project

    # =========================================================================
    # Image Analysis Cache
    # =========================================================================

    def get_image_analysis(self, image_id: UUID) -> Optional[Any]:
        """Get cached image analysis or None."""
        return self._image_analysis.get(image_id)

    def set_image_analysis(self, image_id: UUID, analysis: Any) -> None:
        """Cache image analysis."""
        self._image_analysis[image_id] = analysis

    def get_image_analyses_by_project(self, project_id: UUID) -> list:
        """Get all cached analyses for a project."""
        return [
            a for a in self._image_analysis.values()
            if getattr(a, 'project_id', None) == project_id
        ]

    # =========================================================================
    # Image Metadata Cache
    # =========================================================================

    def get_image_metadata(self, image_id: UUID) -> Optional[Any]:
        """Get cached image metadata or None."""
        return self._image_metadata.get(image_id)

    def set_image_metadata(self, image_id: UUID, metadata: Any) -> None:
        """Cache image metadata."""
        self._image_metadata[image_id] = metadata

    def get_metadata_by_analysis(self, analysis_id: UUID) -> Optional[Any]:
        """Get metadata for a specific analysis."""
        for metadata in self._image_metadata.values():
            if getattr(metadata, 'image_analysis_id', None) == analysis_id:
                return metadata
        return None

    # =========================================================================
    # Generation History Cache
    # =========================================================================

    def get_generation(self, generation_id: UUID) -> Optional[Any]:
        """Get cached generation history or None."""
        return self._generation_history.get(generation_id)

    def set_generation(self, generation_id: UUID, generation: Any) -> None:
        """Cache generation history."""
        self._generation_history[generation_id] = generation

    def get_latest_generation(self, project_id: UUID) -> Optional[Any]:
        """Get the most recent generation for a project."""
        project_generations = [
            g for g in self._generation_history.values()
            if getattr(g, 'project_id', None) == project_id
        ]
        if not project_generations:
            return None
        return max(project_generations, key=lambda g: getattr(g, 'created_at', 0))

    # =========================================================================
    # Critical Elements Cache
    # =========================================================================

    def get_critical_elements(self, image_id: UUID) -> Optional[dict]:
        """Get cached critical elements or None."""
        return self._critical_elements.get(image_id)

    def set_critical_elements(self, image_id: UUID, elements: dict) -> None:
        """Cache critical elements."""
        self._critical_elements[image_id] = elements

    # =========================================================================
    # Budget Context Cache
    # =========================================================================

    def get_budget_context(self, project_id: UUID) -> Optional[Any]:
        """Get cached budget context or None."""
        return self._budget_context.get(project_id)

    def set_budget_context(self, project_id: UUID, context: Any) -> None:
        """Cache budget context."""
        self._budget_context[project_id] = context

    # =========================================================================
    # Correction History Cache
    # =========================================================================

    def get_corrections(self, project_id: UUID) -> list:
        """Get cached corrections for a project."""
        return self._correction_history.get(project_id, [])

    def set_corrections(self, project_id: UUID, corrections: list) -> None:
        """Cache corrections for a project."""
        self._correction_history[project_id] = corrections

    def add_correction(self, project_id: UUID, correction: Any) -> None:
        """Add a correction to the cache."""
        if project_id not in self._correction_history:
            self._correction_history[project_id] = []
        self._correction_history[project_id].append(correction)

    # =========================================================================
    # Cache Management
    # =========================================================================

    def clear(self) -> None:
        """Clear all caches. Call at end of conversation or on state persist."""
        self._image_analysis.clear()
        self._image_metadata.clear()
        self._generation_history.clear()
        self._critical_elements.clear()
        self._budget_context.clear()
        self._correction_history.clear()

    def clear_project(self, project_id: UUID) -> None:
        """Clear all cached data for a specific project."""
        # Remove image analyses for this project
        to_remove = [
            k for k, v in self._image_analysis.items()
            if getattr(v, 'project_id', None) == project_id
        ]
        for k in to_remove:
            del self._image_analysis[k]

        # Remove image metadata for this project
        to_remove = [
            k for k, v in self._image_metadata.items()
            if getattr(v, 'project_id', None) == project_id
        ]
        for k in to_remove:
            del self._image_metadata[k]

        # Remove generations for this project
        to_remove = [
            k for k, v in self._generation_history.items()
            if getattr(v, 'project_id', None) == project_id
        ]
        for k in to_remove:
            del self._generation_history[k]

        # Remove budget context
        if project_id in self._budget_context:
            del self._budget_context[project_id]

        # Remove corrections
        if project_id in self._correction_history:
            del self._correction_history[project_id]

    def stats(self) -> dict:
        """Get cache statistics for debugging."""
        return {
            "image_analysis_count": len(self._image_analysis),
            "image_metadata_count": len(self._image_metadata),
            "generation_history_count": len(self._generation_history),
            "critical_elements_count": len(self._critical_elements),
            "budget_context_count": len(self._budget_context),
            "correction_history_projects": len(self._correction_history),
        }
