"""
Image generation functions for renovation previews.
"""

import uuid
from datetime import datetime

from src.core.logger import get_logger
from src.core.llm.provider import LLMProvider, LLMProviderError

logger = get_logger(__name__)
from src.core.langgraph.prompts import (
    build_image_generation_prompt,
    build_image_regeneration_prompt,
    build_edit_mode_prompt,
    build_selected_image_prompt,
)
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import (
    load_image_as_base64,
    GENERATED_IMAGES_DIR,
)
from src.core.langgraph.nodes.image_analysis_generation.intent_detection import (
    detect_edit_mode,
)


async def generate_renovation_image(
    original_image_urls: list[str],
    project_type: str,
    extracted_data: dict,
    renovation_vision: dict | None = None,
    feedback: list[str] | None = None,
    previous_prompt: str | None = None,
    features_to_retain: list[str] | None = None,
    visible_elements: dict | None = None,
    must_not_add: list[str] | None = None,
    image_scope: dict | None = None,
    selected_image_url: str | None = None,
    previous_changes: list[str] | None = None,
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
        features_to_retain: List of features to preserve in the renovation
        visible_elements: Dict of what's actually visible in the image
        must_not_add: List of things that should NOT be added during generation
        image_scope: Dict with frame_type, room_coverage_pct, camera_angle
        selected_image_url: URL of user-selected canvas image (for editing that specific image)
        previous_changes: List of changes made in previous generations (for edit mode context)

    Returns:
        Tuple of (image_url, generation_prompt, description)
        - image_url: API URL to access the generated image (e.g., /api/v1/files/generated/...)
        - generation_prompt: The prompt used for generation (for potential regeneration)
        - description: Text description of what changes were made

    Raises:
        Exception: If image generation fails
    """
    logger.info(f"[image_generation] Starting generation for {project_type} project...")

    # Log scope information for debugging
    if image_scope:
        logger.info(f"[image_generation] Image scope: {image_scope.get('frame_type', 'unknown')} (~{image_scope.get('room_coverage_pct', 100)}% coverage)")
    if must_not_add:
        logger.info(f"[image_generation] Must NOT add: {must_not_add[:3]}..." if len(must_not_add) > 3 else f"[image_generation] Must NOT add: {must_not_add}")

    # Ensure generated images directory exists
    try:
        GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as dir_error:
        logger.error(f"[image_generation] Failed to create generated images directory: {dir_error}", exc_info=True)
        raise Exception(f"File system error: Unable to create image storage directory") from dir_error

    # Determine which image to use as base
    # Priority: selected_image_url > original_image_urls[0]
    base_image_url = selected_image_url or (original_image_urls[0] if original_image_urls else None)
    if selected_image_url:
        logger.info(f"[image_generation] Using SELECTED canvas image as base: {selected_image_url}")
    else:
        logger.info(f"[image_generation] Using original image as base")

    # Build the generation prompt with intelligent edit mode detection
    edit_mode_result = None
    try:
        if feedback and previous_prompt:
            # Detect edit mode for intelligent prompt building
            feedback_text = feedback[0] if isinstance(feedback, list) and len(feedback) == 1 else (
                " ".join(feedback) if isinstance(feedback, list) else str(feedback)
            )

            try:
                edit_mode_result = await detect_edit_mode(
                    user_feedback=feedback_text,
                    previous_changes=previous_changes,
                    image_url=selected_image_url
                )

                edit_mode = edit_mode_result.get("edit_mode", "modify")
                logger.info(f"[image_generation] Edit mode detected: {edit_mode}")

                # Check if user approved (no regeneration needed)
                if edit_mode == "approve":
                    logger.info(f"[image_generation] User approved - no regeneration needed")
                    # Return the selected image as-is if available
                    if selected_image_url:
                        return selected_image_url, previous_prompt, "User approved the current design."
                    # Otherwise fall through to normal generation
            except LLMProviderError as llm_error:
                logger.error(f"[image_generation] LLM provider error during edit mode detection: {llm_error}", exc_info=True)
                # Fallback to modify mode
                edit_mode_result = {"edit_mode": "modify", "feedback_text": feedback_text}
            except Exception as edit_error:
                logger.error(f"[image_generation] Edit mode detection failed: {edit_error}", exc_info=True)
                # Fallback to modify mode
                edit_mode_result = {"edit_mode": "modify", "feedback_text": feedback_text}

            # Build prompt using the intelligent edit mode system
            try:
                generation_prompt = build_edit_mode_prompt(
                    base_prompt=previous_prompt,
                    edit_mode_result=edit_mode_result,
                    user_feedback=feedback_text
                )
            except Exception as prompt_error:
                logger.error(f"[image_generation] Failed to build edit mode prompt: {prompt_error}", exc_info=True)
                # Fallback to regeneration prompt
                generation_prompt = build_image_regeneration_prompt(
                    previous_prompt=previous_prompt,
                    feedback=feedback_text
                )
            logger.info(f"[image_generation] Regenerating with {edit_mode_result.get('edit_mode', 'modify')} mode: {feedback}")
        else:
            # Initial generation with features to retain and scope constraints
            try:
                generation_prompt = build_image_generation_prompt(
                    project_type=project_type,
                    extracted_data=extracted_data,
                    renovation_vision=renovation_vision,
                    features_to_retain=features_to_retain,
                    visible_elements=visible_elements,
                    must_not_add=must_not_add,
                    image_scope=image_scope,
                )
            except Exception as prompt_error:
                logger.error(f"[image_generation] Failed to build generation prompt: {prompt_error}", exc_info=True)
                raise Exception(f"Failed to prepare image generation instructions: {str(prompt_error)}") from prompt_error
            logger.info(f"[image_generation] Initial generation (retaining: {features_to_retain}, scope: {image_scope})")
    except Exception as e:
        logger.error(f"[image_generation] Unexpected error in prompt preparation: {e}", exc_info=True)
        raise

    # Load the base image as base64 for input
    # Priority: selected_image_url > original_image_urls[0]
    if not base_image_url:
        logger.error("[image_generation] No base image URL provided for generation")
        raise ValueError("No image provided for generation (need either selected_image_url or original_image_urls)")

    try:
        image_data_url = await load_image_as_base64(base_image_url)
    except FileNotFoundError as file_error:
        logger.error(f"[image_generation] Image file not found: {base_image_url}", exc_info=True)
        raise Exception(f"Image file not found: {base_image_url}. Please upload the image again.") from file_error
    except Exception as load_error:
        logger.error(f"[image_generation] Failed to load image {base_image_url}: {load_error}", exc_info=True)
        raise Exception(f"Failed to load image for processing: {str(load_error)}") from load_error

    # Prepare messages for VGM with transformation-focused system message
    system_message = """You are an IMAGE TRANSFORMATION specialist, NOT a room designer.

Your task is to TRANSFORM the provided image by applying renovation changes while STRICTLY PRESERVING:
- The EXACT camera angle and perspective shown in the input image
- The room boundaries and walls visible in the frame
- The architectural structure (window/door positions if any exist)
- The overall room proportions and framing

CRITICAL CONSTRAINTS - You must NOT:
- Add windows, doors, or openings that don't exist in the original image
- Add furniture, beds, or decor items that aren't in the original (unless explicitly requested)
- Change the room's architectural structure or layout
- Expand the visible area beyond what's shown in the original frame
- Generate a different view angle or perspective than the input
- Imagine or hallucinate elements not visible in the input image

ONLY modify: surface finishes (floors, walls, ceilings), paint colors, fixtures, and explicitly requested changes.

The output image MUST be recognizable as the SAME SPACE from the SAME ANGLE as the input."""

    messages = [
        {
            "role": "system",
            "content": system_message
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": generation_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}}
            ]
        }
    ]

    # Determine temperature based on image scope
    # Lower temperature for partial views to be more faithful to original
    if image_scope:
        coverage = image_scope.get("room_coverage_pct", 100)
        frame_type = image_scope.get("frame_type", "full_room")

        if frame_type == "corner_view" or coverage <= 30:
            temperature = 0.3  # Very faithful to original for corner views
            logger.info(f"[image_generation] Using low temperature (0.3) for corner/partial view")
        elif frame_type == "wall_view" or coverage <= 60:
            temperature = 0.4  # Moderately faithful for wall views
            logger.info(f"[image_generation] Using medium temperature (0.4) for wall view")
        else:
            temperature = 0.5  # Standard for full room views
    else:
        temperature = 0.5  # Default

    # Generate image using VGM
    try:
        provider = LLMProvider.for_vgm()
    except Exception as provider_error:
        logger.error(f"[image_generation] Failed to initialize VGM provider: {provider_error}", exc_info=True)
        raise Exception(f"Image generation service is not available: {str(provider_error)}") from provider_error

    try:
        result = await provider.generate_image(
            messages=messages,
            temperature=temperature,
            max_tokens=1024
        )

        # Validate result structure
        if not isinstance(result, dict):
            logger.error(f"[image_generation] Invalid result type from VGM: {type(result)}")
            raise Exception("Image generation returned invalid response format")

        if "image_data" not in result:
            logger.error(f"[image_generation] Missing image_data in VGM result: {result.keys()}")
            raise Exception("Image generation did not return image data")

        image_data = result["image_data"]
        mime_type = result.get("mime_type", "image/png")
        description = result.get("description", "")  # Text description of changes

        # Validate image data
        if not image_data or len(image_data) == 0:
            logger.error("[image_generation] Empty image data received from VGM")
            raise Exception("Image generation returned empty data")

        # Determine file extension from mime type
        ext_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
        }
        ext = ext_map.get(mime_type, ".png")

        # Generate unique filename
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]
            filename = f"renovation_{timestamp}_{unique_id}{ext}"
            file_path = GENERATED_IMAGES_DIR / filename
        except Exception as filename_error:
            logger.error(f"[image_generation] Failed to generate filename: {filename_error}", exc_info=True)
            raise Exception("Failed to prepare image storage") from filename_error

        # Save the image
        try:
            with open(file_path, "wb") as f:
                f.write(image_data)
        except OSError as save_error:
            logger.error(f"[image_generation] Failed to save image to {file_path}: {save_error}", exc_info=True)
            raise Exception(f"Failed to save generated image: {str(save_error)}") from save_error
        except Exception as write_error:
            logger.error(f"[image_generation] Unexpected error writing image: {write_error}", exc_info=True)
            raise Exception(f"Failed to write image file: {str(write_error)}") from write_error

        logger.info(f"[image_generation] Saved generated image to {file_path}")
        logger.info(f"[image_generation] Description: {description[:150]}..." if len(description) > 150 else f"[image_generation] Description: {description}")

        # Return API URL, prompt, and description
        api_url = f"/api/v1/files/generated/{filename}"

        return api_url, generation_prompt, description

    except LLMProviderError as llm_error:
        logger.error(f"[image_generation] LLM provider error during image generation: {llm_error}", exc_info=True)
        raise Exception(f"Image generation service error: {str(llm_error)}. Please try again or contact support if the issue persists.") from llm_error
    except Exception as e:
        # Check if it's already a wrapped exception
        if "Failed to" in str(e):
            raise
        logger.error(f"[image_generation] Unexpected error during image generation: {e}", exc_info=True)
        raise Exception(f"Failed to generate renovation image: {str(e)}") from e
