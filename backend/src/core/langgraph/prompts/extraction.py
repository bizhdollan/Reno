"""
Extraction and feedback classification prompts for the renovation workflow.
"""

FEEDBACK_CLASSIFICATION_PROMPT = """Analyze if the user's message requires regenerating the renovation preview image.

User's message: "{user_message}"

Context: The user has seen a generated renovation preview image and is providing feedback.

Determine if their message requires image regeneration. Return JSON only:
{{
    "requires_regeneration": true/false,
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "extracted_feedback": "what specifically needs to change (if requires_regeneration is true, else null)"
}}

Messages that REQUIRE regeneration:
- Requests to change colors, materials, fixtures, layout
- "Make the walls darker", "Change the flooring to hardwood", "Add a window"
- "I don't like the chandelier", "Can you use marble instead?"
- Any specific design change request

Messages that DO NOT require regeneration:
- General approval: "looks good", "I like it", "perfect", "continue", "proceed"
- Questions about the process: "What's next?", "How long will this take?"
- Compliments: "This is great!", "I love it!"
- Navigation: "Let's move on", "Show me the estimate"
- Clarification questions that don't request changes

Return valid JSON only, no markdown."""


BRIEF_ROOM_SUMMARY_PROMPT = """Analyze this room image and provide a brief, conversational summary.

Project type: {project_type}
Extracted data: {extracted_data}

Create a 2-3 sentence summary that captures the essence of the room. Be conversational, not technical.

Examples:
- "A cozy bathroom with white subway tiles, a modern vanity, and natural light from a window."
- "A spacious kitchen featuring granite countertops, stainless steel appliances, and oak cabinets."

Return JSON:
{{
    "brief_summary": "Your 2-3 sentence summary here",
    "room_vibe": "one word describing the feel (e.g., modern, cozy, dated, bright)"
}}

Return valid JSON only, no markdown."""


FEATURES_TO_RETAIN_PROMPT = """Analyze this room image carefully and identify:

## PART 1: What is ACTUALLY VISIBLE in this exact frame
List ONLY elements you can directly see in this specific image. Do NOT assume or imagine elements that might exist outside the frame.

For each category, state what you see OR explicitly state "Not visible in image":
- Walls: How many walls visible? Color/condition?
- Floor: Type (hardwood, tile, carpet, etc.)? Condition (damaged, worn, good)?
- Windows: Count and position? OR "No windows visible in this frame"
- Doors: Count and position? OR "No doors visible in this frame"
- Fixtures: Light fixtures, outlets, switches visible?
- Furniture: Any furniture in the shot? OR "No furniture visible"
- Ceiling: Visible? Type (flat, beamed, etc.)?

## PART 2: Image Scope Assessment
Analyze how much of the room is shown:
- frame_type: One of "corner_view" (showing a corner, ~25% of room), "wall_view" (showing one wall, ~50%), "full_room" (wide shot, ~75-100%), or "detail_closeup" (zoomed in on small area)
- room_coverage_pct: Estimate what percentage of the total room is visible (10-100)
- camera_angle: "eye_level", "low_angle", or "high_angle"

## PART 3: What should NOT be added during renovation
Based on what you DON'T see in the image, list what should NOT be added to the renovated image:
- If no windows visible: "Do not add windows"
- If no furniture visible: "Do not add furniture, beds, or couches"
- If partial view: "Do not expand beyond visible frame"
- If no doors visible: "Do not add doors"

Return JSON:
{{
    "visible_elements": {{
        "walls": "Description of visible walls (e.g., '2 cream-colored walls meeting at corner, paint peeling')",
        "floor": "Description (e.g., 'Dark hardwood flooring, damaged/scratched condition')",
        "windows": "X windows visible at [positions]" or "No windows visible in this frame",
        "doors": "X doors visible at [positions]" or "No doors visible in this frame",
        "fixtures": ["list of visible fixtures"] or "None visible",
        "furniture": ["list of visible furniture"] or "None visible",
        "ceiling": "Description or 'Not visible'"
    }},
    "image_scope": {{
        "frame_type": "corner_view" | "wall_view" | "full_room" | "detail_closeup",
        "room_coverage_pct": 25,
        "camera_angle": "eye_level"
    }},
    "must_retain": [
        "Exact descriptions of structural features to preserve",
        "e.g., 'Corner angle between two walls'",
        "e.g., 'Room proportions and ceiling height'"
    ],
    "must_not_add": [
        "Do not add windows (none visible in original)",
        "Do not add furniture (none visible in original)",
        "Do not expand beyond the visible corner",
        "Do not add architectural elements not in original"
    ],
    "reasoning": "This is a corner shot showing approximately 25% of the room. Only two walls and the floor are visible. No windows, doors, or furniture are present in the frame. Any renovation should only modify the visible surfaces (floor, walls) without adding elements that don't exist."
}}

CRITICAL INSTRUCTIONS:
1. Be CONSERVATIVE - if you can't clearly see something, assume it's NOT there
2. Do NOT imagine what might be outside the frame
3. The must_not_add list is CRITICAL for preventing hallucination during image generation
4. Be specific about what IS visible and what is NOT

Return valid JSON only, no markdown."""
