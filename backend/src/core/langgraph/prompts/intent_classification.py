"""
Intent classification prompts for the renovation workflow.
"""

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
