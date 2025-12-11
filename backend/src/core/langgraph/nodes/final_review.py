"""
Final Review Node.

Shows complete summary of all collected data before cost estimation.
"""

from src.core.langgraph.state import ProjectState


def format_final_summary(state: ProjectState) -> str:
    """Format complete project summary."""
    lines = []
    
    # Project basics
    lines.append("## Project Details")
    lines.append(f"- **Title:** {state.get('project_title', 'N/A')}")
    lines.append(f"- **Type:** {state.get('project_type', 'N/A')}")
    lines.append(f"- **Location:** {state.get('zip_code', 'N/A')}")
    lines.append("")
    
    # Images
    images = state.get("images", [])
    lines.append(f"## Images Analyzed: {len(images)}")
    lines.append("")
    
    # Measurements
    m = state.get("measurements", {})
    lines.append("## Measurements")
    lines.append(f"- Width: {m.get('width', 0)} ft")
    lines.append(f"- Length: {m.get('length', 0)} ft")
    lines.append(f"- Height: {m.get('height', 9)} ft")
    lines.append(f"- Area: {m.get('area_sqft', 0)} sq ft")
    lines.append("")
    
    # Materials
    materials = state.get("materials", [])
    lines.append("## Materials")
    total_material_cost = 0
    for mat in materials:
        cost = mat.get("quantity", 0) * mat.get("unit_cost", 0)
        total_material_cost += cost
        lines.append(
            f"- {mat.get('name', 'Unknown').title()}: {mat.get('type', 'N/A')} "
            f"({mat.get('quantity', 0)} {mat.get('unit', 'units')}) - ${cost:,.0f}"
        )
    lines.append(f"\n**Estimated Material Total:** ${total_material_cost:,.0f}")
    
    return "\n".join(lines)


def get_message_content(msg) -> tuple[str | None, any]:
    """Extract role and content from message (dict or LangChain Message object)."""
    if isinstance(msg, dict):
        return msg.get("role"), msg.get("content", "")
    role = getattr(msg, "type", None)
    if role == "human":
        role = "user"
    elif role == "ai":
        role = "assistant"
    content = getattr(msg, "content", "")
    return role, content


async def final_review_node(state: ProjectState) -> dict:
    """
    Final review node.
    
    - Shows complete summary
    - Asks for final confirmation
    - Moves to cost estimation when confirmed
    """
    messages = state.get("messages", [])
    
    updates = {}
    
    # Get latest user message
    user_message = None
    for msg in reversed(messages):
        role, content = get_message_content(msg)
        if role == "user":
            if isinstance(content, list):
                user_message = next(
                    (item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"),
                    ""
                )
            else:
                user_message = content
            break
    
    # Check if user confirmed
    if user_message:
        user_lower = user_message.lower()
        if any(w in user_lower for w in ["yes", "confirm", "generate", "proceed", "estimate", "continue", "ok", "good"]):
            updates["current_stage"] = "cost_estimation"
            updates["user_confirmed_continue"] = True
            response = "Generating your cost estimate..."
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = False
            return updates
        elif any(w in user_lower for w in ["no", "change", "edit", "back", "wrong"]):
            response = "What would you like to change? You can say:\n- 'change measurements'\n- 'change materials'\n- Or describe what needs to be updated"
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates
    
    # Show summary
    summary = format_final_summary(state)
    response = f"""Here's a summary of your project:

{summary}

Does everything look correct? Say "yes" to generate the cost estimate, or let me know what needs to be changed."""
    
    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    
    return updates