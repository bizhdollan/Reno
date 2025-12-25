"""
Image generation functions for renovation previews.
"""

import uuid
from datetime import datetime

from src.core.llm.provider import LLMProvider
from src.core.langgraph.prompts import (
    build_image_generation_prompt,
    build_image_regeneration_prompt,
)
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import (
    load_image_as_base64,
    GENERATED_IMAGES_DIR,
)


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
