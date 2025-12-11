"""
Material Verification Node.

Compiles materials from extracted image data, verifies with user.
"""

from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import ProjectState, MaterialItem
from src.core.langgraph.utils import get_message_content
from tests.conftest import parse_json


MATERIAL_SUMMARY_PROMPT = """Based on the extracted image data, compile a list of materials for this {project_type} renovation.

Extracted features:
{features}

For each material, estimate:
- quantity (based on typical {project_type} sizes)
- unit (sqft, linear ft, pieces, etc.)
- approximate unit cost (USD)

Return JSON only:
{{
    "materials": [
        {{"name": "countertop", "type": "granite", "quantity": 30, "unit": "sqft", "unit_cost": 75}},
        {{"name": "cabinets", "type": "shaker", "quantity": 15, "unit": "linear ft", "unit_cost": 200}}
    ]
}}
"""


async def compile_materials(state: ProjectState) -> list[dict]:
    """Compile materials from all extracted image data."""
    provider = LLMProvider.for_llm()
    
    # Gather all features from images
    all_features = []
    for img in state.get("images", []):
        features = img.get("extracted", {}).get("features", [])
        all_features.extend(features)
    
    if not all_features:
        return []
    
    features_str = "\n".join([
        f"- {f.get('name', 'unknown')}: {f.get('material', 'unknown')}"
        for f in all_features
    ])
    
    response = await provider.complete(
        messages=[
            {"role": "system", "content": "You are a renovation cost estimator. Return JSON only."},
            {
                "role": "user",
                "content": MATERIAL_SUMMARY_PROMPT.format(
                    project_type=state.get("project_type", "renovation"),
                    features=features_str
                )
            }
        ],
        temperature=0.2,
        max_tokens=500
    )
    
    try:
        data = parse_json(response)
        return data.get("materials", [])
    except:
        return []


def format_materials_list(materials: list[MaterialItem]) -> str:
    """Format materials for display."""
    if not materials:
        return "No materials identified."
    
    lines = []
    for i, m in enumerate(materials, 1):
        status = "✓" if m.get("confirmed") else "○"
        cost = m.get("quantity", 0) * m.get("unit_cost", 0)
        lines.append(
            f"{status} {i}. {m.get('name', 'unknown').title()}: "
            f"{m.get('type', 'unknown')} - "
            f"{m.get('quantity', 0)} {m.get('unit', 'units')} "
            f"(~${cost:,.0f})"
        )
    
    return "\n".join(lines)


async def process_material_response(user_message: str, materials: list[MaterialItem]) -> dict:
    """Process user's response about materials."""
    provider = LLMProvider.for_llm()
    
    materials_str = format_materials_list(materials)
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": """Analyze user's response about material list.
Return JSON: {
    "action": "confirm_all" | "confirm" | "edit" | "remove" | "add" | "continue",
    "item_index": number or null,
    "new_value": {...} or null
}"""
            },
            {
                "role": "user",
                "content": f"""Materials list:
{materials_str}

User response: "{user_message}"

What action did the user take?"""
            }
        ],
        temperature=0.0,
        max_tokens=100
    )
    
    try:
        return parse_json(response)
    except:
        # Default to continue if can't parse
        user_lower = user_message.lower()
        if any(w in user_lower for w in ["yes", "correct", "confirm", "good", "ok"]):
            return {"action": "confirm_all"}
        if any(w in user_lower for w in ["continue", "next", "proceed"]):
            return {"action": "continue"}
        return {"action": "confirm_all"}


async def material_verification_node(state: ProjectState) -> dict:
    """
    Material verification node.
    
    - Compiles materials from extracted data
    - Shows list to user for verification
    - Handles edits/confirmations
    - Moves to measurement verification when done
    """
    messages = state.get("messages", [])
    materials = list(state.get("materials", []))
    
    updates = {}
    
    # Get latest user message
    user_message = None
    for msg in reversed(messages):
        role, content = get_message_content(msg)
        if role == "user":
            user_message = content
            if isinstance(user_message, list):
                user_message = next(
                    (item.get("text", "") for item in user_message if isinstance(item, dict) and item.get("type") == "text"),
                    ""
                )
            break
    
    # If no materials yet, compile from images
    if not materials:
        materials = await compile_materials(state)
        # Add confirmed=False to each
        materials = [
            MaterialItem(
                name=m.get("name", ""),
                type=m.get("type", ""),
                quantity=m.get("quantity", 0),
                unit=m.get("unit", "units"),
                unit_cost=m.get("unit_cost", 0),
                confirmed=False
            )
            for m in materials
        ]
        updates["materials"] = materials
        
        # Show initial list
        materials_str = format_materials_list(materials)
        response = f"""Based on your images, here are the materials I've identified:

{materials_str}

Does this look correct? You can:
- Say "yes" to confirm all
- Tell me to edit specific items (e.g., "change countertop to quartz")
- Add or remove items"""
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # Process user response
    if user_message:
        action = await process_material_response(user_message, materials)
        
        if action.get("action") == "confirm_all":
            # Mark all as confirmed
            for m in materials:
                m["confirmed"] = True
            updates["materials"] = materials
            updates["current_stage"] = "measurement_verification"
            response = "Materials confirmed! Now let's verify the measurements."
        
        elif action.get("action") == "continue":
            # Check if all confirmed
            all_confirmed = all(m.get("confirmed") for m in materials)
            if all_confirmed:
                updates["current_stage"] = "measurement_verification"
                response = "Moving to measurement verification."
            else:
                # Mark all as confirmed and continue
                for m in materials:
                    m["confirmed"] = True
                updates["materials"] = materials
                updates["current_stage"] = "measurement_verification"
                response = "Materials confirmed! Now let's verify the measurements."
        
        elif action.get("action") == "edit":
            idx = action.get("item_index")
            new_val = action.get("new_value", {})
            if idx is not None and 0 <= idx < len(materials):
                materials[idx].update(new_val)
                materials[idx]["confirmed"] = True
                updates["materials"] = materials
            
            materials_str = format_materials_list(materials)
            response = f"Updated! Here's the revised list:\n\n{materials_str}\n\nAnything else to change?"
        
        else:
            materials_str = format_materials_list(materials)
            response = f"Here's the current list:\n\n{materials_str}\n\nLet me know if this looks correct."
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
    
    return updates