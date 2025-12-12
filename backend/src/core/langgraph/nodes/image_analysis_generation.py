"""
Image Analysis & Generation Node.

Handles the entire image analysis flow:
1. analyzing - Process uploaded images (parallel VLM calls)
2. confirming - Section-by-section confirmation with per-image display
3. generating - Generate preview image (placeholder for now)
4. image_confirmation - User reviews generated image
"""

import asyncio
import uuid
import base64
import httpx
from pathlib import Path

from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import (
    ProjectState, 
    ImageData, 
    ExtractedData,
    get_unconfirmed_sections,
    is_all_confirmed
)
from src.core.langgraph.utils import get_latest_user_message, parse_json


# Configuration
BACKEND_BASE_URL = "http://localhost:8000"
IMAGES_DIR = Path("images")

# Sections in order we want to confirm them
CONFIRMATION_SECTIONS_ORDER = ["materials", "measurements", "colors", "fixtures", "appliances", "style"]


# Comprehensive image analysis prompt
IMAGE_ANALYSIS_PROMPT = """You are a renovation expert analyzing an image for a {project_type} renovation project.

Analyze this image comprehensively and extract ALL renovation-relevant information in a single pass.

Extract the following (include only what you can actually see):

1. **Materials**: What materials are visible? (countertops, cabinets, flooring, walls, etc.)
   - For each: name, type/material, finish, condition (good/fair/poor)

2. **Measurements**: Estimate room/space dimensions if possible
   - Room width, length, height (in feet)
   - Total area estimate

3. **Colors**: What colors are present?
   - For each visible element: element name, color, finish (matte/glossy/etc.)

4. **Fixtures**: What fixtures are visible? (faucets, handles, lighting, etc.)
   - For each: name, type, style, condition

5. **Appliances**: What appliances are visible? (if applicable)
   - For each: name, type, brand if visible, condition

6. **Style & Condition**: Overall assessment
   - Overall style (modern, traditional, transitional, etc.)
   - Overall condition (excellent/good/fair/poor)
   - Estimated age of the space

Return JSON only with this structure:
{{
    "materials": [
        {{"name": "flooring", "type": "hardwood", "finish": "natural", "condition": "good"}}
    ],
    "measurements": {{
        "room_width_ft": 12,
        "room_length_ft": 10,
        "room_height_ft": 9,
        "area_sqft": 120,
        "notes": "estimated from image"
    }},
    "colors": [
        {{"element": "walls", "color": "white", "finish": "matte"}}
    ],
    "fixtures": [
        {{"name": "light fixture", "type": "pendant", "style": "modern", "condition": "good"}}
    ],
    "appliances": [],
    "style": {{
        "overall_style": "modern",
        "condition": "good",
        "age_estimate": "5-10 years"
    }}
}}

Only include sections where you can identify relevant items."""


CORRECTION_PARSE_PROMPT = """The user wants to correct some image analysis data.

We have {num_images} images analyzed. The user said: "{user_message}"

Determine:
1. Is this a confirmation (yes, looks good, correct, ok, etc.)?
2. Is this a correction/change request?
3. If correction, which image number (1, 2, 3, etc.) or "unclear"?
4. What property/field to change and to what value?

Return JSON:
{{
    "is_confirmation": true/false,
    "is_correction": true/false,
    "image_number": 1 or 2 or 3 or "unclear" or null,
    "field_to_change": "materials/colors/fixtures/style/measurements" or null,
    "item_to_change": "flooring/walls/etc" or null,
    "new_value": "the new value" or null,
    "needs_clarification": true/false
}}

Examples:
- "yes" -> is_confirmation=true
- "correct" -> is_confirmation=true
- "looks good" -> is_confirmation=true
- "ok" -> is_confirmation=true
- "image 2 flooring is hardwood" -> is_correction=true, image_number=2, field="materials", item="flooring", new_value="hardwood"
- "the walls are beige not white" -> is_correction=true, image_number="unclear", needs_clarification=true
"""


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


async def analyze_single_image(image_url: str, project_type: str, image_index: int) -> dict:
    """Analyze a single image. Returns dict with url, index, and analysis."""
    print(f"[image_analysis] Starting analysis for image {image_index + 1}: {image_url}")
    
    provider = LLMProvider.for_vlm()
    image_data_url = await load_image_as_base64(image_url)
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a renovation expert. Analyze images thoroughly. Return JSON only, no markdown."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": IMAGE_ANALYSIS_PROMPT.format(project_type=project_type)},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ],
        temperature=0.2,
        max_tokens=1500
    )
    
    try:
        analysis = parse_json(response)
    except:
        analysis = {}
    
    print(f"[image_analysis] Completed image {image_index + 1}: found {list(analysis.keys())}")
    
    return {
        "url": image_url,
        "index": image_index,
        "analysis": analysis
    }


async def analyze_images_parallel(image_urls: list[str], project_type: str) -> list[dict]:
    """Analyze multiple images in parallel."""
    tasks = [
        analyze_single_image(url, project_type, idx) 
        for idx, url in enumerate(image_urls)
    ]
    results = await asyncio.gather(*tasks)
    return sorted(results, key=lambda x: x["index"])


def format_image_analysis_for_display(image_analyses: list[dict], section: str) -> str:
    """Format per-image analysis for a specific section with thumbnail images."""
    lines = []
    
    for img_data in image_analyses:
        img_num = img_data["index"] + 1
        img_url = img_data["url"]
        analysis = img_data.get("analysis", {})
        section_data = analysis.get(section)
        
        if not section_data:
            continue
        
        # Image header with small thumbnail (using HTML for size control)
        lines.append(f"**Image {img_num}**")
        lines.append(f'<img src="{img_url}" width="150" height="100" style="object-fit: cover; border-radius: 8px;" />')
        lines.append("")
        
        # Format section data
        if section == "materials":
            for m in section_data:
                line = f"- **{m.get('name', 'Unknown')}**: {m.get('type', '?')}"
                if m.get('finish'):
                    line += f", {m['finish']} finish"
                if m.get('condition'):
                    line += f" ({m['condition']})"
                lines.append(line)
        
        elif section == "measurements":
            m = section_data
            lines.append(f"- Room: {m.get('room_width_ft', '?')} × {m.get('room_length_ft', '?')} ft")
            lines.append(f"- Height: {m.get('room_height_ft', '?')} ft")
            lines.append(f"- Area: {m.get('area_sqft', '?')} sq ft")
        
        elif section == "colors":
            for c in section_data:
                lines.append(f"- **{c.get('element', 'Unknown')}**: {c.get('color', '?')} ({c.get('finish', 'unknown')})")
        
        elif section == "fixtures":
            for f in section_data:
                lines.append(f"- **{f.get('name', 'Unknown')}**: {f.get('type', '?')} ({f.get('condition', '?')})")
        
        elif section == "appliances":
            for a in section_data:
                lines.append(f"- **{a.get('name', 'Unknown')}**: {a.get('type', '?')}")
        
        elif section == "style":
            s = section_data
            lines.append(f"- Style: {s.get('overall_style', 'Unknown')}")
            lines.append(f"- Condition: {s.get('condition', '?')}")
            lines.append(f"- Age: {s.get('age_estimate', '?')}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines).strip() if lines else "No data found for this section."


async def parse_user_correction(user_message: str, num_images: int) -> dict:
    """Parse user's correction or confirmation response."""
    # Quick check for obvious confirmations without LLM
    lower = user_message.lower().strip()
    if lower in ["yes", "correct", "ok", "okay", "looks good", "good", "right", "confirm", "y"]:
        return {"is_confirmation": True, "is_correction": False, "needs_clarification": False}
    
    provider = LLMProvider.for_llm()
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "Analyze user response to image analysis confirmation. Return JSON only."
            },
            {
                "role": "user",
                "content": CORRECTION_PARSE_PROMPT.format(
                    num_images=num_images,
                    user_message=user_message
                )
            }
        ],
        temperature=0.0,
        max_tokens=200
    )
    
    try:
        return parse_json(response)
    except:
        return {"is_confirmation": False, "is_correction": True, "needs_clarification": True}


def apply_correction_to_analysis(image_analyses: list[dict], image_index: int, 
                                  field: str, item: str, new_value: str) -> list[dict]:
    """Apply a correction to a specific image's analysis."""
    if image_index < 0 or image_index >= len(image_analyses):
        return image_analyses
    
    analysis = image_analyses[image_index].get("analysis", {})
    
    if field == "materials":
        for m in analysis.get("materials", []):
            if m.get("name", "").lower() == item.lower():
                m["type"] = new_value
                break
    
    elif field == "colors":
        for c in analysis.get("colors", []):
            if c.get("element", "").lower() == item.lower():
                c["color"] = new_value
                break
    
    elif field == "style":
        if item.lower() in ["style", "overall_style"]:
            analysis.get("style", {})["overall_style"] = new_value
        elif item.lower() == "condition":
            analysis.get("style", {})["condition"] = new_value
    
    return image_analyses


def get_sections_with_data(image_analyses: list[dict]) -> list[str]:
    """Get list of sections that have data across any image, in defined order."""
    sections_found = set()
    for img_data in image_analyses:
        analysis = img_data.get("analysis", {})
        for key in CONFIRMATION_SECTIONS_ORDER:
            if analysis.get(key):
                sections_found.add(key)
    
    # Return in defined order
    return [s for s in CONFIRMATION_SECTIONS_ORDER if s in sections_found]


def get_next_unconfirmed_section(sections_to_confirm: list[str], confirmation_status: dict) -> str | None:
    """Get the next section that hasn't been confirmed yet."""
    for section in sections_to_confirm:
        if not confirmation_status.get(section):
            return section
    return None


def get_placeholder_image_url() -> str:
    """Get URL for placeholder renovation preview image."""
    return "/api/v1/files/placeholder-renovation.jpg"


async def image_analysis_generation_node(state: ProjectState) -> dict:
    """
    Main image analysis and generation node.
    
    Handles sub-states:
    - analyzing: Process new images (parallel)
    - confirming: Section-by-section confirmation with per-image display
    - generating: Generate preview image
    - image_confirmation: User reviews generated image
    """
    sub_state = state.get("image_sub_state", "analyzing")
    messages = state.get("messages", [])
    user_message, new_image_urls = get_latest_user_message(messages)
    
    # Check for pending images from project_basics transition
    pending_images = state.get("_pending_images", [])
    if pending_images:
        new_image_urls = pending_images
    
    # Get persisted data from state
    image_analyses = state.get("image_analyses", [])
    confirmation_status = dict(state.get("confirmation_status", {}))
    sections_to_confirm = state.get("sections_to_confirm", [])
    current_section = state.get("current_confirmation_section")
    
    updates = {}
    
    # Clear pending images after using
    if pending_images:
        updates["_pending_images"] = []
    
    print(f"[image_analysis] SUB_STATE: {sub_state} | user_message={user_message!r} | new_images={len(new_image_urls)} | pending={len(pending_images)} | stored_analyses={len(image_analyses)}")
    
    # ===== ANALYZING STATE =====
    if sub_state == "analyzing":
        project_type = state.get("project_type", "renovation")
        
        if new_image_urls:
            print(f"[image_analysis] Processing {len(new_image_urls)} images in parallel...")
            
            # Analyze all images in parallel
            image_analyses = await analyze_images_parallel(new_image_urls, project_type)
            
            # Store per-image analyses
            updates["image_analyses"] = image_analyses
            
            # Get sections with data in order
            sections_to_confirm = get_sections_with_data(image_analyses)
            updates["sections_to_confirm"] = sections_to_confirm
            
            print(f"[image_analysis] Sections found: {sections_to_confirm}")
            
            # Move to confirmation
            updates["image_sub_state"] = "confirming"
            
            if sections_to_confirm:
                first_section = sections_to_confirm[0]
                updates["current_confirmation_section"] = first_section
                
                section_display = format_image_analysis_for_display(image_analyses, first_section)
                response = (
                    f"Here's what I found for **{first_section}** in your {len(image_analyses)} images:\n\n"
                    f"{section_display}\n"
                    f"Is this correct? Say 'yes' to confirm, or tell me what needs to be changed."
                )
            else:
                response = "I couldn't extract any renovation details from the images. Please upload clearer images."
        
        else:
            response = "Please upload one or more images of the space you want to renovate."
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # ===== CONFIRMING STATE =====
    elif sub_state == "confirming":
        print(f"[image_analysis] CONFIRMING: current_section={current_section} | sections={sections_to_confirm} | confirmed={confirmation_status}")
        
        if user_message and current_section:
            # Parse user's response
            num_images = len(image_analyses)
            parsed = await parse_user_correction(user_message, num_images)
            
            print(f"[image_analysis] User response parsed: {parsed}")
            
            if parsed.get("is_confirmation"):
                # Mark current section as confirmed
                confirmation_status[current_section] = True
                updates["confirmation_status"] = confirmation_status
                print(f"[image_analysis] Confirmed section: {current_section}")
                
            elif parsed.get("is_correction"):
                if parsed.get("needs_clarification") or parsed.get("image_number") == "unclear":
                    response = (
                        f"I have {num_images} images. Which image are you referring to? "
                        f"Please say something like 'image 1' or 'the first image'."
                    )
                    updates["messages"] = [{"role": "assistant", "content": response}]
                    updates["awaiting_user_input"] = True
                    return updates
                
                else:
                    # Apply correction
                    img_num = parsed.get("image_number")
                    if isinstance(img_num, int) and img_num >= 1:
                        image_analyses = apply_correction_to_analysis(
                            image_analyses,
                            img_num - 1,
                            parsed.get("field_to_change", ""),
                            parsed.get("item_to_change", ""),
                            parsed.get("new_value", "")
                        )
                        updates["image_analyses"] = image_analyses
                    
                    section_display = format_image_analysis_for_display(image_analyses, current_section)
                    response = (
                        f"Updated! Here's the revised **{current_section}**:\n\n"
                        f"{section_display}\n"
                        f"Is this correct now?"
                    )
                    updates["messages"] = [{"role": "assistant", "content": response}]
                    updates["awaiting_user_input"] = True
                    return updates
        
        # Find next unconfirmed section
        next_section = get_next_unconfirmed_section(sections_to_confirm, confirmation_status)
        
        print(f"[image_analysis] Next unconfirmed section: {next_section}")
        
        if next_section:
            updates["current_confirmation_section"] = next_section
            
            section_display = format_image_analysis_for_display(image_analyses, next_section)
            response = (
                f"Now let's review **{next_section}**:\n\n"
                f"{section_display}\n"
                f"Is this correct?"
            )
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
        else:
            # All sections confirmed - move to image generation
            print(f"[image_analysis] All sections confirmed! Moving to generating...")
            confirmation_status["all_confirmed"] = True
            updates["confirmation_status"] = confirmation_status
            updates["image_sub_state"] = "generating"
            updates["awaiting_user_input"] = False
            updates["messages"] = []
        
        return updates
    
    # ===== GENERATING STATE =====
    elif sub_state == "generating":
        generate_image_enabled = state.get("generate_image", False)
        
        if generate_image_enabled:
            generated_url = get_placeholder_image_url()
        else:
            generated_url = get_placeholder_image_url()
        
        updates["generated_image_url"] = generated_url
        updates["image_sub_state"] = "image_confirmation"
        
        response = (
            f"Here's a preview of your renovation:\n\n"
            f"![Renovation Preview]({generated_url})\n\n"
            f"Does this match your vision? Let me know if you'd like any changes, "
            f"or say 'continue' to proceed to the final review."
        )
        
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates
    
    # ===== IMAGE CONFIRMATION STATE =====
    elif sub_state == "image_confirmation":
        if user_message:
            lower = user_message.lower()
            
            if any(w in lower for w in ["continue", "proceed", "yes", "good", "looks good", "perfect", "ok", "okay"]):
                updates["current_stage"] = "final_review"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
            else:
                feedback = list(state.get("image_generation_feedback", []))
                feedback.append(user_message)
                updates["image_generation_feedback"] = feedback
                
                response = (
                    f"I've noted your feedback: \"{user_message}\"\n\n"
                    f"In the full version, I would regenerate the image with these changes. "
                    f"For now, please say 'continue' to proceed to the final review."
                )
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
        else:
            response = "Please review the renovation preview and let me know if it looks good."
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
        
        return updates
    
    # Default fallback
    updates["messages"] = [{"role": "assistant", "content": "Something went wrong. Please try again."}]
    updates["awaiting_user_input"] = True
    return updates