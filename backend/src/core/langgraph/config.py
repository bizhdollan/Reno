"""
Configuration for LangGraph renovation flow.

Flexible configuration for:
- What to extract from images
- How to collect user's renovation vision
"""

# =============================================================================
# EXTRACTION CATEGORIES
# =============================================================================
# These define what the AI extracts from uploaded images.
# Add/remove/modify categories as needed - prompts adapt automatically.

EXTRACTION_CATEGORIES = [
    {
        "key": "materials",
        "label": "Materials",
        "description": "Visible materials in the space",
        "extract_fields": ["name", "type", "finish", "condition"],
        "examples": "flooring, walls, cabinets, countertops, trim, doors"
    },
    {
        "key": "measurements",
        "label": "Measurements",
        "description": "Estimated room/space dimensions",
        "extract_fields": ["room_width_ft", "room_length_ft", "room_height_ft", "area_sqft", "notes"],
        "examples": "room size, ceiling height, total area"
    },
    {
        "key": "colors",
        "label": "Colors",
        "description": "Colors present in the space",
        "extract_fields": ["element", "color", "finish"],
        "examples": "wall color, floor color, trim color"
    },
    {
        "key": "fixtures",
        "label": "Fixtures",
        "description": "Fixed installations and hardware",
        "extract_fields": ["name", "type", "style", "condition"],
        "examples": "light fixtures, faucets, handles, outlets"
    },
    {
        "key": "appliances",
        "label": "Appliances",
        "description": "Appliances visible in the space",
        "extract_fields": ["name", "type", "brand", "condition"],
        "examples": "refrigerator, stove, dishwasher, washer/dryer"
    },
    {
        "key": "style",
        "label": "Style Assessment",
        "description": "Overall style and condition assessment",
        "extract_fields": ["overall_style", "condition", "age_estimate"],
        "examples": "modern, traditional, transitional, current condition"
    },
]


def get_category_keys() -> list[str]:
    """Get list of all category keys."""
    return [cat["key"] for cat in EXTRACTION_CATEGORIES]


def get_category_by_key(key: str) -> dict | None:
    """Get category config by key."""
    for cat in EXTRACTION_CATEGORIES:
        if cat["key"] == key:
            return cat
    return None


def build_extraction_prompt_section() -> str:
    """
    Build the extraction instructions section for the image analysis prompt.
    Automatically adapts to configured categories.
    """
    lines = []
    for i, cat in enumerate(EXTRACTION_CATEGORIES, 1):
        fields_str = ", ".join(cat["extract_fields"])
        lines.append(
            f"{i}. **{cat['label']}**: {cat['description']}\n"
            f"   - Examples: {cat['examples']}\n"
            f"   - Extract: {fields_str}"
        )
    return "\n\n".join(lines)


def build_extraction_json_schema() -> str:
    """
    Build the expected JSON schema section for the prompt.
    """
    schema_parts = []
    for cat in EXTRACTION_CATEGORIES:
        key = cat["key"]
        if key == "measurements":
            # Measurements is a dict, not a list
            schema_parts.append(f'    "{key}": {{\n        "room_width_ft": 12,\n        "room_length_ft": 10,\n        "room_height_ft": 9,\n        "area_sqft": 120,\n        "notes": "estimated from image"\n    }}')
        elif key == "style":
            # Style is also a dict
            schema_parts.append(f'    "{key}": {{\n        "overall_style": "modern",\n        "condition": "good",\n        "age_estimate": "5-10 years"\n    }}')
        else:
            # Others are lists
            fields = cat["extract_fields"]
            example_obj = ", ".join([f'"{f}": "..."' for f in fields])
            schema_parts.append(f'    "{key}": [\n        {{{example_obj}}}\n    ]')
    
    return "{\n" + ",\n".join(schema_parts) + "\n}"


# =============================================================================
# VISION COLLECTION CONFIG
# =============================================================================
# Configuration for collecting user's renovation vision (optional step)

VISION_PROMPT = """Do you have a specific vision for this renovation?

For example, you could tell me about:
- **Style preferences**: Modern, traditional, minimalist, rustic, etc.
- **Material preferences**: Hardwood floors, quartz countertops, specific paint colors
- **Specific changes**: What you want to add, remove, or modify
- **Inspiration**: Any ideas or references you have in mind

Feel free to share as much or as little as you'd like. If you'd prefer, just say **'skip'** and I'll proceed with a general estimate based on what I see in your images."""

VISION_FOLLOWUP_PROMPT = """Based on what you've shared, I want to make sure I understand your vision correctly.

Current understanding:
{current_vision}

{followup_questions}

Let me know if this captures your vision, or add any other details you'd like to include. Say **'done'** when you're ready to proceed."""


# =============================================================================
# NEW: REFACTORED CONVERSATION PROMPTS
# =============================================================================
# These prompts support the new DB-backed, service-driven conversation flow.

# Brief room acknowledgment after image analysis (replaces detailed extraction display)
ROOM_ANALYZED_PROMPT = """{images_display}

**{brief_summary}**

What changes would you like to make to this space?

You can:
- Describe your vision (e.g., *"modern minimalist with white marble"*)
- Ask for suggestions (e.g., *"what would you recommend?"*)
- Ask about budget options (e.g., *"what can I do with $5000?"*)
- Ask questions (e.g., *"what style is this currently?"*)"""

# Budget context detected - suggest appropriate materials
BUDGET_AWARE_RESPONSE = """I understand you're looking for {budget_sentiment} options.

For your {room_type}, here are some suggestions that fit your budget:
{suggested_materials}

Would you like me to generate a preview with these materials, or would you prefer different options?"""

# Clarification for ambiguous regeneration request
REGENERATION_CLARIFY_PROMPT = """I understood you want: *"{user_feedback}"*

Would you like me to:
- **Add to the current design** - Keep what we have and add your changes
- **Start fresh** - Create a completely different design from the original image

Just let me know which approach you prefer!"""

# Additive regeneration acknowledgment
ADDITIVE_GENERATION_PROMPT = """Building on the current design to add your changes...

I'll preserve what you liked and incorporate: {changes}"""

# Restart regeneration acknowledgment
RESTART_GENERATION_PROMPT = """Starting fresh from your original image...

Creating a new design with: {vision}"""

# Before/after review prompt
BEFORE_AFTER_REVIEW_PROMPT = """Here's your renovation transformation:

**Before:**
{before_image}

**After:**
{after_image}

{description}

Are you happy with this design? You can:
- Say **'continue'** to proceed to cost estimation
- Request changes (e.g., *"make the floor darker"*)
- Say **'go back'** to try a different approach"""

# Multi-image same-room validation error
MULTI_IMAGE_ROOM_MISMATCH = """I noticed these images might be from different rooms:
- Image 1: {room_1}
- Image 2: {room_2}

For the best renovation preview, please upload images of a **single room** from different angles.

Would you like to continue with just one image, or upload new images?"""

# Undo confirmation
UNDO_CONFIRMATION_PROMPT = """I've undone the last change: {change_description}

Your data has been reverted to the previous state. What would you like to do next?"""

# Generation with critical elements preserved
GENERATION_WITH_PRESERVATION = """Generating your renovation preview...

I'll preserve the structural elements I detected: {critical_elements}

This ensures the generated image maintains realistic proportions and layout."""

# Insufficient vision - need more details
INSUFFICIENT_VISION_PROMPT = """I'd love to help bring your vision to life! To generate the best preview, could you tell me a bit more about:

{missing_aspects}

Or if you'd like, I can suggest some popular options for your {room_type}."""

# Expert suggestions intro
EXPERT_SUGGESTIONS_INTRO = """Based on your {room_type} and current trends in your area, here are my recommendations:

{suggestions}

Which option catches your eye? You can say "Option 1", combine elements from different options, or describe your own vision."""