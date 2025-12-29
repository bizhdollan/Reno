"""
Final Review Node.

Shows before/after comparison of the renovation project.
User can confirm to proceed to cost estimation or request changes.
"""

from src.core.langgraph.state import ProjectState
from src.core.langgraph.utils import get_latest_user_message


async def generate_comparison_summary(
    extracted_data: dict,
    renovation_vision: dict | None,
    project_type: str
) -> str:
    """Use LLM to generate a friendly comparison summary of changes."""
    from src.core.llm.provider import LLMProvider

    if not renovation_vision:
        return ""

    provider = LLMProvider.for_llm()

    prompt = f"""You are summarizing renovation changes for a {project_type} project.

Current state (before):
- Materials: {extracted_data.get('materials', [])}
- Colors: {extracted_data.get('colors', [])}
- Style: {extracted_data.get('style', {})}

Planned changes (after):
- Vision: {renovation_vision.get('ai_summary', '')}
- Style preferences: {renovation_vision.get('style_preferences', '')}
- Material preferences: {renovation_vision.get('material_preferences', '')}
- Specific changes: {renovation_vision.get('specific_changes', '')}

Write 3-5 bullet points summarizing the key visible changes from before to after.
Format each as: "• [Element]: [Before] → [After]"
Example: "• Walls: beige plaster → white paint"

Be concise and focus on the most impactful visual changes."""

    try:
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "You summarize renovation changes concisely. Return bullet points only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response.strip()
    except Exception as e:
        print(f"[final_review] Failed to generate comparison: {e}")
        return ""


def format_before_section(state: ProjectState) -> str:
    """Format the 'Before' section with original images and extracted data."""
    lines = []

    # Original images
    image_analyses = state.get("image_analyses", [])
    original_urls = state.get("original_image_urls", [])

    # Get original image URLs from analyses or stored URLs
    original_images = []
    for analysis in image_analyses:
        if analysis.get("url"):
            original_images.append(analysis["url"])

    # Fallback to original_image_urls if analyses don't have URLs
    if not original_images and original_urls:
        original_images = original_urls

    if original_images:
        lines.append("### Original Room")
        lines.append("")
        for i, url in enumerate(original_images):
            lines.append(f'<img src="{url}" style="width: 100%; max-width: 400px; border-radius: 8px; margin: 8px 0;" />')
        lines.append("")

    # Extracted data summary
    extracted = state.get("extracted_data", {})

    # Key features
    features = []

    # Materials
    materials = extracted.get("materials", [])
    if materials:
        material_list = [f"{m.get('name', 'unknown')}: {m.get('type', 'N/A')}" for m in materials[:3]]
        features.append(f"**Materials:** {', '.join(material_list)}")

    # Colors
    colors = extracted.get("colors", [])
    if colors:
        color_list = [f"{c.get('element', 'unknown')}: {c.get('color', 'N/A')}" for c in colors[:3]]
        features.append(f"**Colors:** {', '.join(color_list)}")

    # Style
    style = extracted.get("style", {})
    if style.get("overall_style"):
        features.append(f"**Style:** {style['overall_style']}")
    if style.get("condition"):
        features.append(f"**Condition:** {style['condition']}")

    # Measurements
    measurements = extracted.get("measurements", {})
    if measurements.get("area_sqft"):
        features.append(f"**Area:** {measurements['area_sqft']} sq ft")

    if features:
        lines.append("**Current State:**")
        for feature in features:
            lines.append(f"- {feature}")
        lines.append("")

    return "\n".join(lines)


def format_after_section(state: ProjectState) -> str:
    """Format the 'After' section with generated images and renovation vision."""
    lines = []

    # Generated image
    generated_url = state.get("generated_image_url")
    selected_url = state.get("selected_final_image_url")

    # Use selected final image or the current generated image
    final_url = selected_url or generated_url

    if final_url:
        lines.append("### Renovated Room")
        lines.append("")
        lines.append(f'<img src="{final_url}" style="width: 100%; max-width: 600px; border-radius: 12px; margin: 8px 0; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />')
        lines.append("")

    # Renovation vision summary
    vision = state.get("renovation_vision")
    if vision:
        lines.append("**Planned Renovation:**")

        if vision.get("ai_summary"):
            lines.append(f"*{vision['ai_summary']}*")
            lines.append("")

        if vision.get("style_preferences"):
            lines.append(f"- **Style:** {vision['style_preferences']}")
        if vision.get("material_preferences"):
            # Handle both string and dict formats
            materials = vision.get("material_preferences")
            if isinstance(materials, dict):
                material_str = ", ".join(f"{k}: {v}" for k, v in materials.items())
            else:
                material_str = str(materials)
            lines.append(f"- **Materials:** {material_str}")
        if vision.get("specific_changes"):
            changes = vision.get("specific_changes")
            if isinstance(changes, list):
                for change in changes[:3]:
                    lines.append(f"- {change}")
            else:
                lines.append(f"- **Changes:** {changes}")
        lines.append("")

    return "\n".join(lines)


async def format_final_summary(state: ProjectState) -> str:
    """Format complete before/after comparison for final review."""
    lines = []

    # Project header
    project_title = state.get('project_title', 'Your Renovation')
    project_type = state.get('project_type', 'renovation')
    zip_code = state.get('zip_code', '')

    lines.append(f"**{project_title}** | {project_type.title()} | {zip_code}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Before section
    lines.append("## Before")
    lines.append("")
    lines.append(format_before_section(state))

    # After section
    lines.append("## After")
    lines.append("")
    lines.append(format_after_section(state))

    # Changes summary (LLM-generated)
    extracted = state.get("extracted_data", {})
    vision = state.get("renovation_vision")

    if vision:
        comparison = await generate_comparison_summary(extracted, vision, project_type)
        if comparison:
            lines.append("---")
            lines.append("")
            lines.append("### Key Changes")
            lines.append("")
            lines.append(comparison)
            lines.append("")

    # Measurements for cost estimation context
    measurements = extracted.get("measurements", {})
    if measurements:
        lines.append("---")
        lines.append("")
        lines.append("### Project Scope")
        lines.append("")
        if measurements.get("room_width_ft") and measurements.get("room_length_ft"):
            lines.append(f"- **Room Size:** {measurements.get('room_width_ft')} × {measurements.get('room_length_ft')} ft")
        if measurements.get("room_height_ft"):
            lines.append(f"- **Ceiling Height:** {measurements.get('room_height_ft')} ft")
        if measurements.get("area_sqft"):
            lines.append(f"- **Total Area:** {measurements.get('area_sqft')} sq ft")
        lines.append("")

    return "\n".join(lines)


INTENT_DETECTION_PROMPT = """Analyze the user's message in the context of a renovation project final review.

The user has just seen a complete summary of their renovation project including:
- Project details (name, type, location)
- Before images (original room)
- After images (generated renovation preview)
- Key changes summary

They were asked: "Does everything look correct? Say 'yes' to generate your cost estimate, or let me know what needs to be changed."

User's message: "{user_message}"

Determine the user's intent. Return JSON only:
{{
    "intent": "confirm" | "visual_change" | "go_back_to_extraction" | "go_back_to_vision" | "request_changes" | "unclear",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "specific_change": "what they want to change if applicable, else null"
}}

Intent definitions:
- "confirm": User agrees/approves, wants to proceed to cost estimation (e.g., "yes", "looks good", "proceed", "continue", "perfect", "I like it", "let's go")
- "visual_change": User wants to modify the generated image/design - ANY mention of materials, colors, fixtures, or visual changes (e.g., "add tiles", "change the floor", "make walls darker", "I want marble countertops", "put plants", "remove the rug", "there are no books", "the plant is floating", "make it modern", "add lighting")
- "go_back_to_extraction": User specifically wants to change ONLY the extracted data numbers/facts (materials list, measurements, dimensions), NOT the visual design
- "go_back_to_vision": User wants to completely restart with a new renovation vision/style preference
- "request_changes": User wants to modify something but isn't being specific at all
- "unclear": Cannot determine intent, need clarification

CRITICAL: If user mentions ANY material, color, fixture, design element, or visual change they want - classify as "visual_change". This includes complaints about the generated image like "there are no books" or "plants are floating"."""


async def detect_user_intent(user_message: str) -> dict:
    """Use AI to detect user's intent from their message."""
    from src.core.llm.provider import LLMProvider
    from src.core.langgraph.utils import parse_json

    provider = LLMProvider.for_llm()

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent in a renovation estimation context. Return JSON only."
            },
            {
                "role": "user",
                "content": INTENT_DETECTION_PROMPT.format(user_message=user_message)
            }
        ],
        temperature=0.0,
        max_tokens=200
    )

    try:
        return parse_json(response)
    except:
        return {"intent": "unclear", "confidence": 0.0, "reasoning": "Failed to parse response"}


async def final_review_node(state: ProjectState) -> dict:
    """
    Final review node.

    - Shows before/after comparison
    - User can confirm to proceed or request changes
    - Moves to cost_estimation when confirmed
    """
    messages = state.get("messages", [])
    user_message, _ = get_latest_user_message(messages)

    updates = {}

    # Check if we just entered from confirming_proposal - show summary first
    # This flag is set by confirming_proposal when user approves the design
    if state.get("_show_final_review_summary"):
        print("[final_review] Entering from confirming_proposal - showing summary first")
        updates["_show_final_review_summary"] = None  # Clear the flag
        # Fall through to show summary (skip user message processing)
        user_message = None

    # If user provided a message, use LLM to detect intent
    if user_message:
        # Use AI to detect user intent - no hardcoded keywords
        intent_result = await detect_user_intent(user_message)
        intent = intent_result.get("intent", "unclear")

        print(f"[final_review] User intent: {intent} | confidence: {intent_result.get('confidence')} | reasoning: {intent_result.get('reasoning')}")

        if intent == "confirm":
            updates["current_stage"] = "cost_estimation"
            updates["user_confirmed_continue"] = True
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates

        elif intent == "visual_change":
            # User wants to change the generated image/design - go back to Stage 2
            change_request = intent_result.get("specific_change") or user_message
            print(f"[final_review] Visual change detected: going back to Stage 2 with feedback")

            existing_feedback = list(state.get("image_generation_feedback", []))
            existing_feedback.append(change_request)
            updates["image_generation_feedback"] = existing_feedback
            updates["pending_feedback"] = change_request

            # Go back to Stage 2 (image_analysis_generation) for regeneration
            updates["current_stage"] = "image_analysis_generation"
            updates["image_sub_state"] = "confirming_proposal"
            updates["awaiting_user_input"] = False
            # Signal that we're coming back with a change request
            updates["_pending_regeneration"] = change_request
            updates["messages"] = []
            return updates

        elif intent == "go_back_to_extraction":
            updates["current_stage"] = "image_analysis_generation"
            updates["image_sub_state"] = "confirming_extraction"
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates

        elif intent == "go_back_to_vision":
            updates["current_stage"] = "image_analysis_generation"
            updates["image_sub_state"] = "design_conversation"
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates

        elif intent == "request_changes":
            # User wants changes but wasn't specific - ask for clarification
            response = (
                "What would you like to change?\n\n"
                "Just describe what you want (e.g., 'add tiles to the floor') "
                "and I'll regenerate the preview for you."
            )
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

        else:  # unclear
            response = (
                "I'm not sure what you'd like to do. Could you please clarify?\n\n"
                "- Say **'yes'** or **'proceed'** to generate your cost estimate\n"
                "- Or describe what changes you want (e.g., 'change the floor to tiles')"
            )
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

    # Show before/after summary (first time or no user message)
    summary = await format_final_summary(state)

    response = (
        f"# Final Review\n\n"
        f"{summary}\n"
        f"---\n\n"
        f"**Does everything look correct?**\n\n"
        f"Say **'yes'** to generate your cost estimate, or let me know what needs to be changed."
    )

    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True

    return updates
