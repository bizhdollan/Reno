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


FEATURES_TO_RETAIN_PROMPT = """Analyze this room image and identify architectural/structural features that should NEVER be removed during renovation.

These are features that:
1. Are structural (windows, doors, load-bearing walls)
2. Define the room's character
3. Would be expensive/impossible to change
4. The user likely wants to keep

Return JSON:
{{
    "must_retain_features": [
        "2 windows on the east wall",
        "French door leading to balcony",
        "Exposed brick accent wall",
        "Ceiling height and beams",
        "Built-in shelving unit"
    ],
    "reasoning": "Brief explanation of why these are important to retain"
}}

Be specific about location and quantity. Return valid JSON only, no markdown."""
