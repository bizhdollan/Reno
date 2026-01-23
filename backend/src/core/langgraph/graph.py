"""
Main LangGraph definition for renovation estimation.

2-Stage Architecture (project_basics handled by form):
1. image_analysis_generation - Analyze images, confirm, collect vision, generate preview
2. cost_estimation - Generate 3-tier estimate, handle selection
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.core.langgraph.state import ProjectState, create_initial_state
from src.core.langgraph.utils import get_message_content
from src.core.langgraph.nodes import (
    image_analysis_generation_node,
    cost_estimation_node,
)


def route_by_stage(state: ProjectState) -> str:
    """Route to appropriate node based on current stage."""
    stage = state.get("current_stage", "project_basics")

    # project_basics is handled by form submission, not by graph
    # If in this stage, end immediately (awaiting form submission)
    if stage == "project_basics":
        return END

    if stage == "completed":
        return END

    return stage


def should_continue(state: ProjectState) -> str:
    """Check if we should continue to next node or end (wait for user)."""
    if not state.get("awaiting_user_input", True):
        return "continue"
    return "end"


def create_graph(checkpointer: str | None = None):
    """
    Create the renovation estimation graph.

    Supports auto-continue when a node sets awaiting_user_input=False.
    Note: project_basics is now handled by form submission (/api/v1/projects/{token}/basics)
    """
    builder = StateGraph(ProjectState)

    # Add nodes (2 stages - project_basics handled by form)
    builder.add_node("image_analysis_generation", image_analysis_generation_node)
    builder.add_node("cost_estimation", cost_estimation_node)

    # Entry point routes to current stage
    builder.add_conditional_edges(
        START,
        route_by_stage,
        {
            "image_analysis_generation": "image_analysis_generation",
            "cost_estimation": "cost_estimation",
            END: END
        }
    )

    # image_analysis_generation can loop back or continue to cost_estimation
    def image_analysis_router(state: ProjectState) -> str:
        if state.get("awaiting_user_input", True):
            return "end"
        # Check if we should go to cost_estimation
        if state.get("current_stage") == "cost_estimation":
            return "cost_estimation"
        # Otherwise loop back for sub-state processing
        return "continue"

    builder.add_conditional_edges(
        "image_analysis_generation",
        image_analysis_router,
        {
            "continue": "image_analysis_generation",
            "cost_estimation": "cost_estimation",
            "end": END
        }
    )

    # cost_estimation always waits for user (to select tier)
    builder.add_edge("cost_estimation", END)

    if checkpointer == "memory":
        checkpointer = MemorySaver()
    elif checkpointer is None:
        checkpointer = None

    return builder.compile(checkpointer=checkpointer)


# Create default graph instance
graph = create_graph()


async def run_conversation(
    project_id: str,
    user_message: str | list,
    state: ProjectState | None = None,
    selected_image_url: str | None = None
) -> tuple[ProjectState, str | list]:
    """
    Run a single conversation turn.

    Args:
        project_id: Unique project identifier
        user_message: User's message (str or list for multimodal)
        state: Current state (if None, starts fresh)
        selected_image_url: URL of the currently selected canvas image (for image editing context)

    Returns:
        Tuple of (updated_state, assistant_response)
        Response can be str or list (for multimodal/tier_cards)
    """
    if state is None:
        state = create_initial_state()

    # Add user message
    state["messages"].append({"role": "user", "content": user_message})
    state["awaiting_user_input"] = False
    state["user_confirmed_continue"] = False

    # Store selected image URL for image editing context
    if selected_image_url:
        state["selected_image_url"] = selected_image_url

    # Run graph
    config = {"configurable": {"thread_id": project_id}}
    result = await graph.ainvoke(state, config)

    # Extract assistant response(s)
    messages = result.get("messages", [])
    assistant_responses = []

    for msg in messages:
        role, content = get_message_content(msg)
        if role == "assistant" and content:
            assistant_responses.append(content)

    # Return the last (most recent) assistant response
    if assistant_responses:
        final_response = assistant_responses[-1]
    else:
        final_response = ""

    return result, final_response
