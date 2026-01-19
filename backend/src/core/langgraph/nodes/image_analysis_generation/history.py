"""
Image history tracking functions.
"""

from datetime import datetime

from src.core.logger import get_logger

logger = get_logger(__name__)


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
        Updated history list. Returns original history on error.
    """
    try:
        if history is None:
            logger.warning("[add_to_image_history] history is None, initializing empty list")
            history = []

        if not isinstance(history, list):
            logger.error(f"[add_to_image_history] history is not a list: {type(history)}")
            return []

        if not url or not isinstance(url, str):
            logger.error(f"[add_to_image_history] Invalid URL: {url}")
            return history

        # Truncate description for storage
        safe_description = ""
        if description:
            try:
                safe_description = str(description)[:200]
            except Exception as e:
                logger.warning(f"[add_to_image_history] Error truncating description: {e}")
                safe_description = ""

        # Calculate position safely
        try:
            position = len(history) + 1
        except Exception as e:
            logger.warning(f"[add_to_image_history] Error calculating position: {e}")
            position = 1

        # Validate base_perspective
        if not isinstance(base_perspective, int):
            logger.warning(f"[add_to_image_history] Invalid base_perspective: {base_perspective}, using 0")
            base_perspective = 0

        new_entry = {
            "url": url,
            "description": safe_description,
            "position": position,
            "base_perspective": base_perspective,
            "user_satisfied": user_satisfied,
            "timestamp": datetime.now().isoformat()
        }

        updated_history = history + [new_entry]
        logger.debug(f"[add_to_image_history] Added entry at position {position}")
        return updated_history

    except Exception as e:
        logger.exception(f"[add_to_image_history] Unexpected error: {e}")
        return history if isinstance(history, list) else []


def get_image_from_history(history: list, reference: str) -> dict | None:
    """
    Get an image from history based on user reference.

    Args:
        history: Image history list
        reference: User's reference (e.g., "1", "first", "previous", "second")

    Returns:
        Image entry dict or None if not found or on error
    """
    try:
        if not history:
            logger.debug("[get_image_from_history] Empty history")
            return None

        if not isinstance(history, list):
            logger.error(f"[get_image_from_history] history is not a list: {type(history)}")
            return None

        if not reference or not isinstance(reference, str):
            logger.warning(f"[get_image_from_history] Invalid reference: {reference}")
            return None

        reference_lower = reference.lower().strip()

        if not reference_lower:
            logger.warning("[get_image_from_history] Empty reference after stripping")
            return None

        # Handle position numbers
        if reference_lower.isdigit():
            try:
                position = int(reference_lower)
                for img in history:
                    if not isinstance(img, dict):
                        logger.warning(f"[get_image_from_history] Invalid history entry: {type(img)}")
                        continue
                    if img.get("position") == position:
                        logger.debug(f"[get_image_from_history] Found image at position {position}")
                        return img
                logger.debug(f"[get_image_from_history] No image found at position {position}")
                return None
            except ValueError as e:
                logger.error(f"[get_image_from_history] Error converting reference to int: {e}")
                return None

        # Handle word references
        try:
            history_len = len(history)
            word_map = {
                "first": 1,
                "second": 2,
                "third": 3,
                "fourth": 4,
                "last": history_len,
                "previous": history_len - 1 if history_len > 1 else history_len,
                "latest": history_len
            }

            if reference_lower in word_map:
                position = word_map[reference_lower]
                if 0 < position <= history_len:
                    img = history[position - 1]
                    if isinstance(img, dict):
                        logger.debug(f"[get_image_from_history] Found image for '{reference_lower}' at position {position}")
                        return img
                    else:
                        logger.warning(f"[get_image_from_history] Invalid history entry at position {position}")
                        return None
                else:
                    logger.debug(f"[get_image_from_history] Position {position} out of range (1-{history_len})")
                    return None

            logger.debug(f"[get_image_from_history] No match for reference '{reference_lower}'")
            return None

        except Exception as e:
            logger.error(f"[get_image_from_history] Error processing word reference: {e}")
            return None

    except Exception as e:
        logger.exception(f"[get_image_from_history] Unexpected error: {e}")
        return None
