"""
Final Review Node.

Shows complete summary of all confirmed information and generated image.
User can confirm to proceed to cost estimation or request changes.
"""

from src.core.langgraph.state import ProjectState
from src.core.langgraph.utils import get_latest_user_message


def format_final_summary(state: ProjectState) -> str:
    """Format complete project summary for final review."""
    lines = []
    
    # Project basics
    lines.append("## 📋 Project Details\n")
    lines.append(f"- **Project Name:** {state.get('project_title', 'N/A')}")
    lines.append(f"- **Type:** {state.get('project_type', 'N/A').title() if state.get('project_type') else 'N/A'}")
    lines.append(f"- **Location:** {state.get('zip_code', 'N/A')}")
    lines.append("")
    
    # Generated image
    generated_url = state.get("generated_image_url")
    if generated_url:
        lines.append("## 🖼️ Renovation Preview\n")
        lines.append(f"![Renovation Preview]({generated_url})")
        lines.append("")
    
    # Extracted data
    extracted = state.get("extracted_data", {})
    
    # Materials
    materials = extracted.get("materials", [])
    if materials:
        lines.append("## 🧱 Materials\n")
        for m in materials:
            line = f"- **{m.get('name', 'Unknown').title()}**: {m.get('type', 'N/A')}"
            if m.get("finish"):
                line += f" ({m['finish']})"
            if m.get("condition"):
                line += f" - {m['condition']}"
            lines.append(line)
        lines.append("")
    
    # Measurements
    measurements = extracted.get("measurements", {})
    if measurements:
        lines.append("## 📐 Measurements\n")
        if measurements.get("room_width_ft") and measurements.get("room_length_ft"):
            lines.append(f"- **Room Size:** {measurements.get('room_width_ft')} × {measurements.get('room_length_ft')} ft")
        if measurements.get("room_height_ft"):
            lines.append(f"- **Ceiling Height:** {measurements.get('room_height_ft')} ft")
        if measurements.get("area_sqft"):
            lines.append(f"- **Total Area:** {measurements.get('area_sqft')} sq ft")
        lines.append("")
    
    # Colors
    colors = extracted.get("colors", [])
    if colors:
        lines.append("## 🎨 Colors\n")
        for c in colors:
            line = f"- **{c.get('element', 'Unknown').title()}**: {c.get('color', 'N/A')}"
            if c.get("finish"):
                line += f" ({c['finish']})"
            lines.append(line)
        lines.append("")
    
    # Fixtures
    fixtures = extracted.get("fixtures", [])
    if fixtures:
        lines.append("## 💡 Fixtures\n")
        for f in fixtures:
            line = f"- **{f.get('name', 'Unknown').title()}**: {f.get('type', 'N/A')}"
            if f.get("condition"):
                line += f" ({f['condition']})"
            lines.append(line)
        lines.append("")
    
    # Appliances
    appliances = extracted.get("appliances", [])
    if appliances:
        lines.append("## 🔌 Appliances\n")
        for a in appliances:
            line = f"- **{a.get('name', 'Unknown').title()}**: {a.get('type', 'N/A')}"
            if a.get("brand"):
                line += f" ({a['brand']})"
            lines.append(line)
        lines.append("")
    
    # Style
    style = extracted.get("style", {})
    if style:
        lines.append("## 🏠 Style Assessment\n")
        if style.get("overall_style"):
            lines.append(f"- **Overall Style:** {style['overall_style']}")
        if style.get("condition"):
            lines.append(f"- **Current Condition:** {style['condition']}")
        if style.get("age_estimate"):
            lines.append(f"- **Estimated Age:** {style['age_estimate']}")
        lines.append("")
    
    # Renovation Vision (if provided)
    vision = state.get("renovation_vision")
    if vision:
        lines.append("## 💭 Your Renovation Vision\n")
        if vision.get("ai_summary"):
            lines.append(f"*{vision['ai_summary']}*")
        elif vision.get("raw_input"):
            lines.append(f"*{vision['raw_input']}*")
        lines.append("")
        
        if vision.get("style_preferences"):
            lines.append(f"- **Style:** {vision['style_preferences']}")
        if vision.get("material_preferences"):
            lines.append(f"- **Materials:** {vision['material_preferences']}")
        if vision.get("specific_changes"):
            lines.append(f"- **Changes:** {vision['specific_changes']}")
        lines.append("")
    
    return "\n".join(lines)


INTENT_DETECTION_PROMPT = """Analyze the user's message in the context of a renovation project final review.

The user has just seen a complete summary of their renovation project including:
- Project details (name, type, location)
- Extracted materials, measurements, colors, fixtures
- Style assessment
- Renovation vision (if provided)

They were asked: "Does everything look correct? Say 'yes' to generate your cost estimate, or let me know what needs to be changed."

User's message: "{user_message}"

Determine the user's intent. Return JSON only:
{{
    "intent": "confirm" | "request_changes" | "go_back_to_extraction" | "go_back_to_vision" | "unclear",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "specific_change": "what they want to change if applicable, else null"
}}

Intent definitions:
- "confirm": User agrees, wants to proceed to cost estimation
- "request_changes": User wants to modify something but isn't specific about going back
- "go_back_to_extraction": User specifically wants to change materials, measurements, colors, fixtures, or extracted data
- "go_back_to_vision": User wants to change their renovation vision/preferences
- "unclear": Cannot determine intent, need clarification"""


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

    - Shows complete summary of all confirmed data
    - User can confirm to proceed or request changes
    - Moves to cost_estimation when confirmed
    """
    messages = state.get("messages", [])
    user_message, _ = get_latest_user_message(messages)

    updates = {}

    # If user provided a message, check for changes first
    if user_message:
        msg_lower = user_message.lower().strip()

        # Keywords indicating visual/design changes that need image regeneration
        visual_change_keywords = [
            "should be", "should have", "add ", "change ", "make it", "make the",
            "i want", "put ", "use ", "replace", "remove ", "tiles", "marble",
            "wood", "carpet", "paint", "color", "darker", "lighter", "bigger",
            "smaller", "floor", "wall", "ceiling", "flooring", "wallpaper"
        ]

        # Check if user wants a visual change - go directly to confirming_proposal
        wants_visual_change = any(kw in msg_lower for kw in visual_change_keywords)

        if wants_visual_change:
            print(f"[final_review] Visual change detected: going back to confirming_proposal with feedback")
            # Store the change request as pending feedback
            existing_feedback = list(state.get("image_generation_feedback", []))
            existing_feedback.append(user_message)
            updates["image_generation_feedback"] = existing_feedback
            updates["pending_feedback"] = user_message

            # Go directly to confirming_proposal to regenerate
            updates["current_stage"] = "image_analysis_generation"
            updates["image_sub_state"] = "confirming_proposal"
            updates["awaiting_user_input"] = False
            # Signal that we're coming back with a change request
            updates["_pending_regeneration"] = user_message
            updates["messages"] = []
            return updates

        # Use AI to detect other intents
        intent_result = await detect_user_intent(user_message)
        intent = intent_result.get("intent", "unclear")

        print(f"[final_review] User intent: {intent} | confidence: {intent_result.get('confidence')} | reasoning: {intent_result.get('reasoning')}")

        if intent == "confirm":
            updates["current_stage"] = "cost_estimation"
            updates["user_confirmed_continue"] = True
            updates["awaiting_user_input"] = False
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
            updates["image_sub_state"] = "design_conversation"  # Use design_conversation for flexibility
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates

        elif intent == "request_changes":
            specific_change = intent_result.get("specific_change")
            if specific_change:
                # Check if the specific change is visual
                change_lower = specific_change.lower()
                if any(kw in change_lower for kw in visual_change_keywords):
                    # Go directly to confirming_proposal
                    existing_feedback = list(state.get("image_generation_feedback", []))
                    existing_feedback.append(specific_change)
                    updates["image_generation_feedback"] = existing_feedback
                    updates["current_stage"] = "image_analysis_generation"
                    updates["image_sub_state"] = "confirming_proposal"
                    updates["awaiting_user_input"] = False
                    updates["_pending_regeneration"] = specific_change
                    updates["messages"] = []
                    return updates
                else:
                    response = (
                        f"I understand you want to change: **{specific_change}**\n\n"
                        f"Would you like to:\n"
                        f"- Go back to **image preview** to see changes\n"
                        f"- Update your **renovation vision**\n\n"
                        f"Let me know which option works for you."
                    )
            else:
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
    
    # Show summary (first time or no user message)
    summary = format_final_summary(state)
    
    response = (
        f"# Final Review\n\n"
        f"Here's a complete summary of your renovation project:\n\n"
        f"{summary}\n"
        f"---\n\n"
        f"**Does everything look correct?**\n\n"
        f"Say **'yes'** to generate your cost estimate, or let me know what needs to be changed."
    )
    
    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    
    return updates