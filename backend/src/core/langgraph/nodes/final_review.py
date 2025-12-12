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
    lines.append(f"- **Type:** {state.get('project_type', 'N/A').title()}")
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
    if extracted.get("materials"):
        lines.append("## 🧱 Materials\n")
        for m in extracted["materials"]:
            line = f"- **{m.get('name', 'Unknown').title()}**: {m.get('type', 'N/A')}"
            if m.get("finish"):
                line += f" ({m['finish']})"
            lines.append(line)
        lines.append("")
    
    # Measurements
    if extracted.get("measurements"):
        m = extracted["measurements"]
        lines.append("## 📐 Measurements\n")
        lines.append(f"- **Room Size:** {m.get('room_width_ft', '?')} × {m.get('room_length_ft', '?')} ft")
        lines.append(f"- **Ceiling Height:** {m.get('room_height_ft', '?')} ft")
        lines.append(f"- **Total Area:** {m.get('area_sqft', '?')} sq ft")
        lines.append("")
    
    # Colors
    if extracted.get("colors"):
        lines.append("## 🎨 Colors\n")
        for c in extracted["colors"]:
            lines.append(f"- **{c.get('element', 'Unknown').title()}**: {c.get('color', 'N/A')}")
        lines.append("")
    
    # Fixtures
    if extracted.get("fixtures"):
        lines.append("## 🔧 Fixtures\n")
        for f in extracted["fixtures"]:
            lines.append(f"- **{f.get('name', 'Unknown').title()}**: {f.get('type', 'N/A')} ({f.get('condition', 'N/A')})")
        lines.append("")
    
    # Appliances
    if extracted.get("appliances"):
        lines.append("## 🔌 Appliances\n")
        for a in extracted["appliances"]:
            lines.append(f"- **{a.get('name', 'Unknown').title()}**: {a.get('type', 'N/A')}")
        lines.append("")
    
    # Style
    if extracted.get("style"):
        s = extracted["style"]
        lines.append("## 🏠 Style Assessment\n")
        lines.append(f"- **Overall Style:** {s.get('overall_style', 'N/A')}")
        lines.append(f"- **Current Condition:** {s.get('condition', 'N/A')}")
        lines.append(f"- **Estimated Age:** {s.get('age_estimate', 'N/A')}")
        lines.append("")
    
    return "\n".join(lines)


async def final_review_node(state: ProjectState) -> dict:
    """
    Final review node.
    
    - Shows complete summary of all confirmed data immediately
    - User can confirm to proceed or request changes
    - Moves to cost_estimation when confirmed
    """
    messages = state.get("messages", [])
    user_message, _ = get_latest_user_message(messages)
    
    updates = {}
    
    # Check if we already showed the summary (track with flag)
    summary_shown = state.get("_final_review_shown", False)
    
    # If user is responding
    if user_message and summary_shown:
        lower = user_message.lower()
        
        if any(w in lower for w in ["yes", "confirm", "generate", "proceed", "estimate", "continue", "ok", "good", "correct"]):
            updates["current_stage"] = "cost_estimation"
            updates["user_confirmed_continue"] = True
            updates["_final_review_shown"] = False  # Reset for potential re-entry
            
            # Auto-continue to cost estimation - don't wait for user
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates
        
        elif any(w in lower for w in ["no", "change", "edit", "back", "wrong", "update"]):
            response = (
                "What would you like to change?\n\n"
                "You can say things like:\n"
                "- 'Change the countertop material to quartz'\n"
                "- 'Update the room dimensions'\n"
                "- 'Go back to review images'\n\n"
                "Or specify exactly what needs to be updated."
            )
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates
    
    # Show summary (first time entering this stage)
    summary = format_final_summary(state)
    
    response = (
        f"# Final Review\n\n"
        f"Here's a complete summary of your renovation project:\n\n"
        f"{summary}\n"
        f"---\n\n"
        f"**Does everything look correct?**\n\n"
        f"Say **'yes'** to generate your cost estimate, or let me know what needs to be changed."
    )
    
    updates["_final_review_shown"] = True
    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    
    return updates