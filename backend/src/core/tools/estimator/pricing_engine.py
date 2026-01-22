"""
Pricing Engine Tool

Generates 3-tier cost estimates by combining material pricing, labor costs,
and permit fees. Uses Tavily search for local pricing data.
"""
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

import httpx

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)

# Base material prices ($/unit) - national averages
BASE_MATERIAL_PRICES = {
    # Flooring (per sqft)
    "hardwood": {"low": 6, "mid": 10, "high": 16},
    "laminate": {"low": 2, "mid": 4, "high": 7},
    "tile": {"low": 3, "mid": 8, "high": 15},
    "carpet": {"low": 2, "mid": 5, "high": 10},
    "vinyl": {"low": 2, "mid": 4, "high": 8},
    "lvp": {"low": 3, "mid": 5, "high": 9},

    # Paint (per gallon)
    "paint": {"low": 25, "mid": 45, "high": 75},
    "primer": {"low": 20, "mid": 35, "high": 50},

    # Drywall (per sheet)
    "drywall": {"low": 12, "mid": 18, "high": 25},

    # Trim (per linear ft)
    "baseboard": {"low": 1, "mid": 3, "high": 8},
    "crown_molding": {"low": 2, "mid": 5, "high": 12},

    # Countertops (per sqft)
    "laminate_counter": {"low": 15, "mid": 30, "high": 50},
    "granite": {"low": 50, "mid": 80, "high": 150},
    "quartz": {"low": 60, "mid": 100, "high": 175},
    "marble": {"low": 75, "mid": 125, "high": 200},
    "butcher_block": {"low": 40, "mid": 70, "high": 120},

    # Cabinets (per linear ft)
    "cabinets": {"low": 100, "mid": 250, "high": 500},
    "kitchen_cabinets": {"low": 100, "mid": 250, "high": 500},

    # Tile (per sqft)
    "wall_tile": {"low": 4, "mid": 10, "high": 25},
    "backsplash": {"low": 5, "mid": 15, "high": 35},

    # Default
    "default": {"low": 5, "mid": 10, "high": 20},
}

# Tier descriptions for estimates
TIER_DESCRIPTIONS = {
    "low": {
        "name": "Budget-Friendly",
        "description": "Quality materials at competitive prices. Standard finishes and builder-grade options.",
        "features": ["Standard materials", "Basic finishes", "Cost-effective brands"]
    },
    "mid": {
        "name": "Mid-Range",
        "description": "Good balance of quality and value. Upgraded finishes and popular brands.",
        "features": ["Quality materials", "Upgraded finishes", "Popular brands", "Better durability"]
    },
    "high": {
        "name": "Premium",
        "description": "High-end materials and finishes. Designer brands and luxury options.",
        "features": ["Premium materials", "Designer finishes", "Luxury brands", "Superior durability", "Unique details"]
    }
}


@dataclass
class LineItem:
    """A single cost line item."""
    category: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    total: float
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "description": self.description,
            "quantity": round(self.quantity, 2),
            "unit": self.unit,
            "unit_price": round(self.unit_price, 2),
            "total": round(self.total, 2),
            "notes": self.notes
        }


@dataclass
class EstimateTier:
    """A single tier of the estimate."""
    tier: str  # low, mid, high
    name: str
    description: str
    features: List[str]
    material_cost: float
    labor_cost: float
    permit_cost: float
    contingency: float
    gc_overhead: float
    total: float
    line_items: List[LineItem]

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "name": self.name,
            "description": self.description,
            "features": self.features,
            "material_cost": round(self.material_cost, 2),
            "labor_cost": round(self.labor_cost, 2),
            "permit_cost": round(self.permit_cost, 2),
            "contingency": round(self.contingency, 2),
            "gc_overhead": round(self.gc_overhead, 2),
            "total": round(self.total, 2),
            "line_items": [item.to_dict() for item in self.line_items]
        }


@dataclass
class FullEstimate:
    """Complete 3-tier estimate."""
    project_type: str
    location: str
    room_sqft: float
    tiers: Dict[str, EstimateTier]
    timeline_weeks: int
    payment_schedule: List[Dict[str, Any]]
    assumptions: List[str]
    exclusions: List[str]
    sources: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_type": self.project_type,
            "location": self.location,
            "room_sqft": round(self.room_sqft, 1),
            "tiers": {k: v.to_dict() for k, v in self.tiers.items()},
            "timeline_weeks": self.timeline_weeks,
            "payment_schedule": self.payment_schedule,
            "assumptions": self.assumptions,
            "exclusions": self.exclusions,
            "sources": self.sources
        }


def generate_estimate(
    quantities: Dict[str, Any],
    labor_estimate: Dict[str, Any],
    permit_analysis: Optional[Dict[str, Any]] = None,
    project_type: str = "renovation",
    location: str = "Unknown",
    contractor_knowledge: Optional[Dict[str, Any]] = None
) -> ToolResult:
    """
    Generate 3-tier cost estimate.

    Args:
        quantities: Quantity takeoff results
        labor_estimate: Labor estimation results
        permit_analysis: Permit requirement analysis (optional)
        project_type: Type of project
        location: Project location
        contractor_knowledge: Local contractor insights (optional)

    Returns:
        ToolResult with FullEstimate
    """
    start_time = time.time()
    tool_name = "estimate_generator"

    if not quantities:
        return ToolResult.error_result(
            error="Quantities are required to generate estimate",
            tool_name=tool_name
        )

    room_sqft = quantities.get("room_sqft", 100)
    materials = quantities.get("materials", [])

    # Calculate permit costs
    permit_cost = 0
    if permit_analysis:
        permits = permit_analysis.get("permits_required", [])
        for permit in permits:
            if permit.get("required"):
                fee_range = permit.get("fee_range")
                if fee_range:
                    permit_cost += (fee_range[0] + fee_range[1]) / 2  # Average
                else:
                    permit_cost += 500  # Default permit cost estimate

    # Get labor costs by tier
    base_labor_cost = labor_estimate.get("total_labor_cost", 0)
    labor_costs = {
        "low": base_labor_cost * 0.85,   # Lower rates
        "mid": base_labor_cost,          # Base rates
        "high": base_labor_cost * 1.25   # Premium rates
    }

    # Generate each tier
    tiers = {}
    for tier_key in ["low", "mid", "high"]:
        tier_info = TIER_DESCRIPTIONS[tier_key]
        line_items = []
        material_total = 0

        # Material line items
        for material in materials:
            material_name = material.get("material", "").lower().replace(" ", "_")
            quantity = material.get("quantity", 0)
            unit = material.get("unit", "sqft")

            # Get price for this tier
            prices = BASE_MATERIAL_PRICES.get(material_name, BASE_MATERIAL_PRICES["default"])
            unit_price = prices.get(tier_key, prices["mid"])

            item_total = quantity * unit_price
            material_total += item_total

            line_items.append(LineItem(
                category="Materials",
                description=material.get("material", material_name),
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                total=item_total
            ))

        # Labor line item
        labor_cost = labor_costs[tier_key]
        line_items.append(LineItem(
            category="Labor",
            description="All trades labor",
            quantity=labor_estimate.get("total_hours", 0),
            unit="hours",
            unit_price=labor_cost / max(labor_estimate.get("total_hours", 1), 1),
            total=labor_cost
        ))

        # Permit line item
        if permit_cost > 0:
            line_items.append(LineItem(
                category="Permits",
                description="Building permits and fees",
                quantity=1,
                unit="lot",
                unit_price=permit_cost,
                total=permit_cost
            ))

        # Calculate overhead and contingency
        subtotal = material_total + labor_cost + permit_cost
        gc_overhead = subtotal * 0.15  # 15% GC overhead
        contingency_rate = {"low": 0.10, "mid": 0.12, "high": 0.15}[tier_key]
        contingency = subtotal * contingency_rate

        # Add overhead items
        line_items.append(LineItem(
            category="Overhead",
            description="General contractor overhead",
            quantity=1,
            unit="lot",
            unit_price=gc_overhead,
            total=gc_overhead
        ))

        line_items.append(LineItem(
            category="Contingency",
            description=f"Contingency ({int(contingency_rate*100)}%)",
            quantity=1,
            unit="lot",
            unit_price=contingency,
            total=contingency
        ))

        total = subtotal + gc_overhead + contingency

        tiers[tier_key] = EstimateTier(
            tier=tier_key,
            name=tier_info["name"],
            description=tier_info["description"],
            features=tier_info["features"],
            material_cost=material_total,
            labor_cost=labor_cost,
            permit_cost=permit_cost,
            contingency=contingency,
            gc_overhead=gc_overhead,
            total=total,
            line_items=line_items
        )

    # Estimate timeline
    total_hours = labor_estimate.get("total_hours", 0)
    base_weeks = max(2, int(total_hours / 40) + 1)  # Assume 1 crew, 40 hrs/week

    permit_timeline = 0
    if permit_analysis:
        permit_timeline = permit_analysis.get("total_permit_timeline_weeks", 0)

    timeline_weeks = base_weeks + permit_timeline

    # Payment schedule
    payment_schedule = [
        {"milestone": "Contract signing", "percentage": 10, "description": "Deposit to secure project"},
        {"milestone": "Materials ordered", "percentage": 30, "description": "Cover material procurement"},
        {"milestone": "50% completion", "percentage": 30, "description": "Rough work complete"},
        {"milestone": "Final completion", "percentage": 25, "description": "Punch list complete"},
        {"milestone": "Final walkthrough", "percentage": 5, "description": "Held until approval"}
    ]

    # Assumptions and exclusions
    assumptions = [
        "Existing structure is sound and suitable for renovation",
        "Standard working hours (8am-5pm, weekdays)",
        "Owner responsible for permits and approvals",
        "Materials available at quoted prices",
        "No hazardous material remediation required"
    ]

    exclusions = [
        "Architectural or engineering fees",
        "Furniture and decor",
        "Appliances (unless specified)",
        "Unforeseen structural issues",
        "Hazardous material abatement"
    ]

    estimate = FullEstimate(
        project_type=project_type,
        location=location,
        room_sqft=room_sqft,
        tiers=tiers,
        timeline_weeks=timeline_weeks,
        payment_schedule=payment_schedule,
        assumptions=assumptions,
        exclusions=exclusions
    )

    execution_time = (time.time() - start_time) * 1000

    # Confidence based on data completeness
    if labor_estimate.get("total_hours", 0) > 0 and materials:
        confidence = ConfidenceScore.medium(
            reasoning=f"Generated 3-tier estimate for {len(materials)} materials, {timeline_weeks} week timeline"
        )
    else:
        confidence = ConfidenceScore.low(
            reasoning="Limited input data - estimate may need refinement"
        )

    return ToolResult.success_result(
        data=estimate.to_dict(),
        confidence=confidence,
        tool_name=tool_name,
        metadata={
            "execution_time_ms": execution_time,
            "tier_totals": {k: round(v.total, 2) for k, v in tiers.items()}
        }
    )


async def search_local_pricing(
    materials: List[str],
    location: str,
    project_type: str
) -> ToolResult:
    """
    Search for local material pricing using Tavily.

    Args:
        materials: List of materials to price
        location: City/state location
        project_type: Type of project

    Returns:
        ToolResult with pricing data
    """
    start_time = time.time()
    tool_name = "pricing_search"

    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        logger.warning("[pricing_search] TAVILY_API_KEY not configured")
        return ToolResult.success_result(
            data={"prices": BASE_MATERIAL_PRICES.copy(), "source": "default_prices"},
            confidence=ConfidenceScore.low(
                reasoning="Using default prices - Tavily not configured"
            ),
            tool_name=tool_name
        )

    # Build search queries
    material_str = " ".join(materials[:5])
    queries = [
        f"{location} {project_type} renovation cost per sqft 2024",
        f"{location} {material_str} prices contractor",
        f"{location} home renovation material costs",
    ]

    all_results = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for query in queries[:3]:
            try:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": tavily_api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 3
                    }
                )
                response.raise_for_status()
                data = response.json()
                for result in data.get("results", []):
                    all_results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", "")
                    })
            except Exception as e:
                logger.warning(f"[pricing_search] Search failed: {e}")

    if not all_results:
        return ToolResult.success_result(
            data={"prices": BASE_MATERIAL_PRICES.copy(), "source": "default_prices"},
            confidence=ConfidenceScore.medium(
                reasoning="Using default prices - search returned no results"
            ),
            tool_name=tool_name
        )

    # Use Cerebras to extract pricing
    from src.core.llm.provider import LLMProvider

    results_text = "\n\n".join([
        f"Source: {r.get('title', '')}\n{r.get('content', '')}"
        for r in all_results[:6]
    ])

    prompt = f"""Extract material/renovation pricing from these search results for {location}:

{results_text}

Return JSON with material prices (per sqft or unit as appropriate):
{{
  "regional_multiplier": number (1.0 = national average),
  "cost_per_sqft_range": {{"low": x, "mid": y, "high": z}},
  "material_prices": {{
    "material_name": {{"low": x, "mid": y, "high": z, "unit": "sqft/lf/etc"}}
  }},
  "sources": ["url1", "url2"],
  "notes": "any important caveats"
}}

Only include prices you find in the results. Use null for unknown values."""

    try:
        provider = LLMProvider.for_fast_analysis()
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Extract pricing data from search results. Return JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000,
            operation_type="pricing_extraction"
        )

        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(line for line in lines if not line.startswith("```"))

        pricing_data = json.loads(response_text)
        pricing_data["search_results_count"] = len(all_results)

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data=pricing_data,
            confidence=ConfidenceScore.medium(
                reasoning=f"Extracted pricing from {len(all_results)} search results"
            ),
            tool_name=tool_name,
            metadata={
                "execution_time_ms": execution_time,
                "queries_executed": len(queries)
            }
        )

    except Exception as e:
        logger.error(f"[pricing_search] Analysis error: {e}")
        return ToolResult.success_result(
            data={"prices": BASE_MATERIAL_PRICES.copy(), "source": "default_prices"},
            confidence=ConfidenceScore.low(
                reasoning=f"Using default prices - analysis failed: {str(e)}"
            ),
            tool_name=tool_name
        )


def calculate_cost_per_sqft(estimate: Dict[str, Any], tier: str = "mid") -> float:
    """Calculate cost per sqft from estimate."""
    tiers = estimate.get("tiers", {})
    tier_data = tiers.get(tier)
    if not tier_data:
        return 0

    total = tier_data.get("total", 0)
    room_sqft = estimate.get("room_sqft", 1)

    return total / max(room_sqft, 1)


def format_estimate_summary(estimate: Dict[str, Any]) -> str:
    """Format estimate as human-readable summary."""
    tiers = estimate.get("tiers", {})

    lines = [
        f"# Renovation Estimate - {estimate.get('project_type', 'Project')}",
        f"Location: {estimate.get('location', 'Unknown')}",
        f"Room Size: {estimate.get('room_sqft', 0):.0f} sqft",
        f"Timeline: {estimate.get('timeline_weeks', 0)} weeks",
        "",
        "## Cost Summary",
        ""
    ]

    for tier_key in ["low", "mid", "high"]:
        tier = tiers.get(tier_key, {})
        name = tier.get("name", tier_key.title())
        total = tier.get("total", 0)
        cost_per_sqft = total / max(estimate.get("room_sqft", 1), 1)

        lines.append(f"**{name}**: ${total:,.0f} (${cost_per_sqft:.0f}/sqft)")

    lines.extend([
        "",
        "## Payment Schedule",
        ""
    ])

    for payment in estimate.get("payment_schedule", []):
        lines.append(f"- {payment['milestone']}: {payment['percentage']}%")

    return "\n".join(lines)
