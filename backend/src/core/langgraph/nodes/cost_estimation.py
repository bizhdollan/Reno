"""
Cost Estimation Node.

Generates 3-tier cost estimates (Low/Mid/High) based on confirmed project data.
Uses AI to dynamically determine categories and costs based on project type.
"""

import json
from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import ProjectState, CostTier, CategoryBreakdown
from src.core.langgraph.utils import get_latest_user_message, parse_json


COST_ESTIMATION_PROMPT = """You are a renovation cost estimation expert. Generate a detailed 3-tier cost estimate for this project.

## Project Information

**Type:** {project_type}
**Location (Zip):** {zip_code}
**Room Size:** {area_sqft} sq ft

## Confirmed Details

**Materials:**
{materials}

**Measurements:**
{measurements}

**Style:** {style}

## Your Task

Generate THREE cost tiers for this {project_type} renovation:

1. **Low Tier** (Budget-Friendly)
   - Standard quality materials
   - Basic fixtures and finishes  
   - ~20% markup on COGS
   
2. **Mid Tier** (Recommended)
   - Good quality materials
   - Mid-range fixtures and finishes
   - ~35% markup on COGS
   
3. **High Tier** (Premium)
   - Top-tier materials
   - High-end fixtures and finishes
   - ~50% markup on COGS

For EACH tier, provide:
- Detailed category breakdown (materials cost + labor cost per category)
- Categories should be relevant to {project_type} (e.g., for kitchen: Cabinets, Countertops, Flooring, Appliances, Plumbing, Electrical, Lighting, Painting)
- COGS (sum of all materials + labor)
- Markup amount
- Total cost

Return JSON only with this structure:
{{
    "tiers": [
        {{
            "id": "low",
            "name": "Low Tier",
            "badge": "Budget-Friendly",
            "description": "Quality work at the best value",
            "detailed_breakdown": [
                {{
                    "category": "Cabinets",
                    "description": "Stock cabinets, laminate finish",
                    "materials_cost": 3000,
                    "labor_cost": 1500,
                    "total": 4500
                }}
            ],
            "included_items": ["Cabinets", "Countertops", "Flooring", ...],
            "cogs": 20000,
            "markup_percentage": 20,
            "markup_amount": 4000,
            "total_cost": 24000
        }},
        {{
            "id": "mid",
            "name": "Mid Tier",
            "badge": "Recommended",
            "description": "Best balance of quality and price",
            ...
        }},
        {{
            "id": "high", 
            "name": "High Tier",
            "badge": "Premium",
            "description": "Top-tier materials and finishes",
            ...
        }}
    ]
}}

Be realistic with pricing based on the location (zip code) and current market rates.
Ensure Low < Mid < High tier pricing."""


def format_materials_for_prompt(materials: list) -> str:
    """Format materials list for the prompt."""
    if not materials:
        return "No specific materials identified"
    
    lines = []
    for m in materials:
        line = f"- {m.get('name', 'Unknown')}: {m.get('type', 'N/A')}"
        if m.get("condition"):
            line += f" (current condition: {m['condition']})"
        lines.append(line)
    return "\n".join(lines)


def format_measurements_for_prompt(measurements: dict) -> str:
    """Format measurements for the prompt."""
    if not measurements:
        return "No measurements available"
    
    return (
        f"- Room: {measurements.get('room_width_ft', '?')} x {measurements.get('room_length_ft', '?')} ft\n"
        f"- Height: {measurements.get('room_height_ft', '?')} ft\n"
        f"- Area: {measurements.get('area_sqft', '?')} sq ft"
    )


async def generate_cost_tiers(state: ProjectState) -> list[CostTier]:
    """Generate 3-tier cost estimates using AI."""
    provider = LLMProvider.for_llm()
    
    extracted = state.get("extracted_data", {})
    measurements = extracted.get("measurements", {})
    
    prompt = COST_ESTIMATION_PROMPT.format(
        project_type=state.get("project_type", "renovation"),
        zip_code=state.get("zip_code", "unknown"),
        area_sqft=measurements.get("area_sqft", 100),
        materials=format_materials_for_prompt(extracted.get("materials", [])),
        measurements=format_measurements_for_prompt(measurements),
        style=extracted.get("style", {}).get("overall_style", "unknown")
    )
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a renovation cost estimator. Return valid JSON only, no markdown."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2500
    )
    
    try:
        data = parse_json(response)
        return data.get("tiers", [])
    except:
        # Fallback tiers if AI fails
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
    
    - Generates 3-tier cost estimates
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
                
                response_content = [
                    {
                        "type": "text",
                        "text": (
                            f"## ✅ Estimate Confirmed!\n\n"
                            f"You've selected the **{selected_tier['name']}** ({selected_tier['badge']}).\n\n"
                            f"### Your Renovation Estimate\n\n"
                            f"- **Total Cost:** ${selected_tier['total_cost']:,.0f}\n"
                            f"- **COGS:** ${selected_tier['cogs']:,.0f}\n"
                            f"- **Markup ({selected_tier['markup_percentage']}%):** ${selected_tier['markup_amount']:,.0f}\n\n"
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
        cost_tiers = await generate_cost_tiers(state)
        updates["cost_tiers"] = cost_tiers
    
    # Build response with tier cards
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