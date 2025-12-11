"""
Cost Estimation Node.

Generates final cost estimate based on collected data.
"""

from src.core.langgraph.state import ProjectState, CostEstimate


# Simple cost factors (can be enhanced later)
LABOR_RATES = {
    "kitchen": 50,  # per sqft
    "bathroom": 60,
    "bedroom": 30,
    "living room": 25,
    "default": 40
}

OVERHEAD_PERCENT = 0.15  # 15% overhead


def calculate_estimate(state: ProjectState) -> CostEstimate:
    """Calculate cost estimate from state data."""
    project_type = state.get("project_type", "default").lower()
    measurements = state.get("measurements", {})
    materials = state.get("materials", [])
    
    # Calculate area
    area_sqft = measurements.get("area_sqft", 0)
    if not area_sqft:
        width = measurements.get("width", 0)
        length = measurements.get("length", 0)
        area_sqft = width * length
    
    # Labor cost
    labor_rate = LABOR_RATES.get(project_type, LABOR_RATES["default"])
    labor_cost = area_sqft * labor_rate
    
    # Material cost
    material_cost = 0
    breakdown = []
    
    for mat in materials:
        qty = mat.get("quantity", 0)
        unit_cost = mat.get("unit_cost", 0)
        item_total = qty * unit_cost
        material_cost += item_total
        
        breakdown.append({
            "item": mat.get("name", "Unknown"),
            "type": mat.get("type", "N/A"),
            "quantity": qty,
            "unit": mat.get("unit", "units"),
            "unit_cost": unit_cost,
            "total": item_total
        })
    
    # Add labor to breakdown
    breakdown.insert(0, {
        "item": "Labor",
        "type": f"{project_type.title()} renovation",
        "quantity": area_sqft,
        "unit": "sqft",
        "unit_cost": labor_rate,
        "total": labor_cost
    })
    
    # Overhead
    subtotal = labor_cost + material_cost
    overhead = subtotal * OVERHEAD_PERCENT
    
    breakdown.append({
        "item": "Overhead & Permits",
        "type": "15%",
        "quantity": 1,
        "unit": "flat",
        "unit_cost": overhead,
        "total": overhead
    })
    
    total = subtotal + overhead
    
    # Confidence based on data quality
    confidence = 0.5  # Base
    if measurements.get("confirmed"):
        confidence += 0.2
    if all(m.get("confirmed") for m in materials):
        confidence += 0.2
    if len(state.get("images", [])) >= 2:
        confidence += 0.1
    
    return CostEstimate(
        labor_cost=labor_cost,
        material_cost=material_cost,
        overhead=overhead,
        total=total,
        breakdown=breakdown,
        confidence=min(confidence, 1.0)
    )


def format_estimate(estimate: CostEstimate) -> str:
    """Format estimate for display."""
    lines = []
    
    lines.append("# Cost Estimate\n")
    
    # Breakdown table
    lines.append("## Breakdown\n")
    lines.append("| Item | Details | Qty | Unit Cost | Total |")
    lines.append("|------|---------|-----|-----------|-------|")
    
    for item in estimate.get("breakdown", []):
        lines.append(
            f"| {item['item']} | {item['type']} | "
            f"{item['quantity']} {item['unit']} | "
            f"${item['unit_cost']:,.0f} | ${item['total']:,.0f} |"
        )
    
    lines.append("")
    
    # Summary
    lines.append("## Summary\n")
    lines.append(f"- **Labor:** ${estimate.get('labor_cost', 0):,.0f}")
    lines.append(f"- **Materials:** ${estimate.get('material_cost', 0):,.0f}")
    lines.append(f"- **Overhead & Permits:** ${estimate.get('overhead', 0):,.0f}")
    lines.append(f"\n### **Total Estimate: ${estimate.get('total', 0):,.0f}**")
    
    # Confidence
    conf = estimate.get("confidence", 0)
    conf_label = "High" if conf >= 0.8 else "Medium" if conf >= 0.6 else "Low"
    lines.append(f"\n*Estimate confidence: {conf_label} ({conf*100:.0f}%)*")
    
    return "\n".join(lines)


async def cost_estimation_node(state: ProjectState) -> dict:
    """
    Cost estimation node.
    
    - Calculates estimate from collected data
    - Formats and presents to user
    - Marks project as completed
    """
    # Calculate estimate
    estimate = calculate_estimate(state)
    
    # Format for display
    estimate_str = format_estimate(estimate)
    
    response = f"""{estimate_str}

---

This estimate is based on the information you provided. Actual costs may vary based on:
- Local labor rates
- Material availability
- Specific contractor quotes
- Unforeseen conditions

Would you like me to explain any part of this estimate?"""
    
    return {
        "estimate": estimate,
        "current_stage": "completed",
        "messages": [{"role": "assistant", "content": response}],
        "awaiting_user_input": True
    }