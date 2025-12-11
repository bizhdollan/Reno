"""
Edge routing logic for the renovation estimation graph.
"""

from src.core.langgraph.state import ProjectState, Stage


def route_by_stage(state: ProjectState) -> str:
    """
    Route to the appropriate node based on current stage.
    
    This is the main router that determines which node to execute next.
    """
    stage = state.get("current_stage", "project_basics")
    
    # Map stages to node names
    stage_map = {
        "project_basics": "project_basics",
        "visual_collection": "visual_collection",
        "material_verification": "material_verification",
        "measurement_verification": "measurement_verification",
        "final_review": "final_review",
        "cost_estimation": "cost_estimation",
        "completed": "end"
    }
    
    return stage_map.get(stage, "project_basics")


def should_continue(state: ProjectState) -> str:
    """
    Determine if graph should continue or wait for user input.
    
    Returns:
        "continue" - Process next node
        "wait" - Pause for user input
        "end" - Conversation complete
    """
    stage = state.get("current_stage", "project_basics")
    
    if stage == "completed":
        return "end"
    
    if state.get("awaiting_user_input", True):
        return "wait"
    
    return "continue"