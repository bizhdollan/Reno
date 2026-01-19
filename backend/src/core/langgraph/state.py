"""
LangGraph State Schema for Renovation Estimation.

4-Stage Architecture:
1. project_basics - Collect title, type, zip_code
2. image_analysis_generation - Analyze images, confirm info, collect vision, generate preview
3. final_review - Review all confirmed data before estimation
4. cost_estimation - Generate 3-tier cost estimate

NEW REFACTORED ARCHITECTURE (db-first):
- Heavy data stored in database (ImageAnalysis, GenerationHistory, etc.)
- State contains only IDs and lightweight context
- Services handle business logic
"""

from typing import TypedDict, Literal, Annotated, Any, Optional
from uuid import UUID
from langgraph.graph.message import add_messages

from src.core.logger import get_logger

logger = get_logger(__name__)


# Stage types
Stage = Literal[
    "project_basics",
    "image_analysis_generation",
    "final_review",
    "cost_estimation",
    "completed"
]

# Sub-states for image_analysis_generation stage (LEGACY - will be replaced)
ImageSubState = Literal[
    "analyzing",              # Processing uploaded images - extract all data
    "confirming_extraction",  # User reviews/corrects ALL extracted data at once
    "collecting_vision",      # OPTIONAL: collect user's renovation vision/ideas
    "design_conversation",    # Flexible conversation: confirm, correct, vision, suggestions, questions
    "selecting_suggestions",  # User selecting from AI-generated options
    "generating",             # Generate proposal/preview image
    "generating_parallel",    # Generate multiple options in parallel
    "confirming_proposal"     # User reviews generated image
]

# NEW: Simplified conversation phases for refactored architecture
ConversationPhase = Literal[
    "analyzing",    # Processing uploaded images, saving to DB
    "ideating",     # Collecting vision, budget context, clarifications
    "generating",   # Generating/regenerating images (additive/restart loop)
    "reviewing"     # Before/after review, satisfaction check
]

# NEW: Pending decision types for user interaction points
PendingDecision = Literal[
    "budget_tier",           # Waiting for user to select budget tier
    "regeneration_mode",     # Waiting for clarification on additive vs restart
    "conflict_resolution",   # Waiting for user to resolve multi-image conflict
    "undo_confirmation",     # Waiting for undo confirmation
    None
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
    search_context: dict  # For smart Tavily search (detected_era, style_assessment, problem_areas, etc.)
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

    REFACTORED ARCHITECTURE:
    - Heavy data now stored in database tables
    - State contains only IDs and lightweight context
    - Target: 6 core fields (~200 bytes) vs 40+ fields (~2KB)
    """
    # =========================================================================
    # CORE FIELDS (NEW - Lightweight, DB-backed)
    # =========================================================================

    # Conversation history (required by LangGraph)
    messages: Annotated[list[dict], add_messages]

    # Project identifier - links to database records
    project_id: str | None  # Token for frontend (PRJ-XXXXXX)
    internal_project_id: str | None  # UUID as string for DB operations

    # Active image being discussed (ImageAnalysis.id in DB)
    active_image_id: str | None

    # Latest generated image (GenerationHistory.id in DB)
    active_generation_id: str | None

    # Simplified conversation phase (replaces image_sub_state)
    conversation_phase: ConversationPhase

    # Pending user decision (for interaction points)
    pending_user_decision: PendingDecision

    # Session-only context cache (not persisted, cleared each session)
    # This holds temporary data like detected conflicts, etc.
    context_cache: dict

    # =========================================================================
    # LEGACY FIELDS (Maintained for backward compatibility during transition)
    # These will be deprecated once node refactor is complete
    # =========================================================================

    # Stage tracking
    current_stage: Stage
    image_sub_state: ImageSubState

    # Project basics (stage 1)
    project_title: str | None
    project_type: str | None
    zip_code: str | None

    # Image analysis (stage 2) - DEPRECATED: Now in image_analysis table
    # Per-image analysis - preserved during extraction/correction phase
    image_analyses: list[ImageAnalysis]

    # Merged confirmed data - DEPRECATED: Now in image_analysis.extracted_features
    extracted_data: ExtractedData

    # User's renovation vision - DEPRECATED: Now in projects.renovation_vision
    renovation_vision: RenovationVision | None

    # Generated preview image - DEPRECATED: Now in generation_history
    generated_image_url: str | None
    image_generation_feedback: list[str]

    # Image generation state - DEPRECATED: Now in generation_history
    generation_prompt: str | None
    generation_description: str | None
    original_image_urls: list[str] | None
    last_generated_image_url: str | None  # For iterative refinement

    # Image history tracking - DEPRECATED: Now in generation_history table
    generated_image_history: list[dict] | None
    selected_final_image_url: str | None

    # Currently selected canvas image (from frontend for edit context)
    selected_image_url: str | None

    # Original image features - DEPRECATED: Now in image_analysis.critical_elements
    original_features_to_retain: list[str] | None
    brief_room_summary: str | None

    # Expert suggestions flow
    expertise_level: str | None
    pending_suggestions: list[dict] | None
    all_suggestions: list[dict] | None  # Permanent store for option switching
    selected_options_for_generation: list[dict] | None
    generated_options: list[dict] | None
    pending_feedback: str | None

    # Cost estimation (stage 4)
    cost_tiers: list[CostTier] | None
    selected_tier: str | None

    # Control flags
    user_confirmed_continue: bool
    awaiting_user_input: bool

    # Internal tracking (prefixed with _)
    _pending_images: list[str]  # Images waiting to be processed
    _pending_regeneration: str | None  # Feedback for regeneration from final_review
    _show_final_review_summary: bool | None  # Flag to show summary when entering final_review


def create_initial_state(project_id: str | None = None) -> ProjectState:
    """
    Create a fresh project state.

    Args:
        project_id: Optional project UUID to link state to database records

    Returns:
        New ProjectState with initialized fields
    """
    return ProjectState(
        # Core fields (new lightweight architecture)
        messages=[],
        project_id=project_id,  # Token (PRJ-XXXXXX) - set by chat endpoint
        internal_project_id=None,  # UUID - set by chat endpoint
        active_image_id=None,
        active_generation_id=None,
        conversation_phase="analyzing",
        pending_user_decision=None,
        context_cache={},

        # Legacy fields (backward compatibility)
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
        # Image generation state
        generation_prompt=None,
        generation_description=None,
        original_image_urls=None,
        last_generated_image_url=None,
        # Image history and features
        generated_image_history=[],
        selected_final_image_url=None,
        selected_image_url=None,
        original_features_to_retain=None,
        brief_room_summary=None,
        # Expert suggestions flow
        expertise_level=None,
        pending_suggestions=None,
        all_suggestions=None,
        selected_options_for_generation=None,
        generated_options=None,
        pending_feedback=None,
        # Cost estimation
        cost_tiers=None,
        selected_tier=None,
        user_confirmed_continue=False,
        awaiting_user_input=True,
        _pending_images=[]
    )


def create_minimal_state(project_id: str) -> ProjectState:
    """
    Create a minimal state for the refactored architecture.

    This creates only the 6 core fields needed for the new DB-backed approach.
    Use this when implementing the refactored nodes.

    Args:
        project_id: Project UUID (required for DB lookups)

    Returns:
        Minimal ProjectState (~200 bytes)
    """
    return ProjectState(
        messages=[],
        project_id=project_id,
        active_image_id=None,
        active_generation_id=None,
        conversation_phase="analyzing",
        pending_user_decision=None,
        context_cache={},
    )


def get_missing_basics(state: ProjectState) -> list[str]:
    """
    Return list of missing project basic fields.

    Args:
        state: Current project state

    Returns:
        List of missing field names. Returns empty list on error.
    """
    try:
        if not state or not isinstance(state, dict):
            logger.warning(f"[get_missing_basics] Invalid state: {type(state)}")
            return ["project_title", "project_type", "zip_code"]  # Assume all missing

        missing = []
        if not state.get("project_title"):
            missing.append("project_title")
        if not state.get("project_type"):
            missing.append("project_type")
        if not state.get("zip_code"):
            missing.append("zip_code")

        return missing

    except Exception as e:
        logger.exception(f"[get_missing_basics] Unexpected error: {e}")
        return []


def merge_image_analyses_to_extracted(image_analyses: list[ImageAnalysis]) -> ExtractedData:
    """
    Merge per-image analyses into a single ExtractedData dict.

    Strategy:
    - Lists (materials, colors, fixtures, appliances): combine and deduplicate by name
    - Dicts (measurements, style, search_context): use first available or merge intelligently

    Args:
        image_analyses: List of per-image analysis results

    Returns:
        Merged ExtractedData dict. Returns empty structure on error.
    """
    # Initialize empty merged structure
    merged: ExtractedData = {
        "materials": [],
        "measurements": {},
        "colors": [],
        "fixtures": [],
        "appliances": [],
        "style": {},
        "search_context": {}
    }

    try:
        if not image_analyses:
            logger.debug("[merge_image_analyses_to_extracted] Empty image_analyses")
            return merged

        if not isinstance(image_analyses, list):
            logger.error(f"[merge_image_analyses_to_extracted] image_analyses is not a list: {type(image_analyses)}")
            return merged

        seen_materials = set()
        seen_colors = set()
        seen_fixtures = set()
        seen_appliances = set()

        for img_idx, img_data in enumerate(image_analyses):
            try:
                if not isinstance(img_data, dict):
                    logger.warning(f"[merge_image_analyses_to_extracted] Image {img_idx} is not a dict: {type(img_data)}")
                    continue

                analysis = img_data.get("analysis", {})
                if not isinstance(analysis, dict):
                    logger.warning(f"[merge_image_analyses_to_extracted] Image {img_idx} analysis is not a dict: {type(analysis)}")
                    continue

                # Merge materials (dedupe by name)
                try:
                    for item in analysis.get("materials", []):
                        if not isinstance(item, dict):
                            continue
                        key = str(item.get("name", "")).lower()
                        if key and key not in seen_materials:
                            seen_materials.add(key)
                            merged["materials"].append(item)
                except Exception as e:
                    logger.warning(f"[merge_image_analyses_to_extracted] Error merging materials: {e}")

                # Merge colors (dedupe by element)
                try:
                    for item in analysis.get("colors", []):
                        if not isinstance(item, dict):
                            continue
                        key = str(item.get("element", "")).lower()
                        if key and key not in seen_colors:
                            seen_colors.add(key)
                            merged["colors"].append(item)
                except Exception as e:
                    logger.warning(f"[merge_image_analyses_to_extracted] Error merging colors: {e}")

                # Merge fixtures (dedupe by name)
                try:
                    for item in analysis.get("fixtures", []):
                        if not isinstance(item, dict):
                            continue
                        key = str(item.get("name", "")).lower()
                        if key and key not in seen_fixtures:
                            seen_fixtures.add(key)
                            merged["fixtures"].append(item)
                except Exception as e:
                    logger.warning(f"[merge_image_analyses_to_extracted] Error merging fixtures: {e}")

                # Merge appliances (dedupe by name)
                try:
                    for item in analysis.get("appliances", []):
                        if not isinstance(item, dict):
                            continue
                        key = str(item.get("name", "")).lower()
                        if key and key not in seen_appliances:
                            seen_appliances.add(key)
                            merged["appliances"].append(item)
                except Exception as e:
                    logger.warning(f"[merge_image_analyses_to_extracted] Error merging appliances: {e}")

                # Measurements: use first available with actual values
                try:
                    if not merged["measurements"] and analysis.get("measurements"):
                        if isinstance(analysis["measurements"], dict):
                            merged["measurements"] = analysis["measurements"]
                except Exception as e:
                    logger.warning(f"[merge_image_analyses_to_extracted] Error merging measurements: {e}")

                # Style: use first available
                try:
                    if not merged["style"] and analysis.get("style"):
                        if isinstance(analysis["style"], dict):
                            merged["style"] = analysis["style"]
                except Exception as e:
                    logger.warning(f"[merge_image_analyses_to_extracted] Error merging style: {e}")

                # Search context: use first available (for smart Tavily search)
                try:
                    if not merged["search_context"] and analysis.get("search_context"):
                        if isinstance(analysis["search_context"], dict):
                            merged["search_context"] = analysis["search_context"]
                except Exception as e:
                    logger.warning(f"[merge_image_analyses_to_extracted] Error merging search_context: {e}")

            except Exception as e:
                logger.warning(f"[merge_image_analyses_to_extracted] Error processing image {img_idx}: {e}")
                continue

        logger.debug(f"[merge_image_analyses_to_extracted] Merged {len(merged['materials'])} materials, "
                    f"{len(merged['colors'])} colors, {len(merged['fixtures'])} fixtures, "
                    f"{len(merged['appliances'])} appliances")
        return merged

    except Exception as e:
        logger.exception(f"[merge_image_analyses_to_extracted] Unexpected error: {e}")
        return merged


def get_next_stage(current: Stage) -> Stage:
    """
    Get the next stage in sequence.

    Args:
        current: Current stage

    Returns:
        Next stage in sequence. Returns "project_basics" if current is invalid.
    """
    try:
        sequence: list[Stage] = [
            "project_basics",
            "image_analysis_generation",
            "final_review",
            "cost_estimation",
            "completed"
        ]

        if not current:
            logger.warning("[get_next_stage] Current stage is empty")
            return "project_basics"

        try:
            idx = sequence.index(current)
            next_stage = sequence[idx + 1] if idx + 1 < len(sequence) else "completed"
            logger.debug(f"[get_next_stage] {current} -> {next_stage}")
            return next_stage
        except ValueError:
            logger.warning(f"[get_next_stage] Invalid current stage: {current}, defaulting to project_basics")
            return "project_basics"

    except Exception as e:
        logger.exception(f"[get_next_stage] Unexpected error: {e}")
        return "project_basics"


# =============================================================================
# THINKING STATUS MAPPING
# Maps stages and sub-states to user-friendly status messages for frontend
# =============================================================================

THINKING_STATUS_MAP = {
    # Stage-level statuses
    "project_basics": "Getting your project details...",
    "final_review": "Preparing your summary...",
    "cost_estimation": "Calculating your estimate...",
    "completed": "All done!",

    # Sub-state level statuses (for image_analysis_generation stage)
    "analyzing": "Analyzing your room...",
    "confirming_extraction": "Reviewing extracted details...",
    "collecting_vision": "Understanding your vision...",
    "design_conversation": "Understanding your vision...",
    "selecting_suggestions": "Preparing design options...",
    "generating": "Creating your renovation preview...",
    "generating_parallel": "Creating multiple previews...",
    "confirming_proposal": "Reviewing your design...",
}


def get_thinking_status(state: ProjectState) -> str:
    """
    Get user-friendly thinking status based on current stage and sub-state.

    Args:
        state: Current project state

    Returns:
        Friendly status text for the thinking animation.
        Returns "Processing..." on error.
    """
    try:
        if not state or not isinstance(state, dict):
            logger.warning(f"[get_thinking_status] Invalid state: {type(state)}")
            return "Processing..."

        current_stage = state.get("current_stage", "project_basics")

        # For image_analysis_generation, use sub-state for more granular status
        if current_stage == "image_analysis_generation":
            sub_state = state.get("image_sub_state", "analyzing")
            status = THINKING_STATUS_MAP.get(sub_state, "Processing...")
            logger.debug(f"[get_thinking_status] Stage: {current_stage}, Sub-state: {sub_state} -> {status}")
            return status

        status = THINKING_STATUS_MAP.get(current_stage, "Processing...")
        logger.debug(f"[get_thinking_status] Stage: {current_stage} -> {status}")
        return status

    except Exception as e:
        logger.exception(f"[get_thinking_status] Unexpected error: {e}")
        return "Processing..."


def get_stage_progress(state: ProjectState) -> dict:
    """
    Get stage progress information for frontend progress bar.

    Args:
        state: Current project state

    Returns:
        dict with stage_number (1-4), stage_name, total_stages, and sub_state info
        Returns default values on error.
    """
    try:
        stage_map = {
            "project_basics": {"number": 1, "name": "Project Basics"},
            "image_analysis_generation": {"number": 2, "name": "Analysis & Generation"},
            "final_review": {"number": 3, "name": "Review"},
            "cost_estimation": {"number": 4, "name": "Estimation"},
            "completed": {"number": 4, "name": "Completed"},
        }

        if not state or not isinstance(state, dict):
            logger.warning(f"[get_stage_progress] Invalid state: {type(state)}")
            return {
                "stage_number": 1,
                "stage_name": "Project Basics",
                "total_stages": 4,
            }

        current_stage = state.get("current_stage", "project_basics")
        info = stage_map.get(current_stage, {"number": 1, "name": "Project Basics"})

        result = {
            "stage_number": info["number"],
            "stage_name": info["name"],
            "total_stages": 4,
        }

        # Add sub-state info for image_analysis_generation
        if current_stage == "image_analysis_generation":
            try:
                sub_state = state.get("image_sub_state", "analyzing")
                result["sub_state"] = sub_state
                result["is_generating"] = sub_state in ["generating", "generating_parallel"]
            except Exception as e:
                logger.warning(f"[get_stage_progress] Error adding sub-state info: {e}")

        logger.debug(f"[get_stage_progress] Stage {result['stage_number']}: {result['stage_name']}")
        return result

    except Exception as e:
        logger.exception(f"[get_stage_progress] Unexpected error: {e}")
        return {
            "stage_number": 1,
            "stage_name": "Project Basics",
            "total_stages": 4,
        }