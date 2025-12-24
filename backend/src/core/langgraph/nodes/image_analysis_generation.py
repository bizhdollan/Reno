"""
Image Analysis & Generation Node.

Handles the entire image analysis flow with revised sub-states:
1. analyzing - Process uploaded images, extract ALL data
2. confirming_extraction - User reviews/corrects all extracted data at once
3. collecting_vision - OPTIONAL: collect user's renovation vision
4. generating - Generate proposal/preview image
5. confirming_proposal - User reviews generated image
"""

import asyncio
import base64
import json
from pathlib import Path
from datetime import datetime
import uuid

import httpx

from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import (
    ProjectState,
    ImageAnalysis,
    merge_image_analyses_to_extracted,
)
from src.core.langgraph.utils import get_latest_user_message, parse_json
from src.core.langgraph.config import (
    EXTRACTION_CATEGORIES,
    build_extraction_prompt_section,
    build_extraction_json_schema,
    VISION_PROMPT,
)
from src.core.langgraph._prompts import (
    build_image_generation_prompt,
    build_image_regeneration_prompt,
    FEEDBACK_CLASSIFICATION_PROMPT,
    ENHANCED_INTENT_CLASSIFIER_PROMPT,
    EXPERTISE_DETECTOR_PROMPT,
    EXPERT_SUGGESTIONS_PROMPT,
    REGENERATION_MODE_CLASSIFIER_PROMPT,
    VAGUE_REQUEST_CLARIFIER_PROMPT,
    BRIEF_ROOM_SUMMARY_PROMPT,
    FEATURES_TO_RETAIN_PROMPT,
    CONVERSATION_TYPE_CLASSIFIER_PROMPT,
    UNIFIED_CLASSIFIER_PROMPT,
    MULTI_IMAGE_FEEDBACK_PROMPT,
)


# Configuration
IMAGES_DIR = Path("images")
GENERATED_IMAGES_DIR = IMAGES_DIR / "generated"


# =============================================================================
# PROMPTS
# =============================================================================

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


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def load_image_as_base64(image_url: str) -> str:
    """Load an image and convert to base64 data URL for VLM."""
    if image_url.startswith("data:image"):
        return image_url
    
    if image_url.startswith("/api/v1/files/"):
        filename = image_url.replace("/api/v1/files/", "")
        file_path = IMAGES_DIR / filename
        
        if file_path.exists():
            with open(file_path, "rb") as f:
                content = f.read()
            
            ext = file_path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }
            mime_type = mime_types.get(ext, "image/jpeg")
            
            b64 = base64.b64encode(content).decode("utf-8")
            return f"data:{mime_type};base64,{b64}"
        else:
            raise FileNotFoundError(f"Image file not found: {file_path}")
    
    if image_url.startswith("http"):
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "image/jpeg")
            if ";" in content_type:
                content_type = content_type.split(";")[0]
            b64 = base64.b64encode(content).decode("utf-8")
            return f"data:{content_type};base64,{b64}"
    
    raise ValueError(f"Unsupported image URL format: {image_url}")


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
    
    import json
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


USER_INTENT_PROMPT = """Analyze the user's message in a renovation project context.

Current context: {context}

User's message: "{user_message}"

Determine the user's intent. Return JSON only:
{{
    "intent": "{intent_options}",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}"""


async def detect_confirmation_intent(user_message: str, context: str) -> dict:
    """Use AI to detect if user is confirming or wants changes."""
    provider = LLMProvider.for_llm()
    
    prompt = USER_INTENT_PROMPT.format(
        context=context,
        user_message=user_message,
        intent_options="confirm | correction | unclear"
    )
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent. 'confirm' means they agree/approve. 'correction' means they want to change something. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=150
    )
    
    try:
        return parse_json(response)
    except:
        return {"intent": "unclear", "confidence": 0.0}


async def detect_skip_or_vision_intent(user_message: str) -> dict:
    """Use AI to detect if user wants to skip vision or is providing vision details."""
    provider = LLMProvider.for_llm()
    
    prompt = f"""The user was asked if they have a specific vision for their renovation.
They could: provide vision details, skip this step, or say they're done.

User's message: "{user_message}"

Determine intent. Return JSON only:
{{
    "intent": "skip" | "provide_vision" | "done" | "unclear",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}

- "skip": User doesn't want to provide vision, wants to proceed without it
- "provide_vision": User is sharing their renovation ideas/preferences
- "done": User has finished providing vision, ready to move on
- "unclear": Cannot determine"""
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent for renovation vision collection. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=150
    )
    
    try:
        return parse_json(response)
    except:
        return {"intent": "unclear", "confidence": 0.0}


async def detect_proceed_intent(user_message: str, context: str) -> dict:
    """Use AI to detect if user wants to proceed or has feedback."""
    provider = LLMProvider.for_llm()
    
    prompt = f"""Context: {context}

User's message: "{user_message}"

Determine intent. Return JSON only:
{{
    "intent": "proceed" | "feedback" | "unclear",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "feedback_content": "extracted feedback if intent is feedback, else null"
}}

- "proceed": User wants to continue/move forward
- "feedback": User is providing feedback or requesting changes
- "unclear": Cannot determine"""
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=200
    )
    
    try:
        return parse_json(response)
    except:
        return {"intent": "unclear", "confidence": 0.0}


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


def get_placeholder_image_url() -> str:
    """Get URL for placeholder renovation preview image."""
    return "/api/v1/files/placeholder-renovation.jpg"


async def generate_renovation_image(
    original_image_urls: list[str],
    project_type: str,
    extracted_data: dict,
    renovation_vision: dict | None = None,
    feedback: list[str] | None = None,
    previous_prompt: str | None = None,
    features_to_retain: list[str] | None = None,
) -> tuple[str, str, str]:
    """
    Generate a renovation preview image using Gemini's image generation model.

    The model returns BOTH an image and a text description of changes made.

    Args:
        original_image_urls: List of URLs to original uploaded images
        project_type: Type of renovation project
        extracted_data: Extracted materials, measurements, colors, etc.
        renovation_vision: Optional user vision with preferences
        feedback: Optional list of user feedback for regeneration
        previous_prompt: Previous generation prompt (for regeneration)

    Returns:
        Tuple of (image_url, generation_prompt, description)
        - image_url: API URL to access the generated image (e.g., /api/v1/files/generated/...)
        - generation_prompt: The prompt used for generation (for potential regeneration)
        - description: Text description of what changes were made

    Raises:
        Exception: If image generation fails
    """
    print(f"[image_generation] Starting generation for {project_type} project...")

    # Ensure generated images directory exists
    GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Build the generation prompt
    if feedback and previous_prompt:
        # Regeneration with feedback
        generation_prompt = build_image_regeneration_prompt(previous_prompt, feedback)
        print(f"[image_generation] Regenerating with feedback: {feedback}")
    else:
        # Initial generation with features to retain
        generation_prompt = build_image_generation_prompt(
            project_type=project_type,
            extracted_data=extracted_data,
            renovation_vision=renovation_vision,
            features_to_retain=features_to_retain,
        )
        print(f"[image_generation] Initial generation (retaining: {features_to_retain})")

    # Load the first original image as base64 for input
    # (Using first image as primary reference)
    if not original_image_urls:
        raise ValueError("No original images provided for generation")

    primary_image_url = original_image_urls[0]
    image_data_url = await load_image_as_base64(primary_image_url)

    # Prepare messages for VGM
    messages = [
        {
            "role": "system",
            "content": "You are an expert architectural visualization AI. Generate photorealistic renovation previews based on the provided image and instructions."
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": generation_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}}
            ]
        }
    ]

    # Generate image using VGM
    try:
        provider = LLMProvider.for_vgm()
        result = await provider.generate_image(
            messages=messages,
            temperature=0.7,
            max_tokens=1024
        )

        image_data = result["image_data"]
        mime_type = result["mime_type"]
        description = result.get("description", "")  # Text description of changes

        # Determine file extension from mime type
        ext_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
        }
        ext = ext_map.get(mime_type, ".png")

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"renovation_{timestamp}_{unique_id}{ext}"
        file_path = GENERATED_IMAGES_DIR / filename

        # Save the image
        with open(file_path, "wb") as f:
            f.write(image_data)

        print(f"[image_generation] Saved generated image to {file_path}")
        print(f"[image_generation] Description: {description[:150]}..." if len(description) > 150 else f"[image_generation] Description: {description}")

        # Return API URL, prompt, and description
        api_url = f"/api/v1/files/generated/{filename}"

        return api_url, generation_prompt, description

    except Exception as e:
        print(f"[image_generation] ERROR: {e}")
        raise Exception(f"Failed to generate renovation image: {str(e)}") from e


async def classify_feedback_for_regeneration(user_message: str) -> dict:
    """
    Use LLM to classify if user feedback requires image regeneration.

    Returns:
        dict with keys: requires_regeneration, confidence, reasoning, extracted_feedback
    """
    provider = LLMProvider.for_llm()

    prompt = FEEDBACK_CLASSIFICATION_PROMPT.format(user_message=user_message)

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user feedback to determine if image regeneration is needed. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=200
    )

    try:
        return parse_json(response)
    except:
        # Default to not regenerating if parsing fails
        return {
            "requires_regeneration": False,
            "confidence": 0.0,
            "reasoning": "Failed to parse classification",
            "extracted_feedback": None
        }


async def detect_enhanced_intent(user_message: str, context: str) -> dict:
    """
    Enhanced multi-intent classifier.

    Detects: confirm, correction, direct_vision, ask_suggestions, ask_question,
             vague_request, skip, mixed

    Returns:
        dict with keys: primary_intent, secondary_intents, confidence, reasoning, extracted_content
    """
    provider = LLMProvider.for_llm()

    prompt = ENHANCED_INTENT_CLASSIFIER_PROMPT.format(
        context=context,
        user_message=user_message
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You analyze user intent with support for multiple intents. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=300
    )

    try:
        return parse_json(response)
    except:
        return {
            "primary_intent": "unclear",
            "secondary_intents": [],
            "confidence": 0.0,
            "reasoning": "Failed to parse",
            "extracted_content": {}
        }


async def detect_expertise_level(user_message: str, history_summary: str = "") -> dict:
    """
    Detect user's expertise level based on their language and conversation.

    Returns:
        dict with keys: expertise_level, confidence, indicators, recommended_communication_style
    """
    provider = LLMProvider.for_llm()

    prompt = EXPERTISE_DETECTOR_PROMPT.format(
        user_message=user_message,
        history_summary=history_summary or "No prior conversation"
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You detect user expertise level in renovation/construction. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=200
    )

    try:
        return parse_json(response)
    except:
        return {
            "expertise_level": "novice",
            "confidence": 0.5,
            "indicators": [],
            "recommended_communication_style": "explanatory"
        }


async def generate_expert_suggestions(
    project_type: str,
    current_state_summary: str,
    user_preferences: str,
    expertise_level: str
) -> dict:
    """
    Generate 2-3 expert renovation suggestions based on current state.

    Returns:
        dict with keys: options (list), follow_up_message
    """
    provider = LLMProvider.for_llm()

    prompt = EXPERT_SUGGESTIONS_PROMPT.format(
        project_type=project_type,
        current_state_summary=current_state_summary,
        user_preferences=user_preferences or "None provided yet",
        expertise_level=expertise_level
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a panel of renovation experts providing tailored suggestions. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1500
    )

    try:
        return parse_json(response)
    except:
        return {
            "options": [],
            "follow_up_message": "I'd be happy to suggest some options. Could you tell me more about what style or changes you're interested in?"
        }


async def detect_regeneration_mode(user_feedback: str, current_design_summary: str) -> dict:
    """
    Determine if regeneration should use original image (style change) or last generated (refinement).

    Returns:
        dict with keys: mode (style_change | iterative_refinement | ask_user),
                       confidence, reasoning, extracted_changes
    """
    provider = LLMProvider.for_llm()

    prompt = REGENERATION_MODE_CLASSIFIER_PROMPT.format(
        user_feedback=user_feedback,
        current_design_summary=current_design_summary or "No current design"
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You classify regeneration mode for image generation. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=200
    )

    try:
        result = parse_json(response)
        # If low confidence, ask user
        if result.get("confidence", 0) < 0.7:
            result["mode"] = "ask_user"
        return result
    except:
        return {
            "mode": "ask_user",
            "confidence": 0.0,
            "reasoning": "Failed to parse",
            "extracted_changes": user_feedback
        }


async def clarify_vague_request(
    user_request: str,
    project_type: str,
    extracted_data_summary: str,
    expertise_level: str
) -> dict:
    """
    Generate clarifying questions for vague user requests.

    Returns:
        dict with keys: interpreted_intent, clarifying_questions, suggested_response
    """
    provider = LLMProvider.for_llm()

    prompt = VAGUE_REQUEST_CLARIFIER_PROMPT.format(
        user_request=user_request,
        project_type=project_type,
        extracted_data_summary=extracted_data_summary or "No data extracted yet",
        expertise_level=expertise_level
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You help clarify vague renovation requests by asking smart questions. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=400
    )

    try:
        return parse_json(response)
    except:
        return {
            "interpreted_intent": "Unable to interpret",
            "clarifying_questions": ["Could you provide more details about what you'd like to change?"],
            "suggested_response": "I'd love to help! Could you provide more details about what changes you have in mind?"
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


async def detect_conversation_type(
    user_message: str,
    context: str,
    has_generated_images: bool
) -> dict:
    """
    Classify the type of user message: discussion, generation_request, reference_previous, move_forward, clarify.

    Returns:
        dict with conversation_type, confidence, and relevant extracted data
    """
    provider = LLMProvider.for_llm()

    prompt = CONVERSATION_TYPE_CLASSIFIER_PROMPT.format(
        user_message=user_message,
        context=context,
        has_generated_images=str(has_generated_images).lower()
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You classify user intent in renovation conversations. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=250
    )

    try:
        return parse_json(response)
    except:
        return {
            "conversation_type": "clarify",
            "confidence": 0.0,
            "reasoning": "Failed to parse",
            "extracted_question": None,
            "referenced_image_position": None,
            "generation_changes": None
        }


async def unified_classify(
    user_message: str,
    context: str,
    has_generated_images: bool
) -> dict:
    """
    Unified classifier that combines expertise detection, intent classification,
    and conversation type into a SINGLE LLM call to reduce latency.

    Replaces separate calls to:
    - detect_expertise_level()
    - detect_enhanced_intent()
    - detect_conversation_type()

    Returns:
        dict with all classification results:
        - expertise_level, expertise_indicators
        - conversation_type
        - primary_intent, secondary_intents
        - confidence, reasoning
        - extracted_content (confirmation, corrections, vision_details, questions,
                            generation_changes, referenced_image_position)
    """
    provider = LLMProvider.for_llm()

    prompt = UNIFIED_CLASSIFIER_PROMPT.format(
        user_message=user_message,
        context=context,
        has_generated_images=str(has_generated_images).lower()
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a multi-purpose classifier for renovation conversations. Analyze expertise, intent, and conversation type in one response. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=400
    )

    try:
        result = parse_json(response)
        # Ensure all required fields exist
        return {
            "expertise_level": result.get("expertise_level", "novice"),
            "expertise_indicators": result.get("expertise_indicators", []),
            "conversation_type": result.get("conversation_type", "clarify"),
            "primary_intent": result.get("primary_intent", "unclear"),
            "secondary_intents": result.get("secondary_intents", []),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
            "extracted_content": result.get("extracted_content", {})
        }
    except:
        return {
            "expertise_level": "novice",
            "expertise_indicators": [],
            "conversation_type": "clarify",
            "primary_intent": "unclear",
            "secondary_intents": [],
            "confidence": 0.0,
            "reasoning": "Failed to parse unified classification",
            "extracted_content": {}
        }


async def answer_image_question(
    question: str,
    image_url: str,
    context: str = ""
) -> str:
    """
    Use VLM to answer a question about an image without generating new images.

    Returns:
        str: The answer to the question
    """
    provider = LLMProvider.for_vlm()
    image_data_url = await load_image_as_base64(image_url)

    prompt = f"""Answer this question about the image:

Question: {question}

{f"Context: {context}" if context else ""}

Provide a helpful, concise answer. If you can identify specific details (color codes, material types, dimensions), include them.
For colors, try to provide hex codes when possible (e.g., "The wall appears to be a warm beige, approximately #D4C4A8")."""

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful renovation expert answering questions about room images. Be specific and accurate."
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
        max_tokens=400
    )

    return response


def add_to_image_history(
    history: list,
    url: str,
    description: str,
    base_perspective: int = 0,
    user_satisfied: bool | None = None
) -> list:
    """
    Add a generated image to the history tracking.

    Args:
        history: Existing history list
        url: URL of the generated image
        description: Brief description of what was generated
        base_perspective: Index of the source image perspective
        user_satisfied: Whether user expressed satisfaction (None if unknown)

    Returns:
        Updated history list
    """
    new_entry = {
        "url": url,
        "description": description[:200] if description else "",  # Truncate for storage
        "position": len(history) + 1,
        "base_perspective": base_perspective,
        "user_satisfied": user_satisfied,
        "timestamp": datetime.now().isoformat()
    }
    return history + [new_entry]


def get_image_from_history(history: list, reference: str) -> dict | None:
    """
    Get an image from history based on user reference.

    Args:
        history: Image history list
        reference: User's reference (e.g., "1", "first", "previous", "second")

    Returns:
        Image entry dict or None
    """
    if not history:
        return None

    reference_lower = reference.lower().strip()

    # Handle position numbers
    if reference_lower.isdigit():
        position = int(reference_lower)
        for img in history:
            if img.get("position") == position:
                return img
        return None

    # Handle word references
    word_map = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "last": len(history),
        "previous": len(history) - 1 if len(history) > 1 else len(history),
        "latest": len(history)
    }

    if reference_lower in word_map:
        position = word_map[reference_lower]
        if 0 < position <= len(history):
            return history[position - 1]

    return None


async def parse_multi_image_feedback(
    user_feedback: str,
    num_images: int
) -> dict:
    """
    Parse user feedback to identify which images are being referenced
    and what changes are requested for each.

    Args:
        user_feedback: User's feedback message
        num_images: Number of generated images available

    Returns:
        dict with:
        - references_multiple_images: bool
        - image_feedback: list of {image_position, feedback, confidence}
        - applies_to_all: bool
        - general_feedback: str or None
    """
    if num_images <= 1:
        # Single image - no need to parse
        return {
            "references_multiple_images": False,
            "image_feedback": [{"image_position": 1, "feedback": user_feedback, "confidence": 1.0}],
            "applies_to_all": True,
            "general_feedback": user_feedback
        }

    provider = LLMProvider.for_llm()

    prompt = MULTI_IMAGE_FEEDBACK_PROMPT.format(
        user_feedback=user_feedback,
        num_images=num_images
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You parse user feedback about multiple images. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=300
    )

    try:
        result = parse_json(response)
        # Validate image positions
        validated_feedback = []
        for fb in result.get("image_feedback", []):
            pos = fb.get("image_position", 1)
            if 1 <= pos <= num_images:
                validated_feedback.append(fb)
        result["image_feedback"] = validated_feedback
        return result
    except:
        # Default: apply to all images
        return {
            "references_multiple_images": False,
            "image_feedback": [],
            "applies_to_all": True,
            "general_feedback": user_feedback
        }


# =============================================================================
# MAIN NODE
# =============================================================================

async def image_analysis_generation_node(state: ProjectState) -> dict:
    """
    Main image analysis and generation node.
    
    Sub-states:
    - analyzing: Process new images, extract ALL data
    - confirming_extraction: User reviews/corrects all data at once
    - collecting_vision: OPTIONAL - collect user's renovation vision
    - generating: Generate proposal/preview image
    - confirming_proposal: User reviews generated image
    """
    sub_state = state.get("image_sub_state", "analyzing")
    messages = state.get("messages", [])
    user_message, new_image_urls = get_latest_user_message(messages)
    
    # Check for pending images from project_basics transition
    pending_images = state.get("_pending_images", [])
    if pending_images:
        new_image_urls = pending_images
    
    # IMPORTANT: Always preserve existing state data
    image_analyses = list(state.get("image_analyses", []))
    extracted_data = dict(state.get("extracted_data", {}))
    renovation_vision = state.get("renovation_vision")

    updates = {
        "image_analyses": image_analyses,
        "extracted_data": extracted_data,
    }

    # Preserve generation-related state (critical for regeneration)
    if state.get("generated_image_url"):
        updates["generated_image_url"] = state["generated_image_url"]
    if state.get("generation_prompt"):
        updates["generation_prompt"] = state["generation_prompt"]
    if state.get("generation_description"):
        updates["generation_description"] = state["generation_description"]
    if state.get("original_image_urls"):
        updates["original_image_urls"] = state["original_image_urls"]
    if state.get("image_generation_feedback"):
        updates["image_generation_feedback"] = state["image_generation_feedback"]

    # Preserve new conversation state fields
    if state.get("expertise_level"):
        updates["expertise_level"] = state["expertise_level"]
    if state.get("last_generated_image_url"):
        updates["last_generated_image_url"] = state["last_generated_image_url"]
    if state.get("pending_suggestions"):
        updates["pending_suggestions"] = state["pending_suggestions"]
    if state.get("selected_options_for_generation"):
        updates["selected_options_for_generation"] = state["selected_options_for_generation"]
    if state.get("generated_options"):
        updates["generated_options"] = state["generated_options"]
    if state.get("pending_feedback"):
        updates["pending_feedback"] = state["pending_feedback"]

    # Preserve image history and feature retention
    if state.get("generated_image_history"):
        updates["generated_image_history"] = state["generated_image_history"]
    if state.get("selected_final_image_url"):
        updates["selected_final_image_url"] = state["selected_final_image_url"]
    if state.get("original_features_to_retain"):
        updates["original_features_to_retain"] = state["original_features_to_retain"]
    if state.get("brief_room_summary"):
        updates["brief_room_summary"] = state["brief_room_summary"]
    
    # Clear pending images after using
    if pending_images:
        updates["_pending_images"] = []
    
    project_type = state.get("project_type", "renovation")
    
    print(f"[image_analysis] SUB_STATE: {sub_state} | user_message={user_message!r} | "
          f"new_images={len(new_image_urls)} | stored_analyses={len(image_analyses)}")
    
    # =========================================================================
    # ANALYZING STATE - Extract all data from images
    # =========================================================================
    if sub_state == "analyzing":
        if new_image_urls:
            print(f"[image_analysis] Processing {len(new_image_urls)} images in parallel...")

            # Analyze all images in parallel
            image_analyses = await analyze_images_parallel(new_image_urls, project_type)
            updates["image_analyses"] = image_analyses

            # Merge into extracted_data (kept internally, not shown to user)
            extracted_data = merge_image_analyses_to_extracted(image_analyses)
            updates["extracted_data"] = extracted_data

            # Detect features to retain (parallel with summary generation)
            primary_image_url = new_image_urls[0]

            # Run feature detection and brief summary in parallel
            features_task = detect_features_to_retain(primary_image_url)
            summary_task = generate_brief_room_summary(primary_image_url, project_type, extracted_data)

            features_result, summary_result = await asyncio.gather(features_task, summary_task)

            # Store features to retain for later image generation
            features_to_retain = features_result.get("must_retain_features", [])
            updates["original_features_to_retain"] = features_to_retain
            print(f"[image_analysis] Features to retain: {features_to_retain}")

            # Store brief summary
            brief_summary = summary_result.get("brief_summary", f"A {project_type} space.")
            room_vibe = summary_result.get("room_vibe", "current")
            updates["brief_room_summary"] = brief_summary

            # Initialize empty image history
            updates["generated_image_history"] = []

            # Move to design conversation (flexible flow)
            updates["image_sub_state"] = "design_conversation"

            # Build conversational response with larger images
            image_html_parts = []
            for img in image_analyses:
                image_html_parts.append(
                    f'<img src="{img["url"]}" style="width: 100%; max-width: 600px; '
                    f'border-radius: 12px; margin: 8px 0; cursor: pointer;" />'
                )
            images_display = "\n".join(image_html_parts)

            response = (
                f"{images_display}\n\n"
                f"**{brief_summary}**\n\n"
                f"What changes would you like to make to this space?\n\n"
                f"You can:\n"
                f"- Describe your vision (e.g., *\"modern minimalist with white marble\"*)\n"
                f"- Ask for suggestions (e.g., *\"what would you recommend?\"*)\n"
                f"- Ask questions (e.g., *\"what style is this currently?\"*)"
            )
        else:
            response = "Please upload one or more images of the space you want to renovate."

        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # =========================================================================
    # DESIGN CONVERSATION STATE - Flexible conversation after extraction
    # Handles: confirm, correction, direct_vision, ask_suggestions, ask_question, vague_request, skip, mixed
    # =========================================================================
    elif sub_state in ["confirming_extraction", "collecting_vision", "design_conversation"]:
        # Get cached expertise level or default
        expertise_level = state.get("expertise_level", "novice")

        if user_message:
            # Check if user is selecting from pending suggestions
            pending_suggestions = state.get("pending_suggestions", [])
            if pending_suggestions:
                # Try to parse option selection
                selected_indices = []
                message_lower = user_message.lower()

                for i, opt in enumerate(pending_suggestions):
                    # Check for option number references
                    if f"option {i+1}" in message_lower or f"#{i+1}" in message_lower or f"option{i+1}" in message_lower:
                        selected_indices.append(i)
                    # Check for style name references
                    style_name = opt.get("style_name", "").lower()
                    if style_name and style_name in message_lower:
                        selected_indices.append(i)

                # Check for "all" options
                if not selected_indices and "all" in message_lower and ("generate" in message_lower or "show" in message_lower):
                    selected_indices = list(range(len(pending_suggestions)))

                # Deduplicate while preserving order
                selected_indices = list(dict.fromkeys(selected_indices))

                if selected_indices:
                    print(f"[design_conversation] Option selection detected: indices {selected_indices}")
                    selected_options = [pending_suggestions[i] for i in selected_indices if i < len(pending_suggestions)]

                    if len(selected_options) == 1:
                        # Single option - standard generation
                        opt = selected_options[0]
                        updates["renovation_vision"] = {
                            "raw_input": f"Style: {opt.get('style_name')}",
                            "ai_summary": opt.get("description", ""),
                            "style_preferences": opt.get("style_name"),
                            "material_preferences": json.dumps(opt.get("materials", {})),
                            "specific_changes": ", ".join(opt.get("key_changes", [])),
                            "selected_option": opt
                        }
                        updates["pending_suggestions"] = []  # Clear pending suggestions
                        updates["image_sub_state"] = "generating"
                        updates["awaiting_user_input"] = False
                        updates["messages"] = []
                        return updates
                    else:
                        # Multiple options - parallel generation
                        updates["selected_options_for_generation"] = selected_options
                        updates["pending_suggestions"] = []  # Clear pending suggestions
                        updates["image_sub_state"] = "generating_parallel"
                        updates["awaiting_user_input"] = False
                        updates["messages"] = []
                        return updates

            # Use UNIFIED classifier (combines expertise + intent + conversation type in ONE call)
            context = (
                f"User is in a {project_type} renovation project. "
                f"Extracted data includes: {list(extracted_data.keys())}. "
                f"User can: confirm extraction, correct data, provide vision, ask suggestions, ask questions, skip steps."
            )
            unified_result = await unified_classify(
                user_message=user_message,
                context=context,
                has_generated_images=len(state.get("generated_image_history", [])) > 0
            )

            # Extract all results from unified classifier
            primary_intent = unified_result.get("primary_intent", "unclear")
            secondary_intents = unified_result.get("secondary_intents", [])
            extracted_content = unified_result.get("extracted_content", {})

            # Cache expertise level if not already set
            if not state.get("expertise_level"):
                expertise_level = unified_result.get("expertise_level", "novice")
                updates["expertise_level"] = expertise_level
                print(f"[design_conversation] Detected expertise: {expertise_level}")

            print(f"[design_conversation] Intent: {primary_intent} | secondary: {secondary_intents} | "
                  f"confidence: {unified_result.get('confidence')}")

            # Handle corrections (can combine with other intents)
            if primary_intent == "correction" or "correction" in secondary_intents:
                corrections = extracted_content.get("corrections") or user_message
                print(f"[design_conversation] Applying correction: {corrections}")
                corrected_data = await apply_user_correction(extracted_data, corrections, project_type)
                updates["extracted_data"] = corrected_data
                extracted_data = corrected_data  # Update local reference

            # Handle based on primary intent
            if primary_intent == "confirm" or primary_intent == "mixed":
                # User confirmed - check for vision in the same message
                vision_details = extracted_content.get("vision_details")

                if vision_details or primary_intent == "mixed":
                    # User confirmed AND provided vision
                    print(f"[design_conversation] Confirm + Vision: {vision_details}")
                    updates["renovation_vision"] = {
                        "raw_input": vision_details or user_message,
                        "ai_summary": vision_details or user_message
                    }
                    # Move directly to generation
                    updates["image_sub_state"] = "generating"
                    updates["awaiting_user_input"] = False
                    updates["messages"] = []
                    return updates
                else:
                    # Just confirmation - ask for vision
                    print("[design_conversation] User confirmed. Asking for vision.")
                    updates["image_sub_state"] = "design_conversation"
                    response = VISION_PROMPT
                    updates["messages"] = [{"role": "assistant", "content": response}]
                    updates["awaiting_user_input"] = True
                    return updates

            elif primary_intent == "direct_vision":
                # User directly provided vision without confirming
                vision_details = extracted_content.get("vision_details") or user_message
                print(f"[design_conversation] Direct vision provided: {vision_details}")

                updates["renovation_vision"] = {
                    "raw_input": vision_details,
                    "ai_summary": vision_details
                }

                # Move directly to generation
                updates["image_sub_state"] = "generating"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates

            elif primary_intent == "ask_suggestions":
                # User wants AI recommendations
                print("[design_conversation] User asking for suggestions")

                import json
                current_state_summary = json.dumps(extracted_data, indent=2)[:800]
                user_prefs = renovation_vision.get("raw_input", "") if renovation_vision else ""

                suggestions_result = await generate_expert_suggestions(
                    project_type=project_type,
                    current_state_summary=current_state_summary,
                    user_preferences=user_prefs,
                    expertise_level=expertise_level
                )

                # Store suggestions for later selection
                updates["pending_suggestions"] = suggestions_result.get("options", [])

                # Format suggestions for display
                options = suggestions_result.get("options", [])
                response_parts = ["# Renovation Options\n\nBased on your space, here are my recommendations:\n"]

                for i, opt in enumerate(options, 1):
                    response_parts.append(f"\n### Option {i}: {opt.get('style_name', 'Option')}\n")
                    response_parts.append(f"{opt.get('description', '')}\n\n")
                    response_parts.append("**Key Changes:**\n")
                    for change in opt.get("key_changes", []):
                        response_parts.append(f"- {change}\n")
                    response_parts.append(f"\n*Budget: {opt.get('budget_tier', 'mid-range')} | "
                                         f"Transformation: {opt.get('transformation_level', 'moderate')}*\n")

                response_parts.append(f"\n---\n\n{suggestions_result.get('follow_up_message', '')}")
                response_parts.append("\n\nYou can say things like:")
                response_parts.append("\n- \"Show me option 1\"")
                response_parts.append("\n- \"Generate option 2 and 3\"")
                response_parts.append("\n- \"I like the modern style, generate it\"")

                response = "".join(response_parts)
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

            elif primary_intent == "ask_question":
                # User has questions - answer them
                questions = extracted_content.get("questions", [])
                print(f"[design_conversation] User questions: {questions}")

                # Use LLM to answer renovation questions
                provider = LLMProvider.for_llm()
                answer_prompt = f"""Answer this renovation question helpfully.
Project type: {project_type}
Current room: {json.dumps(extracted_data, indent=2)[:500] if extracted_data else 'Not analyzed yet'}
User's question: {user_message}

Provide a helpful, informative answer. Keep it concise but educational.
At the end, gently guide them back to the renovation planning."""

                answer = await provider.complete(
                    messages=[
                        {"role": "system", "content": "You are a helpful renovation expert."},
                        {"role": "user", "content": answer_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=500
                )

                response = f"{answer}\n\n---\n\nWould you like to continue with your renovation vision, or do you have more questions?"
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

            elif primary_intent == "vague_request":
                # User made vague request - ask clarifying questions
                vague_needs = extracted_content.get("vague_needs") or user_message
                print(f"[design_conversation] Vague request: {vague_needs}")

                import json
                extracted_summary = json.dumps(extracted_data, indent=2)[:500] if extracted_data else ""

                clarification = await clarify_vague_request(
                    user_request=vague_needs,
                    project_type=project_type,
                    extracted_data_summary=extracted_summary,
                    expertise_level=expertise_level
                )

                response = clarification.get("suggested_response",
                    "Could you tell me more about what you'd like to change?")
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

            elif primary_intent == "skip":
                # User wants to skip - move to generation with no specific vision
                print("[design_conversation] User skipped vision. Moving to generation.")
                updates["renovation_vision"] = None
                updates["image_sub_state"] = "generating"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates

            elif primary_intent == "correction":
                # Already handled above, show updated data
                display = format_extracted_data_for_display(extracted_data, image_analyses)
                response = (
                    f"# Updated Information:\n\n"
                    f"{display}\n"
                    f"---\n\n"
                    f"Anything else to change? Or tell me your renovation vision to continue."
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

            else:  # unclear
                response = (
                    "I'm here to help! You can:\n"
                    "- **Confirm** the extracted info is correct\n"
                    "- **Correct** anything that needs fixing\n"
                    "- **Share your vision** (e.g., 'add marble tiles and chandelier')\n"
                    "- **Ask for suggestions** (e.g., 'what do you recommend?')\n"
                    "- **Ask questions** about materials or styles\n"
                    "- Say **'skip'** to proceed with a general design"
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

        # No user message - show current data with flexible prompt
        display = format_extracted_data_for_display(extracted_data, image_analyses)
        response = (
            f"# Extracted Information:\n\n"
            f"{display}\n"
            f"---\n\n"
            f"What would you like to do?\n"
            f"- Tell me your renovation vision\n"
            f"- Ask for my suggestions\n"
            f"- Correct any details above\n"
            f"- Or say 'skip' to proceed"
        )
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates

    # =========================================================================
    # SELECTING SUGGESTIONS STATE - User selects from AI suggestions (for parallel generation)
    # =========================================================================
    elif sub_state == "selecting_suggestions":
        pending_suggestions = state.get("pending_suggestions", [])

        if user_message:
            # Parse which options user wants to generate
            # Simple parsing: look for option numbers or style names
            selected_indices = []
            message_lower = user_message.lower()

            for i, opt in enumerate(pending_suggestions):
                # Check for option number references
                if f"option {i+1}" in message_lower or f"#{i+1}" in message_lower:
                    selected_indices.append(i)
                # Check for style name references
                if opt.get("style_name", "").lower() in message_lower:
                    selected_indices.append(i)

            # If no specific options found, check for "all" or single generation
            if not selected_indices:
                if "all" in message_lower:
                    selected_indices = list(range(len(pending_suggestions)))
                elif pending_suggestions:
                    # Default to first option if user says something like "yes" or "generate"
                    selected_indices = [0]

            if selected_indices:
                # Store selected options as vision and generate
                selected_options = [pending_suggestions[i] for i in selected_indices if i < len(pending_suggestions)]

                if len(selected_options) == 1:
                    # Single option - standard generation
                    opt = selected_options[0]
                    updates["renovation_vision"] = {
                        "raw_input": f"Style: {opt.get('style_name')}",
                        "ai_summary": opt.get("description", ""),
                        "selected_option": opt
                    }
                    updates["image_sub_state"] = "generating"
                    updates["awaiting_user_input"] = False
                    updates["messages"] = []
                    return updates
                else:
                    # Multiple options - parallel generation
                    # Store selected options for parallel generation
                    updates["selected_options_for_generation"] = selected_options
                    updates["image_sub_state"] = "generating_parallel"
                    updates["awaiting_user_input"] = False
                    updates["messages"] = []
                    return updates
            else:
                response = (
                    "I couldn't identify which option(s) you'd like to see. Please specify:\n"
                    "- **'Option 1'** or **'Option 2'** to generate that style\n"
                    "- **'Generate all'** to see all options\n"
                    "- Or describe what you're looking for"
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

        # No message - prompt for selection
        response = "Which option would you like me to generate? You can say 'Option 1', 'Option 2', or 'Generate all'."
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # =========================================================================
    # GENERATING STATE - Generate proposal image(s) for all perspectives
    # =========================================================================
    elif sub_state == "generating":
        print("[image_analysis] Generating renovation preview image(s)...")

        # Get original image URLs from image_analyses
        original_image_urls = [img["url"] for img in image_analyses]
        features_to_retain = state.get("original_features_to_retain", [])
        image_history = list(state.get("generated_image_history", []))

        if not original_image_urls:
            # Fallback to placeholder if no images
            print("[image_analysis] WARNING: No original images found, using placeholder")
            generated_url = get_placeholder_image_url()
            generation_prompt = ""
            description = ""
            generated_results = []
        elif len(original_image_urls) == 1:
            # Single image - generate one preview
            try:
                generated_url, generation_prompt, description = await generate_renovation_image(
                    original_image_urls=original_image_urls,
                    project_type=project_type,
                    extracted_data=extracted_data,
                    renovation_vision=renovation_vision,
                    feedback=None,
                    previous_prompt=None,
                    features_to_retain=features_to_retain,
                )
                print(f"[image_analysis] Successfully generated image: {generated_url}")

                image_history = add_to_image_history(
                    history=image_history,
                    url=generated_url,
                    description=description,
                    base_perspective=0,
                    user_satisfied=None
                )
                generated_results = [{"url": generated_url, "description": description, "perspective": 0}]
            except Exception as e:
                print(f"[image_analysis] Image generation failed: {e}")
                generated_url = get_placeholder_image_url()
                generation_prompt = ""
                description = ""
                generated_results = []
                updates["_generation_error"] = str(e)
        else:
            # Multiple images/perspectives - generate for each in parallel
            print(f"[image_analysis] Multiple perspectives detected ({len(original_image_urls)}). Generating in parallel...")

            async def generate_for_perspective(img_url: str, perspective_idx: int):
                try:
                    url, prompt, desc = await generate_renovation_image(
                        original_image_urls=[img_url],
                        project_type=project_type,
                        extracted_data=extracted_data,
                        renovation_vision=renovation_vision,
                        feedback=None,
                        previous_prompt=None,
                        features_to_retain=features_to_retain,
                    )
                    return {"url": url, "prompt": prompt, "description": desc, "perspective": perspective_idx, "success": True}
                except Exception as e:
                    print(f"[image_analysis] Failed perspective {perspective_idx}: {e}")
                    return {"url": get_placeholder_image_url(), "description": str(e), "perspective": perspective_idx, "success": False}

            # Generate all perspectives in parallel
            generated_results = await asyncio.gather(*[
                generate_for_perspective(url, idx) for idx, url in enumerate(original_image_urls)
            ])

            # Add successful results to history
            for result in generated_results:
                if result.get("success"):
                    image_history = add_to_image_history(
                        history=image_history,
                        url=result["url"],
                        description=result.get("description", ""),
                        base_perspective=result["perspective"],
                        user_satisfied=None
                    )

            # Use first successful result as primary
            successful = [r for r in generated_results if r.get("success")]
            if successful:
                generated_url = successful[0]["url"]
                generation_prompt = successful[0].get("prompt", "")
                description = successful[0].get("description", "")
            else:
                generated_url = get_placeholder_image_url()
                generation_prompt = ""
                description = ""
                updates["_generation_error"] = "All perspective generations failed"

        updates["generated_image_url"] = generated_url
        updates["last_generated_image_url"] = generated_url
        updates["generation_prompt"] = generation_prompt
        updates["generation_description"] = description
        updates["original_image_urls"] = original_image_urls
        updates["generated_image_history"] = image_history
        updates["image_sub_state"] = "confirming_proposal"

        # Build response based on number of perspectives
        error_note = ""
        if updates.get("_generation_error"):
            error_note = "\n\n*Note: Some images encountered issues.*\n\n"

        if len(generated_results) > 1:
            # Multiple perspectives - show all
            response_parts = []
            successful_results = [r for r in generated_results if r.get("success", False)]

            for i, result in enumerate(successful_results, 1):
                response_parts.append(f"**Perspective {i}**\n")
                response_parts.append(
                    f'<img src="{result["url"]}" style="width: 100%; max-width: 800px; '
                    f'border-radius: 12px; margin: 8px 0;" />\n\n'
                )
                # Show full description (AI is instructed to keep it brief)
                if result.get("description"):
                    response_parts.append(f"{result['description']}\n\n")

            response_parts.append(f"{error_note}")
            response_parts.append("---\n\n")
            response_parts.append("How do these look? Say **'continue'** to proceed, or request changes.")
            response = "".join(response_parts)
        else:
            # Single perspective - show full description (AI is instructed to keep it brief)
            desc_section = ""
            if description and not updates.get("_generation_error"):
                desc_section = f"{description}\n\n"

            response = (
                f'<img src="{generated_url}" style="width: 100%; max-width: 800px; '
                f'border-radius: 12px; margin: 16px 0;" />\n\n'
                f"{error_note}"
                f"{desc_section}"
                f"How does this look? Say **'continue'** to proceed, or tell me what to change."
            )

        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates

    # =========================================================================
    # GENERATING PARALLEL STATE - Generate multiple options/perspectives in parallel
    # =========================================================================
    elif sub_state == "generating_parallel":
        selected_options = state.get("selected_options_for_generation", [])
        original_image_urls = [img["url"] for img in image_analyses]
        features_to_retain = state.get("original_features_to_retain", [])
        image_history = list(state.get("generated_image_history", []))

        if not selected_options or not original_image_urls:
            response = "Unable to generate options. Please go back and select options again."
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["image_sub_state"] = "design_conversation"
            updates["awaiting_user_input"] = True
            return updates

        print(f"[image_analysis] Generating {len(selected_options)} options in parallel...")

        # Generate all options in parallel with features to retain
        async def generate_option(option, perspective_idx=0):
            try:
                vision = {
                    "raw_input": f"Style: {option.get('style_name')}",
                    "ai_summary": option.get("description", ""),
                    "selected_option": option
                }
                # Use specific perspective if multiple images
                base_urls = [original_image_urls[perspective_idx]] if perspective_idx < len(original_image_urls) else original_image_urls
                url, prompt, desc = await generate_renovation_image(
                    original_image_urls=base_urls,
                    project_type=project_type,
                    extracted_data=extracted_data,
                    renovation_vision=vision,
                    feedback=None,
                    previous_prompt=None,
                    features_to_retain=features_to_retain,
                )
                return {
                    "style_name": option.get("style_name"),
                    "url": url,
                    "prompt": prompt,
                    "description": desc,
                    "perspective": perspective_idx,
                    "success": True
                }
            except Exception as e:
                print(f"[image_analysis] Failed to generate {option.get('style_name')}: {e}")
                return {
                    "style_name": option.get("style_name"),
                    "url": get_placeholder_image_url(),
                    "description": f"Failed to generate: {e}",
                    "perspective": perspective_idx,
                    "success": False
                }

        # Run all generations in parallel
        results = await asyncio.gather(*[generate_option(opt, 0) for opt in selected_options])

        # Add all successful results to image history
        for result in results:
            if result.get("success"):
                image_history = add_to_image_history(
                    history=image_history,
                    url=result["url"],
                    description=result.get("description", ""),
                    base_perspective=result.get("perspective", 0),
                    user_satisfied=None
                )

        # Store all generated options
        updates["generated_options"] = results
        updates["original_image_urls"] = original_image_urls
        updates["generated_image_history"] = image_history
        updates["image_sub_state"] = "confirming_proposal"

        # Build response with larger images
        response_parts = []

        for i, result in enumerate(results, 1):
            response_parts.append(f"**Option {i}: {result.get('style_name', 'Option')}**\n\n")
            response_parts.append(
                f'<img src="{result.get("url")}" style="width: 100%; max-width: 800px; '
                f'border-radius: 12px; margin: 8px 0;" />\n\n'
            )
            # Show full description (AI is instructed to keep it brief)
            if result.get("description") and result.get("success"):
                response_parts.append(f"{result.get('description', '')}\n\n")

        response_parts.append("---\n\n")
        response_parts.append("Which option do you prefer? Say **'option 1'** to continue, or request changes.")

        response = "".join(response_parts)
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # =========================================================================
    # CONFIRMING PROPOSAL STATE - User reviews generated image with smart conversation handling
    # =========================================================================
    elif sub_state == "confirming_proposal":
        image_history = list(state.get("generated_image_history", []))
        current_generated_url = state.get("generated_image_url", "")
        features_to_retain = state.get("original_features_to_retain", [])

        # Check if we're coming back from final_review with a pending regeneration
        pending_regeneration = state.get("_pending_regeneration")
        if pending_regeneration:
            print(f"[confirming_proposal] Handling pending regeneration from final_review: {pending_regeneration}")
            user_message = pending_regeneration
            # Clear the pending flag
            updates["_pending_regeneration"] = None

        if user_message:
            # Quick keyword-based pre-check for obvious change requests
            # This catches cases like "the floor should be tiles" that LLM might misclassify
            msg_lower = user_message.lower().strip()

            # Keywords that strongly indicate a change request
            change_keywords = [
                "should be", "should have", "add ", "change ", "make it", "make the",
                "i want", "put ", "use ", "replace", "remove ", "tiles", "marble",
                "wood", "carpet", "paint", "color", "darker", "lighter", "bigger",
                "smaller", "modern", "traditional", "floor", "wall", "ceiling",
                "let's add", "lets add", "can you add", "give me", "show me with"
            ]

            # Keywords that indicate pure approval (move_forward)
            approval_keywords = [
                "looks good", "look good", "perfect", "continue", "proceed",
                "i'm happy", "im happy", "that's good", "thats good", "great",
                "love it", "like it", "yes", "ok", "okay", "done", "finish"
            ]

            # Check if it's an obvious change request
            is_obvious_change = any(kw in msg_lower for kw in change_keywords)
            is_pure_approval = any(kw in msg_lower for kw in approval_keywords) and not is_obvious_change

            # If obvious change request, skip classifier and go straight to generation
            if is_obvious_change:
                print(f"[confirming_proposal] Keyword pre-check: obvious change request detected")
                conversation_type = "generation_request"
                conv_type = {
                    "conversation_type": "generation_request",
                    "confidence": 0.95,
                    "extracted_question": None,
                    "referenced_image_position": None,
                    "generation_changes": user_message  # Use full message as the change request
                }
            elif is_pure_approval:
                print(f"[confirming_proposal] Keyword pre-check: pure approval detected")
                conversation_type = "move_forward"
                conv_type = {
                    "conversation_type": "move_forward",
                    "confidence": 0.95,
                    "extracted_question": None,
                    "referenced_image_position": None,
                    "generation_changes": None
                }
            else:
                # Use UNIFIED classifier for ambiguous cases
                context = (
                    f"User is reviewing a generated renovation preview. "
                    f"They have {len(image_history)} generated images in history. "
                    f"Current image: {current_generated_url}"
                )
                unified_result = await unified_classify(
                    user_message=user_message,
                    context=context,
                    has_generated_images=len(image_history) > 0
                )

                conversation_type = unified_result.get("conversation_type", "clarify")
                # Also extract relevant content for use below
                conv_type = {
                    "conversation_type": conversation_type,
                    "confidence": unified_result.get("confidence", 0.5),
                    "extracted_question": unified_result.get("extracted_content", {}).get("questions", [None])[0] if unified_result.get("extracted_content", {}).get("questions") else None,
                    "referenced_image_position": unified_result.get("extracted_content", {}).get("referenced_image_position"),
                    "generation_changes": unified_result.get("extracted_content", {}).get("generation_changes")
                }

            print(f"[confirming_proposal] Conversation type: {conversation_type} | "
                  f"confidence: {conv_type.get('confidence')}")

            # Handle DISCUSSION - Answer questions about images without generating
            if conversation_type == "discussion":
                question = conv_type.get("extracted_question") or user_message
                # Determine which image to analyze
                image_to_analyze = current_generated_url or (image_analyses[0]["url"] if image_analyses else None)

                if image_to_analyze:
                    answer = await answer_image_question(
                        question=question,
                        image_url=image_to_analyze,
                        context=f"This is a {project_type} renovation preview"
                    )
                    response = f"{answer}\n\n---\n\nAnything else you'd like to know, or are you ready to continue?"
                else:
                    response = "I don't have an image to analyze. Would you like me to generate a renovation preview?"

                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

            # Handle REFERENCE_PREVIOUS - User wants to use/see a previous image
            elif conversation_type == "reference_previous":
                ref = conv_type.get("referenced_image_position") or "previous"
                referenced_image = get_image_from_history(image_history, str(ref))

                if referenced_image:
                    # Mark this image as user satisfied
                    for img in image_history:
                        if img.get("url") == referenced_image.get("url"):
                            img["user_satisfied"] = True
                        else:
                            img["user_satisfied"] = False

                    updates["generated_image_history"] = image_history
                    updates["selected_final_image_url"] = referenced_image.get("url")
                    updates["generated_image_url"] = referenced_image.get("url")

                    response = (
                        f'<img src="{referenced_image.get("url")}" style="width: 100%; max-width: 800px; '
                        f'border-radius: 12px; margin: 16px 0;" />\n\n'
                        f"Got it! I've selected this design. Say **'continue'** to proceed to review."
                    )
                else:
                    response = f"I couldn't find that image. You have {len(image_history)} generated images. Which one would you like?"

                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

            # Handle MOVE_FORWARD - Show before/after review and proceed
            elif conversation_type == "move_forward":
                # Mark current image as user satisfied
                if image_history and current_generated_url:
                    for img in image_history:
                        if img.get("url") == current_generated_url:
                            img["user_satisfied"] = True
                    updates["generated_image_history"] = image_history

                updates["selected_final_image_url"] = current_generated_url

                # Show before/after comparison
                original_url = image_analyses[0]["url"] if image_analyses else None
                brief_summary = state.get("brief_room_summary", "Your space")

                if original_url and current_generated_url:
                    response = (
                        f"## Before & After\n\n"
                        f'<div style="display: flex; gap: 16px; flex-wrap: wrap;">\n'
                        f'<div style="flex: 1; min-width: 300px;">\n'
                        f'<p><strong>Before:</strong></p>\n'
                        f'<img src="{original_url}" style="width: 100%; border-radius: 12px;" />\n'
                        f'</div>\n'
                        f'<div style="flex: 1; min-width: 300px;">\n'
                        f'<p><strong>After:</strong></p>\n'
                        f'<img src="{current_generated_url}" style="width: 100%; border-radius: 12px;" />\n'
                        f'</div>\n'
                        f'</div>\n\n'
                        f"Ready to proceed to cost estimation?"
                    )
                else:
                    response = "Ready to proceed to cost estimation?"

                # Move to final review stage
                updates["current_stage"] = "final_review"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates

            # Handle GENERATION_REQUEST - Regenerate with changes (supports multi-image)
            elif conversation_type == "generation_request":
                raw_feedback = conv_type.get("generation_changes") or user_message
                # Ensure feedback is always a string (LLM might return dict)
                if isinstance(raw_feedback, dict):
                    feedback_content = json.dumps(raw_feedback) if raw_feedback else user_message
                elif isinstance(raw_feedback, list):
                    feedback_content = "; ".join(str(item) for item in raw_feedback)
                else:
                    feedback_content = str(raw_feedback) if raw_feedback else user_message

                stored_original_urls = state.get("original_image_urls", [])
                if not stored_original_urls:
                    stored_original_urls = [img["url"] for img in image_analyses]

                # Check if we have multiple images and parse multi-image feedback
                generated_options = state.get("generated_options", [])
                num_current_images = len(generated_options) if generated_options else 1

                if num_current_images > 1:
                    # Parse which images user is referring to
                    multi_feedback = await parse_multi_image_feedback(feedback_content, num_current_images)
                    print(f"[confirming_proposal] Multi-image feedback: {multi_feedback}")

                    if multi_feedback.get("references_multiple_images") or multi_feedback.get("applies_to_all"):
                        # Regenerate specific images in parallel
                        async def regenerate_single_image(img_idx: int, specific_feedback: str):
                            try:
                                # Get base image for this index
                                base_url = generated_options[img_idx].get("url") if img_idx < len(generated_options) else stored_original_urls[0]
                                url, prompt, desc = await generate_renovation_image(
                                    original_image_urls=[base_url],
                                    project_type=project_type,
                                    extracted_data=extracted_data,
                                    renovation_vision=renovation_vision,
                                    feedback=[specific_feedback],
                                    previous_prompt=generated_options[img_idx].get("prompt") if img_idx < len(generated_options) else None,
                                    features_to_retain=features_to_retain,
                                )
                                return {"position": img_idx + 1, "url": url, "description": desc, "success": True}
                            except Exception as e:
                                print(f"[confirming_proposal] Failed to regenerate image {img_idx + 1}: {e}")
                                return {"position": img_idx + 1, "url": None, "description": str(e), "success": False}

                        # Build regeneration tasks
                        regen_tasks = []
                        if multi_feedback.get("applies_to_all"):
                            # Apply general feedback to all images
                            general_fb = multi_feedback.get("general_feedback") or feedback_content
                            for i in range(num_current_images):
                                regen_tasks.append(regenerate_single_image(i, general_fb))
                        else:
                            # Apply specific feedback to specific images
                            for fb_item in multi_feedback.get("image_feedback", []):
                                img_pos = fb_item.get("image_position", 1) - 1  # Convert to 0-indexed
                                specific_fb = fb_item.get("feedback", feedback_content)
                                if 0 <= img_pos < num_current_images:
                                    regen_tasks.append(regenerate_single_image(img_pos, specific_fb))

                        if regen_tasks:
                            # Run regenerations in parallel
                            results = await asyncio.gather(*regen_tasks)

                            # Update generated_options with new images
                            for result in results:
                                if result.get("success"):
                                    pos = result["position"] - 1
                                    if pos < len(generated_options):
                                        generated_options[pos]["url"] = result["url"]
                                        generated_options[pos]["description"] = result["description"]
                                    # Add to history
                                    image_history = add_to_image_history(
                                        history=image_history,
                                        url=result["url"],
                                        description=result["description"],
                                        base_perspective=pos,
                                        user_satisfied=None
                                    )

                            updates["generated_options"] = generated_options
                            updates["generated_image_history"] = image_history
                            updates["image_generation_feedback"] = [str(feedback_content)]

                            # Build response with updated images
                            response_parts = []
                            for i, opt in enumerate(generated_options, 1):
                                response_parts.append(f"**Image {i}: {opt.get('style_name', 'Option')}**\n\n")
                                response_parts.append(
                                    f'<img src="{opt.get("url")}" style="width: 100%; max-width: 800px; '
                                    f'border-radius: 12px; margin: 8px 0;" />\n\n'
                                )
                                if opt.get("description"):
                                    response_parts.append(f"{opt.get('description', '')}\n\n")

                            response_parts.append("---\n\n")
                            response_parts.append("How do these look now? Say **'continue'** to proceed, or request more changes.")

                            response = "".join(response_parts)
                            updates["messages"] = [{"role": "assistant", "content": response}]
                            updates["awaiting_user_input"] = True
                            return updates

                # Single image regeneration (original flow)
                # Detect regeneration mode: style_change vs iterative_refinement
                current_description = state.get("generation_description", "")
                mode_result = await detect_regeneration_mode(feedback_content, current_description)
                regen_mode = mode_result.get("mode", "iterative_refinement")

                print(f"[confirming_proposal] Regeneration mode: {regen_mode}")

                # If mode is "ask_user", we need clarification
                if regen_mode == "ask_user":
                    # Truncate for display
                    display_feedback = feedback_content[:200] + "..." if len(feedback_content) > 200 else feedback_content
                    response = (
                        f"I understood you want: *\"{display_feedback}\"*\n\n"
                        f"Would you like me to:\n"
                        f"- **Start fresh** with a completely different style\n"
                        f"- **Refine this design** with the specific changes\n"
                    )
                    updates["pending_feedback"] = str(feedback_content)  # Ensure string
                    updates["messages"] = [{"role": "assistant", "content": response}]
                    updates["awaiting_user_input"] = True
                    return updates

                # Get feedback list and base images (ensure all items are strings)
                existing_feedback = state.get("image_generation_feedback", [])
                feedback_list = [str(f) for f in existing_feedback]  # Ensure strings
                feedback_list.append(str(feedback_content))
                updates["image_generation_feedback"] = feedback_list

                last_generated_url = state.get("last_generated_image_url", "")
                stored_generation_prompt = state.get("generation_prompt", "")

                # Choose base image based on mode
                if regen_mode == "style_change":
                    base_image_urls = stored_original_urls
                    feedback_list = [str(feedback_content)]  # Reset with just new feedback as string
                    updates["image_generation_feedback"] = feedback_list
                else:
                    base_image_urls = [last_generated_url] if last_generated_url else stored_original_urls

                try:
                    new_url, new_prompt, new_description = await generate_renovation_image(
                        original_image_urls=base_image_urls,
                        project_type=project_type,
                        extracted_data=extracted_data,
                        renovation_vision=renovation_vision,
                        feedback=feedback_list,
                        previous_prompt=stored_generation_prompt if regen_mode != "style_change" else None,
                        features_to_retain=features_to_retain,
                    )

                    # Add to history
                    image_history = add_to_image_history(
                        history=image_history,
                        url=new_url,
                        description=new_description,
                        base_perspective=0,
                        user_satisfied=None
                    )

                    updates["generated_image_url"] = new_url
                    updates["last_generated_image_url"] = new_url
                    updates["generation_prompt"] = new_prompt
                    updates["generation_description"] = new_description
                    updates["generated_image_history"] = image_history

                    # Show full description (AI is instructed to keep it brief in prompt)
                    response = (
                        f'<img src="{new_url}" style="width: 100%; max-width: 800px; '
                        f'border-radius: 12px; margin: 16px 0;" />\n\n'
                        f"{new_description}\n\n"
                        f"How's this? Say **'continue'** when ready, or request more changes."
                    )
                except Exception as e:
                    print(f"[confirming_proposal] Regeneration failed: {e}")
                    response = f"I encountered an issue. Say **'continue'** to proceed or try a different request."

                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

            # Handle CLARIFY - User needs more info
            else:
                response = (
                    "I can help! You can:\n"
                    "- **Ask questions** about the image (e.g., 'what color is that wall?')\n"
                    "- **Request changes** (e.g., 'make the floor darker')\n"
                    "- **Reference previous designs** (e.g., 'go back to the first one')\n"
                    "- Say **'continue'** when you're happy with the design"
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

        # No message - prompt user
        response = "How does this look? Let me know if you'd like any changes, or say **'continue'** to proceed."
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # Fallback
    updates["messages"] = [{"role": "assistant", "content": "Something went wrong. Please try again."}]
    updates["awaiting_user_input"] = True
    return updates