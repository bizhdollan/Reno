"""
LangGraph State Schema for Renovation Estimation.

4-Stage Architecture:
1. project_basics - Collect title, type, zip_code
2. image_analysis_generation - Analyze images, confirm info, collect vision, generate preview
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
    "analyzing",              # Processing uploaded images - extract all data
    "confirming_extraction",  # User reviews/corrects ALL extracted data at once
    "collecting_vision",      # OPTIONAL: collect user's renovation vision/ideas
    "generating",             # Generate proposal/preview image
    "confirming_proposal"     # User reviews generated image
]


class ImageAnalysis(TypedDict, total=False):
    """Analysis data for a single uploaded image."""
    url: str
    index: int
    analysis: dict  # Contains all extracted categories


class ExtractedData(TypedDict, total=False):
    """Merged extraction data from all images (after user confirms)."""
    materials: list[dict]
    measurements: dict
    colors: list[dict]
    fixtures: list[dict]
    appliances: list[dict]
    style: dict
    # Extensible - add more categories as needed


class RenovationVision(TypedDict, total=False):
    """User's renovation vision/preferences (optional)."""
    raw_input: str  # User's original description
    style_preferences: str
    material_preferences: str
    specific_changes: str
    additional_notes: str
    ai_summary: str  # AI's interpreted summary


class CategoryBreakdown(TypedDict, total=False):
    """Cost breakdown for a single category."""
    category: str
    description: str
    materials_cost: float
    labor_cost: float
    total: float


class CostTier(TypedDict, total=False):
    """Single tier in 3-tier cost structure."""
    id: str
    name: str
    badge: str
    description: str
    total_cost: float
    cogs: float
    markup_percentage: float
    markup_amount: float
    included_items: list[str]
    detailed_breakdown: list[CategoryBreakdown]


class ProjectState(TypedDict, total=False):
    """
    Main state for the renovation estimation graph.
    """
    # Conversation history
    messages: Annotated[list[dict], add_messages]
    
    # Stage tracking
    current_stage: Stage
    image_sub_state: ImageSubState
    
    # Project basics (stage 1)
    project_title: str | None
    project_type: str | None
    zip_code: str | None
    
    # Image analysis (stage 2)
    # Per-image analysis - preserved during extraction/correction phase
    image_analyses: list[ImageAnalysis]
    
    # Merged confirmed data - populated after user confirms extraction
    extracted_data: ExtractedData
    
    # User's renovation vision (optional)
    renovation_vision: RenovationVision | None
    
    # Generated preview image
    generated_image_url: str | None
    image_generation_feedback: list[str]
    
    # Cost estimation (stage 4)
    cost_tiers: list[CostTier] | None
    selected_tier: str | None
    
    # Control flags
    user_confirmed_continue: bool
    awaiting_user_input: bool
    
    # Internal tracking (prefixed with _)
    _pending_images: list[str]  # Images waiting to be processed


def create_initial_state() -> ProjectState:
    """Create a fresh project state."""
    return ProjectState(
        messages=[],
        current_stage="project_basics",
        image_sub_state="analyzing",
        project_title=None,
        project_type=None,
        zip_code=None,
        image_analyses=[],
        extracted_data={},
        renovation_vision=None,
        generated_image_url=None,
        image_generation_feedback=[],
        cost_tiers=None,
        selected_tier=None,
        user_confirmed_continue=False,
        awaiting_user_input=True,
        _pending_images=[]
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


def merge_image_analyses_to_extracted(image_analyses: list[ImageAnalysis]) -> ExtractedData:
    """
    Merge per-image analyses into a single ExtractedData dict.
    
    Strategy:
    - Lists (materials, colors, fixtures, appliances): combine and deduplicate by name
    - Dicts (measurements, style): use first available or merge intelligently
    """
    merged: ExtractedData = {
        "materials": [],
        "measurements": {},
        "colors": [],
        "fixtures": [],
        "appliances": [],
        "style": {}
    }
    
    seen_materials = set()
    seen_colors = set()
    seen_fixtures = set()
    seen_appliances = set()
    
    for img_data in image_analyses:
        analysis = img_data.get("analysis", {})
        
        # Merge materials (dedupe by name)
        for item in analysis.get("materials", []):
            key = item.get("name", "").lower()
            if key and key not in seen_materials:
                seen_materials.add(key)
                merged["materials"].append(item)
        
        # Merge colors (dedupe by element)
        for item in analysis.get("colors", []):
            key = item.get("element", "").lower()
            if key and key not in seen_colors:
                seen_colors.add(key)
                merged["colors"].append(item)
        
        # Merge fixtures (dedupe by name)
        for item in analysis.get("fixtures", []):
            key = item.get("name", "").lower()
            if key and key not in seen_fixtures:
                seen_fixtures.add(key)
                merged["fixtures"].append(item)
        
        # Merge appliances (dedupe by name)
        for item in analysis.get("appliances", []):
            key = item.get("name", "").lower()
            if key and key not in seen_appliances:
                seen_appliances.add(key)
                merged["appliances"].append(item)
        
        # Measurements: use first available with actual values
        if not merged["measurements"] and analysis.get("measurements"):
            merged["measurements"] = analysis["measurements"]
        
        # Style: use first available
        if not merged["style"] and analysis.get("style"):
            merged["style"] = analysis["style"]
    
    return merged


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