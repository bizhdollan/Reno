"""
Expert suggestions and clarification prompts for the renovation workflow.
"""

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
