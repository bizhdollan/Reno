"""
Prompts for image generation in the renovation workflow.
"""


def build_image_generation_prompt(
    project_type: str,
    extracted_data: dict,
    renovation_vision: dict | None = None,
    features_to_retain: list[str] | None = None,
) -> str:
    """
    Build a comprehensive prompt for generating renovation preview images.
    Uses 2-step structure: 1) Describe changes, 2) Generate image
    This ensures the model returns both text description and generated image.

    Args:
        project_type: Type of renovation (e.g., "bathroom", "kitchen", "bedroom")
        extracted_data: Dictionary containing materials, measurements, colors, fixtures, etc.
        renovation_vision: Optional user vision with style preferences, materials, specific changes

    Returns:
        Formatted prompt string for image generation
    """
    # Start with 2-step instruction header
    prompt_parts = [
        f"# {project_type.title()} Renovation",
        "",
        "## Current Space Details",
        ""
    ]

    # Add extracted data details
    if extracted_data.get("measurements"):
        measurements = extracted_data["measurements"]
        prompt_parts.append("**Room Dimensions:**")
        if measurements.get("room_width_ft") and measurements.get("room_length_ft"):
            prompt_parts.append(f"- {measurements['room_width_ft']} × {measurements['room_length_ft']} ft")
        if measurements.get("room_height_ft"):
            prompt_parts.append(f"- Ceiling height: {measurements['room_height_ft']} ft")
        if measurements.get("area_sqft"):
            prompt_parts.append(f"- Total area: {measurements['area_sqft']} sq ft")
        prompt_parts.append("")

    if extracted_data.get("materials"):
        materials = extracted_data["materials"]
        prompt_parts.append("**Current Materials:**")
        for mat in materials:
            mat_desc = f"- {mat.get('name', 'Unknown')}: {mat.get('type', 'N/A')}"
            if mat.get('finish'):
                mat_desc += f", {mat['finish']} finish"
            prompt_parts.append(mat_desc)
        prompt_parts.append("")

    if extracted_data.get("colors"):
        colors = extracted_data["colors"]
        prompt_parts.append("**Current Colors:**")
        for color in colors:
            prompt_parts.append(f"- {color.get('element', 'Unknown')}: {color.get('color', 'N/A')}")
        prompt_parts.append("")

    if extracted_data.get("fixtures"):
        fixtures = extracted_data["fixtures"]
        prompt_parts.append("**Current Fixtures:**")
        for fix in fixtures[:5]:  # Limit to avoid too long prompts
            prompt_parts.append(f"- {fix.get('name', 'Unknown')}: {fix.get('type', 'N/A')}")
        prompt_parts.append("")

    if extracted_data.get("style", {}).get("overall_style"):
        prompt_parts.append(f"**Current Style:** {extracted_data['style']['overall_style']}")
        prompt_parts.append("")

    # Add renovation vision if provided
    if renovation_vision:
        prompt_parts.append("## Renovation Vision")
        prompt_parts.append("")

        if renovation_vision.get("ai_summary"):
            prompt_parts.append(f"**Summary:** {renovation_vision['ai_summary']}")
            prompt_parts.append("")

        if renovation_vision.get("style_preferences"):
            prompt_parts.append(f"**Target Style:** {renovation_vision['style_preferences']}")

        if renovation_vision.get("material_preferences"):
            prompt_parts.append(f"**Materials:** {renovation_vision['material_preferences']}")

        if renovation_vision.get("specific_changes"):
            prompt_parts.append(f"**Specific Changes:** {renovation_vision['specific_changes']}")

        if renovation_vision.get("additional_notes"):
            prompt_parts.append(f"**Notes:** {renovation_vision['additional_notes']}")

        prompt_parts.append("")

    # CRITICAL: Features to retain (prevent hallucination/loss of important elements)
    if features_to_retain:
        prompt_parts.extend([
            "## MUST RETAIN (DO NOT REMOVE OR ALTER)",
            "",
            "The following features MUST be preserved in the renovation:",
        ])
        for feature in features_to_retain:
            prompt_parts.append(f"- {feature}")
        prompt_parts.append("")

    # CRITICAL: 2-step structure for text + image output
    prompt_parts.extend([
        "## Your Task (2 Steps)",
        "",
        "**Step 1: Describe changes BRIEFLY**",
        "Write a short description (3-5 bullet points max) of the key visible changes:",
        "• One line per change, focusing on what's most impactful",
        "• Example format: '• Flooring: dark wood → white marble'",
        "• Keep total description under 500 characters",
        "",
        "**Step 2: GENERATE THE RENOVATED IMAGE**",
        "Create a photorealistic rendering showing these changes.",
        "Requirements:",
        "- PRESERVE all features listed in 'MUST RETAIN' section",
        "- Keep original room layout, proportions, and perspective",
        "- Professional architectural visualization quality",
        "- Realistic lighting matching the original"
    ])

    return "\n".join(prompt_parts)


def build_image_regeneration_prompt(
    original_prompt: str,
    feedback: str | list[str]
) -> str:
    """
    Build a prompt for regenerating an image based on user feedback.

    Args:
        original_prompt: The original generation prompt
        feedback: User feedback (string or list of feedback strings)

    Returns:
        Updated prompt incorporating feedback
    """
    if isinstance(feedback, list):
        feedback_text = "\n".join([f"- {f}" for f in feedback])
    else:
        feedback_text = feedback

    return f"""{original_prompt}

## User Feedback / Requested Changes

{feedback_text}

**Step 1: Describe updates BRIEFLY (3-5 bullet points, under 500 chars)**
• List only the changes made based on feedback above
• Keep each point to one short line

**Step 2: GENERATE THE UPDATED IMAGE**
Regenerate the image incorporating these changes while maintaining all other aspects of the design."""
