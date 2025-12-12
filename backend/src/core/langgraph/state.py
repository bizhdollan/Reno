"""
LangGraph State Schema for Renovation Estimation.

4-Stage Architecture:
1. project_basics - Collect title, type, zip_code
2. image_analysis_generation - Analyze images, confirm info, generate preview
3. final_review - Review all confirmed data before estimation
4. cost_estimation - Generate 3-tier cost estimate
"""

from typing import TypedDict, Literal, Annotated, Any
from langgraph.graph.message import add_messages


# Stage types
Stage = Literal[
    "project_basics",
    "image_analysis_generation",
    "final_review",
    "cost_estimation",
    "completed"
]

# Sub-states for image_analysis_generation stage
ImageSubState = Literal[
    "analyzing",        # Processing uploaded images
    "confirming",       # Back-and-forth confirmation loop
    "generating",       # Generating preview image
    "image_confirmation"  # User reviewing generated image
]


class ImageData(TypedDict, total=False):
    """Data for a single uploaded image."""
    id: str
    url: str  # base64 data URL or file path
    analyzed: bool  # Whether image has been analyzed


class ExtractedData(TypedDict, total=False):
    """All data extracted from images in single pass."""
    materials: list[dict]  # [{name, type, finish, condition, dimensions, confidence}]
    measurements: dict  # {room_width, room_length, room_height, area_sqft, ...}
    colors: list[dict]  # [{element, color, finish}]
    fixtures: list[dict]  # [{name, type, brand, condition}]
    appliances: list[dict]  # [{name, type, brand, condition}]
    style: dict  # {overall_style, condition, age_estimate}
    other: list[dict]  # Any other relevant details


class ConfirmationStatus(TypedDict, total=False):
    """Track what has been confirmed by user."""
    materials: bool
    measurements: bool
    colors: bool
    fixtures: bool
    appliances: bool
    style: bool
    other: bool
    all_confirmed: bool  # True when everything is confirmed


class CategoryBreakdown(TypedDict, total=False):
    """Cost breakdown for a single category."""
    category: str  # "Cabinets", "Countertops", "Flooring", etc.
    description: str
    materials_cost: float
    labor_cost: float
    total: float


class CostTier(TypedDict, total=False):
    """Single tier in 3-tier cost structure."""
    id: str  # "low", "mid", "high"
    name: str  # "Low Tier", "Mid Tier", "High Tier"
    badge: str  # "Budget-Friendly", "Recommended", "Premium"
    description: str
    total_cost: float  # COGS + markup
    cogs: float  # Cost of Goods Sold
    markup_percentage: float  # 20, 35, 50
    markup_amount: float
    included_items: list[str]  # ["Cabinets", "Countertops", ...]
    detailed_breakdown: list[CategoryBreakdown]


class ProjectState(TypedDict, total=False):
    """
    Main state for the renovation estimation graph.
    """
    # Conversation history
    messages: Annotated[list[dict], add_messages]
    
    # Stage tracking
    current_stage: Stage
    image_sub_state: ImageSubState  # Sub-state within image_analysis_generation
    
    # Project basics (stage 1)
    project_title: str | None
    project_type: str | None
    zip_code: str | None
    
    # Image analysis (stage 2)
    images: list[ImageData]  # Uploaded images
    extracted_data: ExtractedData  # All extracted info from images
    confirmation_status: ConfirmationStatus  # What's been confirmed
    current_confirmation_section: str | None  # Which section is being confirmed
    
    # Generated image
    generate_image: bool  # Flag to enable/disable image generation
    generated_image_url: str | None  # URL of generated/placeholder image
    image_generation_feedback: list[str]  # User feedback for regeneration
    
    # Cost estimation (stage 4)
    cost_tiers: list[CostTier] | None  # 3-tier options
    selected_tier: str | None  # User's selected tier id
    
    # Control flags
    user_confirmed_continue: bool
    awaiting_user_input: bool


def create_initial_state() -> ProjectState:
    """Create a fresh project state."""
    return ProjectState(
        messages=[],
        current_stage="project_basics",
        image_sub_state="analyzing",
        project_title=None,
        project_type=None,
        zip_code=None,
        images=[],
        extracted_data={},
        confirmation_status={
            "materials": False,
            "measurements": False,
            "colors": False,
            "fixtures": False,
            "appliances": False,
            "style": False,
            "other": False,
            "all_confirmed": False
        },
        current_confirmation_section=None,
        generate_image=False,  # Disabled by default
        generated_image_url=None,
        image_generation_feedback=[],
        cost_tiers=None,
        selected_tier=None,
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


def get_unconfirmed_sections(state: ProjectState) -> list[str]:
    """Return list of sections that haven't been confirmed yet."""
    status = state.get("confirmation_status", {})
    extracted = state.get("extracted_data", {})
    
    unconfirmed = []
    
    # Only include sections that have extracted data
    if extracted.get("materials") and not status.get("materials"):
        unconfirmed.append("materials")
    if extracted.get("measurements") and not status.get("measurements"):
        unconfirmed.append("measurements")
    if extracted.get("colors") and not status.get("colors"):
        unconfirmed.append("colors")
    if extracted.get("fixtures") and not status.get("fixtures"):
        unconfirmed.append("fixtures")
    if extracted.get("appliances") and not status.get("appliances"):
        unconfirmed.append("appliances")
    if extracted.get("style") and not status.get("style"):
        unconfirmed.append("style")
    if extracted.get("other") and not status.get("other"):
        unconfirmed.append("other")
    
    return unconfirmed


def is_all_confirmed(state: ProjectState) -> bool:
    """Check if all extracted sections are confirmed."""
    return len(get_unconfirmed_sections(state)) == 0


def get_next_stage(current: Stage) -> Stage:
    """Get the next stage in sequence."""
    sequence: list[Stage] = [
        "project_basics",
        "image_analysis_generation",
        "final_review",
        "cost_estimation",
        "completed"
    ]
    try:
        idx = sequence.index(current)
        return sequence[idx + 1] if idx + 1 < len(sequence) else "completed"
    except ValueError:
        return "project_basics"