"""
Main LangGraph definition for renovation estimation.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.core.langgraph.state import ProjectState, create_initial_state
from src.core.langgraph.utils import get_message_content
from src.core.langgraph.nodes import (
    project_basics_node,
    visual_collection_node,
    material_verification_node,
    measurement_verification_node,
    final_review_node,
    cost_estimation_node,
)


def route_by_stage(state: ProjectState) -> str:
    """Route to appropriate node based on current stage."""
    stage = state.get("current_stage", "project_basics")
    
    if stage == "completed":
        return END
    
    return stage


def create_graph(checkpointer=None):
    """
    Create the renovation estimation graph.
    
    Each invoke runs ONE node then stops (awaiting user input).
    """
    builder = StateGraph(ProjectState)
    
    # Add nodes
    builder.add_node("project_basics", project_basics_node)
    builder.add_node("visual_collection", visual_collection_node)
    builder.add_node("material_verification", material_verification_node)
    builder.add_node("measurement_verification", measurement_verification_node)
    builder.add_node("final_review", final_review_node)
    builder.add_node("cost_estimation", cost_estimation_node)
    
    # Entry point routes to current stage
    builder.add_conditional_edges(
        START,
        route_by_stage,
        {
            "project_basics": "project_basics",
            "visual_collection": "visual_collection",
            "material_verification": "material_verification",
            "measurement_verification": "measurement_verification",
            "final_review": "final_review",
            "cost_estimation": "cost_estimation",
            END: END
        }
    )
    
    # Each node goes to END after processing (wait for next user input)
    builder.add_edge("project_basics", END)
    builder.add_edge("visual_collection", END)
    builder.add_edge("material_verification", END)
    builder.add_edge("measurement_verification", END)
    builder.add_edge("final_review", END)
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
) -> tuple[ProjectState, str]:
    """
    Run a single conversation turn.
    
    Args:
        project_id: Unique project identifier
        user_message: User's message (str or list for multimodal)
        state: Current state (if None, starts fresh)
    
    Returns:
        Tuple of (updated_state, assistant_response)
    """
    if state is None:
        state = create_initial_state()
    
    # Add user message
    state["messages"].append({"role": "user", "content": user_message})
    state["awaiting_user_input"] = False
    state["user_confirmed_continue"] = False
    
    # Run graph (single step)
    config = {"configurable": {"thread_id": project_id}}
    result = await graph.ainvoke(state, config)
    
    # Extract assistant response
    messages = result.get("messages", [])
    assistant_response = ""
    for msg in reversed(messages):
        role, content = get_message_content(msg)
        if role == "assistant":
            assistant_response = content
            break
    
    return result, assistant_response