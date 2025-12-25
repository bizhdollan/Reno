"""
Intent detection and classification functions.
"""

import json

from src.core.llm.provider import LLMProvider
from src.core.langgraph.utils import parse_json
from src.core.langgraph.prompts import (
    ENHANCED_INTENT_CLASSIFIER_PROMPT,
    CONVERSATION_TYPE_CLASSIFIER_PROMPT,
    UNIFIED_CLASSIFIER_PROMPT,
    REGENERATION_MODE_CLASSIFIER_PROMPT,
    EXPERTISE_DETECTOR_PROMPT,
    EXPERT_SUGGESTIONS_PROMPT,
    VAGUE_REQUEST_CLARIFIER_PROMPT,
    MULTI_IMAGE_FEEDBACK_PROMPT,
)
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import (
    load_image_as_base64,
)


USER_INTENT_PROMPT = """Analyze the user's message in a renovation project context.

Current context: {context}

User's message: "{user_message}"

Determine the user's intent. Return JSON only:
{{
    "intent": "{intent_options}",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}"""


async def detect_confirmation_intent(user_message: str, context: str) -> dict:
    """Use AI to detect if user is confirming or wants changes."""
    provider = LLMProvider.for_llm()

    prompt = USER_INTENT_PROMPT.format(
        context=context,
        user_message=user_message,
        intent_options="confirm | correction | unclear"
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent. 'confirm' means they agree/approve. 'correction' means they want to change something. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=150
    )

    try:
        return parse_json(response)
    except:
        return {"intent": "unclear", "confidence": 0.0}


async def detect_skip_or_vision_intent(user_message: str) -> dict:
    """Use AI to detect if user wants to skip vision or is providing vision details."""
    provider = LLMProvider.for_llm()

    prompt = f"""The user was asked if they have a specific vision for their renovation.
They could: provide vision details, skip this step, or say they're done.

User's message: "{user_message}"

Determine intent. Return JSON only:
{{
    "intent": "skip" | "provide_vision" | "done" | "unclear",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}

- "skip": User doesn't want to provide vision, wants to proceed without it
- "provide_vision": User is sharing their renovation ideas/preferences
- "done": User has finished providing vision, ready to move on
- "unclear": Cannot determine"""

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent for renovation vision collection. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=150
    )

    try:
        return parse_json(response)
    except:
        return {"intent": "unclear", "confidence": 0.0}


async def detect_proceed_intent(user_message: str, context: str) -> dict:
    """Use AI to detect if user wants to proceed or has feedback."""
    provider = LLMProvider.for_llm()

    prompt = f"""Context: {context}

User's message: "{user_message}"

Determine intent. Return JSON only:
{{
    "intent": "proceed" | "feedback" | "unclear",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "feedback_content": "extracted feedback if intent is feedback, else null"
}}

- "proceed": User wants to continue/move forward
- "feedback": User is providing feedback or requesting changes
- "unclear": Cannot determine"""

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=200
    )

    try:
        return parse_json(response)
    except:
        return {"intent": "unclear", "confidence": 0.0}


async def detect_enhanced_intent(user_message: str, context: str) -> dict:
    """
    Enhanced multi-intent classifier.

    Detects: confirm, correction, direct_vision, ask_suggestions, ask_question,
             vague_request, skip, mixed

    Returns:
        dict with keys: primary_intent, secondary_intents, confidence, reasoning, extracted_content
    """
    provider = LLMProvider.for_llm()

    prompt = ENHANCED_INTENT_CLASSIFIER_PROMPT.format(
        context=context,
        user_message=user_message
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent with support for multiple intents. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=300
    )

    try:
        return parse_json(response)
    except:
        return {
            "primary_intent": "unclear",
            "secondary_intents": [],
            "confidence": 0.0,
            "reasoning": "Failed to parse",
            "extracted_content": {}
        }


async def detect_expertise_level(user_message: str, history_summary: str = "") -> dict:
    """
    Detect user's expertise level based on their language and conversation.

    Returns:
        dict with keys: expertise_level, confidence, indicators, recommended_communication_style
    """
    provider = LLMProvider.for_llm()

    prompt = EXPERTISE_DETECTOR_PROMPT.format(
        user_message=user_message,
        history_summary=history_summary or "No prior conversation"
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You detect user expertise level in renovation/construction. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=200
    )

    try:
        return parse_json(response)
    except:
        return {
            "expertise_level": "novice",
            "confidence": 0.5,
            "indicators": [],
            "recommended_communication_style": "explanatory"
        }


async def generate_expert_suggestions(
    project_type: str,
    current_state_summary: str,
    user_preferences: str,
    expertise_level: str
) -> dict:
    """
    Generate 2-3 expert renovation suggestions based on current state.

    Returns:
        dict with keys: options (list), follow_up_message
    """
    provider = LLMProvider.for_llm()

    prompt = EXPERT_SUGGESTIONS_PROMPT.format(
        project_type=project_type,
        current_state_summary=current_state_summary,
        user_preferences=user_preferences or "None provided yet",
        expertise_level=expertise_level
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a panel of renovation experts providing tailored suggestions. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1500
    )

    try:
        return parse_json(response)
    except:
        return {
            "options": [],
            "follow_up_message": "I'd be happy to suggest some options. Could you tell me more about what style or changes you're interested in?"
        }


async def detect_regeneration_mode(user_feedback: str, current_design_summary: str) -> dict:
    """
    Determine if regeneration should use original image (style change) or last generated (refinement).

    Returns:
        dict with keys: mode (style_change | iterative_refinement | ask_user),
                       confidence, reasoning, extracted_changes
    """
    provider = LLMProvider.for_llm()

    prompt = REGENERATION_MODE_CLASSIFIER_PROMPT.format(
        user_feedback=user_feedback,
        current_design_summary=current_design_summary or "No current design"
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You classify regeneration mode for image generation. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=200
    )

    try:
        result = parse_json(response)
        # If low confidence, ask user
        if result.get("confidence", 0) < 0.7:
            result["mode"] = "ask_user"
        return result
    except:
        return {
            "mode": "ask_user",
            "confidence": 0.0,
            "reasoning": "Failed to parse",
            "extracted_changes": user_feedback
        }


async def clarify_vague_request(
    user_request: str,
    project_type: str,
    extracted_data_summary: str,
    expertise_level: str
) -> dict:
    """
    Generate clarifying questions for vague user requests.

    Returns:
        dict with keys: interpreted_intent, clarifying_questions, suggested_response
    """
    provider = LLMProvider.for_llm()

    prompt = VAGUE_REQUEST_CLARIFIER_PROMPT.format(
        user_request=user_request,
        project_type=project_type,
        extracted_data_summary=extracted_data_summary or "No data extracted yet",
        expertise_level=expertise_level
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You help clarify vague renovation requests by asking smart questions. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=400
    )

    try:
        return parse_json(response)
    except:
        return {
            "interpreted_intent": "Unable to interpret",
            "clarifying_questions": ["Could you provide more details about what you'd like to change?"],
            "suggested_response": "I'd love to help! Could you provide more details about what changes you have in mind?"
        }


async def detect_conversation_type(
    user_message: str,
    context: str,
    has_generated_images: bool
) -> dict:
    """
    Classify the type of user message: discussion, generation_request, reference_previous, move_forward, clarify.

    Returns:
        dict with conversation_type, confidence, and relevant extracted data
    """
    provider = LLMProvider.for_llm()

    prompt = CONVERSATION_TYPE_CLASSIFIER_PROMPT.format(
        user_message=user_message,
        context=context,
        has_generated_images=str(has_generated_images).lower()
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You classify user intent in renovation conversations. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=250
    )

    try:
        return parse_json(response)
    except:
        return {
            "conversation_type": "clarify",
            "confidence": 0.0,
            "reasoning": "Failed to parse",
            "extracted_question": None,
            "referenced_image_position": None,
            "generation_changes": None
        }


async def unified_classify(
    user_message: str,
    context: str,
    has_generated_images: bool
) -> dict:
    """
    Unified classifier that combines expertise detection, intent classification,
    and conversation type into a SINGLE LLM call to reduce latency.

    Replaces separate calls to:
    - detect_expertise_level()
    - detect_enhanced_intent()
    - detect_conversation_type()

    Returns:
        dict with all classification results:
        - expertise_level, expertise_indicators
        - conversation_type
        - primary_intent, secondary_intents
        - confidence, reasoning
        - extracted_content (confirmation, corrections, vision_details, questions,
                            generation_changes, referenced_image_position)
    """
    provider = LLMProvider.for_llm()

    prompt = UNIFIED_CLASSIFIER_PROMPT.format(
        user_message=user_message,
        context=context,
        has_generated_images=str(has_generated_images).lower()
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a multi-purpose classifier for renovation conversations. Analyze expertise, intent, and conversation type in one response. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=400
    )

    try:
        result = parse_json(response)
        # Ensure all required fields exist
        return {
            "expertise_level": result.get("expertise_level", "novice"),
            "expertise_indicators": result.get("expertise_indicators", []),
            "conversation_type": result.get("conversation_type", "clarify"),
            "primary_intent": result.get("primary_intent", "unclear"),
            "secondary_intents": result.get("secondary_intents", []),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
            "extracted_content": result.get("extracted_content", {})
        }
    except:
        return {
            "expertise_level": "novice",
            "expertise_indicators": [],
            "conversation_type": "clarify",
            "primary_intent": "unclear",
            "secondary_intents": [],
            "confidence": 0.0,
            "reasoning": "Failed to parse unified classification",
            "extracted_content": {}
        }


async def answer_image_question(
    question: str,
    image_url: str,
    context: str = ""
) -> str:
    """
    Use VLM to answer a question about an image without generating new images.

    Returns:
        str: The answer to the question
    """
    provider = LLMProvider.for_vlm()
    image_data_url = await load_image_as_base64(image_url)

    prompt = f"""Answer this question about the image:

Question: {question}

{f"Context: {context}" if context else ""}

Provide a helpful, concise answer. If you can identify specific details (color codes, material types, dimensions), include them.
For colors, try to provide hex codes when possible (e.g., "The wall appears to be a warm beige, approximately #D4C4A8")."""

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful renovation expert answering questions about room images. Be specific and accurate."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ],
        temperature=0.3,
        max_tokens=400
    )

    return response


async def parse_multi_image_feedback(
    user_feedback: str,
    num_images: int
) -> dict:
    """
    Parse user feedback to identify which images are being referenced
    and what changes are requested for each.

    Args:
        user_feedback: User's feedback message
        num_images: Number of generated images available

    Returns:
        dict with:
        - references_multiple_images: bool
        - image_feedback: list of {image_position, feedback, confidence}
        - applies_to_all: bool
        - general_feedback: str or None
    """
    if num_images <= 1:
        # Single image - no need to parse
        return {
            "references_multiple_images": False,
            "image_feedback": [{"image_position": 1, "feedback": user_feedback, "confidence": 1.0}],
            "applies_to_all": True,
            "general_feedback": user_feedback
        }

    provider = LLMProvider.for_llm()

    prompt = MULTI_IMAGE_FEEDBACK_PROMPT.format(
        user_feedback=user_feedback,
        num_images=num_images
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You parse user feedback about multiple images. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=300
    )

    try:
        result = parse_json(response)
        # Validate image positions
        validated_feedback = []
        for fb in result.get("image_feedback", []):
            pos = fb.get("image_position", 1)
            if 1 <= pos <= num_images:
                validated_feedback.append(fb)
        result["image_feedback"] = validated_feedback
        return result
    except:
        # Default: apply to all images
        return {
            "references_multiple_images": False,
            "image_feedback": [],
            "applies_to_all": True,
            "general_feedback": user_feedback
        }
