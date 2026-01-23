"""
Prompts for the renovation workflow.

Organized by functionality:
- image_generation: Image generation and regeneration prompts
- intent_classification: User intent classification prompts
- extraction: Data extraction and feedback prompts
- suggestions: Expert suggestions and clarification prompts
"""

from src.core.langgraph.prompts.image_generation import (
    build_image_generation_prompt,
    build_image_regeneration_prompt,
    build_edit_mode_prompt,
    build_selected_image_prompt,
)
from src.core.langgraph.prompts.intent_classification import (
    ENHANCED_INTENT_CLASSIFIER_PROMPT,
    CONVERSATION_TYPE_CLASSIFIER_PROMPT,
    UNIFIED_CLASSIFIER_PROMPT,
    REGENERATION_MODE_CLASSIFIER_PROMPT,
)
from src.core.langgraph.prompts.extraction import (
    FEEDBACK_CLASSIFICATION_PROMPT,
    # BRIEF_ROOM_SUMMARY_PROMPT,  # DEPRECATED - now in comprehensive_analysis.py
    # FEATURES_TO_RETAIN_PROMPT,  # DEPRECATED - now in comprehensive_analysis.py
)
from src.core.langgraph.prompts.suggestions import (
    EXPERTISE_DETECTOR_PROMPT,
    EXPERT_SUGGESTIONS_PROMPT,
    VAGUE_REQUEST_CLARIFIER_PROMPT,
    MULTI_IMAGE_FEEDBACK_PROMPT,
)

__all__ = [
    # Image generation
    "build_image_generation_prompt",
    "build_image_regeneration_prompt",
    "build_edit_mode_prompt",
    "build_selected_image_prompt",
    # Intent classification
    "ENHANCED_INTENT_CLASSIFIER_PROMPT",
    "CONVERSATION_TYPE_CLASSIFIER_PROMPT",
    "UNIFIED_CLASSIFIER_PROMPT",
    "REGENERATION_MODE_CLASSIFIER_PROMPT",
    # Extraction
    "FEEDBACK_CLASSIFICATION_PROMPT",
    # "BRIEF_ROOM_SUMMARY_PROMPT",  # DEPRECATED
    # "FEATURES_TO_RETAIN_PROMPT",  # DEPRECATED
    # Suggestions
    "EXPERTISE_DETECTOR_PROMPT",
    "EXPERT_SUGGESTIONS_PROMPT",
    "VAGUE_REQUEST_CLARIFIER_PROMPT",
    "MULTI_IMAGE_FEEDBACK_PROMPT",
]
