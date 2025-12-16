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