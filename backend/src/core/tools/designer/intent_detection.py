"""
Intent Detection Tool

Wraps existing intent detection functionality in the ToolResult format.
Provides unified intent classification for the multi-agent system.
"""
import time
from typing import Optional, Dict, Any

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)


async def detect_user_intent(
    user_message: str,
    context: str = "",
    has_generated_images: bool = False
) -> ToolResult:
    """
    Unified intent detection for user messages.

    Wraps the existing unified_classify function in ToolResult format.

    Args:
        user_message: User's message to analyze
        context: Current conversation context
        has_generated_images: Whether images have been generated

    Returns:
        ToolResult with intent classification
    """
    start_time = time.time()
    tool_name = "intent_detection"

    if not user_message or not user_message.strip():
        return ToolResult.error_result(
            error="Empty user message",
            tool_name=tool_name
        )

    try:
        # Use existing unified classifier
        from src.core.langgraph.nodes.image_analysis_generation.intent_detection import (
            unified_classify
        )

        result = await unified_classify(
            user_message=user_message,
            context=context,
            has_generated_images=has_generated_images
        )

        execution_time = (time.time() - start_time) * 1000

        confidence_value = result.get("confidence", 0.5)

        return ToolResult.success_result(
            data={
                "primary_intent": result.get("primary_intent", "unclear"),
                "secondary_intents": result.get("secondary_intents", []),
                "conversation_type": result.get("conversation_type"),
                "expertise_level": result.get("expertise_level", "novice"),
                "expertise_indicators": result.get("expertise_indicators", []),
                "extracted_content": result.get("extracted_content", {}),
                "reasoning": result.get("reasoning", "")
            },
            confidence=ConfidenceScore(
                value=confidence_value,
                reasoning=result.get("reasoning", ""),
                field_name="intent"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[intent_detection] Error: {e}")
        return ToolResult.error_result(
            error=f"Intent detection failed: {str(e)}",
            tool_name=tool_name
        )


async def detect_confirmation(
    user_message: str,
    context: str = ""
) -> ToolResult:
    """
    Detect if user is confirming or wants changes.

    Args:
        user_message: User's message
        context: Conversation context

    Returns:
        ToolResult with confirmation intent (confirm/correction/unclear)
    """
    start_time = time.time()
    tool_name = "confirmation_detection"

    if not user_message or not user_message.strip():
        return ToolResult.error_result(
            error="Empty user message",
            tool_name=tool_name
        )

    try:
        from src.core.langgraph.nodes.image_analysis_generation.intent_detection import (
            detect_confirmation_intent
        )

        result = await detect_confirmation_intent(user_message, context)

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "intent": result.get("intent", "unclear"),
                "reasoning": result.get("reasoning", "")
            },
            confidence=ConfidenceScore(
                value=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", ""),
                field_name="confirmation"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[confirmation_detection] Error: {e}")
        return ToolResult.error_result(
            error=f"Confirmation detection failed: {str(e)}",
            tool_name=tool_name
        )


async def detect_edit_intent(
    user_feedback: str,
    previous_changes: Optional[list] = None
) -> ToolResult:
    """
    Detect the type of edit operation the user is requesting.

    Edit modes: add, modify, remove, correct, approve, mixed

    Args:
        user_feedback: User's feedback about generated content
        previous_changes: List of previous changes for context

    Returns:
        ToolResult with edit mode and elements
    """
    start_time = time.time()
    tool_name = "edit_intent_detection"

    if not user_feedback or not user_feedback.strip():
        return ToolResult.error_result(
            error="Empty user feedback",
            tool_name=tool_name
        )

    try:
        from src.core.langgraph.nodes.image_analysis_generation.intent_detection import (
            detect_edit_mode
        )

        result = await detect_edit_mode(
            user_feedback=user_feedback,
            previous_changes=previous_changes
        )

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "edit_mode": result.get("edit_mode", "modify"),
                "elements": result.get("elements", []),
                "sub_operations": result.get("sub_operations", []),
                "prompt_strategy": result.get("prompt_strategy", "replacement"),
                "reasoning": result.get("reasoning", "")
            },
            confidence=ConfidenceScore(
                value=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", ""),
                field_name="edit_mode"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[edit_intent_detection] Error: {e}")
        return ToolResult.error_result(
            error=f"Edit intent detection failed: {str(e)}",
            tool_name=tool_name
        )


async def detect_expertise_level(
    user_message: str,
    history_summary: str = ""
) -> ToolResult:
    """
    Detect user's renovation expertise level.

    Levels: novice, intermediate, expert

    Args:
        user_message: User's message
        history_summary: Summary of prior conversation

    Returns:
        ToolResult with expertise level and communication style recommendation
    """
    start_time = time.time()
    tool_name = "expertise_detection"

    if not user_message or not user_message.strip():
        return ToolResult.success_result(
            data={
                "expertise_level": "novice",
                "indicators": [],
                "recommended_communication_style": "explanatory"
            },
            confidence=ConfidenceScore.medium(reasoning="Empty message, defaulting to novice"),
            tool_name=tool_name
        )

    try:
        from src.core.langgraph.nodes.image_analysis_generation.intent_detection import (
            detect_expertise_level as _detect_expertise
        )

        result = await _detect_expertise(user_message, history_summary)

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "expertise_level": result.get("expertise_level", "novice"),
                "indicators": result.get("indicators", []),
                "recommended_communication_style": result.get("recommended_communication_style", "explanatory")
            },
            confidence=ConfidenceScore(
                value=result.get("confidence", 0.5),
                reasoning=f"Indicators: {result.get('indicators', [])}",
                field_name="expertise"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[expertise_detection] Error: {e}")
        return ToolResult.error_result(
            error=f"Expertise detection failed: {str(e)}",
            tool_name=tool_name
        )
