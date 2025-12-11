"""
Measurement Verification Node.

Compiles measurements from extracted image data, verifies with user.
"""

from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import ProjectState, Measurements
from tests.conftest import parse_json


MEASUREMENT_PROMPT = """Based on the image analysis, estimate room measurements.

Project type: {project_type}
Extracted dimension hints: {dimensions}

Provide your best estimate for a typical {project_type}.

Return JSON only:
{{
    "width_ft": number,
    "length_ft": number,
    "height_ft": number (usually 8-10),
    "area_sqft": number,
    "confidence": 0-1
}}
"""


async def compile_measurements(state: ProjectState) -> dict:
    """Compile measurements from extracted data or estimate."""
    provider = LLMProvider.for_llm()
    
    # Gather dimension hints from images
    dim_hints = []
    for img in state.get("images", []):
        dims = img.get("extracted", {}).get("estimated_dimensions", {})
        if dims:
            dim_hints.append(dims)
    
    dims_str = str(dim_hints) if dim_hints else "No dimensions extracted from images"
    
    response = await provider.complete(
        messages=[
            {"role": "system", "content": "You are a renovation estimator. Return JSON only."},
            {
                "role": "user",
                "content": MEASUREMENT_PROMPT.format(
                    project_type=state.get("project_type", "renovation"),
                    dimensions=dims_str
                )
            }
        ],
        temperature=0.3,
        max_tokens=150
    )
    
    try:
        return parse_json(response)
    except:
        # Default estimates
        return {
            "width_ft": 12,
            "length_ft": 10,
            "height_ft": 9,
            "area_sqft": 120,
            "confidence": 0.3
        }


def format_measurements(m: Measurements) -> str:
    """Format measurements for display."""
    if not m:
        return "No measurements available."
    
    area = m.get("area_sqft") or (m.get("width", 0) * m.get("length", 0))
    conf = m.get("confidence", 0)
    conf_str = "(estimated)" if conf < 0.7 else "(from image)"
    
    return f"""Room Dimensions {conf_str}:
- Width: {m.get('width', m.get('width_ft', 0))} ft
- Length: {m.get('length', m.get('length_ft', 0))} ft
- Height: {m.get('height', m.get('height_ft', 9))} ft
- Total Area: {area} sq ft"""


async def parse_measurement_update(user_message: str, current: Measurements) -> dict:
    """Parse user's measurement corrections."""
    provider = LLMProvider.for_llm()
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": """Extract measurement updates from user message.
Return JSON: {"width_ft": num or null, "length_ft": num or null, "height_ft": num or null, "confirmed": true/false}
Set confirmed=true if user accepts current values."""
            },
            {
                "role": "user",
                "content": f"""Current: width={current.get('width', current.get('width_ft', 0))}, length={current.get('length', current.get('length_ft', 0))}, height={current.get('height', current.get('height_ft', 9))}
User says: "{user_message}"

Extract any corrections or confirmation."""
            }
        ],
        temperature=0.0,
        max_tokens=100
    )
    
    try:
        return parse_json(response)
    except:
        user_lower = user_message.lower()
        if any(w in user_lower for w in ["yes", "correct", "confirm", "good", "ok", "continue"]):
            return {"confirmed": True}
        return {}


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


async def measurement_verification_node(state: ProjectState) -> dict:
    """
    Measurement verification node.
    
    - Shows estimated/extracted measurements
    - Allows user to correct
    - Moves to final review when confirmed
    """
    messages = state.get("messages", [])
    measurements = dict(state.get("measurements", {}))
    
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
    
    # If no measurements yet, compile from images
    if not measurements or not measurements.get("width", measurements.get("width_ft")):
        compiled = await compile_measurements(state)
        measurements = Measurements(
            width=compiled.get("width_ft", 12),
            length=compiled.get("length_ft", 10),
            height=compiled.get("height_ft", 9),
            area_sqft=compiled.get("area_sqft", 120),
            unit="ft",
            confirmed=False
        )
        updates["measurements"] = measurements
        
        measurements_str = format_measurements(measurements)
        response = f"""Here are the estimated measurements:

{measurements_str}

Are these correct? Please provide the actual dimensions if you have them, or say "yes" to confirm."""
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # Process user response
    if user_message:
        parsed = await parse_measurement_update(user_message, measurements)
        
        # Apply updates
        if parsed.get("width_ft"):
            measurements["width"] = parsed["width_ft"]
        if parsed.get("length_ft"):
            measurements["length"] = parsed["length_ft"]
        if parsed.get("height_ft"):
            measurements["height"] = parsed["height_ft"]
        
        # Recalculate area
        measurements["area_sqft"] = measurements.get("width", 0) * measurements.get("length", 0)
        
        if parsed.get("confirmed"):
            measurements["confirmed"] = True
            updates["measurements"] = measurements
            updates["current_stage"] = "final_review"
            updates["user_confirmed_continue"] = False  # Reset for final review
            
            response = "Measurements confirmed! Let me show you a summary of everything before we generate the estimate."
        else:
            updates["measurements"] = measurements
            measurements_str = format_measurements(measurements)
            response = f"""Updated measurements:

{measurements_str}

Does this look correct now?"""
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
    
    return updates