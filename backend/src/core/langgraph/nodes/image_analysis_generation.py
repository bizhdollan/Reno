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
from pathlib import Path

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


# Configuration
IMAGES_DIR = Path("images")


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
            lines.append(f'<img src="{img["url"]}" width="120" height="80" style="object-fit: cover; border-radius: 8px; display: inline-block; margin-right: 8px;" />')
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
            
            # Analyze all images
            image_analyses = await analyze_images_parallel(new_image_urls, project_type)
            updates["image_analyses"] = image_analyses
            
            # Merge into extracted_data
            extracted_data = merge_image_analyses_to_extracted(image_analyses)
            updates["extracted_data"] = extracted_data
            
            # Move to confirmation
            updates["image_sub_state"] = "confirming_extraction"
            
            # Format and display all extracted data
            display = format_extracted_data_for_display(extracted_data, image_analyses)
            
            response = (
                f"# Here's what I found in your images:\n\n"
                f"{display}\n"
                f"---\n\n"
                f"**Is this information correct?**\n\n"
                f"Let me know if anything needs to be added, removed, or corrected. "
                f"When everything looks good, say **'confirm'** to continue."
            )
        else:
            response = "Please upload one or more images of the space you want to renovate."
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # =========================================================================
    # CONFIRMING EXTRACTION STATE - User reviews/corrects data
    # =========================================================================
    elif sub_state == "confirming_extraction":
        if user_message:
            # Use AI to detect intent
            intent_result = await detect_confirmation_intent(
                user_message,
                "User is reviewing extracted data from their renovation images. They can confirm if correct or request corrections."
            )
            intent = intent_result.get("intent", "unclear")
            
            print(f"[image_analysis] Extraction confirmation intent: {intent} | confidence: {intent_result.get('confidence')}")
            
            if intent == "confirm":
                print("[image_analysis] User confirmed extraction. Moving to vision collection.")
                updates["image_sub_state"] = "collecting_vision"
                
                response = VISION_PROMPT
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates
            
            elif intent == "correction":
                # Apply correction using AI
                print(f"[image_analysis] Applying user correction: {user_message}")
                corrected_data = await apply_user_correction(
                    extracted_data,
                    user_message,
                    project_type
                )
                
                updates["extracted_data"] = corrected_data
                
                # Show updated data
                display = format_extracted_data_for_display(corrected_data, image_analyses)
                
                response = (
                    f"# Updated Information:\n\n"
                    f"{display}\n"
                    f"---\n\n"
                    f"Anything else to change? Say **'confirm'** when everything looks correct."
                )
                
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates
            
            else:  # unclear
                response = (
                    "I'm not sure what you'd like to do. Could you please:\n"
                    "- Say **'confirm'** if the information looks correct\n"
                    "- Or tell me what needs to be changed"
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates
        
        # No user message yet - show current data
        display = format_extracted_data_for_display(extracted_data, image_analyses)
        response = (
            f"# Extracted Information:\n\n"
            f"{display}\n"
            f"---\n\n"
            f"Please review and let me know if anything needs to be corrected."
        )
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # =========================================================================
    # COLLECTING VISION STATE - Optional renovation vision
    # =========================================================================
    elif sub_state == "collecting_vision":
        if user_message:
            # Use AI to detect intent
            intent_result = await detect_skip_or_vision_intent(user_message)
            intent = intent_result.get("intent", "unclear")
            
            print(f"[image_analysis] Vision intent: {intent} | confidence: {intent_result.get('confidence')}")
            
            if intent == "skip":
                print("[image_analysis] User skipped vision. Moving to generating.")
                updates["renovation_vision"] = None
                updates["image_sub_state"] = "generating"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates
            
            if intent == "done":
                print("[image_analysis] User done with vision. Moving to generating.")
                updates["image_sub_state"] = "generating"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates
            
            if intent == "provide_vision":
                # Analyze the vision input
                import json
                current_details = json.dumps(extracted_data, indent=2)[:500]
                vision_analysis = await analyze_vision_input(
                    user_message,
                    project_type,
                    current_details
                )
                
                # Store vision
                updates["renovation_vision"] = {
                    "raw_input": user_message,
                    "ai_summary": vision_analysis.get("summary", ""),
                    **vision_analysis.get("parsed_vision", {})
                }
                
                # Check if we need follow-up questions
                if not vision_analysis.get("is_clear") and vision_analysis.get("followup_questions"):
                    questions = vision_analysis["followup_questions"]
                    questions_text = "\n".join([f"- {q}" for q in questions[:3]])
                    
                    response = (
                        f"Thanks for sharing! I understood: **{vision_analysis.get('summary', user_message)}**\n\n"
                        f"A few quick questions to help with the estimate:\n{questions_text}\n\n"
                        f"Feel free to answer or say **'done'** to proceed."
                    )
                    updates["messages"] = [{"role": "assistant", "content": response}]
                    updates["awaiting_user_input"] = True
                    return updates
                else:
                    # Vision is clear, move to generating
                    updates["image_sub_state"] = "generating"
                    updates["awaiting_user_input"] = False
                    updates["messages"] = []
                    return updates
            
            else:  # unclear
                response = (
                    "I'm not sure what you'd like to do. You can:\n"
                    "- Share your renovation vision (style, materials, changes you want)\n"
                    "- Say **'skip'** to proceed without a specific vision\n"
                    "- Say **'done'** if you've finished sharing"
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates
        
        # First time in this state - show the vision prompt
        response = VISION_PROMPT
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # =========================================================================
    # GENERATING STATE - Generate proposal image
    # =========================================================================
    elif sub_state == "generating":
        # Simulate image generation with placeholder
        # TODO: Replace with actual image generation using extracted_data + renovation_vision + images
        import asyncio
        print("[image_analysis] Simulating image generation (5 second delay)...")
        await asyncio.sleep(5)  # Simulate generation time
        
        generated_url = get_placeholder_image_url()
        
        updates["generated_image_url"] = generated_url
        updates["image_sub_state"] = "confirming_proposal"
        
        # Build context message - only show vision if provided
        vision = state.get("renovation_vision")
        if vision and vision.get("ai_summary"):
            context = f"\n\nBased on your vision: *{vision['ai_summary']}*"
        else:
            context = ""
        
        response = (
            f"# Renovation Preview{context}\n\n"
            f"![Renovation Preview]({generated_url})\n\n"
            f"This is a preview of your renovation project. "
            f"In the full version, this would be an AI-generated visualization based on your images and preferences.\n\n"
            f"Say **'continue'** to proceed to the final review, or let me know if you have feedback."
        )
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # =========================================================================
    # CONFIRMING PROPOSAL STATE - User reviews generated image
    # =========================================================================
    elif sub_state == "confirming_proposal":
        if user_message:
            # Use AI to detect intent
            intent_result = await detect_proceed_intent(
                user_message,
                "User is reviewing a generated renovation preview image. They can proceed to final review or provide feedback."
            )
            intent = intent_result.get("intent", "unclear")
            
            print(f"[image_analysis] Proposal confirmation intent: {intent} | confidence: {intent_result.get('confidence')}")
            
            if intent == "proceed":
                updates["current_stage"] = "final_review"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates
            
            elif intent == "feedback":
                # Store feedback
                feedback = list(state.get("image_generation_feedback", []))
                feedback_content = intent_result.get("feedback_content") or user_message
                feedback.append(feedback_content)
                updates["image_generation_feedback"] = feedback
                
                response = (
                    f"I've noted your feedback: *\"{feedback_content}\"*\n\n"
                    f"In the full version, I would regenerate the image with these changes. "
                    f"For now, say **'continue'** to proceed to the final review."
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates
            
            else:  # unclear
                response = (
                    "I'm not sure what you'd like to do. You can:\n"
                    "- Say **'continue'** to proceed to the final review\n"
                    "- Or share any feedback about the preview"
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates
        
        # No message - prompt user
        response = "Please review the renovation preview and let me know if it looks good, or share any feedback."
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # Fallback
    updates["messages"] = [{"role": "assistant", "content": "Something went wrong. Please try again."}]
    updates["awaiting_user_input"] = True
    return updates