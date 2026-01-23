import asyncio
import json

from src.core.logger import get_logger
from src.core.llm.provider import LLMProvider

logger = get_logger(__name__)

from src.core.langgraph.state import ImageAnalysis
from src.core.langgraph.utils import parse_json
from src.core.langgraph.config import (
    build_extraction_prompt_section,
    build_extraction_json_schema,
)
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import (
    load_image_as_base64,
)
from src.core.services.event_broadcaster import (
    emit_analysis_progress,
    emit_analysis_complete,
)

from src.core.langgraph.nodes.image_analysis_generation.comprehensive_analysis import (
    comprehensive_image_analysis,
    _convert_to_legacy_extracted_data,
)

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
    project_id: str | None = None,
    project_title: str | None = None
) -> ImageAnalysis:
    """
    Analyze a single image and return structured analysis.

    REFACTORED: Uses comprehensive_image_analysis for a SINGLE VLM call.
    Extracts ALL data in one call:
    - Room type, materials, fixtures, entities
    - Image scope, visible elements, must_not_add (for VGM)
    - Features to retain, structural elements
    - Contractor context, UI summary, confidence notes

    Args:
        image_url: URL of the image to analyze
        project_type: Type of renovation project
        image_index: Index of this image (0-based)
        total_images: Total number of images being analyzed
        project_id: Optional project ID for event broadcasting
        project_title: Optional project title for context

    Returns:
        ImageAnalysis with analysis dict and comprehensive unified_data
    """
    logger.info(f"[image_analysis] Starting COMPREHENSIVE analysis for image {image_index + 1}: {image_url}")

    # Emit progress event - loading image
    if project_id:
        await emit_analysis_progress(
            project_id=project_id,
            image_index=image_index,
            total_images=total_images,
            step="loading_image",
            details={"url": image_url}
        )

    # Emit progress event - extracting data
    if project_id:
        await emit_analysis_progress(
            project_id=project_id,
            image_index=image_index,
            total_images=total_images,
            step="extracting_data",
            details={"categories": "comprehensive_single_vlm_analysis"}
        )

    # Single comprehensive VLM call - extracts EVERYTHING
    comprehensive_result = {}
    legacy_analysis = {}

    try:
        comprehensive_result = await comprehensive_image_analysis(
            image_url=image_url,
            project_title=project_title,
            project_type=project_type
        )

        # Convert to legacy format for backward compatibility
        legacy_analysis = _convert_to_legacy_extracted_data(comprehensive_result)

        logger.info(f"[image_analysis] Comprehensive analysis successful for image {image_index + 1}")

    except Exception as e:
        logger.error(f"[image_analysis] Comprehensive analysis failed for image {image_index + 1}: {e}", exc_info=True)
        comprehensive_result = {}
        legacy_analysis = {}

    # Log what was found
    categories_found = [k for k in legacy_analysis.keys() if legacy_analysis.get(k)]
    logger.info(f"[image_analysis] Completed analysis for image {image_index + 1}: found {categories_found}")

    # Log VGM-critical data
    if comprehensive_result:
        image_scope = comprehensive_result.get("image_scope", {})
        logger.info(f"[image_analysis] Image scope: {image_scope.get('frame_type')} "
                    f"(~{image_scope.get('room_coverage_pct', 0)}% coverage)")
        logger.info(f"[image_analysis] Must NOT add: {comprehensive_result.get('must_not_add', [])}")
        logger.info(f"[image_analysis] Features to retain: {len(comprehensive_result.get('features_to_retain', []))} items")
        logger.info(f"[image_analysis] Entities: {len(comprehensive_result.get('entities', []))} found")

    # Emit completion event
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
        analysis=legacy_analysis,
        unified_data=comprehensive_result  # Full comprehensive data for all downstream use
    )


async def analyze_images_parallel(
    image_urls: list[str],
    project_type: str,
    project_id: str | None = None,
    project_title: str | None = None
) -> list[ImageAnalysis]:
    """
    Analyze multiple images in parallel.

    REFACTORED: Each image analyzed with single comprehensive VLM call.

    Args:
        image_urls: List of image URLs to analyze
        project_type: Type of renovation project
        project_id: Optional project ID for event broadcasting
        project_title: Optional project title for context

    Returns:
        List of ImageAnalysis objects sorted by index
    """
    total_images = len(image_urls)
    logger.info(f"[image_analysis] Starting parallel analysis of {total_images} images")

    tasks = [
        analyze_single_image(
            image_url=url,
            project_type=project_type,
            image_index=idx,
            total_images=total_images,
            project_id=project_id,
            project_title=project_title
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
        lines.append("### Materials\n")
        for m in materials:
            line = f"- **{m.get('name', 'Unknown')}**: {m.get('type', 'N/A')}"
            if m.get('finish'):
                line += f", {m['finish']} finish"
            if m.get('condition'):
                line += f" ({m['condition']})"
            lines.append(line)
        lines.append("")

    # Note: Measurements removed - user provides manually via canvas UI
    # measurements = extracted_data.get("measurements", {})

    # Colors
    colors = extracted_data.get("colors", [])
    if colors:
        lines.append("### Colors\n")
        for c in colors:
            line = f"- **{c.get('element', 'Unknown')}**: {c.get('color', 'N/A')}"
            if c.get('finish'):
                line += f" ({c['finish']})"
            lines.append(line)
        lines.append("")

    # Fixtures
    fixtures = extracted_data.get("fixtures", [])
    if fixtures:
        lines.append("### Fixtures\n")
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
        lines.append("### Appliances\n")
        for a in appliances:
            line = f"- **{a.get('name', 'Unknown')}**: {a.get('type', 'N/A')}"
            if a.get('brand'):
                line += f" ({a['brand']})"
            lines.append(line)
        lines.append("")

    # Style
    style = extracted_data.get("style", {})
    if style:
        lines.append("### Style Assessment\n")
        if style.get("overall_style"):
            lines.append(f"- **Overall Style**: {style['overall_style']}")
        if style.get("condition"):
            lines.append(f"- **Current Condition**: {style['condition']}")
        lines.append("")

    return "\n".join(lines)


async def apply_user_correction(
    current_data: dict,
    user_message: str,
    project_type: str
) -> dict:
    """
    Use AI to apply user's correction to extracted data.

    Args:
        current_data: Current extracted data dict
        user_message: User's correction message
        project_type: Type of renovation project

    Returns:
        Updated extracted data dict
    """
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
        max_tokens=5000,
        operation_type="user_correction"
    )

    try:
        return parse_json(response)
    except Exception as e:
        logger.info(f"[image_analysis] Failed to parse correction: {e}")
        return current_data


async def analyze_vision_input(
    user_vision: str,
    project_type: str,
    current_details: str
) -> dict:
    """
    Analyze user's vision input and determine if clarification needed.

    Args:
        user_vision: User's description of their renovation vision
        project_type: Type of renovation project
        current_details: Current extracted details as string

    Returns:
        Dict with is_clear, summary, followup_questions, parsed_vision
    """
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
        max_tokens=2000,
        operation_type="vision_analysis"
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

