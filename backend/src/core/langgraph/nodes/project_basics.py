"""
Project Basics Node.

Collects: project_title, project_type, zip_code
Smart extraction - infers what it can, only asks for missing fields.
User can edit until they upload an image (which triggers stage transition).
"""

from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import ProjectState
from src.core.langgraph.utils import get_latest_user_message, parse_json
from src.core.services.location_service import validate_us_zip_code, extract_location_from_zip
from src.core.services.renovation_inspiration_service import start_location_prefetch_background
from src.db.database import SessionLocal
from src.db.models import Project


SMART_EXTRACTION_PROMPT = """Extract project information from the user's message.

Current known values:
- Project Title: {current_title}
- Project Type: {current_type}
- Zip Code: {current_zip}

User message: "{message}"

Extract ANY of these fields that you can identify from the message:
1. project_title - A name for the renovation project
2. project_type - Type of space (kitchen, bathroom, bedroom, basement, hallway, stairs, etc. - can be compound like "hallway and stairs")
3. zip_code - US zip code (5 digits)

Also check if user is:
- Confirming something (yes, correct, looks good, etc.)
- Wanting to edit/change something (change, update, no, wrong, etc.)

Return JSON only:
{{
    "extracted": {{
        "project_title": "value or null if not found",
        "project_type": "value or null if not found", 
        "zip_code": "value or null if not found"
    }},
    "inferred_type": "if project_title mentions a room type, infer it here, else null",
    "is_confirmation": true/false,
    "wants_edit": true/false,
    "edit_field": "title/type/zip or null",
    "edit_value": "new value if provided, else null"
}}

Examples:
- "Kitchen Renovation Project" -> title="Kitchen Renovation Project", inferred_type="kitchen"
- "My bathroom remodel" -> title="My bathroom remodel", inferred_type="bathroom"
- "10001" -> zip_code="10001"
- "yes" -> is_confirmation=true
- "change the type to bedroom" -> wants_edit=true, edit_field="type", edit_value="bedroom"
- "change the type to hallway and stairs" -> wants_edit=true, edit_field="type", edit_value="hallway and stairs"
"""


async def smart_extract(message: str, current_state: dict) -> dict:
    """Extract all possible fields from user message."""
    provider = LLMProvider.for_llm()
    
    response = await provider.complete(
        messages=[
            {"role": "system", "content": "Extract project information. Return JSON only."},
            {"role": "user", "content": SMART_EXTRACTION_PROMPT.format(
                current_title=current_state.get("project_title") or "Not set",
                current_type=current_state.get("project_type") or "Not set",
                current_zip=current_state.get("zip_code") or "Not set",
                message=message
            )}
        ],
        temperature=0.0,
        max_tokens=200
    )
    
    try:
        return parse_json(response)
    except:
        return {"extracted": {}, "is_confirmation": False, "wants_edit": False}


def get_missing_fields(state: ProjectState) -> list[str]:
    """Return list of missing required fields."""
    missing = []
    if not state.get("project_title"):
        missing.append("project_title")
    if not state.get("project_type"):
        missing.append("project_type")
    if not state.get("zip_code"):
        missing.append("zip_code")
    return missing


def format_summary(state: ProjectState) -> str:
    """Format current project info as summary."""
    return (
        f"- **Project Name:** {state.get('project_title', 'Not set')}\n"
        f"- **Type:** {state.get('project_type', 'Not set')}\n"
        f"- **Zip Code:** {state.get('zip_code', 'Not set')}"
    )


async def project_basics_node(state: ProjectState) -> dict:
    """
    Project basics node with smart extraction.
    
    Flow:
    1. Ask for project name (first turn)
    2. Extract title + infer type from response
    3. Ask for type (one at a time)
    4. Ask for zip code
    5. Show summary when all fields filled
    6. Allow edits until image is uploaded
    7. Image upload -> transition to next stage
    """
    messages = state.get("messages", [])
    user_message, image_urls = get_latest_user_message(messages)
    
    updates = {}
    
    # Get current values
    title = state.get("project_title")
    ptype = state.get("project_type")
    zipcode = state.get("zip_code")
    
    # DEBUG logging
    print(f"[project_basics] INPUT: title={title} | type={ptype} | zip={zipcode}")
    print(f"[project_basics] user_message={user_message!r} | has_images={len(image_urls) > 0}")
    
    # Check if user uploaded images -> transition to next stage
    if image_urls:
        # Must have all basics before proceeding
        if not all([title, ptype, zipcode]):
            missing = get_missing_fields(state)
            field_names = {"project_title": "project name", "project_type": "project type", "zip_code": "zip code"}
            missing_str = ", ".join(field_names[f] for f in missing)
            response = f"Before I can analyze your images, I need a few more details: {missing_str}."
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates
        
        # All basics complete - transition with images
        updates["current_stage"] = "image_analysis_generation"
        updates["image_sub_state"] = "analyzing"
        updates["awaiting_user_input"] = False
        updates["messages"] = []
        # Store the image URLs for the next node to process
        updates["_pending_images"] = image_urls
        print(f"[project_basics] Transitioning to image_analysis with {len(image_urls)} pending images")
        return updates
    
    # First turn - no user message yet
    if not user_message:
        response = "Welcome! Let's get started with your renovation estimate.\n\nWhat would you like to call this project?"
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # Process user message with smart extraction
    extraction = await smart_extract(user_message, state)
    extracted = extraction.get("extracted", {})
    inferred_type = extraction.get("inferred_type")
    is_confirmation = extraction.get("is_confirmation", False)
    wants_edit = extraction.get("wants_edit", False)
    edit_field = extraction.get("edit_field")
    edit_value = extraction.get("edit_value")
    
    # DEBUG logging
    print(f"[project_basics] EXTRACTION: {extraction}")
    
    # Handle edit requests (only when basics are complete)
    if wants_edit and edit_field and not get_missing_fields(state):
        field_map = {"title": "project_title", "type": "project_type", "zip": "zip_code"}
        actual_field = field_map.get(edit_field, edit_field)
        
        # Try edit_value first, then fall back to extracted value
        new_value = edit_value or extracted.get(actual_field)
        
        if new_value:
            updates[actual_field] = new_value
            ptype_for_msg = new_value if actual_field == "project_type" else state.get("project_type", "space")
            response = f"Updated! Here's your project info:\n\n{format_summary({**state, actual_field: new_value})}\n\nUpload images of your {ptype_for_msg} to continue, or let me know if anything needs to change."
        else:
            field_names = {"project_title": "project name", "project_type": "type", "zip_code": "zip code"}
            response = f"What would you like to change the {field_names.get(actual_field, 'field')} to?"
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        print(f"[project_basics] EDIT HANDLED: {actual_field} = {new_value}")
        return updates
    
    # Apply extracted values
    if extracted.get("project_title") and not title:
        updates["project_title"] = extracted["project_title"]
        title = extracted["project_title"]
    
    if extracted.get("project_type"):
        updates["project_type"] = extracted["project_type"]
        ptype = extracted["project_type"]
    elif inferred_type and not ptype:
        updates["project_type"] = inferred_type
        ptype = inferred_type
    
    if extracted.get("zip_code"):
        updates["zip_code"] = extracted["zip_code"]
        zipcode = extracted["zip_code"]
    
    # Determine what to ask next
    missing = get_missing_fields({**state, **updates})

    if not missing:
        # All fields complete - show summary
        ptype_for_msg = updates.get("project_type") or state.get("project_type", "space")
        final_zip = updates.get("zip_code") or state.get("zip_code")
        final_type = updates.get("project_type") or state.get("project_type")

        # Start background task to prefetch location data (Census + Climate)
        # Tavily search is deferred until image analysis provides search insights
        project_id_token = state.get("project_id")
        if project_id_token and final_zip:
            # Validate zip code before starting background task
            if validate_us_zip_code(final_zip):
                # Get project UUID from database
                try:
                    db = SessionLocal()
                    try:
                        project = db.query(Project).filter(Project.token == project_id_token).first()
                        if project:
                            print(f"[project_basics] Starting location prefetch for zip {final_zip} (Tavily deferred until image analysis)")
                            start_location_prefetch_background(
                                project_id=project.id,
                                zip_code=final_zip
                            )
                        else:
                            print(f"[project_basics] Project not found for token {project_id_token}")
                    finally:
                        db.close()
                except Exception as e:
                    print(f"[project_basics] Failed to start location prefetch: {e}")
            else:
                print(f"[project_basics] Invalid zip code {final_zip}, skipping location prefetch")

        response = (
            f"Here's what I have:\n\n"
            f"{format_summary({**state, **updates})}\n\n"
            f"Upload images of your {ptype_for_msg} to continue, or let me know if anything needs to change."
        )
    
    elif "project_title" in missing:
        # Still need title
        response = "What would you like to call this renovation project?"
    
    elif "project_type" in missing:
        # Need type (ask one at a time)
        response = "What type of space are you renovating? (kitchen, bathroom, bedroom, etc.)"
    
    elif "zip_code" in missing:
        # Have title and type - ask for zip
        response = f"Great! A **{ptype}** renovation. What's the zip code for this project?"
    
    else:
        # Fallback
        response = "Let me know any other details or upload images when ready."
    
    print(f"[project_basics] UPDATES: {updates}")
    print(f"[project_basics] RESPONSE: {response[:100]}...")
    
    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    
    return updates