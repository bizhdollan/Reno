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


async def analyze_single_image(image_url: str, project_type: str, image_index: int) -> ImageAnalysis:
    """Analyze a single image and return structured analysis."""
    print(f"[image_analysis] Starting analysis for image {image_index + 1}: {image_url}")

    provider = LLMProvider.for_vlm()
    image_data_url = await load_image_as_base64(image_url)
    prompt = build_image_analysis_prompt(project_type)

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a renovation expert. Analyze images thoroughly. Return JSON only, no markdown."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ],
        temperature=0.2,
        max_tokens=2000
    )

    try:
        analysis = parse_json(response)
    except Exception as e:
        print(f"[image_analysis] Failed to parse response for image {image_index + 1}: {e}")
        analysis = {}

    categories_found = [k for k in analysis.keys() if analysis.get(k)]
    print(f"[image_analysis] Completed image {image_index + 1}: found {categories_found}")

    return ImageAnalysis(
        url=image_url,
        index=image_index,
        analysis=analysis
    )


async def analyze_images_parallel(image_urls: list[str], project_type: str) -> list[ImageAnalysis]:
    """Analyze multiple images in parallel."""
    tasks = [
        analyze_single_image(url, project_type, idx)
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
    Analyze image to identify architectural features that must be preserved.

    Returns:
        dict with keys: must_retain_features (list), reasoning
    """
    provider = LLMProvider.for_vlm()
    image_data_url = await load_image_as_base64(image_url)

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are an architect identifying structural/important features in rooms. Return JSON only."
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
        max_tokens=400
    )

    try:
        return parse_json(response)
    except:
        return {
            "must_retain_features": [],
            "reasoning": "Unable to detect features"
        }
