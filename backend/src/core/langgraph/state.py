"""
LangGraph State Schema for Renovation Estimation.

Stages:
1. project_basics - Collect title, type, zip_code
2. visual_collection - Upload images, extract details, confirm
3. material_verification - Verify extracted materials
4. measurement_verification - Verify measurements
5. final_review - User confirms all data
6. cost_estimation - Generate estimate
"""

from typing import TypedDict, Literal, Annotated
from langgraph.graph.message import add_messages


# Stage type
Stage = Literal[
    "project_basics",
    "visual_collection", 
    "material_verification",
    "measurement_verification",
    "final_review",
    "cost_estimation",
    "completed"
]


class ImageData(TypedDict, total=False):
    """Data extracted from a single image."""
    id: str
    url: str  # base64 data URL or file path
    extracted: dict  # AI-extracted information
    confirmed: bool  # User confirmed extraction


class MaterialItem(TypedDict, total=False):
    """A single material item."""
    name: str
    type: str  # e.g., "granite", "oak", "ceramic"
    quantity: float
    unit: str  # e.g., "sqft", "linear ft", "pieces"
    unit_cost: float
    confirmed: bool


class Measurements(TypedDict, total=False):
    """Room/scope measurements."""
    width: float
    length: float
    height: float
    area_sqft: float
    unit: str  # "ft" or "m"
    confirmed: bool


class Scope(TypedDict, total=False):
    """What is being renovated."""
    type: str  # "kitchen", "bathroom", etc.
    description: str
    dimensions: Measurements
    materials: list[MaterialItem]


class CostEstimate(TypedDict, total=False):
    """Final cost estimate."""
    labor_cost: float
    material_cost: float
    overhead: float
    total: float
    breakdown: list[dict]
    confidence: float  # 0-1


class PendingConfirmation(TypedDict):
    """Item awaiting user confirmation."""
    field: str  # What field this relates to
    extracted_value: str  # What AI thinks it is
    confidence: float  # How confident AI is (0-1)
    source_image_id: str | None  # Which image it came from


class ProjectState(TypedDict, total=False):
    """
    Main state for the renovation estimation graph.
    
    This state flows through all nodes and persists between interactions.
    """
    # Conversation history
    messages: Annotated[list[dict], add_messages]
    
    # Stage tracking
    current_stage: Stage
    
    # Project basics (stage 1)
    project_title: str | None
    project_type: str | None
    zip_code: str | None
    
    # Visual collection (stage 2)
    images: list[ImageData]
    pending_confirmations: list[PendingConfirmation]
    
    # Scope - what's being renovated
    scope: Scope
    
    # Materials (stage 3)
    materials: list[MaterialItem]
    
    # Measurements (stage 4)
    measurements: Measurements
    
    # Final estimate (stage 6)
    estimate: CostEstimate | None
    
    # Control flags
    user_confirmed_continue: bool  # User said "continue" to next stage
    awaiting_user_input: bool  # Graph is paused for user response


def create_initial_state() -> ProjectState:
    """Create a fresh project state."""
    return ProjectState(
        messages=[],
        current_stage="project_basics",
        project_title=None,
        project_type=None,
        zip_code=None,
        images=[],
        pending_confirmations=[],
        scope={},
        materials=[],
        measurements={},
        estimate=None,
        user_confirmed_continue=False,
        awaiting_user_input=True
    )


def get_missing_basics(state: ProjectState) -> list[str]:
    """Return list of missing project basic fields."""
    missing = []
    if not state.get("project_title"):
        missing.append("project_title")
    if not state.get("project_type"):
        missing.append("project_type")
    if not state.get("zip_code"):
        missing.append("zip_code")
    return missing


def is_stage_complete(state: ProjectState, stage: Stage) -> bool:
    """Check if a stage has all required data."""
    if stage == "project_basics":
        return len(get_missing_basics(state)) == 0
    
    if stage == "visual_collection":
        has_images = len(state.get("images", [])) > 0
        no_pending = len(state.get("pending_confirmations", [])) == 0
        user_ready = state.get("user_confirmed_continue", False)
        return has_images and no_pending and user_ready
    
    if stage == "material_verification":
        materials = state.get("materials", [])
        return len(materials) > 0 and all(m.get("confirmed") for m in materials)
    
    if stage == "measurement_verification":
        measurements = state.get("measurements", {})
        return measurements.get("confirmed", False)
    
    if stage == "final_review":
        return state.get("user_confirmed_continue", False)
    
    if stage == "cost_estimation":
        return state.get("estimate") is not None
    
    return False


def get_next_stage(current: Stage) -> Stage:
    """Get the next stage in sequence."""
    sequence = [
        "project_basics",
        "visual_collection",
        "material_verification",
        "measurement_verification",
        "final_review",
        "cost_estimation",
        "completed"
    ]
    try:
        idx = sequence.index(current)
        return sequence[idx + 1] if idx + 1 < len(sequence) else "completed"
    except ValueError:
        return "project_basics"