"""
Correction Service.

Handles user corrections with undo capability:
- Apply corrections to extraction or vision data
- Store correction history (last 10)
- Undo last correction
"""

import json
from typing import Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.core.logger import get_logger
from src.db.models import CorrectionHistory, ImageAnalysis, Project

logger = get_logger(__name__)
from src.core.llm.provider import LLMProvider
from src.core.langgraph.utils import parse_json
from .session_cache import SessionCache


class CorrectionService:
    """
    Service for managing user corrections with undo capability.

    Responsibilities:
    - Apply corrections to extraction data
    - Apply corrections to vision data
    - Store correction history (keep last 10)
    - Undo last correction
    """

    # Maximum corrections to keep per project
    MAX_CORRECTIONS = 10

    def __init__(
        self,
        db: Session,
        llm_provider: Optional[LLMProvider] = None,
        cache: Optional[SessionCache] = None
    ):
        self.db = db
        self.llm = llm_provider or LLMProvider.for_llm()
        self.cache = cache or SessionCache()

    async def apply_correction(
        self,
        project_id: UUID,
        correction_type: str,
        field_changed: str,
        new_value: Any,
        user_message: str
    ) -> CorrectionHistory:
        """
        Apply user correction and store in history.

        Args:
            project_id: UUID of the project
            correction_type: "extraction" or "vision"
            field_changed: Dot-notation path to field (e.g., "materials.floor")
            new_value: New value to set
            user_message: User's correction message

        Returns:
            CorrectionHistory record
        """
        logger.info(f"[CorrectionService] Applying {correction_type} correction: {field_changed}")

        # Get current value
        old_value = await self._get_current_value(project_id, correction_type, field_changed)

        # Store correction in history
        correction = CorrectionHistory(
            project_id=project_id,
            correction_type=correction_type,
            field_changed=field_changed,
            old_value=old_value,
            new_value=new_value,
            user_message=user_message[:500] if user_message else None
        )
        self.db.add(correction)

        # Apply the change
        await self._set_value(project_id, correction_type, field_changed, new_value)

        self.db.commit()
        self.db.refresh(correction)

        # Update cache
        self.cache.add_correction(project_id, correction)

        # Cleanup old corrections
        await self._cleanup_old_corrections(project_id)

        logger.info(f"[CorrectionService] Correction applied and stored: {correction.id}")
        return correction

    async def apply_correction_from_message(
        self,
        project_id: UUID,
        user_message: str,
        current_data: dict,
        data_type: str = "extraction"
    ) -> tuple[dict, CorrectionHistory]:
        """
        Use AI to interpret user's correction and apply it.

        Args:
            project_id: UUID of the project
            user_message: User's correction message
            current_data: Current extracted data
            data_type: "extraction" or "vision"

        Returns:
            (updated_data, correction_record)
        """
        logger.info(f"[CorrectionService] Interpreting correction: {user_message[:50]}...")

        prompt = f"""You are helping update renovation data based on user feedback.

## Current Data
{json.dumps(current_data, indent=2)[:2000]}

## User's Correction
"{user_message}"

## Your Task
Apply the user's correction to the data. The user might:
- Add new items (e.g., "there's also a mirror on the wall")
- Correct existing items (e.g., "the flooring is hardwood, not laminate")
- Remove items (e.g., "remove the rug, it's not part of the renovation")
- Change details (e.g., "the walls are beige, not white")

Return JSON with:
{{
    "updated_data": {{...complete updated data...}},
    "field_changed": "path.to.field",
    "old_value": {{...old value...}},
    "new_value": {{...new value...}},
    "change_summary": "Brief description of what changed"
}}

Return the COMPLETE updated data. Return valid JSON only, no markdown."""

        try:
            response = await self.llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You update renovation data based on user corrections. Return JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            result = parse_json(response)
            updated_data = result.get("updated_data", current_data)
            field_changed = result.get("field_changed", "unknown")
            old_value = result.get("old_value")
            new_value = result.get("new_value")

            # Store correction
            correction = CorrectionHistory(
                project_id=project_id,
                correction_type=data_type,
                field_changed=field_changed,
                old_value=old_value,
                new_value=new_value,
                user_message=user_message[:500]
            )
            self.db.add(correction)
            self.db.commit()
            self.db.refresh(correction)

            # Update cache
            self.cache.add_correction(project_id, correction)

            # Cleanup old corrections
            await self._cleanup_old_corrections(project_id)

            return updated_data, correction

        except Exception as e:
            logger.info(f"[CorrectionService] Failed to interpret correction: {e}")
            raise ValueError(f"Failed to apply correction: {e}")

    async def undo_last_correction(
        self,
        project_id: UUID
    ) -> tuple[bool, str]:
        """
        Undo the last correction for this project.

        Args:
            project_id: UUID of the project

        Returns:
            (success, message)
        """
        # Get last correction
        last = self.db.query(CorrectionHistory).filter_by(
            project_id=project_id
        ).order_by(desc(CorrectionHistory.created_at)).first()

        if not last:
            return False, "Nothing to undo."

        logger.info(f"[CorrectionService] Undoing correction: {last.field_changed}")

        try:
            # Rollback the change
            await self._set_value(
                project_id,
                last.correction_type,
                last.field_changed,
                last.old_value
            )

            # Delete the correction record
            self.db.delete(last)
            self.db.commit()

            # Update cache
            corrections = self.cache.get_corrections(project_id)
            if corrections:
                corrections.pop()
                self.cache.set_corrections(project_id, corrections)

            return True, f"Undone: {last.field_changed} reverted to previous value."

        except Exception as e:
            logger.info(f"[CorrectionService] Failed to undo: {e}")
            return False, f"Failed to undo: {str(e)}"

    async def get_correction_history(
        self,
        project_id: UUID,
        limit: int = 10
    ) -> list[CorrectionHistory]:
        """Get correction history for a project."""
        # Try cache first
        cached = self.cache.get_corrections(project_id)
        if cached:
            return cached[:limit]

        # Query database
        corrections = self.db.query(CorrectionHistory).filter_by(
            project_id=project_id
        ).order_by(desc(CorrectionHistory.created_at)).limit(limit).all()

        # Cache results
        self.cache.set_corrections(project_id, corrections)

        return corrections

    async def _get_current_value(
        self,
        project_id: UUID,
        data_type: str,
        field_path: str
    ) -> Any:
        """Get current value from database."""
        if data_type == "extraction":
            analysis = self.db.query(ImageAnalysis).filter_by(
                project_id=project_id
            ).order_by(desc(ImageAnalysis.created_at)).first()

            if analysis and analysis.extracted_features:
                return self._get_nested_value(analysis.extracted_features, field_path)

        elif data_type == "vision":
            project = self.db.query(Project).filter_by(id=project_id).first()
            if project and project.renovation_vision:
                return self._get_nested_value(project.renovation_vision, field_path)

        return None

    async def _set_value(
        self,
        project_id: UUID,
        data_type: str,
        field_path: str,
        value: Any
    ) -> None:
        """Set value in database."""
        if data_type == "extraction":
            analysis = self.db.query(ImageAnalysis).filter_by(
                project_id=project_id
            ).order_by(desc(ImageAnalysis.created_at)).first()

            if analysis:
                if not analysis.extracted_features:
                    analysis.extracted_features = {}
                self._set_nested_value(analysis.extracted_features, field_path, value)
                # Mark as modified for SQLAlchemy
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(analysis, 'extracted_features')

        elif data_type == "vision":
            project = self.db.query(Project).filter_by(id=project_id).first()
            if project:
                if not project.renovation_vision:
                    project.renovation_vision = {}
                self._set_nested_value(project.renovation_vision, field_path, value)
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(project, 'renovation_vision')

    async def _cleanup_old_corrections(self, project_id: UUID) -> None:
        """Keep only last MAX_CORRECTIONS corrections per project."""
        corrections = self.db.query(CorrectionHistory).filter_by(
            project_id=project_id
        ).order_by(desc(CorrectionHistory.created_at)).all()

        if len(corrections) > self.MAX_CORRECTIONS:
            to_delete = corrections[self.MAX_CORRECTIONS:]
            for c in to_delete:
                self.db.delete(c)
            self.db.commit()
            logger.info(f"[CorrectionService] Cleaned up {len(to_delete)} old corrections")

    def _get_nested_value(self, obj: dict, path: str) -> Any:
        """Get value from nested dict using dot notation."""
        if not obj or not path:
            return None

        keys = path.split(".")
        value = obj

        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    value = value[int(key)]
                else:
                    return None
            return value
        except (KeyError, IndexError, TypeError):
            return None

    def _set_nested_value(self, obj: dict, path: str, value: Any) -> None:
        """Set value in nested dict using dot notation."""
        if not obj or not path:
            return

        keys = path.split(".")
        target = obj

        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        target[keys[-1]] = value

    def can_undo(self, project_id: UUID) -> bool:
        """Check if there are corrections to undo."""
        count = self.db.query(CorrectionHistory).filter_by(
            project_id=project_id
        ).count()
        return count > 0
