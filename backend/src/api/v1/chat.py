"""Chat endpoint for LangGraph renovation flow."""

from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.langgraph import create_initial_state, run_conversation
from src.core.langgraph.graph import get_message_content
from src.core.langgraph.state import ProjectState


router = APIRouter(prefix="/api/v1", tags=["chat"])

# Simple in-memory store keyed by project_id
_STATE_STORE: Dict[str, ProjectState] = {}


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


class ChatResponse(BaseModel):
    """Response returned to the frontend chat UI."""

    assistant: str = Field(..., description="Assistant reply text")
    state: ProjectState = Field(..., description="Updated project state after this turn")


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatMessage) -> ChatResponse:
    """
    Run a single synchronous chat turn against the LangGraph flow.

    - Uses `project_id` as the LangGraph thread id.
    - Accepts text or multimodal messages (string or list of message parts).
    - Persists state in memory per project_id for now; frontend can also pass state explicitly.
    """
    project_id = payload.project_id

    # Resolve starting state: client-provided > cached > fresh
    state = payload.state or _STATE_STORE.get(project_id) or create_initial_state()

    print(
        f"[chat] incoming project_id={project_id} | "
        f"message_type={'list' if isinstance(payload.message, list) else 'str'} | "
        f"state_current_stage={state.get('current_stage')}"
    )

    try:
        new_state, assistant_reply = await run_conversation(
            project_id=project_id,
            user_message=payload.message,
            state=state,
        )
    except Exception as exc:  # pragma: no cover - surfaced as HTTP error
        # Surface provider errors cleanly
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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

    print(
        "[chat] outgoing "
        f"current_stage={serializable_state.get('current_stage')} | "
        f"title={serializable_state.get('project_title')} | "
        f"type={serializable_state.get('project_type')} | "
        f"zip={serializable_state.get('zip_code')} | "
        f"assistant_reply_len={len(assistant_reply or '')}"
    )

    # Cache state for subsequent turns
    _STATE_STORE[project_id] = serializable_state

    return ChatResponse(assistant=assistant_reply, state=serializable_state)

