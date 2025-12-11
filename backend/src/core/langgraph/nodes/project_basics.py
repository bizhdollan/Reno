"""
Project Basics Node.

Collects: project_title, project_type, zip_code
One field at a time. Skips if already filled.
"""

from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import ProjectState, get_missing_basics
from src.core.langgraph.utils import get_message_content
from tests.conftest import parse_json


EXTRACTION_PROMPT = """You are a renovation assistant. Extract project information from the user's message.

Current project state:
- Title: {title}
- Type: {type}
- Zip Code: {zip}

User message: "{message}"

Extract any of these fields if mentioned:
- project_title: Name/title for the project
- project_type: Type of renovation (kitchen, bathroom, bedroom, living room, etc.)
- zip_code: 5-digit US zip code

Return JSON only:
{{"project_title": "..." or null, "project_type": "..." or null, "zip_code": "..." or null}}
"""

QUESTION_PROMPTS = {
    "project_title": "What would you like to call this renovation project?",
    "project_type": "What type of space are you renovating? (e.g., kitchen, bathroom, bedroom)",
    "zip_code": "What's the zip code for this project location?"
}


async def extract_basics(state: ProjectState, user_message: str) -> dict:
    """Extract project basics from user message."""
    provider = LLMProvider.for_llm()
    
    prompt = EXTRACTION_PROMPT.format(
        title=state.get("project_title") or "not set",
        type=state.get("project_type") or "not set",
        zip=state.get("zip_code") or "not set",
        message=user_message
    )
    
    response = await provider.complete(
        messages=[
            {"role": "system", "content": "Extract information. Return JSON only, no markdown."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=100
    )
    
    try:
        return parse_json(response)
    except:
        return {}


async def project_basics_node(state: ProjectState) -> dict:
    """
    Project basics node.
    
    - Extracts info from latest user message
    - Updates state with extracted fields
    - Returns next question for missing field
    """
    messages = state.get("messages", [])
    
    # Get latest user message
    user_message = None
    for msg in reversed(messages):
        role, content = get_message_content(msg)
        if role == "user":
            user_message = content
            break
    
    updates = {}
    
    # Extract from user message if present
    if user_message:
        extracted = await extract_basics(state, user_message)
        print(
            "[project_basics] user_message="
            f"{user_message!r} extracted={extracted} "
            f"existing_title={state.get('project_title')} "
            f"existing_type={state.get('project_type')} "
            f"existing_zip={state.get('zip_code')}"
        )
        
        # Update only if extracted and not already set
        if extracted.get("project_title") and not state.get("project_title"):
            updates["project_title"] = extracted["project_title"]
        if extracted.get("project_type") and not state.get("project_type"):
            updates["project_type"] = extracted["project_type"]
        if extracted.get("zip_code") and not state.get("zip_code"):
            updates["zip_code"] = extracted["zip_code"]
    
    # Merge updates to check what's still missing
    merged_state = {**state, **updates}
    missing = get_missing_basics(merged_state)
    
    # Generate response
    if missing:
        # Ask for next missing field
        next_field = missing[0]
        response = QUESTION_PROMPTS[next_field]
        updates["awaiting_user_input"] = True
    else:
        # All basics collected, confirm and prepare to move on
        response = (
            f"Got it! Here's what I have:\n"
            f"- Project: {merged_state.get('project_title')}\n"
            f"- Type: {merged_state.get('project_type')}\n"
            f"- Location: {merged_state.get('zip_code')}\n\n"
            f"Now, please upload some images of the space you want to renovate."
        )
        updates["current_stage"] = "visual_collection"
        updates["awaiting_user_input"] = True

    print(
        "[project_basics] missing="
        f"{missing} next_stage={updates.get('current_stage')} "
        f"response_preview={response[:80]!r}"
    )
    
    # Add assistant message
    updates["messages"] = [{"role": "assistant", "content": response}]
    
    return updates