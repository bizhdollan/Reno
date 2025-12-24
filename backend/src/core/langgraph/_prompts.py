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


# =============================================================================
# ENHANCED MULTI-INTENT CLASSIFIER
# =============================================================================

ENHANCED_INTENT_CLASSIFIER_PROMPT = """Analyze the user's message in a renovation project context to determine their intent.

Current context: {context}
User's message: "{user_message}"

The user may have ONE or MULTIPLE intents. Identify ALL that apply.

Possible intents:
1. **confirm** - User confirms/approves current information ("yes", "looks good", "correct", "that's right")
2. **correction** - User wants to correct extraction data ("the walls are white not beige", "floor is hardwood not laminate")
3. **direct_vision** - User directly provides renovation vision/preferences ("add marble tiles", "I want modern style", "install chandelier")
4. **ask_suggestions** - User asks for AI recommendations ("what do you suggest?", "give me ideas", "what would look good?")
5. **ask_question** - User asks questions about materials/process ("what's the difference between X and Y?", "how much does that cost?")
6. **vague_request** - User makes vague request ("make it pretty", "fix the floor", "modernize it")
7. **skip** - User wants to skip current step ("skip", "move on", "next", "I don't care")
8. **mixed** - Combination of confirm + vision ("looks good, add marble tiles")

Return JSON:
{{
    "primary_intent": "main intent",
    "secondary_intents": ["any", "additional", "intents"],
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "extracted_content": {{
        "confirmation": true/false/null,
        "corrections": "any corrections mentioned or null",
        "vision_details": "any vision/preferences mentioned or null",
        "questions": ["any questions asked"] or null,
        "vague_needs": "vague requests or null"
    }}
}}

Return valid JSON only, no markdown."""


# =============================================================================
# EXPERTISE LEVEL DETECTOR
# =============================================================================

EXPERTISE_DETECTOR_PROMPT = """Analyze the user's message to detect their expertise level in renovation/construction.

User's message: "{user_message}"
Conversation history summary: {history_summary}

Look for indicators:

**Expert/Professional indicators** (contractor, architect, designer):
- Technical terms: "12x24 porcelain", "LVT flooring", "matte finish", "recessed lighting", "R-value", "load-bearing"
- Specific measurements and specs
- Industry jargon and acronyms
- Mentions of codes, permits, specifications
- Professional workflow terms

**Novice/Homeowner indicators**:
- Vague descriptions: "make it nice", "pretty tiles", "good lights"
- Questions about basic concepts
- Uncertainty about materials
- Focus on aesthetics over specs
- Asking for recommendations

Return JSON:
{{
    "expertise_level": "expert" | "intermediate" | "novice",
    "confidence": 0.0 to 1.0,
    "indicators": ["list", "of", "indicators", "found"],
    "recommended_communication_style": "technical" | "balanced" | "explanatory"
}}

Return valid JSON only, no markdown."""


# =============================================================================
# EXPERT SUGGESTIONS SYSTEM
# =============================================================================

EXPERT_SUGGESTIONS_PROMPT = """You are a panel of renovation experts (interior designers, architects, contractors) providing recommendations.

Project details:
- Room type: {project_type}
- Current state: {current_state_summary}
- User's preferences (if any): {user_preferences}
- Expertise level: {expertise_level}

Generate 2-3 distinct renovation options, each with a different style/approach.

For each option, provide:
1. **Style name** (e.g., "Modern Minimalist", "Industrial Chic", "Classic Traditional")
2. **Key changes** - Specific materials, fixtures, colors
3. **Why it works** - Brief explanation based on room condition and user needs
4. **Estimated impact** - Budget tier (economy/mid-range/premium) and transformation level

Return JSON:
{{
    "options": [
        {{
            "style_name": "...",
            "description": "Brief 2-3 sentence description",
            "key_changes": [
                "Specific change 1",
                "Specific change 2",
                "Specific change 3"
            ],
            "why_it_works": "...",
            "budget_tier": "economy" | "mid-range" | "premium",
            "materials": {{"floor": "...", "walls": "...", "fixtures": "..."}},
            "transformation_level": "subtle" | "moderate" | "dramatic"
        }}
    ],
    "follow_up_message": "Message to ask user which option(s) they'd like to see visualized"
}}

Adjust complexity based on expertise_level:
- Expert: Technical specs, specific product types
- Novice: Clear explanations, avoid jargon

Return valid JSON only, no markdown."""


# =============================================================================
# TWO-MODE REGENERATION CLASSIFIER
# =============================================================================

REGENERATION_MODE_CLASSIFIER_PROMPT = """Determine if the user wants a STYLE CHANGE or ITERATIVE REFINEMENT.

User's feedback: "{user_feedback}"
Current design summary: {current_design_summary}

**STYLE CHANGE** (use original uploaded image as base):
- User doesn't like the overall design/style
- Wants completely different approach
- Examples: "try modern instead", "show me traditional style", "I don't like this", "completely different", "start over"

**ITERATIVE REFINEMENT** (use last generated image as base):
- User likes the design but wants specific tweaks
- Minor modifications to existing design
- Examples: "make walls darker", "add a sofa", "remove chandelier", "change floor color to grey", "bigger windows"

Return JSON:
{{
    "mode": "style_change" | "iterative_refinement",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "extracted_changes": "what user wants changed"
}}

When unsure (confidence < 0.7), mode should be "ask_user" to clarify.

Return valid JSON only, no markdown."""


# =============================================================================
# VAGUE REQUEST CLARIFIER
# =============================================================================

# =============================================================================
# BRIEF ROOM SUMMARY (Conversational flow)
# =============================================================================

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


# =============================================================================
# FEATURES TO RETAIN DETECTION
# =============================================================================

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


# =============================================================================
# UNIFIED CLASSIFIER (Combines expertise + intent + conversation type)
# =============================================================================

UNIFIED_CLASSIFIER_PROMPT = """Analyze the user's message in a renovation project context. Classify their expertise level, intent, and conversation type in ONE response.

User's message: "{user_message}"
Current context: {context}
Has generated images: {has_generated_images}

Return JSON with ALL of the following:

{{
    "expertise_level": "expert" | "intermediate" | "novice",
    "expertise_indicators": ["list of indicators found"],

    "conversation_type": "discussion" | "generation_request" | "reference_previous" | "move_forward" | "clarify",

    "primary_intent": "confirm" | "correction" | "direct_vision" | "ask_suggestions" | "ask_question" | "vague_request" | "skip" | "mixed",
    "secondary_intents": [],

    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",

    "extracted_content": {{
        "confirmation": true/false/null,
        "corrections": "any corrections mentioned or null",
        "vision_details": "any vision/preferences mentioned or null",
        "questions": ["any questions asked"] or null,
        "generation_changes": "what changes are requested for image generation (as string) or null",
        "referenced_image_position": "if reference_previous: which image (1, 2, 'previous', 'first', etc.) or null"
    }}
}}

**Expertise Indicators:**
- Expert: technical terms (12x24 porcelain, LVT, R-value), specific measurements, industry jargon
- Novice: vague descriptions (make it nice), questions about basics, uncertainty about materials

**Conversation Types (CRITICAL - read carefully):**

1. **generation_request** - User wants ANY visual change to the generated image. THIS IS THE MOST COMMON TYPE.
   Examples that ARE generation_request:
   - "the floor should be tiles" → generation_request (wants floor changed)
   - "make the walls blue" → generation_request
   - "add a shoe rack" → generation_request
   - "I want tiles" → generation_request
   - "change the flooring" → generation_request
   - "the floor should have tiles" → generation_request
   - "add tiles" → generation_request
   - "let's add tiles" → generation_request
   - "give me the image with tiles" → generation_request
   - Any request mentioning materials, colors, fixtures, or changes → generation_request

2. **move_forward** - ONLY when user explicitly approves WITHOUT requesting changes
   Examples: "looks good", "perfect", "continue", "proceed", "I'm happy with this", "let's move on", "yes" (when approving)
   NOT move_forward: "yes, add tiles" (this is generation_request), "sure, let's add tiles" (generation_request)

3. **discussion** - ONLY pure questions that don't request changes
   Examples: "what color is that wall?", "what type of tiles are those?", "what style is this?"
   NOT discussion: "I said the floor should have tiles" (this is generation_request - user is requesting a change)

4. **reference_previous** - Referring to a specific earlier image BY POSITION
   Examples: "use the first one", "go back to image 2", "I prefer the previous design"

5. **clarify** - User is confused or needs explanation
   Examples: "what options do I have?", "I don't understand"

IMPORTANT: If the user mentions ANY material, color, fixture, or change they want, classify as generation_request.
"should be", "should have", "add", "change", "make it", "I want" → generation_request

Return valid JSON only, no markdown."""


# =============================================================================
# CONVERSATION TYPE CLASSIFIER
# =============================================================================

CONVERSATION_TYPE_CLASSIFIER_PROMPT = """Determine what type of response the user needs based on their message.

User's message: "{user_message}"
Current context: {context}
Has generated images: {has_generated_images}

Classify the user's intent:

1. **generation_request** - User wants ANY visual change. THIS IS THE MOST COMMON TYPE.
   Examples that ARE generation_request:
   - "the floor should be tiles" → generation_request
   - "make the walls blue" → generation_request
   - "add a shoe rack" → generation_request
   - "I want tiles" → generation_request
   - "the floor should have tiles" → generation_request
   - "add tiles" → generation_request
   - "let's add tiles" → generation_request
   - "sure, let's add tiles" → generation_request
   - "I said the floor should have tiles" → generation_request (user is insisting on a change)
   - "give me the image for that" (after discussing a change) → generation_request
   - Any mention of materials, colors, fixtures they WANT → generation_request

2. **move_forward** - ONLY explicit approval WITHOUT any change request
   Examples: "looks good", "perfect", "continue", "proceed", "I'm happy", "yes" (pure approval)
   NOT move_forward: "yes, add tiles", "sure, let's add tiles", "continue but change X"

3. **discussion** - ONLY pure questions, no change request
   Examples: "what color is that wall?", "what type of tiles are those?"
   NOT discussion: "I said the floor should have tiles" (this requests a change)

4. **reference_previous** - Referring to earlier image BY POSITION
   Examples: "use the first one", "go back to image 2"

5. **clarify** - User confused or needs explanation
   Examples: "what options do I have?", "I don't understand"

CRITICAL: If user mentions ANY material/color/fixture they want, it's generation_request.
Keywords like "should be", "should have", "add", "change", "I want", "make it" → generation_request

Return JSON:
{{
    "conversation_type": "discussion" | "generation_request" | "reference_previous" | "move_forward" | "clarify",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "extracted_question": "if discussion, the specific question to answer (else null)",
    "referenced_image_position": "if reference_previous, which image position (1, 2, 'previous', 'first', etc.) (else null)",
    "generation_changes": "if generation_request, what changes are requested (else null)"
}}

Return valid JSON only, no markdown."""


# =============================================================================
# MULTI-IMAGE FEEDBACK PARSER
# =============================================================================

MULTI_IMAGE_FEEDBACK_PROMPT = """Parse the user's feedback to identify which specific images they're referring to and what changes they want for each.

User's feedback: "{user_feedback}"
Number of generated images: {num_images}

The user may reference images by:
- Numbers: "image 1", "the first one", "#2", "second image"
- Position words: "first", "second", "third", "last", "all"
- Descriptions: "the one with marble", "the modern one"

Return JSON:
{{
    "references_multiple_images": true/false,
    "image_feedback": [
        {{
            "image_position": 1,
            "feedback": "specific feedback for this image",
            "confidence": 0.0 to 1.0
        }}
    ],
    "applies_to_all": true/false,
    "general_feedback": "feedback that applies to all images or null"
}}

If the user says "all images" or doesn't specify, set applies_to_all: true.
If feedback is for a single image, still include it in image_feedback array.

Return valid JSON only, no markdown."""


VAGUE_REQUEST_CLARIFIER_PROMPT = """The user made a vague renovation request. Generate clarifying questions.

User's request: "{user_request}"
Project type: {project_type}
Current extracted data: {extracted_data_summary}
Expertise level: {expertise_level}

Generate 2-3 specific clarifying questions to understand what the user wants.

For novice users, provide:
- Simple questions with examples
- Common options to choose from

For expert users:
- Direct technical questions
- Assume they know terminology

Return JSON:
{{
    "interpreted_intent": "What you think they mean",
    "clarifying_questions": [
        "Question 1 with context",
        "Question 2 with options if applicable",
        "Question 3 if needed"
    ],
    "suggested_response": "Complete message to send to user asking these questions"
}}

Return valid JSON only, no markdown."""
