"""
Image analysis functions for extracting data from images.
"""

import asyncio
import json

from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import ImageAnalysis
from src.core.langgraph.utils import parse_json
from src.core.langgraph.config import (
    build_extraction_prompt_section,
    build_extraction_json_schema,
    VISION_PROMPT,
)
from src.core.langgraph.prompts import (
    BRIEF_ROOM_SUMMARY_PROMPT,
    FEATURES_TO_RETAIN_PROMPT,
)
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import (
    load_image_as_base64,
)
from src.core.services.event_broadcaster import (
    emit_analysis_progress,
    emit_analysis_complete,
)


def build_image_analysis_prompt(project_type: str) -> str:
    """Build the full image analysis prompt with configured categories."""
    categories_section = build_extraction_prompt_section()
    json_schema = build_extraction_json_schema()

    return f"""You are a renovation expert analyzing an image for a {project_type} renovation project.

Analyze this image comprehensively and extract ALL renovation-relevant information.

## What to Extract

{categories_section}

## Instructions

- Only include categories where you can actually identify relevant items
- Be specific and accurate in your descriptions
- For measurements, provide estimates based on visual cues (doorways, standard fixture sizes, etc.)
- Note the condition of items where visible (excellent, good, fair, poor)

## Response Format

Return JSON only with this structure:
{json_schema}

Only include categories where you found relevant items. Return valid JSON, no markdown."""


CORRECTION_PROMPT = """You are helping update renovation extraction data based on user feedback.

## Current Extracted Data
{current_data}

## User's Correction/Addition
"{user_message}"

## Your Task

Apply the user's correction or addition to the data. The user might:
- Add new items (e.g., "there's also a mirror on the wall")
- Correct existing items (e.g., "the flooring is hardwood, not laminate")
- Remove items (e.g., "remove the rug, it's not part of the renovation")
- Change details (e.g., "the walls are beige, not white")

Return the COMPLETE updated data as JSON. Include ALL existing items (modified or not) plus any additions.
Keep the same structure as the current data. Return valid JSON only, no markdown.

{json_schema}"""


VISION_CLARIFICATION_PROMPT = """The user has shared their renovation vision:

"{user_vision}"

Project type: {project_type}
Current space details: {current_details}

Analyze if the user's vision is clear enough or needs clarification. Consider:
- Is the scope of work clear?
- Are material preferences specific enough for estimation?
- Are there any ambiguities that could affect the estimate?

Return JSON:
{{
    "is_clear": true/false,
    "summary": "Brief summary of understood vision",
    "followup_questions": ["question1", "question2"] or [] if clear,
    "parsed_vision": {{
        "style_preferences": "...",
        "material_preferences": "...",
        "specific_changes": "...",
        "additional_notes": "..."
    }}
}}"""


async def analyze_single_image(
    image_url: str,
    project_type: str,
    image_index: int,
    total_images: int = 1,
    project_id: str | None = None
) -> ImageAnalysis:
    """Analyze a single image and return structured analysis."""
    print(f"[image_analysis] Starting analysis for image {image_index + 1}: {image_url}")

    # Emit progress event
    if project_id:
        await emit_analysis_progress(
            project_id=project_id,
            image_index=image_index,
            total_images=total_images,
            step="loading_image",
            details={"url": image_url}
        )

    provider = LLMProvider.for_vlm()
    image_data_url = await load_image_as_base64(image_url)
    prompt = build_image_analysis_prompt(project_type)

    # Emit extraction start
    if project_id:
        await emit_analysis_progress(
            project_id=project_id,
            image_index=image_index,
            total_images=total_images,
            step="extracting_data",
            details={"categories": "materials, measurements, colors, fixtures, search_context"}
        )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a renovation expert. Analyze images thoroughly and identify search-relevant context (era, style, problem areas). Return JSON only, no markdown."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ],
        temperature=0.4,  # Increased from 0.2 for richer, more descriptive insights
        max_tokens=2500   # Increased to accommodate new categories
    )

    try:
        analysis = parse_json(response)
    except Exception as e:
        print(f"[image_analysis] Failed to parse response for image {image_index + 1}: {e}")
        analysis = {}

    categories_found = [k for k in analysis.keys() if analysis.get(k)]
    print(f"[image_analysis] Completed image {image_index + 1}: found {categories_found}")

    # Emit completion for this image
    if project_id:
        await emit_analysis_progress(
            project_id=project_id,
            image_index=image_index,
            total_images=total_images,
            step="completed",
            details={"categories_found": categories_found}
        )

    return ImageAnalysis(
        url=image_url,
        index=image_index,
        analysis=analysis
    )


async def analyze_images_parallel(
    image_urls: list[str],
    project_type: str,
    project_id: str | None = None
) -> list[ImageAnalysis]:
    """Analyze multiple images in parallel."""
    total_images = len(image_urls)
    tasks = [
        analyze_single_image(
            image_url=url,
            project_type=project_type,
            image_index=idx,
            total_images=total_images,
            project_id=project_id
        )
        for idx, url in enumerate(image_urls)
    ]
    results = await asyncio.gather(*tasks)
    return sorted(results, key=lambda x: x["index"])


def format_extracted_data_for_display(extracted_data: dict, image_analyses: list[ImageAnalysis]) -> str:
    """Format all extracted data for user review."""
    lines = []

    # Show which images were analyzed
    if image_analyses:
        lines.append(f"**Analyzed {len(image_analyses)} image(s)**\n")
        for img in image_analyses:
            lines.append(f'<img src="{img["url"]}" width="300" height="200" style="object-fit: cover; border-radius: 8px; display: inline-block; margin-right: 8px; cursor: pointer;" />')
        lines.append("\n")

    lines.append("---\n")

    # Materials
    materials = extracted_data.get("materials", [])
    if materials:
        lines.append("### 🧱 Materials\n")
        for m in materials:
            line = f"- **{m.get('name', 'Unknown')}**: {m.get('type', 'N/A')}"
            if m.get('finish'):
                line += f", {m['finish']} finish"
            if m.get('condition'):
                line += f" ({m['condition']})"
            lines.append(line)
        lines.append("")

    # Measurements
    measurements = extracted_data.get("measurements", {})
    if measurements:
        lines.append("### 📐 Measurements\n")
        if measurements.get("room_width_ft") and measurements.get("room_length_ft"):
            lines.append(f"- **Room Size**: {measurements.get('room_width_ft')} × {measurements.get('room_length_ft')} ft")
        if measurements.get("room_height_ft"):
            lines.append(f"- **Ceiling Height**: {measurements.get('room_height_ft')} ft")
        if measurements.get("area_sqft"):
            lines.append(f"- **Total Area**: {measurements.get('area_sqft')} sq ft")
        if measurements.get("notes"):
            lines.append(f"- *Note: {measurements.get('notes')}*")
        lines.append("")

    # Colors
    colors = extracted_data.get("colors", [])
    if colors:
        lines.append("### 🎨 Colors\n")
        for c in colors:
            line = f"- **{c.get('element', 'Unknown')}**: {c.get('color', 'N/A')}"
            if c.get('finish'):
                line += f" ({c['finish']})"
            lines.append(line)
        lines.append("")

    # Fixtures
    fixtures = extracted_data.get("fixtures", [])
    if fixtures:
        lines.append("### 💡 Fixtures\n")
        for f in fixtures:
            line = f"- **{f.get('name', 'Unknown')}**: {f.get('type', 'N/A')}"
            if f.get('style'):
                line += f", {f['style']}"
            if f.get('condition'):
                line += f" ({f['condition']})"
            lines.append(line)
        lines.append("")

    # Appliances
    appliances = extracted_data.get("appliances", [])
    if appliances:
        lines.append("### 🔌 Appliances\n")
        for a in appliances:
            line = f"- **{a.get('name', 'Unknown')}**: {a.get('type', 'N/A')}"
            if a.get('brand'):
                line += f" ({a['brand']})"
            lines.append(line)
        lines.append("")

    # Style
    style = extracted_data.get("style", {})
    if style:
        lines.append("### 🏠 Style Assessment\n")
        if style.get("overall_style"):
            lines.append(f"- **Overall Style**: {style['overall_style']}")
        if style.get("condition"):
            lines.append(f"- **Current Condition**: {style['condition']}")
        if style.get("age_estimate"):
            lines.append(f"- **Estimated Age**: {style['age_estimate']}")
        lines.append("")

    return "\n".join(lines)


async def apply_user_correction(
    current_data: dict,
    user_message: str,
    project_type: str
) -> dict:
    """Use AI to apply user's correction to extracted data."""
    provider = LLMProvider.for_llm()

    current_data_str = json.dumps(current_data, indent=2)
    json_schema = build_extraction_json_schema()

    prompt = CORRECTION_PROMPT.format(
        current_data=current_data_str,
        user_message=user_message,
        json_schema=json_schema
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are updating renovation data based on user feedback. Return valid JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=2000
    )

    try:
        return parse_json(response)
    except Exception as e:
        print(f"[image_analysis] Failed to parse correction: {e}")
        return current_data


async def analyze_vision_input(
    user_vision: str,
    project_type: str,
    current_details: str
) -> dict:
    """Analyze user's vision input and determine if clarification needed."""
    provider = LLMProvider.for_llm()

    prompt = VISION_CLARIFICATION_PROMPT.format(
        user_vision=user_vision,
        project_type=project_type,
        current_details=current_details
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "Analyze renovation vision and identify if clarification is needed. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=800
    )

    try:
        return parse_json(response)
    except:
        return {
            "is_clear": True,
            "summary": user_vision,
            "followup_questions": [],
            "parsed_vision": {"additional_notes": user_vision}
        }


async def generate_brief_room_summary(
    image_url: str,
    project_type: str,
    extracted_data: dict
) -> dict:
    """
    Generate a brief, conversational summary of the room for user interaction.

    Returns:
        dict with keys: brief_summary, room_vibe
    """
    provider = LLMProvider.for_vlm()
    image_data_url = await load_image_as_base64(image_url)

    prompt = BRIEF_ROOM_SUMMARY_PROMPT.format(
        project_type=project_type,
        extracted_data=json.dumps(extracted_data, indent=2)[:500] if extracted_data else "{}"
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You describe rooms in a conversational, friendly way. Return JSON only."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ],
        temperature=0.3,
        max_tokens=300
    )

    try:
        return parse_json(response)
    except:
        return {
            "brief_summary": f"A {project_type} space ready for renovation.",
            "room_vibe": "current"
        }


async def detect_features_to_retain(image_url: str) -> dict:
    """
    Analyze image to identify what's ACTUALLY VISIBLE and what should NOT be added.

    This is CRITICAL for preventing VGM hallucination. The function returns:
    - visible_elements: What's actually in the image (walls, floor, windows, doors, etc.)
    - image_scope: Frame type (corner_view, wall_view, full_room), coverage percentage
    - must_retain: Structural features to preserve
    - must_not_add: Explicit list of things NOT to add during generation

    Returns:
        dict with keys: visible_elements, image_scope, must_retain, must_not_add, reasoning
    """
    provider = LLMProvider.for_vlm()
    image_data_url = await load_image_as_base64(image_url)

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": """You are an image analyst for renovation projects. Your task is to identify:
1. What is ACTUALLY VISIBLE in this specific image frame
2. What is NOT visible (and therefore should NOT be added during renovation)
3. The scope/coverage of the image (corner view, partial wall, full room, etc.)

Be CONSERVATIVE - if you cannot clearly see something, assume it's NOT there.
Do NOT imagine or assume elements that might exist outside the visible frame.
Return valid JSON only, no markdown."""
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": FEATURES_TO_RETAIN_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ],
        temperature=0.2,
        max_tokens=800  # Increased for more detailed response
    )

    try:
        result = parse_json(response)

        # Ensure all expected fields are present
        if "visible_elements" not in result:
            result["visible_elements"] = {}
        if "image_scope" not in result:
            result["image_scope"] = {
                "frame_type": "full_room",
                "room_coverage_pct": 100,
                "camera_angle": "eye_level"
            }
        if "must_retain" not in result:
            # Fallback to old format if present
            result["must_retain"] = result.get("must_retain_features", [])
        if "must_not_add" not in result:
            # Generate default must_not_add based on visible_elements
            result["must_not_add"] = _generate_default_must_not_add(result.get("visible_elements", {}))

        print(f"[features_detection] Scope: {result.get('image_scope', {}).get('frame_type', 'unknown')}")
        print(f"[features_detection] Must retain: {len(result.get('must_retain', []))} items")
        print(f"[features_detection] Must NOT add: {result.get('must_not_add', [])}")

        return result
    except Exception as e:
        print(f"[features_detection] Failed to parse response: {e}")
        return {
            "visible_elements": {},
            "image_scope": {
                "frame_type": "full_room",
                "room_coverage_pct": 100,
                "camera_angle": "eye_level"
            },
            "must_retain": [],
            "must_not_add": [
                "Do not add windows that don't exist in the original",
                "Do not add furniture unless specifically requested",
                "Do not add doors that don't exist in the original"
            ],
            "reasoning": "Unable to detect features - using safe defaults"
        }


def _generate_default_must_not_add(visible_elements: dict) -> list[str]:
    """Generate must_not_add list based on what's NOT visible in visible_elements."""
    must_not_add = []

    # Check windows
    windows = visible_elements.get("windows", "")
    if not windows or "no windows" in str(windows).lower() or "none" in str(windows).lower():
        must_not_add.append("Do not add windows (none visible in original)")

    # Check doors
    doors = visible_elements.get("doors", "")
    if not doors or "no doors" in str(doors).lower() or "none" in str(doors).lower():
        must_not_add.append("Do not add doors (none visible in original)")

    # Check furniture
    furniture = visible_elements.get("furniture", "")
    if not furniture or "no furniture" in str(furniture).lower() or "none" in str(furniture).lower():
        must_not_add.append("Do not add furniture, beds, or couches (none visible in original)")

    # Check fixtures
    fixtures = visible_elements.get("fixtures", "")
    if not fixtures or "none" in str(fixtures).lower():
        must_not_add.append("Do not add light fixtures (none visible in original)")

    # Always include frame constraint
    must_not_add.append("Do not expand beyond the visible frame of the original image")

    return must_not_add
