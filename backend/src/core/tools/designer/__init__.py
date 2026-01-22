"""
Domain 3: Designer Tools

Provides design assistance and preference tracking:
- Intent detection from user messages
- Style suggestions based on context and contractor knowledge
- Sticky notes for session preferences
"""

from .intent_detection import (
    detect_user_intent,
    detect_confirmation,
    detect_edit_intent,
    detect_expertise_level,
)
from .style_suggestions import (
    generate_style_suggestions,
    clarify_vague_request,
    match_style_to_preferences,
)
from .sticky_notes import (
    add_sticky_note,
    get_sticky_notes,
    remove_sticky_note,
    clear_sticky_notes,
    format_sticky_notes_for_prompt,
    extract_preferences_from_message,
    StickyNote,
    StickyNoteCategory,
)

__all__ = [
    # Intent detection
    "detect_user_intent",
    "detect_confirmation",
    "detect_edit_intent",
    "detect_expertise_level",
    # Style suggestions
    "generate_style_suggestions",
    "clarify_vague_request",
    "match_style_to_preferences",
    # Sticky notes
    "add_sticky_note",
    "get_sticky_notes",
    "remove_sticky_note",
    "clear_sticky_notes",
    "format_sticky_notes_for_prompt",
    "extract_preferences_from_message",
    "StickyNote",
    "StickyNoteCategory",
]
