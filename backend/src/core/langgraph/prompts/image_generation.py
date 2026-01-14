"""
Prompts for image generation in the renovation workflow.
"""


def build_image_generation_prompt(
    project_type: str,
    extracted_data: dict,
    renovation_vision: dict | None = None,
    features_to_retain: list[str] | None = None,
    visible_elements: dict | None = None,
    must_not_add: list[str] | None = None,
    image_scope: dict | None = None,
) -> str:
    """
    Build a comprehensive prompt for generating renovation preview images.
    Uses 2-step structure: 1) Describe changes, 2) Transform image

    IMPORTANT: This prompt is structured to PREVENT hallucination by:
    1. Using "Transform" language instead of "Create"
    2. Placing constraints AFTER task description (VGM prioritizes later instructions)
    3. Including explicit "DO NOT ADD" constraints
    4. Adding scope constraints for partial/corner views

    Args:
        project_type: Type of renovation (e.g., "bathroom", "kitchen", "bedroom")
        extracted_data: Dictionary containing materials, measurements, colors, fixtures, etc.
        renovation_vision: Optional user vision with style preferences, materials, specific changes
        features_to_retain: List of features to preserve in the renovation
        visible_elements: Dict of what's actually visible in the image (walls, floor, windows, etc.)
        must_not_add: List of things that should NOT be added (e.g., "windows", "furniture")
        image_scope: Dict with frame_type, room_coverage_pct, camera_angle

    Returns:
        Formatted prompt string for image generation
    """
    prompt_parts = [
        f"# {project_type.title()} Renovation - IMAGE TRANSFORMATION",
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
        prompt_parts.append("## Renovation Changes to Apply")
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

    # TASK DESCRIPTION - This comes BEFORE constraints (VGM prioritizes later instructions)
    prompt_parts.extend([
        "## Your Task (2 Steps)",
        "",
        "**Step 1: Describe changes BRIEFLY**",
        "Write a short description (3-5 bullet points max) of the key visible changes:",
        "• One line per change, focusing on what's most impactful",
        "• Example format: '• Flooring: dark wood → white marble'",
        "• Keep total description under 500 characters",
        "",
        "**Step 2: TRANSFORM THE IMAGE**",
        "Transform THIS EXACT IMAGE by applying the renovation changes above.",
        "This is an IMAGE TRANSFORMATION task, NOT image generation.",
        "The output must show the SAME SPACE from the SAME ANGLE with renovated surfaces.",
        ""
    ])

    # SCOPE CONSTRAINTS (for partial/corner views) - placed strategically before final constraints
    if image_scope:
        frame_type = image_scope.get("frame_type", "full_room")
        coverage = image_scope.get("room_coverage_pct", 100)

        if frame_type == "corner_view" or coverage <= 30:
            prompt_parts.extend([
                "## SCOPE CONSTRAINT - CORNER VIEW",
                "",
                f"This is a CORNER VIEW showing only ~{coverage}% of the room.",
                "- Transform ONLY this visible corner area",
                "- DO NOT expand to show other parts of the room",
                "- DO NOT imagine what's outside the frame",
                "- Maintain the EXACT camera angle and framing",
                ""
            ])
        elif frame_type == "wall_view" or coverage <= 60:
            prompt_parts.extend([
                "## SCOPE CONSTRAINT - PARTIAL VIEW",
                "",
                f"This is a PARTIAL VIEW showing ~{coverage}% of the room.",
                "- Transform only the visible portion",
                "- DO NOT expand the visible area",
                "- Maintain the exact camera perspective",
                ""
            ])

    # CRITICAL CONSTRAINTS - Placed at END where VGM pays most attention
    prompt_parts.extend([
        "## CRITICAL CONSTRAINTS (MUST FOLLOW)",
        "",
        "1. PRESERVE the EXACT camera angle shown in the input image",
        "2. PRESERVE room boundaries - do NOT expand the visible area",
        "3. ONLY MODIFY: surface finishes (floors, walls, ceilings), paint, fixtures",
        "4. The output MUST look like the SAME ROOM from the SAME ANGLE",
        ""
    ])

    # Features to retain - now positioned after constraints for reinforcement
    if features_to_retain:
        prompt_parts.extend([
            "## Elements to PRESERVE (from original image):",
        ])
        for feature in features_to_retain:
            prompt_parts.append(f"- {feature}")
        prompt_parts.append("")

    # EXPLICIT NEGATIVE CONSTRAINTS - Critical for preventing hallucination
    prompt_parts.append("## DO NOT ADD (these are NOT in the original image):")

    if must_not_add:
        for item in must_not_add:
            prompt_parts.append(f"- {item}")
    else:
        # Default negative constraints if none provided
        prompt_parts.extend([
            "- Do NOT add windows that don't exist in the original",
            "- Do NOT add doors that don't exist in the original",
            "- Do NOT add furniture unless specifically requested",
            "- Do NOT add beds, couches, or large items not in original",
            "- Do NOT change the room's architectural structure",
        ])

    prompt_parts.append("")

    # RENOVATION VS STAGING DISTINCTION
    # Check if user explicitly mentioned furniture/staging in their vision
    furniture_keywords = ["furniture", "bed", "couch", "sofa", "chair", "table", "desk", "dresser",
                         "nightstand", "bookshelf", "rug", "curtain", "staging", "decorated",
                         "furnish", "decorate"]

    vision_text = ""
    if renovation_vision:
        vision_text = " ".join([
            str(renovation_vision.get("raw_input", "")),
            str(renovation_vision.get("ai_summary", "")),
            str(renovation_vision.get("specific_changes", "")),
            str(renovation_vision.get("additional_notes", ""))
        ]).lower()

    user_requested_furniture = any(keyword in vision_text for keyword in furniture_keywords)

    if not user_requested_furniture:
        prompt_parts.extend([
            "## STAGING CONSTRAINT",
            "The user has NOT requested furniture or staging.",
            "Apply RENOVATION changes only (floors, walls, ceilings, fixtures, paint).",
            "Do NOT add furniture, beds, rugs, curtains, or decorative items.",
            "Show the renovated EMPTY SPACE as it would appear after construction.",
            ""
        ])

    # Final reinforcement
    prompt_parts.extend([
        "## FINAL REMINDER",
        "Transform the PROVIDED image. The output should be immediately recognizable",
        "as the SAME SPACE with renovated surfaces, NOT a completely different room."
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


def build_edit_mode_prompt(
    base_prompt: str,
    edit_mode_result: dict,
    user_feedback: str
) -> str:
    """
    Build a prompt dynamically based on the detected edit mode.

    This creates targeted prompts for different edit operations:
    - add: Focuses on adding new elements while preserving existing
    - modify: Focuses on changing specific elements
    - remove: Explicitly instructs to remove elements
    - correct: Addresses AI hallucination by removing unwanted elements

    Args:
        base_prompt: The base generation prompt
        edit_mode_result: Result from detect_edit_mode() function
        user_feedback: The user's original feedback

    Returns:
        Formatted prompt string optimized for the edit operation
    """
    edit_mode = edit_mode_result.get("edit_mode", "modify")
    elements = edit_mode_result.get("elements", [])
    sub_operations = edit_mode_result.get("sub_operations", [])
    prompt_strategy = edit_mode_result.get("prompt_strategy", "replacement")

    # Build element list string
    elements_str = ", ".join(elements) if elements else "the mentioned elements"

    if edit_mode == "add" or prompt_strategy == "additive":
        return f"""{base_prompt}

## ADDITIVE EDIT REQUEST

User wants to ADD: {user_feedback}

**TASK: Add the following elements while preserving EVERYTHING else:**
{chr(10).join(f'- ADD: {el}' for el in elements) if elements else f'- ADD: {user_feedback}'}

**Step 1: Describe ONLY the additions (2-3 bullet points)**
• List each new element being added
• Keep descriptions brief

**Step 2: GENERATE IMAGE with additions**
- Add the requested new elements
- PRESERVE all existing renovations and design choices
- Maintain the same camera angle and room structure
- Do NOT change anything that wasn't specifically mentioned"""

    elif edit_mode == "remove" or prompt_strategy == "removal":
        return f"""{base_prompt}

## REMOVAL EDIT REQUEST

User wants to REMOVE: {user_feedback}

**TASK: Remove the following elements completely:**
{chr(10).join(f'- REMOVE: {el}' for el in elements) if elements else f'- REMOVE: {user_feedback}'}

**CRITICAL CONSTRAINT - DO NOT INCLUDE:**
{chr(10).join(f'- {el} (USER EXPLICITLY REQUESTED REMOVAL)' for el in elements) if elements else f'- {user_feedback}'}

**Step 1: Describe the removal (1-2 bullet points)**
• Note what was removed
• Note what replaced it (if applicable - usually original/empty space)

**Step 2: GENERATE IMAGE without the removed elements**
- The removed elements should NOT appear in the output
- Replace removed elements with appropriate alternatives (original wall, empty space, etc.)
- PRESERVE all other renovations and design choices
- Maintain the same camera angle and room structure"""

    elif edit_mode == "correct" or prompt_strategy == "correction":
        return f"""{base_prompt}

## CORRECTION REQUEST - AI MISTAKE FIX

The previous generation included elements that were NOT requested: {user_feedback}

**TASK: Remove the AI-generated mistake and regenerate correctly:**
{chr(10).join(f'- REMOVE (MISTAKE): {el} - THIS WAS NOT REQUESTED' for el in elements) if elements else f'- REMOVE (MISTAKE): {user_feedback}'}

**CRITICAL - THESE ELEMENTS SHOULD NOT EXIST:**
{chr(10).join(f'- DO NOT INCLUDE: {el}' for el in elements) if elements else f'- DO NOT INCLUDE elements related to: {user_feedback}'}

**Step 1: Acknowledge the correction (1-2 bullet points)**
• Note the mistakenly added element being removed
• Confirm what should appear instead

**Step 2: REGENERATE without the hallucinated elements**
- Generate a NEW image that does NOT include the mentioned elements
- These elements were added by mistake and should NOT appear
- Return to the original room structure where applicable
- PRESERVE intended renovations (floors, walls, fixtures that WERE requested)"""

    elif edit_mode == "approve" or prompt_strategy == "preserve":
        # User approves - this shouldn't trigger regeneration, but handle gracefully
        return f"""## DESIGN APPROVED

The user has approved the current design.

User said: "{user_feedback}"

No changes needed. The current design is accepted."""

    else:  # modify or default
        return f"""{base_prompt}

## MODIFICATION REQUEST

User feedback: {user_feedback}

**TASK: Modify the following elements:**
{chr(10).join(f'- {op.get("mode", "modify").upper()}: {op.get("element", "element")} - {op.get("details", "")}' for op in sub_operations) if sub_operations else f'- MODIFY: {user_feedback}'}

**Step 1: Describe the modifications (2-4 bullet points)**
• List each change being made
• Be specific about what's changing

**Step 2: GENERATE the modified image**
- Apply the requested modifications
- PRESERVE everything not explicitly mentioned
- Maintain the same camera angle and room structure"""


def build_selected_image_prompt(
    selected_image_url: str,
    edit_mode_result: dict,
    user_feedback: str,
    extracted_data: dict | None = None
) -> str:
    """
    Build a prompt specifically for editing a user-selected image.

    This is used when the user has selected a specific image in the canvas
    and wants to apply changes to that image.

    Args:
        selected_image_url: URL of the selected canvas image
        edit_mode_result: Result from detect_edit_mode() function
        user_feedback: The user's feedback/request
        extracted_data: Optional extracted data about the room

    Returns:
        Formatted prompt string for editing the selected image
    """
    edit_mode = edit_mode_result.get("edit_mode", "modify")
    elements = edit_mode_result.get("elements", [])

    # Build base context
    base_context = """## EDITING SELECTED IMAGE

You are modifying a specific image that the user has selected.
This image may be either:
- An originally uploaded photo of their room
- A previously generated renovation preview

Your task is to apply the user's requested changes to THIS specific image."""

    # Add room context if available
    room_context = ""
    if extracted_data:
        if extracted_data.get("style", {}).get("overall_style"):
            room_context += f"\nCurrent style: {extracted_data['style']['overall_style']}"
        if extracted_data.get("materials"):
            room_context += f"\nMaterials: {', '.join(m.get('name', '') for m in extracted_data['materials'][:3])}"

    # Build edit-specific instructions
    edit_instructions = ""
    if edit_mode == "add":
        edit_instructions = f"""
**ADD elements to this image:**
{chr(10).join(f'• Add: {el}' for el in elements) if elements else f'• Add: {user_feedback}'}

Preserve all existing elements and add the new ones."""

    elif edit_mode == "remove":
        edit_instructions = f"""
**REMOVE elements from this image:**
{chr(10).join(f'• Remove: {el}' for el in elements) if elements else f'• Remove: {user_feedback}'}

The removed elements should NOT appear in the output."""

    elif edit_mode == "correct":
        edit_instructions = f"""
**CORRECT AI mistakes in this image:**
{chr(10).join(f'• Remove (mistake): {el}' for el in elements) if elements else f'• Remove (mistake): {user_feedback}'}

These elements were incorrectly added and should be removed."""

    else:  # modify
        edit_instructions = f"""
**MODIFY this image based on feedback:**
{user_feedback}

Apply the changes while preserving the overall design."""

    return f"""{base_context}
{room_context}

{edit_instructions}

**CRITICAL CONSTRAINTS:**
1. Maintain the SAME camera angle as the selected image
2. Preserve the room structure and boundaries
3. Only change what was explicitly requested
4. The output must be recognizable as the same space

**Step 1: Describe changes briefly (2-3 points)**
**Step 2: Generate the updated image**"""
