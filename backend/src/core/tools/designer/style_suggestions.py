"""
Style Suggestions Tool

Generates renovation style suggestions based on:
- Project type and current state
- User preferences (sticky notes)
- Location-based contractor knowledge
- Expertise level
"""
import time
from typing import Optional, Dict, Any, List

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)


async def generate_style_suggestions(
    project_type: str,
    current_state_summary: str,
    user_preferences: str = "",
    expertise_level: str = "novice",
    contractor_knowledge: Optional[Dict[str, Any]] = None,
    num_options: int = 3
) -> ToolResult:
    """
    Generate style suggestions for a renovation project.

    Wraps existing expert_suggestions functionality in ToolResult format.

    Args:
        project_type: Type of project (kitchen, bathroom, etc.)
        current_state_summary: Summary of current room state from image analysis
        user_preferences: User's stated preferences
        expertise_level: User's expertise level (novice/intermediate/expert)
        contractor_knowledge: Optional location-based contractor knowledge
        num_options: Number of options to generate (default 3)

    Returns:
        ToolResult with style options
    """
    start_time = time.time()
    tool_name = "style_suggestions"

    if not project_type:
        return ToolResult.error_result(
            error="Project type is required",
            tool_name=tool_name
        )

    if not current_state_summary:
        return ToolResult.error_result(
            error="Current state summary is required",
            tool_name=tool_name
        )

    try:
        from src.core.langgraph.nodes.image_analysis_generation.intent_detection import (
            generate_expert_suggestions
        )

        # Build inspirations dict from contractor knowledge
        inspirations = None
        if contractor_knowledge:
            inspirations = {
                "location": contractor_knowledge.get("location", {}),
                "contractor_knowledge": contractor_knowledge.get("contractor_knowledge", contractor_knowledge),
                "budget_indicators": contractor_knowledge.get("budget_indicators", {}),
                "climate": contractor_knowledge.get("climate", {})
            }

        result = await generate_expert_suggestions(
            project_type=project_type,
            current_state_summary=current_state_summary,
            user_preferences=user_preferences,
            expertise_level=expertise_level,
            inspirations=inspirations
        )

        options = result.get("options", [])
        follow_up = result.get("follow_up_message", "")

        execution_time = (time.time() - start_time) * 1000

        # Determine confidence based on results
        if len(options) >= num_options:
            confidence = ConfidenceScore.high(
                reasoning=f"Generated {len(options)} style options"
            )
        elif len(options) > 0:
            confidence = ConfidenceScore.medium(
                reasoning=f"Generated {len(options)} options (requested {num_options})"
            )
        else:
            confidence = ConfidenceScore.low(
                reasoning="No options generated"
            )

        return ToolResult.success_result(
            data={
                "options": options,
                "follow_up_message": follow_up,
                "options_count": len(options)
            },
            confidence=confidence,
            tool_name=tool_name,
            metadata={
                "execution_time_ms": execution_time,
                "had_contractor_knowledge": contractor_knowledge is not None
            }
        )

    except Exception as e:
        logger.error(f"[style_suggestions] Error: {e}")
        return ToolResult.error_result(
            error=f"Style suggestion generation failed: {str(e)}",
            tool_name=tool_name
        )


async def clarify_vague_request(
    user_request: str,
    project_type: str,
    extracted_data_summary: str,
    expertise_level: str = "novice"
) -> ToolResult:
    """
    Generate clarifying questions for vague style requests.

    Args:
        user_request: User's vague request
        project_type: Type of project
        extracted_data_summary: Summary of extracted room data
        expertise_level: User's expertise level

    Returns:
        ToolResult with clarifying questions and suggested response
    """
    start_time = time.time()
    tool_name = "clarify_request"

    if not user_request or not user_request.strip():
        return ToolResult.error_result(
            error="User request cannot be empty",
            tool_name=tool_name
        )

    try:
        from src.core.langgraph.nodes.image_analysis_generation.intent_detection import (
            clarify_vague_request as _clarify
        )

        result = await _clarify(
            user_request=user_request,
            project_type=project_type,
            extracted_data_summary=extracted_data_summary,
            expertise_level=expertise_level
        )

        execution_time = (time.time() - start_time) * 1000

        questions = result.get("clarifying_questions", [])

        return ToolResult.success_result(
            data={
                "interpreted_intent": result.get("interpreted_intent", ""),
                "clarifying_questions": questions,
                "suggested_response": result.get("suggested_response", "")
            },
            confidence=ConfidenceScore.high(
                reasoning=f"Generated {len(questions)} clarifying questions"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[clarify_request] Error: {e}")
        return ToolResult.error_result(
            error=f"Request clarification failed: {str(e)}",
            tool_name=tool_name
        )


async def match_style_to_preferences(
    available_styles: List[Dict[str, Any]],
    user_preferences: List[Dict[str, Any]],
    project_type: str
) -> ToolResult:
    """
    Match available styles to user preferences.

    Args:
        available_styles: List of available style options
        user_preferences: List of user preference sticky notes
        project_type: Type of project

    Returns:
        ToolResult with ranked style matches
    """
    start_time = time.time()
    tool_name = "style_matching"

    if not available_styles:
        return ToolResult.error_result(
            error="No styles provided to match",
            tool_name=tool_name
        )

    from src.core.llm.provider import LLMProvider
    import json

    provider = LLMProvider.for_fast_analysis()

    # Format preferences
    prefs_text = "\n".join([
        f"- [{p.get('category', 'general')}] {p.get('content', '')}"
        for p in user_preferences
    ]) if user_preferences else "No specific preferences stated"

    # Format styles
    styles_text = "\n".join([
        f"{i+1}. {s.get('name', 'Unknown')}: {s.get('description', 'No description')}"
        for i, s in enumerate(available_styles)
    ])

    prompt = f"""Match these renovation styles to user preferences for a {project_type} project.

USER PREFERENCES:
{prefs_text}

AVAILABLE STYLES:
{styles_text}

Rank the styles by how well they match the user's preferences. Return JSON:
{{
  "ranked_styles": [
    {{
      "style_index": 1,
      "style_name": "Style Name",
      "match_score": 0.0-1.0,
      "match_reasoning": "Why this style matches/doesn't match"
    }}
  ],
  "top_recommendation": "Brief recommendation for the best match"
}}

Return ALL styles, sorted by match_score descending."""

    try:
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Match renovation styles to user preferences. Return JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500,
            operation_type="style_matching"
        )

        # Parse response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(line for line in lines if not line.startswith("```"))

        data = json.loads(response_text)

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "ranked_styles": data.get("ranked_styles", []),
                "top_recommendation": data.get("top_recommendation", ""),
                "total_styles_ranked": len(data.get("ranked_styles", []))
            },
            confidence=ConfidenceScore.high(
                reasoning="Styles ranked by preference match"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except json.JSONDecodeError as e:
        logger.warning(f"[style_matching] JSON parse error: {e}")
        return ToolResult.error_result(
            error=f"Failed to parse style matching response: {str(e)}",
            tool_name=tool_name
        )
    except Exception as e:
        logger.error(f"[style_matching] Error: {e}")
        return ToolResult.error_result(
            error=f"Style matching failed: {str(e)}",
            tool_name=tool_name
        )
