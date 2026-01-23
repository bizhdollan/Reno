"""
Intent detection and classification functions.
"""

import json

from src.core.logger import get_logger
from src.core.llm.provider import LLMProvider

logger = get_logger(__name__)
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
    """
    Use AI to detect if user is confirming or wants changes.

    Args:
        user_message: User's message to analyze
        context: Current conversation context

    Returns:
        dict with keys: intent, confidence, reasoning
        Default fallback on error: {"intent": "unclear", "confidence": 0.0}
    """
    try:
        if not user_message or not user_message.strip():
            logger.warning("[detect_confirmation_intent] Empty user message received")
            return {"intent": "unclear", "confidence": 0.0, "reasoning": "Empty message"}

        provider = LLMProvider.for_llm()

        prompt = USER_INTENT_PROMPT.format(
            context=context or "No context available",
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

        result = parse_json(response)
        logger.debug(f"[detect_confirmation_intent] Detected intent: {result.get('intent')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[detect_confirmation_intent] JSON parse error: {e}")
        return {"intent": "unclear", "confidence": 0.0, "reasoning": "Failed to parse response"}
    except Exception as e:
        logger.exception(f"[detect_confirmation_intent] Unexpected error: {e}")
        return {"intent": "unclear", "confidence": 0.0, "reasoning": f"Error: {str(e)}"}


async def detect_skip_or_vision_intent(user_message: str) -> dict:
    """
    Use AI to detect if user wants to skip vision or is providing vision details.

    Args:
        user_message: User's message to analyze

    Returns:
        dict with keys: intent (skip|provide_vision|done|unclear), confidence, reasoning
        Default fallback on error: {"intent": "unclear", "confidence": 0.0}
    """
    try:
        if not user_message or not user_message.strip():
            logger.warning("[detect_skip_or_vision_intent] Empty user message received")
            return {"intent": "unclear", "confidence": 0.0, "reasoning": "Empty message"}

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

        result = parse_json(response)
        logger.debug(f"[detect_skip_or_vision_intent] Detected intent: {result.get('intent')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[detect_skip_or_vision_intent] JSON parse error: {e}")
        return {"intent": "unclear", "confidence": 0.0, "reasoning": "Failed to parse response"}
    except Exception as e:
        logger.exception(f"[detect_skip_or_vision_intent] Unexpected error: {e}")
        return {"intent": "unclear", "confidence": 0.0, "reasoning": f"Error: {str(e)}"}


async def detect_proceed_intent(user_message: str, context: str) -> dict:
    """
    Use AI to detect if user wants to proceed or has feedback.

    Args:
        user_message: User's message to analyze
        context: Current conversation context

    Returns:
        dict with keys: intent (proceed|feedback|unclear), confidence, reasoning, feedback_content
        Default fallback on error: {"intent": "unclear", "confidence": 0.0}
    """
    try:
        if not user_message or not user_message.strip():
            logger.warning("[detect_proceed_intent] Empty user message received")
            return {"intent": "unclear", "confidence": 0.0, "reasoning": "Empty message", "feedback_content": None}

        provider = LLMProvider.for_llm()

        prompt = f"""Context: {context or "No context available"}

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

        result = parse_json(response)
        logger.debug(f"[detect_proceed_intent] Detected intent: {result.get('intent')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[detect_proceed_intent] JSON parse error: {e}")
        return {"intent": "unclear", "confidence": 0.0, "reasoning": "Failed to parse response", "feedback_content": None}
    except Exception as e:
        logger.exception(f"[detect_proceed_intent] Unexpected error: {e}")
        return {"intent": "unclear", "confidence": 0.0, "reasoning": f"Error: {str(e)}", "feedback_content": None}


async def detect_enhanced_intent(user_message: str, context: str) -> dict:
    """
    Enhanced multi-intent classifier.

    Detects: confirm, correction, direct_vision, ask_suggestions, ask_question,
             vague_request, skip, mixed

    Args:
        user_message: User's message to analyze
        context: Current conversation context

    Returns:
        dict with keys: primary_intent, secondary_intents, confidence, reasoning, extracted_content
        Default fallback on error with primary_intent="unclear"
    """
    try:
        if not user_message or not user_message.strip():
            logger.warning("[detect_enhanced_intent] Empty user message received")
            return {
                "primary_intent": "unclear",
                "secondary_intents": [],
                "confidence": 0.0,
                "reasoning": "Empty message",
                "extracted_content": {}
            }

        provider = LLMProvider.for_llm()

        prompt = ENHANCED_INTENT_CLASSIFIER_PROMPT.format(
            context=context or "No context available",
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

        result = parse_json(response)
        logger.debug(f"[detect_enhanced_intent] Primary intent: {result.get('primary_intent')}, Secondary: {result.get('secondary_intents')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[detect_enhanced_intent] JSON parse error: {e}")
        return {
            "primary_intent": "unclear",
            "secondary_intents": [],
            "confidence": 0.0,
            "reasoning": "Failed to parse response",
            "extracted_content": {}
        }
    except Exception as e:
        logger.exception(f"[detect_enhanced_intent] Unexpected error: {e}")
        return {
            "primary_intent": "unclear",
            "secondary_intents": [],
            "confidence": 0.0,
            "reasoning": f"Error: {str(e)}",
            "extracted_content": {}
        }


async def detect_expertise_level(user_message: str, history_summary: str = "") -> dict:
    """
    Detect user's expertise level based on their language and conversation.

    Args:
        user_message: User's message to analyze
        history_summary: Optional summary of prior conversation

    Returns:
        dict with keys: expertise_level, confidence, indicators, recommended_communication_style
        Default fallback on error: expertise_level="novice" with low confidence
    """
    try:
        if not user_message or not user_message.strip():
            logger.warning("[detect_expertise_level] Empty user message received")
            return {
                "expertise_level": "novice",
                "confidence": 0.5,
                "indicators": [],
                "recommended_communication_style": "explanatory"
            }

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

        result = parse_json(response)
        logger.debug(f"[detect_expertise_level] Detected level: {result.get('expertise_level')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[detect_expertise_level] JSON parse error: {e}")
        return {
            "expertise_level": "novice",
            "confidence": 0.5,
            "indicators": [],
            "recommended_communication_style": "explanatory"
        }
    except Exception as e:
        logger.exception(f"[detect_expertise_level] Unexpected error: {e}")
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
    expertise_level: str,
    inspirations: dict = None
) -> dict:
    """
    Generate expert renovation suggestions based on current state and local contractor knowledge.
    Generates one option per available style from contractor knowledge (typically 3-7 options).

    Args:
        project_type: Type of space being renovated
        current_state_summary: Summary of extracted data from images
        user_preferences: User's stated preferences/vision
        expertise_level: User's expertise level (novice/intermediate/expert)
        inspirations: Optional location-based renovation inspirations from database

    Returns:
        dict with keys: options (list), follow_up_message
        Default fallback on error: empty options list with friendly message
    """
    try:
        if not project_type or not current_state_summary:
            logger.warning("[generate_expert_suggestions] Missing required parameters")
            return {
                "options": [],
                "follow_up_message": "I'd be happy to suggest some options. Could you tell me more about what style or changes you're interested in?"
            }

        provider = LLMProvider.for_llm()

        # Format contractor knowledge context if available
        if inspirations:
            location = inspirations.get("location", {})
            location_str = f"{location.get('city', 'Unknown')}, {location.get('state_abbr', 'Unknown')}"
            contractor_knowledge = inspirations.get("contractor_knowledge", {})
            budget_indicators = inspirations.get("budget_indicators", {})
            climate = inspirations.get("climate", {})

            # Format popular styles - use ALL styles, no limit
            styles = contractor_knowledge.get("popular_styles", [])
            logger.info(f"[generate_expert_suggestions] Processing {len(styles)} styles from contractor knowledge")
            styles_str = "\n".join([
                f"- {s['name']}: {s['description']}\n  Key elements: {', '.join(s.get('key_elements', []))}\n  Color palette: {', '.join(s.get('color_palette', []))}"
                for s in styles  # ALL styles - no limit
            ]) if styles else "No style data available"

            # Format popular materials
            materials = contractor_knowledge.get("popular_materials", [])
            materials_str = "\n".join([
                f"- {m['name']} ({m.get('category', 'unknown')}): {m['description']}\n  Pairs well with: {', '.join(m.get('pairs_well_with', []))}\n  Budget tier: {m.get('budget_tier', 'unknown')}\n  Maintenance: {m.get('maintenance', 'N/A')}"
                for m in materials[:12]  # Show many materials
            ]) if materials else "No material data available"

            # Format budget expectations
            budget_exp = contractor_knowledge.get("budget_expectations", [])
            budget_str = "\n".join([
                f"- {b['item']}: {b['insight']}"
                for b in budget_exp[:5]
            ]) if budget_exp else "No budget data available"

            # Format timeline expectations
            timeline_exp = contractor_knowledge.get("timeline_expectations", [])
            timeline_str = "\n".join([
                f"- {t['project_type']}: {t['duration']} ({t.get('notes', 'No notes')})"
                for t in timeline_exp[:3]
            ]) if timeline_exp else "No timeline data available"

            # Format code requirements
            code_req = contractor_knowledge.get("code_requirements", [])
            code_str = "\n".join([f"- {req}" for req in code_req]) if code_req else "No specific code requirements found"

            # Format customer examples
            examples = contractor_knowledge.get("customer_project_examples", [])
            examples_str = "\n".join([f"- {ex}" for ex in examples[:5]]) if examples else "No examples available"

            contractor_knowledge_context = f"""
    Contractor Knowledge for {location_str}:
    Budget Tier: {budget_indicators.get('finish_tier', 'unknown')}
    Median Home Value: ${budget_indicators.get('median_home_value', 0):,}
    Temperature Range: {climate.get('temp_range_f', {}).get('min', 'N/A')}°F - {climate.get('temp_range_f', {}).get('max', 'N/A')}°F

    **Popular Styles in {location_str}:**
    {styles_str}

    **Popular Materials & Finishes:**
    {materials_str}

    **Real Customer Project Examples:**
    {examples_str}

    **Budget Expectations:**
    {budget_str}

    **Timeline Expectations:**
    {timeline_str}

    **Code Requirements:**
    {code_str}
    """
        else:
            location_str = "Unknown Location"
            contractor_knowledge_context = "No contractor knowledge available. Generate suggestions based on general best practices."

        # Log styles being used for verification
        if inspirations:
            style_names = [s.get('name', 'Unknown') for s in styles]
            logger.info(f"[generate_expert_suggestions] Styles to generate options for: {style_names}")

        prompt = EXPERT_SUGGESTIONS_PROMPT.format(
            project_type=project_type,
            location_display=location_str,
            current_state_summary=current_state_summary,
            user_preferences=user_preferences or "None provided yet",
            expertise_level=expertise_level or "novice",
            contractor_knowledge_context=contractor_knowledge_context
        )

        # Add explicit count instruction at the end of prompt
        num_styles = len(styles) if inspirations and styles else 5
        explicit_count_instruction = f"\n\n**REMINDER: You MUST generate exactly {num_styles} options, one for each style listed above. Do not generate fewer.**"
        prompt_with_count = prompt + explicit_count_instruction

        response = await provider.complete(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a panel of renovation experts. CRITICAL RULE: Generate exactly {num_styles} renovation options (one for each popular_style). If there are {num_styles} styles, output exactly {num_styles} options. Each option must have 5-8 key_changes. Return JSON only, no markdown."
                },
                {"role": "user", "content": prompt_with_count}
            ],
            temperature=0.3,
            max_tokens=12000,  # Increased to ensure room for all options
            operation_type="expert_suggestions"
        )
        logger.debug(f"[expert_suggestions] Response: {response[:500]}..." if len(response) > 500 else f"[expert_suggestions] Response: {response}")

        result = parse_json(response)
        logger.info(f"[generate_expert_suggestions] Generated {len(result.get('options', []))} suggestions")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[generate_expert_suggestions] JSON parse error: {e}")
        return {
            "options": [],
            "follow_up_message": "I'd be happy to suggest some options. Could you tell me more about what style or changes you're interested in?"
        }
    except Exception as e:
        logger.exception(f"[generate_expert_suggestions] Unexpected error: {e}")
        return {
            "options": [],
            "follow_up_message": "I'd be happy to suggest some options. Could you tell me more about what style or changes you're interested in?"
        }


async def detect_regeneration_mode(user_feedback: str, current_design_summary: str) -> dict:
    """
    Determine if regeneration should use original image (style change) or last generated (refinement).

    Args:
        user_feedback: User's feedback about the current design
        current_design_summary: Summary of current design state

    Returns:
        dict with keys: mode (style_change | iterative_refinement | ask_user),
                       confidence, reasoning, extracted_changes
        Default fallback on error: mode="ask_user" with low confidence
    """
    try:
        if not user_feedback or not user_feedback.strip():
            logger.warning("[detect_regeneration_mode] Empty user feedback received")
            return {
                "mode": "ask_user",
                "confidence": 0.0,
                "reasoning": "Empty feedback",
                "extracted_changes": ""
            }

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

        result = parse_json(response)
        # If low confidence, ask user
        if result.get("confidence", 0) < 0.7:
            result["mode"] = "ask_user"
            logger.debug(f"[detect_regeneration_mode] Low confidence, asking user")
        else:
            logger.debug(f"[detect_regeneration_mode] Detected mode: {result.get('mode')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[detect_regeneration_mode] JSON parse error: {e}")
        return {
            "mode": "ask_user",
            "confidence": 0.0,
            "reasoning": "Failed to parse response",
            "extracted_changes": user_feedback
        }
    except Exception as e:
        logger.exception(f"[detect_regeneration_mode] Unexpected error: {e}")
        return {
            "mode": "ask_user",
            "confidence": 0.0,
            "reasoning": f"Error: {str(e)}",
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

    Args:
        user_request: User's vague request
        project_type: Type of project
        extracted_data_summary: Summary of extracted data
        expertise_level: User's expertise level

    Returns:
        dict with keys: interpreted_intent, clarifying_questions, suggested_response
        Default fallback on error: generic clarification message
    """
    try:
        if not user_request or not user_request.strip():
            logger.warning("[clarify_vague_request] Empty user request received")
            return {
                "interpreted_intent": "Unable to interpret",
                "clarifying_questions": ["Could you provide more details about what you'd like to change?"],
                "suggested_response": "I'd love to help! Could you provide more details about what changes you have in mind?"
            }

        provider = LLMProvider.for_llm()

        prompt = VAGUE_REQUEST_CLARIFIER_PROMPT.format(
            user_request=user_request,
            project_type=project_type or "unknown",
            extracted_data_summary=extracted_data_summary or "No data extracted yet",
            expertise_level=expertise_level or "novice"
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

        result = parse_json(response)
        logger.debug(f"[clarify_vague_request] Generated {len(result.get('clarifying_questions', []))} questions")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[clarify_vague_request] JSON parse error: {e}")
        return {
            "interpreted_intent": "Unable to interpret",
            "clarifying_questions": ["Could you provide more details about what you'd like to change?"],
            "suggested_response": "I'd love to help! Could you provide more details about what changes you have in mind?"
        }
    except Exception as e:
        logger.exception(f"[clarify_vague_request] Unexpected error: {e}")
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

    Args:
        user_message: User's message to analyze
        context: Current conversation context
        has_generated_images: Whether images have been generated

    Returns:
        dict with conversation_type, confidence, and relevant extracted data
        Default fallback on error: conversation_type="clarify" with low confidence
    """
    try:
        if not user_message or not user_message.strip():
            logger.warning("[detect_conversation_type] Empty user message received")
            return {
                "conversation_type": "clarify",
                "confidence": 0.0,
                "reasoning": "Empty message",
                "extracted_question": None,
                "referenced_image_position": None,
                "generation_changes": None
            }

        provider = LLMProvider.for_llm()

        prompt = CONVERSATION_TYPE_CLASSIFIER_PROMPT.format(
            user_message=user_message,
            context=context or "No context available",
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

        result = parse_json(response)
        logger.debug(f"[detect_conversation_type] Detected type: {result.get('conversation_type')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[detect_conversation_type] JSON parse error: {e}")
        return {
            "conversation_type": "clarify",
            "confidence": 0.0,
            "reasoning": "Failed to parse response",
            "extracted_question": None,
            "referenced_image_position": None,
            "generation_changes": None
        }
    except Exception as e:
        logger.exception(f"[detect_conversation_type] Unexpected error: {e}")
        return {
            "conversation_type": "clarify",
            "confidence": 0.0,
            "reasoning": f"Error: {str(e)}",
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
    try:
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
            max_tokens=400,
            operation_type="intent_classification"
        )

        result = parse_json(response)
        # Ensure all required fields exist
        return {
            "expertise_level": result.get("expertise_level", "novice"),
            "expertise_indicators": result.get("expertise_indicators", []),
            "conversation_type": result.get("conversation_type"),  # Will be None if not present
            "primary_intent": result.get("primary_intent", "unclear"),
            "secondary_intents": result.get("secondary_intents", []),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
            "extracted_content": result.get("extracted_content", {})
        }
    except Exception as e:
        logger.warning(f"[unified_classify] Classification failed after retries: {e}")
        # Return empty result - caller will use contextual defaults
        return {
            "expertise_level": "novice",
            "expertise_indicators": [],
            "conversation_type": None,  # None signals caller to use contextual default
            "primary_intent": "unclear",
            "secondary_intents": [],
            "confidence": 0.0,
            "reasoning": f"Classification failed: {str(e)}",
            "extracted_content": {}
        }


async def answer_image_question(
    question: str,
    image_url: str,
    context: str = ""
) -> str:
    """
    Use VLM to answer a question about an image without generating new images.

    Args:
        question: Question to answer about the image
        image_url: URL of the image
        context: Optional additional context

    Returns:
        str: The answer to the question, or error message on failure
    """
    try:
        if not question or not question.strip():
            logger.warning("[answer_image_question] Empty question received")
            return "I need a question to answer. What would you like to know about the image?"

        if not image_url:
            logger.error("[answer_image_question] No image URL provided")
            return "I need an image to answer questions about. Please provide an image."

        provider = LLMProvider.for_vlm()

        # Load image with error handling
        try:
            image_data_url = await load_image_as_base64(image_url)
        except FileNotFoundError as e:
            logger.error(f"[answer_image_question] Image not found: {e}")
            return "I couldn't find that image. Please make sure the image is uploaded correctly."
        except Exception as e:
            logger.error(f"[answer_image_question] Failed to load image: {e}")
            return "I had trouble loading that image. Please try uploading it again."

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

        logger.debug(f"[answer_image_question] Successfully answered question about {image_url}")
        return response

    except Exception as e:
        logger.exception(f"[answer_image_question] Unexpected error: {e}")
        return "I encountered an error while analyzing the image. Please try again."


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
        Default fallback on error: applies to all images
    """
    try:
        if not user_feedback or not user_feedback.strip():
            logger.warning("[parse_multi_image_feedback] Empty user feedback received")
            return {
                "references_multiple_images": False,
                "image_feedback": [],
                "applies_to_all": True,
                "general_feedback": ""
            }

        if num_images <= 0:
            logger.warning(f"[parse_multi_image_feedback] Invalid num_images: {num_images}")
            num_images = 1

        if num_images <= 1:
            # Single image - no need to parse
            logger.debug("[parse_multi_image_feedback] Single image, returning direct feedback")
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

        result = parse_json(response)
        # Validate image positions
        validated_feedback = []
        for fb in result.get("image_feedback", []):
            pos = fb.get("image_position", 1)
            if 1 <= pos <= num_images:
                validated_feedback.append(fb)
            else:
                logger.warning(f"[parse_multi_image_feedback] Invalid image position {pos}, expected 1-{num_images}")

        result["image_feedback"] = validated_feedback
        logger.debug(f"[parse_multi_image_feedback] Parsed feedback for {len(validated_feedback)} images")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[parse_multi_image_feedback] JSON parse error: {e}")
        # Default: apply to all images
        return {
            "references_multiple_images": False,
            "image_feedback": [],
            "applies_to_all": True,
            "general_feedback": user_feedback
        }
    except Exception as e:
        logger.exception(f"[parse_multi_image_feedback] Unexpected error: {e}")
        # Default: apply to all images
        return {
            "references_multiple_images": False,
            "image_feedback": [],
            "applies_to_all": True,
            "general_feedback": user_feedback
        }


async def detect_edit_mode(
    user_feedback: str,
    previous_changes: list[str] | None = None,
    image_url: str | None = None
) -> dict:
    """
    Intelligently detect the type of edit operation the user is requesting.

    Edit modes:
    - add: User wants to ADD new elements (e.g., "add a window", "include pendant lights")
    - modify: User wants to CHANGE/UPDATE existing elements (e.g., "change floor to marble", "make it darker")
    - remove: User wants to REMOVE/DELETE unwanted elements (e.g., "remove the arched doorway", "get rid of the rug")
    - correct: User is CORRECTING AI mistakes/hallucinations (e.g., "that doorway shouldn't be there", "I didn't ask for that")
    - approve: User approves and wants to continue (e.g., "looks good", "perfect", "continue")

    Args:
        user_feedback: The user's feedback message
        previous_changes: List of changes made in previous generation (for context)
        image_url: Optional URL to the image being discussed (for VLM analysis if needed)

    Returns:
        dict with keys:
        - edit_mode: "add" | "modify" | "remove" | "correct" | "approve" | "mixed"
        - confidence: 0.0 to 1.0
        - elements: list of specific elements being targeted
        - reasoning: brief explanation
        - prompt_strategy: recommended approach for the prompt
    """
    try:
        provider = LLMProvider.for_llm()

        # Build context about previous changes
        changes_context = ""
        if previous_changes:
            changes_context = f"""
Previous changes made to this image:
{chr(10).join(f'- {c}' for c in previous_changes)}
"""

        prompt = f"""Analyze this user feedback about a generated renovation image.

User's feedback: "{user_feedback}"
{changes_context}

Determine the edit operation type and extract specific elements.

EDIT MODES:
- "add": User wants NEW elements added (keywords: add, include, put, insert, create, want, need)
- "modify": User wants to CHANGE existing elements (keywords: change, make, update, different, switch, replace with)
- "remove": User wants elements DELETED (keywords: remove, delete, get rid of, take out, no more, don't want)
- "correct": User is fixing AI MISTAKES - elements that shouldn't have been added (keywords: shouldn't be there, wasn't asked, didn't request, wrong, mistake, hallucination, I didn't say)
- "approve": User is SATISFIED and wants to continue (keywords: looks good, perfect, great, continue, proceed, approve, love it)
- "mixed": Multiple edit types in one request

IMPORTANT DISTINCTION:
- "remove" = User acknowledges element EXISTS but wants it GONE
- "correct" = User says element SHOULDN'T EXIST (AI added it by mistake)

Return JSON only:
{{
    "edit_mode": "add" | "modify" | "remove" | "correct" | "approve" | "mixed",
    "confidence": 0.0 to 1.0,
    "elements": ["list", "of", "specific", "elements", "mentioned"],
    "reasoning": "brief explanation of why this mode was detected",
    "sub_operations": [
        {{
            "mode": "add" | "modify" | "remove" | "correct",
            "element": "specific element",
            "details": "what to do with this element"
        }}
    ],
    "prompt_strategy": "recommended_approach"
}}

Prompt strategies:
- "additive": Add new elements while preserving everything else
- "replacement": Replace/modify specific elements
- "removal": Remove elements completely (set explicit constraints)
- "correction": Undo AI mistake and regenerate without the hallucinated element
- "preserve": Keep current design, proceed to next step"""

        response = await provider.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You analyze image editing feedback to determine operation type. Return JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=400,
            operation_type="edit_mode_detection"
        )

        result = parse_json(response)
        logger.info(f"[detect_edit_mode] Detected: {result.get('edit_mode')} (confidence: {result.get('confidence')})")
        logger.info(f"[detect_edit_mode] Elements: {result.get('elements')}")
        return result
    except Exception as e:
        logger.warning(f"[detect_edit_mode] Detection failed after retries: {e}")
        # Default fallback - treat as modify if unclear
        return {
            "edit_mode": "modify",
            "confidence": 0.5,
            "elements": [user_feedback],
            "reasoning": f"Detection failed, defaulting to modify: {str(e)}",
            "sub_operations": [],
            "prompt_strategy": "replacement"
        }
