"""
Sticky Notes Tool

Manages user preferences and session notes that persist across the conversation.
These notes are included in LLM prompts to maintain context and personalization.
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)


class StickyNoteCategory:
    """Categories for organizing sticky notes."""
    STYLE = "style"           # Style preferences (modern, traditional, etc.)
    MATERIAL = "material"     # Material preferences (no carpet, prefer marble, etc.)
    COLOR = "color"           # Color preferences (warm tones, no red, etc.)
    CONSTRAINT = "constraint" # Constraints (budget, timeline, restrictions)
    BRAND = "brand"           # Brand preferences
    AVOID = "avoid"           # Things to avoid
    MUST_HAVE = "must_have"   # Required features
    GENERAL = "general"       # General notes


@dataclass
class StickyNote:
    """A single sticky note preference."""
    content: str
    category: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    source: str = "user"  # user, inferred, image_analysis
    confidence: float = 1.0  # How confident we are in this preference
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "confidence": self.confidence,
            "active": self.active
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StickyNote":
        return cls(
            content=data["content"],
            category=data["category"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            source=data.get("source", "user"),
            confidence=data.get("confidence", 1.0),
            active=data.get("active", True)
        )


async def add_sticky_note(
    project_id: str,
    content: str,
    category: str = StickyNoteCategory.GENERAL,
    source: str = "user",
    confidence: float = 1.0
) -> ToolResult:
    """
    Add a preference note to the project.

    Args:
        project_id: Project UUID or token
        content: Note content
        category: Note category (style, material, color, constraint, etc.)
        source: Where the note came from (user, inferred, image_analysis)
        confidence: Confidence level (1.0 for user-provided)

    Returns:
        ToolResult with the added note
    """
    start_time = time.time()
    tool_name = "add_sticky_note"

    if not content or not content.strip():
        return ToolResult.error_result(
            error="Note content cannot be empty",
            tool_name=tool_name
        )

    # Validate category
    valid_categories = [
        StickyNoteCategory.STYLE,
        StickyNoteCategory.MATERIAL,
        StickyNoteCategory.COLOR,
        StickyNoteCategory.CONSTRAINT,
        StickyNoteCategory.BRAND,
        StickyNoteCategory.AVOID,
        StickyNoteCategory.MUST_HAVE,
        StickyNoteCategory.GENERAL,
    ]
    if category not in valid_categories:
        category = StickyNoteCategory.GENERAL

    from src.db.database import SessionLocal
    from src.db.models import Project

    db = SessionLocal()
    try:
        # Find project
        try:
            project = db.query(Project).filter(Project.id == UUID(project_id)).first()
        except ValueError:
            project = db.query(Project).filter(Project.token == project_id).first()

        if not project:
            return ToolResult.error_result(
                error=f"Project not found: {project_id}",
                tool_name=tool_name
            )

        # Create new note
        note = StickyNote(
            content=content.strip(),
            category=category,
            source=source,
            confidence=confidence
        )

        # Load existing notes or initialize
        existing_notes = project.session_sticky_notes or []
        existing_notes.append(note.to_dict())

        # Save to database
        project.session_sticky_notes = existing_notes
        db.commit()

        execution_time = (time.time() - start_time) * 1000

        logger.info(f"[sticky_notes] Added note to {project_id}: [{category}] {content[:50]}...")

        return ToolResult.success_result(
            data={
                "note": note.to_dict(),
                "total_notes": len(existing_notes)
            },
            confidence=ConfidenceScore.user_provided() if source == "user" else ConfidenceScore.high(),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[sticky_notes] Error adding note: {e}")
        db.rollback()
        return ToolResult.error_result(
            error=f"Failed to add note: {str(e)}",
            tool_name=tool_name
        )
    finally:
        db.close()


async def get_sticky_notes(
    project_id: str,
    category: Optional[str] = None,
    active_only: bool = True
) -> ToolResult:
    """
    Get all sticky notes for a project.

    Args:
        project_id: Project UUID or token
        category: Optional filter by category
        active_only: If True, only return active notes

    Returns:
        ToolResult with list of notes
    """
    start_time = time.time()
    tool_name = "get_sticky_notes"

    from src.db.database import SessionLocal
    from src.db.models import Project

    db = SessionLocal()
    try:
        # Find project
        try:
            project = db.query(Project).filter(Project.id == UUID(project_id)).first()
        except ValueError:
            project = db.query(Project).filter(Project.token == project_id).first()

        if not project:
            return ToolResult.error_result(
                error=f"Project not found: {project_id}",
                tool_name=tool_name
            )

        notes_data = project.session_sticky_notes or []

        # Filter notes
        notes = [StickyNote.from_dict(n) for n in notes_data]

        if active_only:
            notes = [n for n in notes if n.active]

        if category:
            notes = [n for n in notes if n.category == category]

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "notes": [n.to_dict() for n in notes],
                "count": len(notes),
                "by_category": _group_by_category(notes)
            },
            confidence=ConfidenceScore.high(),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[sticky_notes] Error getting notes: {e}")
        return ToolResult.error_result(
            error=f"Failed to get notes: {str(e)}",
            tool_name=tool_name
        )
    finally:
        db.close()


async def remove_sticky_note(
    project_id: str,
    content: str
) -> ToolResult:
    """
    Remove (deactivate) a sticky note by content.

    Args:
        project_id: Project UUID or token
        content: Content of the note to remove

    Returns:
        ToolResult indicating success/failure
    """
    start_time = time.time()
    tool_name = "remove_sticky_note"

    from src.db.database import SessionLocal
    from src.db.models import Project

    db = SessionLocal()
    try:
        # Find project
        try:
            project = db.query(Project).filter(Project.id == UUID(project_id)).first()
        except ValueError:
            project = db.query(Project).filter(Project.token == project_id).first()

        if not project:
            return ToolResult.error_result(
                error=f"Project not found: {project_id}",
                tool_name=tool_name
            )

        notes_data = project.session_sticky_notes or []

        # Find and deactivate matching note
        found = False
        for note_data in notes_data:
            if note_data.get("content", "").lower() == content.lower():
                note_data["active"] = False
                found = True
                break

        if not found:
            return ToolResult.error_result(
                error=f"Note not found: {content[:50]}...",
                tool_name=tool_name
            )

        project.session_sticky_notes = notes_data
        db.commit()

        execution_time = (time.time() - start_time) * 1000

        logger.info(f"[sticky_notes] Removed note from {project_id}: {content[:50]}...")

        return ToolResult.success_result(
            data={"removed_content": content},
            confidence=ConfidenceScore.high(),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[sticky_notes] Error removing note: {e}")
        db.rollback()
        return ToolResult.error_result(
            error=f"Failed to remove note: {str(e)}",
            tool_name=tool_name
        )
    finally:
        db.close()


async def clear_sticky_notes(
    project_id: str,
    category: Optional[str] = None
) -> ToolResult:
    """
    Clear all sticky notes (or by category).

    Args:
        project_id: Project UUID or token
        category: Optional category to clear (None = all)

    Returns:
        ToolResult with count of cleared notes
    """
    start_time = time.time()
    tool_name = "clear_sticky_notes"

    from src.db.database import SessionLocal
    from src.db.models import Project

    db = SessionLocal()
    try:
        # Find project
        try:
            project = db.query(Project).filter(Project.id == UUID(project_id)).first()
        except ValueError:
            project = db.query(Project).filter(Project.token == project_id).first()

        if not project:
            return ToolResult.error_result(
                error=f"Project not found: {project_id}",
                tool_name=tool_name
            )

        notes_data = project.session_sticky_notes or []
        original_count = len(notes_data)

        if category:
            # Deactivate notes in category
            cleared = 0
            for note_data in notes_data:
                if note_data.get("category") == category and note_data.get("active", True):
                    note_data["active"] = False
                    cleared += 1
        else:
            # Deactivate all
            cleared = sum(1 for n in notes_data if n.get("active", True))
            for note_data in notes_data:
                note_data["active"] = False

        project.session_sticky_notes = notes_data
        db.commit()

        execution_time = (time.time() - start_time) * 1000

        logger.info(f"[sticky_notes] Cleared {cleared} notes from {project_id}")

        return ToolResult.success_result(
            data={
                "cleared_count": cleared,
                "category_cleared": category
            },
            confidence=ConfidenceScore.high(),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[sticky_notes] Error clearing notes: {e}")
        db.rollback()
        return ToolResult.error_result(
            error=f"Failed to clear notes: {str(e)}",
            tool_name=tool_name
        )
    finally:
        db.close()


def format_sticky_notes_for_prompt(notes: List[Dict[str, Any]]) -> str:
    """
    Format sticky notes for inclusion in LLM prompts.

    Args:
        notes: List of note dictionaries

    Returns:
        Formatted string for prompt inclusion
    """
    if not notes:
        return ""

    active_notes = [n for n in notes if n.get("active", True)]

    if not active_notes:
        return ""

    # Group by category
    by_category: Dict[str, List[str]] = {}
    for note in active_notes:
        cat = note.get("category", "general")
        content = note.get("content", "")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(content)

    # Format output
    lines = ["USER PREFERENCES (Sticky Notes):"]

    category_labels = {
        StickyNoteCategory.STYLE: "Style Preferences",
        StickyNoteCategory.MATERIAL: "Material Preferences",
        StickyNoteCategory.COLOR: "Color Preferences",
        StickyNoteCategory.CONSTRAINT: "Constraints",
        StickyNoteCategory.BRAND: "Brand Preferences",
        StickyNoteCategory.AVOID: "Things to Avoid",
        StickyNoteCategory.MUST_HAVE: "Must-Have Features",
        StickyNoteCategory.GENERAL: "General Notes",
    }

    for cat, items in by_category.items():
        label = category_labels.get(cat, cat.title())
        lines.append(f"\n{label}:")
        for item in items:
            lines.append(f"  - {item}")

    return "\n".join(lines)


def _group_by_category(notes: List[StickyNote]) -> Dict[str, int]:
    """Group notes by category and count."""
    counts: Dict[str, int] = {}
    for note in notes:
        counts[note.category] = counts.get(note.category, 0) + 1
    return counts


async def extract_preferences_from_message(
    user_message: str,
    project_type: str = "renovation"
) -> ToolResult:
    """
    Extract preferences from a user message and create sticky notes.

    Uses LLM to identify preferences mentioned in natural language.

    Args:
        user_message: User's message
        project_type: Type of project for context

    Returns:
        ToolResult with extracted preferences
    """
    start_time = time.time()
    tool_name = "extract_preferences"

    if not user_message or len(user_message.strip()) < 10:
        return ToolResult.success_result(
            data={"extracted_notes": [], "count": 0},
            confidence=ConfidenceScore.high(),
            tool_name=tool_name
        )

    from src.core.llm.provider import LLMProvider
    import json

    provider = LLMProvider.for_fast_analysis()

    prompt = f"""Extract user preferences from this message about their {project_type} project.

User message: "{user_message}"

Identify any preferences related to:
- style (modern, traditional, farmhouse, etc.)
- material (hardwood, marble, quartz, etc.)
- color (warm tones, blue accents, etc.)
- constraint (budget limits, timeline, restrictions)
- brand (specific brands mentioned)
- avoid (things they don't want)
- must_have (required features)

Return JSON only:
{{
  "preferences": [
    {{"content": "preference description", "category": "style|material|color|constraint|brand|avoid|must_have|general", "confidence": 0.0-1.0}}
  ]
}}

Only extract CLEAR preferences. If unsure, don't include it. Return empty list if no preferences found."""

    try:
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Extract user preferences as JSON. Be conservative - only extract clear preferences."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000,
            operation_type="preference_extraction"
        )

        # Parse response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(line for line in lines if not line.startswith("```"))

        data = json.loads(response_text)
        preferences = data.get("preferences", [])

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "extracted_notes": preferences,
                "count": len(preferences)
            },
            confidence=ConfidenceScore.high(
                reasoning=f"Extracted {len(preferences)} preferences"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except json.JSONDecodeError as e:
        logger.warning(f"[extract_preferences] JSON parse error: {e}")
        return ToolResult.success_result(
            data={"extracted_notes": [], "count": 0},
            confidence=ConfidenceScore.medium(reasoning="Parse error"),
            tool_name=tool_name
        )
    except Exception as e:
        logger.error(f"[extract_preferences] Error: {e}")
        return ToolResult.error_result(
            error=f"Preference extraction failed: {str(e)}",
            tool_name=tool_name
        )
