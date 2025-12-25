"""
Image history tracking functions.
"""

from datetime import datetime


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
