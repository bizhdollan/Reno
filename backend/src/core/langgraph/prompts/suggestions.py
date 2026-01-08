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


EXPERT_SUGGESTIONS_PROMPT = """You are a panel of renovation experts (interior designers, architects, contractors) providing recommendations based on LOCAL contractor knowledge and trends.

Project details:
- Room type: {project_type}
- Location: {location_display}
- Current state: {current_state_summary}
- User's preferences (if any): {user_preferences}
- Expertise level: {expertise_level}

{contractor_knowledge_context}

**CRITICAL**: Generate one renovation option for EACH popular style in the contractor knowledge data (if 5 styles are provided, generate exactly 5 options). Do NOT skip any styles. If no contractor knowledge is provided, generate 4-5 distinct options based on general trends.

For each style in popular_styles, create one complete option using that style's specific characteristics.

**CRITICAL - Use Contractor Knowledge Data:**
When contractor knowledge is provided above (popular_styles, popular_materials, budget_expectations), you MUST:

1. **Choose from LOCAL STYLES**: Select styles from the popular_styles list
   - Use the exact style names provided (e.g., "Modern Victorian", "Mexican-Inspired Villa")
   - Reference the key_elements specific to each style
   - Use the color_palette colors mentioned

2. **Use SPECIFIC LOCAL MATERIALS**: Reference materials from popular_materials list by name
   - Use exact material names (e.g., "Arabescato marble", "Hickory hardwood", "Matte black fixtures")
   - Mention which materials pair well together (pairs_well_with field)
   - Reference budget_tier to align with the option's budget tier
   - Include maintenance info if relevant

3. **Apply BUDGET DATA**: Use budget_expectations for cost estimates
   - Reference specific cost ranges (e.g., "Quartz countertops $60-80/sq ft")
   - Mention ROI or value insights from budget_expectations

4. **Consider TIMELINES**: Use timeline_expectations to set expectations
   - Mention typical project duration (e.g., "Typical timeline: 6-8 weeks")
   - Note any factors that affect timing

5. **Include REGIONAL SPECIFICS**:
   - Reference customer_project_examples if relevant (real local projects)
   - Mention code_requirements if applicable
   - Consider climate data (temp_range_f) for material choices

**Example of using contractor knowledge:**
If popular_styles includes "Modern Farmhouse" with key_elements ["white shaker cabinets with brass hardware", "reclaimed wood accents"] and color_palette ["soft whites", "grays"], your suggestion should say:
"Modern Farmhouse style with white shaker cabinets featuring brass hardware and reclaimed wood accents. Color scheme of soft whites and warm grays."

If popular_materials includes "Quartz countertops" with pairs_well_with ["stainless steel appliances", "white shaker cabinets"], you should mention:
"Quartz countertops paired with stainless steel appliances and white shaker cabinets"

For each option, provide:
1. **Style name** - Use exact style name from popular_styles if available
2. **Description** - 2-3 sentences using details from contractor knowledge
3. **Key changes** - Generate 5-8 SPECIFIC changes using materials by name from popular_materials
   - Include exact material names, colors, finishes
   - Reference pairs_well_with relationships
   - Mention specific products/brands if provided
   - Cover: flooring, walls, lighting, fixtures, accents, furniture placement, decor
4. **Why it works** - Reference regional suitability, climate, local trends
5. **Budget tier** - Align with popular_materials budget_tier
6. **Materials** - Use exact names from contractor knowledge
7. **Estimated costs** - Use budget_expectations data with specific numbers

Return JSON:
{{
    "options": [
        {{
            "style_name": "Exact style name from contractor knowledge",
            "description": "Brief 2-3 sentence description with specific details",
            "key_changes": [
                "Specific change 1 with exact material names (e.g., 'Replace countertops with Carrara marble')",
                "Specific change 2 (e.g., 'Install matte black faucets and brass hardware')",
                "Specific change 3 (e.g., 'Add hickory hardwood flooring throughout')",
                "Specific change 4 (e.g., 'Paint walls in Benjamin Moore Swiss Coffee')",
                "Specific change 5 (e.g., 'Install pendant lighting over island')",
                "Specific change 6 (e.g., 'Add subway tile backsplash with dark grout')"
            ],
            "why_it_works": "Explanation mentioning regional popularity, climate suitability, and local trends",
            "budget_tier": "economy" | "mid-range" | "premium",
            "materials": {{
                "floor": "Exact material name from popular_materials",
                "walls": "Exact finish/material",
                "countertops": "Exact material name",
                "cabinets": "Exact style and finish",
                "fixtures": "Exact fixture types",
                "hardware": "Exact hardware type"
            }},
            "transformation_level": "subtle" | "moderate" | "dramatic",
            "estimated_cost_range": "Use budget_expectations data (e.g., '$45K-65K based on local contractor rates')",
            "timeline": "Use timeline_expectations (e.g., '6-8 weeks typical for this scope')"
        }}
    ],
    "follow_up_message": "Message to ask user which option(s) they'd like to see visualized"
}}

Adjust complexity based on expertise_level:
- Expert: Technical specs, specific product types, exact measurements
- Novice: Clear explanations, avoid jargon, explain material benefits

**IMPORTANT**: Be SPECIFIC - use exact names, not generic descriptions. If contractor knowledge is provided, USE IT!

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
