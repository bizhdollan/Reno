"""
Cost Estimation Node.

Generates 3-tier cost estimates (Low/Mid/High) based on confirmed project data.
Uses AI to dynamically determine categories and costs based on:
- Extracted data from images
- User's renovation vision (if provided)
- Project basics (type, location)
"""

import json
from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import ProjectState, CostTier, CategoryBreakdown
from src.core.langgraph.utils import get_latest_user_message, parse_json


COST_ESTIMATION_PROMPT = """You are a renovation cost estimation expert with LOCAL contractor knowledge. Generate a detailed 3-tier cost estimate for this project using SPECIFIC regional pricing data.

## Project Information

**Type:** {project_type}
**Location:** {location}
**Room Size:** {area_sqft} sq ft

## Current Space Details

**Materials:**
{materials}

**Measurements:**
{measurements}

**Style:** {style}

## Renovation Vision
{renovation_vision}

{contractor_budget_context}

## Your Task

Generate THREE cost tiers for this {project_type} renovation using the LOCAL pricing data above:

1. **Low Tier** (Budget-Friendly)
   - Use budget-tier materials from the popular_materials list
   - Standard quality materials
   - Basic fixtures and finishes
   - ~20% markup on COGS

2. **Mid Tier** (Recommended)
   - Use mid-tier materials from the popular_materials list
   - Good quality materials
   - Mid-range fixtures and finishes
   - ~35% markup on COGS

3. **High Tier** (Premium)
   - Use upper-mid/luxury-tier materials from the popular_materials list
   - Top-tier materials
   - High-end fixtures and finishes
   - ~50% markup on COGS

**CRITICAL - Use Local Pricing Data:**
- MUST use specific prices from budget_expectations (e.g., "Quartz countertops $60-80/sq ft installed in Austin")
- Reference exact material names from popular_materials (e.g., "Arabescato marble", "Hickory hardwood")
- Use timeline_expectations for realistic project duration
- Calculate costs based on actual local contractor rates provided

For EACH tier, provide:
- Detailed category breakdown (materials cost + labor cost per category)
- Use SPECIFIC material names from popular_materials
- Apply budget_tier filtering (budget-tier materials for Low, mid-tier for Mid, luxury for High)
- Reference local pricing from budget_expectations
- Categories should be relevant to {project_type} and the renovation vision
- COGS (sum of all materials + labor)
- Markup amount
- Total cost

**Example of using local data:**
If budget_expectations shows "Quartz countertops $60-80/sq ft installed" and room is 150 sq ft, use:
- Materials: $60-80/sq ft × area
- Include installation labor in the rate
- Match to mid-tier since quartz is listed as "mid" in popular_materials

Return JSON only with this structure:
{{
    "tiers": [
        {{
            "id": "low",
            "name": "Low Tier",
            "badge": "Budget-Friendly",
            "description": "Quality work at the best value using budget-tier local materials",
            "detailed_breakdown": [
                {{
                    "category": "Countertops",
                    "description": "Specific material name from popular_materials (e.g., Vinyl countertops)",
                    "materials_cost": 1500,
                    "labor_cost": 800,
                    "total": 2300
                }}
            ],
            "included_items": ["List of materials from popular_materials"],
            "cogs": 8000,
            "markup_percentage": 20,
            "markup_amount": 1600,
            "total_cost": 9600,
            "timeline": "Duration from timeline_expectations"
        }},
        {{
            "id": "mid",
            "name": "Mid Tier",
            "badge": "Recommended",
            "description": "Best balance of quality and price with mid-tier local materials",
            "timeline": "Duration from timeline_expectations",
            ...
        }},
        {{
            "id": "high",
            "name": "High Tier",
            "badge": "Premium",
            "description": "Top-tier materials from local contractors (luxury/upper-mid tier)",
            "timeline": "Duration from timeline_expectations",
            ...
        }}
    ]
}}

**IMPORTANT:**
- Use EXACT pricing from budget_expectations where available
- Reference SPECIFIC material names from popular_materials
- Ensure Low < Mid < High tier pricing
- Include timeline from timeline_expectations in each tier"""


def format_materials_for_prompt(materials: list) -> str:
    """Format materials list for the prompt."""
    if not materials:
        return "No specific materials identified"
    
    lines = []
    for m in materials:
        line = f"- {m.get('name', 'Unknown')}: {m.get('type', 'N/A')}"
        if m.get("finish"):
            line += f", {m['finish']} finish"
        if m.get("condition"):
            line += f" (current condition: {m['condition']})"
        lines.append(line)
    return "\n".join(lines)


def format_measurements_for_prompt(measurements: dict) -> str:
    """Format measurements for the prompt."""
    if not measurements:
        return "No measurements available"
    
    lines = []
    if measurements.get("room_width_ft") and measurements.get("room_length_ft"):
        lines.append(f"- Room: {measurements.get('room_width_ft')} x {measurements.get('room_length_ft')} ft")
    if measurements.get("room_height_ft"):
        lines.append(f"- Height: {measurements.get('room_height_ft')} ft")
    if measurements.get("area_sqft"):
        lines.append(f"- Area: {measurements.get('area_sqft')} sq ft")
    
    return "\n".join(lines) if lines else "No measurements available"


def format_vision_for_prompt(vision: dict | None) -> str:
    """Format renovation vision for the prompt."""
    if not vision:
        return "No specific vision provided - generate a general estimate based on current space condition."
    
    lines = []
    if vision.get("ai_summary"):
        lines.append(f"Summary: {vision['ai_summary']}")
    if vision.get("style_preferences"):
        lines.append(f"Style: {vision['style_preferences']}")
    if vision.get("material_preferences"):
        lines.append(f"Materials: {vision['material_preferences']}")
    if vision.get("specific_changes"):
        lines.append(f"Specific changes: {vision['specific_changes']}")
    if vision.get("additional_notes"):
        lines.append(f"Notes: {vision['additional_notes']}")
    if vision.get("raw_input") and not lines:
        lines.append(vision["raw_input"])
    
    return "\n".join(lines) if lines else "No specific vision provided."


def format_contractor_budget_context(inspirations: dict | None) -> str:
    """Format contractor knowledge budget data for cost estimation."""
    if not inspirations:
        return "## Local Contractor Pricing\n\nNo regional pricing data available. Use general market rates for the zip code."

    contractor_knowledge = inspirations.get("contractor_knowledge", {})
    location = inspirations.get("location", {})
    location_str = f"{location.get('city', 'Unknown')}, {location.get('state_abbr', 'XX')}"

    # Format budget expectations
    budget_exp = contractor_knowledge.get("budget_expectations", [])
    budget_str = "\n".join([f"- {b['item']}: {b['insight']}" for b in budget_exp]) if budget_exp else "No specific pricing data available"

    # Format materials with budget tiers
    materials = contractor_knowledge.get("popular_materials", [])
    materials_by_tier = {"budget": [], "mid": [], "upper-mid": [], "luxury": []}
    for m in materials:
        tier = m.get("budget_tier", "mid")
        materials_by_tier.get(tier, materials_by_tier["mid"]).append(m)

    budget_materials = "\n".join([f"  • {m['name']} ({m.get('category', 'unknown')}): {m.get('description', '')}" for m in materials_by_tier["budget"][:5]]) if materials_by_tier["budget"] else "  Use standard quality materials"
    mid_materials = "\n".join([f"  • {m['name']} ({m.get('category', 'unknown')}): {m.get('description', '')}" for m in materials_by_tier["mid"][:5]]) if materials_by_tier["mid"] else "  Use mid-range quality materials"
    luxury_materials = "\n".join([f"  • {m['name']} ({m.get('category', 'unknown')}): {m.get('description', '')}" for m in (materials_by_tier["upper-mid"] + materials_by_tier["luxury"])[:5]]) if (materials_by_tier["upper-mid"] + materials_by_tier["luxury"]) else "  Use premium quality materials"

    # Format timelines
    timeline_exp = contractor_knowledge.get("timeline_expectations", [])
    timeline_str = "\n".join([f"- {t['project_type']}: {t['duration']} ({t.get('notes', 'No notes')})" for t in timeline_exp[:3]]) if timeline_exp else "No timeline data available"

    return f"""## Local Contractor Pricing Data for {location_str}

**Budget Expectations (Local Contractor Rates):**
{budget_str}

**Materials by Budget Tier:**

Budget Tier (for Low estimate):
{budget_materials}

Mid Tier (for Mid estimate):
{mid_materials}

Luxury Tier (for High estimate):
{luxury_materials}

**Timeline Expectations:**
{timeline_str}

**Instructions:** Use these SPECIFIC local prices and materials when generating estimates. Reference exact material names and pricing."""


async def generate_cost_tiers(state: ProjectState) -> list[CostTier]:
    """Generate 3-tier cost estimates using AI with contractor knowledge."""
    provider = LLMProvider.for_llm()

    extracted = state.get("extracted_data", {})
    measurements = extracted.get("measurements", {})
    vision = state.get("renovation_vision")
    inspirations = state.get("renovation_inspirations")

    # Get location info
    location = inspirations.get("location", {}) if inspirations else {}
    location_str = f"{location.get('city', 'Unknown')}, {location.get('state_abbr', 'XX')}" if location else f"Zip {state.get('zip_code', 'unknown')}"

    prompt = COST_ESTIMATION_PROMPT.format(
        project_type=state.get("project_type", "renovation"),
        location=location_str,
        area_sqft=measurements.get("area_sqft", 100),
        materials=format_materials_for_prompt(extracted.get("materials", [])),
        measurements=format_measurements_for_prompt(measurements),
        style=extracted.get("style", {}).get("overall_style", "unknown"),
        renovation_vision=format_vision_for_prompt(vision),
        contractor_budget_context=format_contractor_budget_context(inspirations)
    )

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a renovation cost estimator using LOCAL contractor pricing data. Return valid JSON only, no markdown."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=3000,
        operation_type="cost_estimation"
    )

    try:
        data = parse_json(response)
        return data.get("tiers", [])
    except Exception as e:
        print(f"[cost_estimation] Failed to parse AI response: {e}")
        return generate_fallback_tiers(state)


def generate_fallback_tiers(state: ProjectState) -> list[CostTier]:
    """Generate fallback tiers if AI generation fails."""
    extracted = state.get("extracted_data", {})
    measurements = extracted.get("measurements", {})
    area = measurements.get("area_sqft", 100)
    
    # Base cost per sqft by tier
    low_rate = 150
    mid_rate = 225
    high_rate = 350
    
    def create_tier(tier_id: str, name: str, badge: str, desc: str, rate: float, markup_pct: float) -> CostTier:
        cogs = area * rate
        markup_amount = cogs * (markup_pct / 100)
        total = cogs + markup_amount
        
        return CostTier(
            id=tier_id,
            name=name,
            badge=badge,
            description=desc,
            cogs=cogs,
            markup_percentage=markup_pct,
            markup_amount=markup_amount,
            total_cost=total,
            included_items=["Materials", "Labor", "Basic Fixtures"],
            detailed_breakdown=[
                CategoryBreakdown(
                    category="General Renovation",
                    description=f"{name} quality materials and labor",
                    materials_cost=cogs * 0.6,
                    labor_cost=cogs * 0.4,
                    total=cogs
                )
            ]
        )
    
    return [
        create_tier("low", "Low Tier", "Budget-Friendly", "Quality work at the best value", low_rate, 20),
        create_tier("mid", "Mid Tier", "Recommended", "Best balance of quality and price", mid_rate, 35),
        create_tier("high", "High Tier", "Premium", "Top-tier materials and finishes", high_rate, 50),
    ]


def format_tier_cards_message(tiers: list[CostTier]) -> dict:
    """Format tiers as a special message for frontend rendering."""
    return {
        "type": "tier_cards",
        "tiers": tiers
    }


async def cost_estimation_node(state: ProjectState) -> dict:
    """
    Cost estimation node.
    
    - Generates 3-tier cost estimates based on extracted data and vision
    - Returns special tier_cards message for frontend
    - Handles tier selection
    - Marks project as completed when tier is selected
    """
    messages = state.get("messages", [])
    user_message, _ = get_latest_user_message(messages)
    
    updates = {}
    cost_tiers = state.get("cost_tiers")
    
    # Check if user is selecting a tier
    if user_message and cost_tiers:
        lower = user_message.lower()
        
        selected = None
        if "low" in lower or "budget" in lower or "tier 1" in lower or "first" in lower:
            selected = "low"
        elif "mid" in lower or "recommend" in lower or "tier 2" in lower or "second" in lower or "middle" in lower:
            selected = "mid"
        elif "high" in lower or "premium" in lower or "tier 3" in lower or "third" in lower:
            selected = "high"
        
        if selected:
            # Find selected tier
            selected_tier = next((t for t in cost_tiers if t["id"] == selected), None)
            
            if selected_tier:
                updates["selected_tier"] = selected
                updates["current_stage"] = "completed"
                
                # Include vision summary if available
                vision = state.get("renovation_vision")
                vision_note = ""
                if vision and vision.get("ai_summary"):
                    vision_note = f"\n\n**Your Vision:** *{vision['ai_summary']}*"
                
                response_content = [
                    {
                        "type": "text",
                        "text": (
                            f"## ✅ Estimate Confirmed!\n\n"
                            f"You've selected the **{selected_tier['name']}** ({selected_tier['badge']}).\n\n"
                            f"### Your Renovation Estimate\n\n"
                            f"- **Total Cost:** ${selected_tier['total_cost']:,.0f}\n"
                            f"- **COGS:** ${selected_tier['cogs']:,.0f}\n"
                            f"- **Markup ({selected_tier['markup_percentage']}%):** ${selected_tier['markup_amount']:,.0f}"
                            f"{vision_note}\n\n"
                            f"---\n\n"
                            f"Thank you for using our renovation estimator! "
                            f"Your project details have been saved. "
                            f"You can now connect with contractors in your area who can bring this vision to life."
                        )
                    }
                ]
                
                updates["messages"] = [{"role": "assistant", "content": response_content}]
                updates["awaiting_user_input"] = True
                return updates
        else:
            # User said something but didn't select a tier
            response = "Please select one of the three tiers: **Low**, **Mid**, or **High**. You can click on a tier card or type your choice."
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates
    
    # Generate tiers if not already done
    if not cost_tiers:
        print("[cost_estimation] Generating cost tiers...")
        cost_tiers = await generate_cost_tiers(state)
        updates["cost_tiers"] = cost_tiers
    
    # Build response with tier cards
    vision = state.get("renovation_vision")
    if vision and vision.get("ai_summary"):
        intro_text = (
            f"# Your Renovation Estimate\n\n"
            f"Based on your space analysis and vision (*{vision['ai_summary']}*), "
            f"here are three options for your renovation:\n"
        )
    else:
        intro_text = (
            "# Your Renovation Estimate\n\n"
            "Based on your project details, here are three options for your renovation:\n"
        )
    
    response_content = [
        {"type": "text", "text": intro_text},
        format_tier_cards_message(cost_tiers),
        {"type": "text", "text": "\n\nSelect a tier to see the detailed breakdown and confirm your estimate."}
    ]
    
    updates["messages"] = [{"role": "assistant", "content": response_content}]
    updates["awaiting_user_input"] = True
    
    return updates