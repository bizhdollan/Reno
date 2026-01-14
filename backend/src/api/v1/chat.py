"""Chat endpoint for LangGraph renovation flow."""

import traceback
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import httpx

from src.core.logger import get_logger
from src.core.langgraph import create_initial_state, run_conversation

logger = get_logger(__name__)
from src.core.langgraph.graph import get_message_content
from src.core.langgraph.state import ProjectState, get_thinking_status, get_stage_progress
from src.db.database import get_db
from src.db.models import Project, ConversationState
from src.utils.token_generator import generate_token


class ChatError(BaseModel):
    """Structured error response for chat endpoint."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="User-friendly error message")
    details: Optional[str] = Field(None, description="Technical details (only in dev mode)")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")


router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatMessage(BaseModel):
    """User message payload (text or multimodal list)."""

    project_id: str = Field(..., description="Unique project identifier")
    message: Union[str, List[dict]] = Field(
        ...,
        description="User message; string or LangChain-style message list for images",
    )
    state: Optional[ProjectState] = Field(
        None,
        description="Optional prior state; if omitted we use the server-stored state for the project or start fresh",
    )
    selected_image_url: Optional[str] = Field(
        None,
        description="URL of the currently selected canvas image for context in image editing",
    )


class ChatResponse(BaseModel):
    """Response returned to the frontend chat UI."""

    # Assistant reply can be plain text or structured content (e.g., tier cards)
    assistant: Any = Field(..., description="Assistant reply (text or structured content)")
    state: ProjectState = Field(..., description="Updated project state after this turn")
    project_id: str = Field(..., description="Canonical project token (PRJ-XXXXXX)")
    internal_id: str = Field(..., description="Internal project UUID for draft tracking")
    thinking_status: str = Field(
        default="Processing...",
        description="User-friendly status for thinking animation"
    )
    stage_progress: dict = Field(
        default_factory=dict,
        description="Stage progress info for frontend progress bar"
    )


@router.get("/conversation/{id_or_token}")
async def get_conversation_state(
    id_or_token: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve conversation state by project UUID or PRJ- token.

    Used for resuming conversations after page refresh.
    Accepts either internal UUID or PRJ- token.

    Args:
        id_or_token: Project UUID or PRJ- token
        db: Database session

    Returns:
        Full conversation state or null if not found
    """
    project = None

    # Check if it's a PRJ- token or UUID
    if id_or_token.startswith("PRJ-"):
        # Look up by token
        project = db.query(Project).filter(Project.token == id_or_token).first()
    else:
        # Assume it's a UUID
        try:
            from uuid import UUID
            uuid_obj = UUID(id_or_token)
            project = db.query(Project).filter(Project.id == uuid_obj).first()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid project ID or token format")

    if not project:
        return {"state": None, "project_id": None}

    # Get conversation state
    conv_state = db.query(ConversationState).filter(
        ConversationState.project_id == project.id
    ).first()

    if not conv_state:
        return {"state": None, "project_id": project.token}

    # Return state with project token
    state_dict = dict(conv_state.state)
    state_dict["project_id"] = project.token

    return {
        "state": state_dict,
        "project_id": project.token,
        "internal_id": str(project.id)
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatMessage,
    db: Session = Depends(get_db)
) -> ChatResponse:
    """
    Run a single synchronous chat turn against the LangGraph flow.

    - Uses `project_id` as the project token (PRJ-XXXXXX).
    - Accepts text or multimodal messages (string or list of message parts).
    - Persists state in PostgreSQL database for durability.
    - Creates new project if project_id doesn't exist or is "new".
    """
    project_id = payload.project_id
    
    # Handle new project creation
    if not project_id or project_id == "new":
        # Generate new project token
        project_id = generate_token("PRJ")
        logger.info(f"[chat] Creating new project with token: {project_id}")
    
    # Load or create project in database
    project = db.query(Project).filter(Project.token == project_id).first()
    
    if not project:
        # Create new project
        project = Project(
            token=project_id,
            status="draft"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        logger.info(f"[chat] Created new project in database: {project.id}")
    
    # Load conversation state from database
    conv_state = db.query(ConversationState).filter(
        ConversationState.project_id == project.id
    ).first()
    
    # Resolve starting state: database > fresh
    # Ignore any client-provided state to prevent duplication/drift.
    if conv_state:
        state = conv_state.state
    else:
        state = create_initial_state()

    logger.info(
        f"[chat] incoming project_id={project_id} (db_id={project.id}) | "
        f"message_type={'list' if isinstance(payload.message, list) else 'str'} | "
        f"state_current_stage={state.get('current_stage')} | "
        f"state_source={'database' if conv_state else 'fresh'}"
    )
    # Log raw user input for debugging
    logger.info(f"[chat] user_input={payload.message!r}")
    if payload.selected_image_url:
        logger.info(f"[chat] selected_image_url={payload.selected_image_url}")

    try:
        new_state, assistant_reply = await run_conversation(
            project_id=project_id,
            user_message=payload.message,
            state=state,
            selected_image_url=payload.selected_image_url,
        )
    except httpx.TimeoutException as exc:
        # LLM/API timeout
        logger.info(f"[chat] Timeout error: {exc}")
        return JSONResponse(
            status_code=504,
            content=ChatError(
                error="timeout",
                message="The request took too long. Please try again.",
                details=str(exc),
                retry_after=5
            ).model_dump()
        )
    except httpx.HTTPStatusError as exc:
        # HTTP errors from external APIs
        status_code = exc.response.status_code
        logger.info(f"[chat] HTTP error {status_code}: {exc}")

        if status_code == 429:
            # Rate limit
            return JSONResponse(
                status_code=429,
                content=ChatError(
                    error="rate_limit",
                    message="Too many requests. Please wait a moment and try again.",
                    details=str(exc),
                    retry_after=30
                ).model_dump()
            )
        elif status_code >= 500:
            # Upstream server error
            return JSONResponse(
                status_code=502,
                content=ChatError(
                    error="upstream_error",
                    message="Our AI service is temporarily unavailable. Please try again shortly.",
                    details=str(exc),
                    retry_after=10
                ).model_dump()
            )
        else:
            return JSONResponse(
                status_code=status_code,
                content=ChatError(
                    error="api_error",
                    message="An error occurred while processing your request.",
                    details=str(exc)
                ).model_dump()
            )
    except ValidationError as exc:
        # Pydantic validation errors
        logger.info(f"[chat] Validation error: {exc}")
        return JSONResponse(
            status_code=422,
            content=ChatError(
                error="validation_error",
                message="There was an issue with the data format. Please try again.",
                details=str(exc)
            ).model_dump()
        )
    except SQLAlchemyError as exc:
        # Database errors
        logger.info(f"[chat] Database error: {exc}")
        logger.error("Full traceback", exc_info=True)
        return JSONResponse(
            status_code=503,
            content=ChatError(
                error="database_error",
                message="We're having trouble saving your progress. Please try again.",
                details=str(exc),
                retry_after=5
            ).model_dump()
        )
    except Exception as exc:
        # Catch-all for unexpected errors
        logger.info(f"[chat] Unexpected error: {exc}")
        logger.error("Full traceback", exc_info=True)

        # Check for common LLM error patterns in the message
        error_msg = str(exc).lower()
        if "api key" in error_msg or "authentication" in error_msg:
            return JSONResponse(
                status_code=500,
                content=ChatError(
                    error="configuration_error",
                    message="There's a configuration issue. Please contact support.",
                    details=str(exc)
                ).model_dump()
            )
        elif "rate limit" in error_msg or "quota" in error_msg:
            return JSONResponse(
                status_code=429,
                content=ChatError(
                    error="rate_limit",
                    message="Service is busy. Please try again in a few seconds.",
                    details=str(exc),
                    retry_after=15
                ).model_dump()
            )
        elif "timeout" in error_msg or "timed out" in error_msg:
            return JSONResponse(
                status_code=504,
                content=ChatError(
                    error="timeout",
                    message="The request took too long. Please try again.",
                    details=str(exc),
                    retry_after=5
                ).model_dump()
            )
        else:
            return JSONResponse(
                status_code=500,
                content=ChatError(
                    error="internal_error",
                    message="Something went wrong. Please try again.",
                    details=str(exc)
                ).model_dump()
            )

    # Convert message objects (HumanMessage/AIMessage) to plain dicts for JSON
    serializable_state: Dict[str, Any] = dict(new_state)
    serializable_messages: List[Dict[str, Any]] = []
    for msg in new_state.get("messages", []):
        if isinstance(msg, dict):
            serializable_messages.append(msg)
            continue
        role, content = get_message_content(msg)
        serializable_messages.append({"role": role or "assistant", "content": content})
    serializable_state["messages"] = serializable_messages

    logger.info(
        "[chat] outgoing "
        f"current_stage={serializable_state.get('current_stage')} | "
        f"title={serializable_state.get('project_title')} | "
        f"type={serializable_state.get('project_type')} | "
        f"zip={serializable_state.get('zip_code')} | "
        f"assistant_reply_len={len(assistant_reply or '')}"
    )
    # Log assistant reply for debugging
    logger.info(f"[chat] assistant_reply={assistant_reply!r}")

    # Save state to database
    if conv_state:
        # Update existing state
        conv_state.state = serializable_state
        logger.info(f"[chat] Updated conversation state in database")
    else:
        # Create new state
        conv_state = ConversationState(
            project_id=project.id,
            state=serializable_state
        )
        db.add(conv_state)
        logger.info(f"[chat] Created conversation state in database")
    
    # Update project fields from state if available
    if serializable_state.get('project_type'):
        project.project_type = serializable_state['project_type']
    if serializable_state.get('zip_code'):
        project.zip_code = serializable_state['zip_code']

    # Sync JSONB fields from conversation state
    if serializable_state.get('image_analyses'):
        project.images = serializable_state['image_analyses']

    if serializable_state.get('extracted_data'):
        project.extracted_data = serializable_state['extracted_data']

    if serializable_state.get('renovation_vision'):
        project.renovation_vision = serializable_state['renovation_vision']

    # Sync full estimate with all 3 tiers
    if serializable_state.get('cost_tiers'):
        tiers = serializable_state.get('cost_tiers', [])
        # Convert tiers list to dict format for full_estimate JSONB
        full_estimate_dict = {}
        for tier in tiers:
            tier_id = tier.get('id', '').lower()  # 'low', 'mid', 'high'
            if tier_id in ['low', 'mid', 'high']:
                full_estimate_dict[tier_id] = tier

        if full_estimate_dict:
            project.full_estimate = full_estimate_dict

    # Update selected tier and total price
    if serializable_state.get('cost_tiers') and serializable_state.get('selected_tier'):
        # Extract selected tier info
        selected_tier = serializable_state.get('selected_tier')
        tiers = serializable_state.get('cost_tiers', [])
        for tier in tiers:
            if tier.get('id') == selected_tier:
                project.accepted_tier = selected_tier
                project.total_price = tier.get('total_cost', 0)
                break

    # Generate brief scope for marketplace preview (first 200 chars of description)
    if serializable_state.get('extracted_data'):
        extracted = serializable_state['extracted_data']
        # Try to create a brief description from extracted data
        brief_parts = []
        if extracted.get('project_description'):
            brief_parts.append(extracted['project_description'])
        elif extracted.get('materials'):
            materials = extracted['materials']
            if isinstance(materials, list) and materials:
                brief_parts.append(f"Project includes: {', '.join(str(m) for m in materials[:3])}")

        if brief_parts:
            project.brief_scope = ' '.join(brief_parts)[:200]

    # Update project status based on conversation stage
    current_stage = serializable_state.get('current_stage')
    if current_stage == 'completed':
        project.status = 'completed'
    elif project.status == 'draft':
        # Keep as draft until conversation completes
        project.status = 'draft'
    
    # Attach project_id/token to state for frontend convenience
    serializable_state["project_id"] = project_id
    # Attach internal UUID for service operations (DB queries)
    serializable_state["internal_project_id"] = str(project.id)

    db.commit()
    logger.info(f"[chat] Saved to database: project_status={project.status}")

    # Get thinking status and stage progress for frontend
    thinking_status = get_thinking_status(serializable_state)
    stage_progress = get_stage_progress(serializable_state)

    return ChatResponse(
        assistant=assistant_reply,
        state=serializable_state,
        project_id=project_id,
        internal_id=str(project.id),
        thinking_status=thinking_status,
        stage_progress=stage_progress,
    )
