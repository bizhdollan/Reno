"""
Main LangGraph definition for renovation estimation.

4-Stage Architecture:
1. project_basics - Collect title, type, zip_code
2. image_analysis_generation - Analyze images, confirm, generate preview
3. final_review - Review all data before estimation
4. cost_estimation - Generate 3-tier estimate, handle selection
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.core.langgraph.state import ProjectState, create_initial_state
from src.core.langgraph.utils import get_message_content
from src.core.langgraph.nodes import (
    project_basics_node,
    image_analysis_generation_node,
    final_review_node,
    cost_estimation_node,
)


def route_by_stage(state: ProjectState) -> str:
    """Route to appropriate node based on current stage."""
    stage = state.get("current_stage", "project_basics")
    
    if stage == "completed":
        return END
    
    return stage


def should_continue(state: ProjectState) -> str:
    """Check if we should continue to next node or end (wait for user)."""
    # If awaiting_user_input is False, continue processing
    if not state.get("awaiting_user_input", True):
        return "continue"
    return "end"


def create_graph(checkpointer=None):
    """
    Create the renovation estimation graph.
    
    Supports auto-continue when a node sets awaiting_user_input=False.
    """
    builder = StateGraph(ProjectState)
    
    # Add nodes (4 stages)
    builder.add_node("project_basics", project_basics_node)
    builder.add_node("image_analysis_generation", image_analysis_generation_node)
    builder.add_node("final_review", final_review_node)
    builder.add_node("cost_estimation", cost_estimation_node)
    
    # Entry point routes to current stage
    builder.add_conditional_edges(
        START,
        route_by_stage,
        {
            "project_basics": "project_basics",
            "image_analysis_generation": "image_analysis_generation",
            "final_review": "final_review",
            "cost_estimation": "cost_estimation",
            END: END
        }
    )
    
    # Each node checks if it should continue or wait
    # project_basics always waits for user
    # builder.add_edge("project_basics", END)
    builder.add_conditional_edges(
        "project_basics",
        should_continue,
        {
            "continue": "image_analysis_generation",
            "end": END
        }
    )
    
    # image_analysis_generation can auto-continue (e.g., after confirming all, go to generating)
    builder.add_conditional_edges(
        "image_analysis_generation",
        should_continue,
        {
            "continue": "image_analysis_generation",  # Loop back to process next sub-state
            "end": END
        }
    )
    
    # final_review can auto-continue to cost_estimation
    builder.add_conditional_edges(
        "final_review",
        should_continue,
        {
            "continue": "cost_estimation",  # Auto-proceed to cost estimation
            "end": END
        }
    )
    
    # cost_estimation always waits for user (to select tier)
    builder.add_edge("cost_estimation", END)
    
    # Use provided checkpointer or default to memory
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return builder.compile(checkpointer=checkpointer)


# Create default graph instance
graph = create_graph()


async def run_conversation(
    project_id: str,
    user_message: str | list,
    state: ProjectState | None = None
) -> tuple[ProjectState, str | list]:
    """
    Run a single conversation turn.
    
    Args:
        project_id: Unique project identifier
        user_message: User's message (str or list for multimodal)
        state: Current state (if None, starts fresh)
    
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
    
    # Run graph
    config = {"configurable": {"thread_id": project_id}}
    result = await graph.ainvoke(state, config)
    
    # Extract assistant response(s) - may have multiple from auto-continue
    messages = result.get("messages", [])
    assistant_responses = []
    
    for msg in messages:
        role, content = get_message_content(msg)
        if role == "assistant" and content:
            assistant_responses.append(content)
    
    # Return the last (most recent) assistant response
    if assistant_responses:
        # If there are multiple responses, combine them or return the last meaningful one
        final_response = assistant_responses[-1]
    else:
        final_response = ""
    
    return result, final_response