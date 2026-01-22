"""
Labor Estimation Tool

Estimates labor hours by trade using industry standards and local market data.
Integrates with Tavily search for local labor rate insights.
"""
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import httpx

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)

# Standard labor productivity rates (hours per unit)
LABOR_PRODUCTIVITY = {
    # Flooring (hours per 100 sqft)
    "flooring_hardwood": {"hours_per_100sqft": 6, "trade": "flooring"},
    "flooring_laminate": {"hours_per_100sqft": 4, "trade": "flooring"},
    "flooring_tile": {"hours_per_100sqft": 8, "trade": "tile"},
    "flooring_carpet": {"hours_per_100sqft": 2, "trade": "flooring"},
    "flooring_vinyl": {"hours_per_100sqft": 3, "trade": "flooring"},
    "flooring_lvp": {"hours_per_100sqft": 4, "trade": "flooring"},

    # Painting (hours per 100 sqft)
    "paint_walls": {"hours_per_100sqft": 1.5, "trade": "painter"},
    "paint_ceiling": {"hours_per_100sqft": 2, "trade": "painter"},
    "paint_trim": {"hours_per_100lf": 2, "trade": "painter"},

    # Drywall (hours per 100 sqft)
    "drywall_install": {"hours_per_100sqft": 3, "trade": "drywall"},
    "drywall_finish": {"hours_per_100sqft": 4, "trade": "drywall"},

    # Tile (hours per 100 sqft)
    "tile_floor": {"hours_per_100sqft": 8, "trade": "tile"},
    "tile_wall": {"hours_per_100sqft": 10, "trade": "tile"},
    "tile_backsplash": {"hours_per_100sqft": 12, "trade": "tile"},

    # Trim/Molding (hours per 100 linear ft)
    "baseboard": {"hours_per_100lf": 4, "trade": "carpenter"},
    "crown_molding": {"hours_per_100lf": 6, "trade": "carpenter"},
    "door_casing": {"hours_per_door": 1.5, "trade": "carpenter"},

    # Cabinets (hours per linear ft)
    "cabinet_base": {"hours_per_lf": 1.5, "trade": "carpenter"},
    "cabinet_upper": {"hours_per_lf": 1.5, "trade": "carpenter"},
    "cabinet_install": {"hours_per_cabinet": 2, "trade": "carpenter"},

    # Countertops (hours per linear ft)
    "countertop_laminate": {"hours_per_lf": 0.5, "trade": "countertop"},
    "countertop_granite": {"hours_per_lf": 1, "trade": "countertop"},
    "countertop_quartz": {"hours_per_lf": 1, "trade": "countertop"},

    # Plumbing (hours per fixture)
    "plumbing_sink": {"hours_per_fixture": 4, "trade": "plumber"},
    "plumbing_toilet": {"hours_per_fixture": 3, "trade": "plumber"},
    "plumbing_faucet": {"hours_per_fixture": 1.5, "trade": "plumber"},
    "plumbing_shower": {"hours_per_fixture": 8, "trade": "plumber"},
    "plumbing_bathtub": {"hours_per_fixture": 6, "trade": "plumber"},
    "plumbing_disposal": {"hours_per_fixture": 2, "trade": "plumber"},

    # Electrical (hours per item)
    "electrical_outlet": {"hours_per_item": 1, "trade": "electrician"},
    "electrical_switch": {"hours_per_item": 0.75, "trade": "electrician"},
    "electrical_light_fixture": {"hours_per_item": 1.5, "trade": "electrician"},
    "electrical_recessed_light": {"hours_per_item": 2, "trade": "electrician"},
    "electrical_panel_upgrade": {"hours_per_item": 8, "trade": "electrician"},

    # Demo (hours per 100 sqft)
    "demo_flooring": {"hours_per_100sqft": 2, "trade": "demo"},
    "demo_drywall": {"hours_per_100sqft": 1.5, "trade": "demo"},
    "demo_tile": {"hours_per_100sqft": 4, "trade": "demo"},
    "demo_cabinet": {"hours_per_cabinet": 1, "trade": "demo"},

    # Appliances (hours per item)
    "appliance_install": {"hours_per_item": 2, "trade": "general"},
}

# Base labor rates by trade ($/hour) - will be adjusted by location
BASE_LABOR_RATES = {
    "general": 45,
    "demo": 35,
    "flooring": 55,
    "tile": 65,
    "painter": 50,
    "drywall": 55,
    "carpenter": 60,
    "countertop": 70,
    "plumber": 85,
    "electrician": 85,
    "hvac": 90,
    "gc_overhead": 0.15,  # GC markup percentage
}

# Regional cost multipliers (relative to national average)
REGIONAL_MULTIPLIERS = {
    "new york": 1.45,
    "nyc": 1.50,
    "manhattan": 1.60,
    "brooklyn": 1.45,
    "queens": 1.40,
    "san francisco": 1.50,
    "los angeles": 1.30,
    "chicago": 1.15,
    "boston": 1.35,
    "seattle": 1.25,
    "miami": 1.15,
    "denver": 1.10,
    "dallas": 1.00,
    "atlanta": 1.00,
    "phoenix": 0.95,
    "default": 1.0
}


@dataclass
class LaborItem:
    """A single labor line item."""
    task: str
    trade: str
    hours: float
    hourly_rate: float
    total_cost: float
    quantity: float
    unit: str
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "trade": self.trade,
            "hours": round(self.hours, 1),
            "hourly_rate": round(self.hourly_rate, 2),
            "total_cost": round(self.total_cost, 2),
            "quantity": round(self.quantity, 1),
            "unit": self.unit,
            "notes": self.notes
        }


@dataclass
class LaborEstimate:
    """Complete labor estimate."""
    labor_items: List[LaborItem]
    total_hours: float
    total_labor_cost: float
    hours_by_trade: Dict[str, float]
    cost_by_trade: Dict[str, float]
    regional_multiplier: float
    location: str

    def to_dict(self) -> dict:
        return {
            "labor_items": [item.to_dict() for item in self.labor_items],
            "total_hours": round(self.total_hours, 1),
            "total_labor_cost": round(self.total_labor_cost, 2),
            "hours_by_trade": {k: round(v, 1) for k, v in self.hours_by_trade.items()},
            "cost_by_trade": {k: round(v, 2) for k, v in self.cost_by_trade.items()},
            "regional_multiplier": self.regional_multiplier,
            "location": self.location
        }


def get_regional_multiplier(location: str) -> float:
    """Get labor cost multiplier for a location."""
    location_lower = location.lower()
    for key, multiplier in REGIONAL_MULTIPLIERS.items():
        if key in location_lower:
            return multiplier
    return REGIONAL_MULTIPLIERS["default"]


def estimate_labor(
    scope_items: List[Dict[str, Any]],
    quantities: Dict[str, Any],
    location: str,
    project_type: str = "renovation"
) -> ToolResult:
    """
    Estimate labor hours and costs from scope and quantities.

    Args:
        scope_items: List of work items with type and details
        quantities: Quantity takeoff results
        location: Project location for rate adjustment
        project_type: Type of project

    Returns:
        ToolResult with LaborEstimate
    """
    start_time = time.time()
    tool_name = "labor_estimation"

    if not scope_items and not quantities:
        return ToolResult.error_result(
            error="Either scope_items or quantities required",
            tool_name=tool_name
        )

    regional_multiplier = get_regional_multiplier(location)
    labor_items = []
    hours_by_trade = {}
    cost_by_trade = {}

    # Process quantities from takeoff
    materials = quantities.get("materials", [])
    room_sqft = quantities.get("room_sqft", 0)
    wall_sqft = quantities.get("wall_sqft", 0)
    perimeter_ft = quantities.get("perimeter_ft", 0)

    for material in materials:
        material_name = material.get("material", "").lower().replace(" ", "_")
        quantity = material.get("quantity", 0)
        unit = material.get("unit", "sqft")

        # Map material to labor task
        labor_key = _map_material_to_labor(material_name)
        if not labor_key:
            continue

        productivity = LABOR_PRODUCTIVITY.get(labor_key)
        if not productivity:
            continue

        trade = productivity.get("trade", "general")
        base_rate = BASE_LABOR_RATES.get(trade, BASE_LABOR_RATES["general"])
        adjusted_rate = base_rate * regional_multiplier

        # Calculate hours based on productivity rate
        hours = _calculate_hours(productivity, quantity, unit)

        if hours > 0:
            total_cost = hours * adjusted_rate

            labor_items.append(LaborItem(
                task=f"Install {material.get('material', material_name)}",
                trade=trade,
                hours=hours,
                hourly_rate=adjusted_rate,
                total_cost=total_cost,
                quantity=quantity,
                unit=unit
            ))

            hours_by_trade[trade] = hours_by_trade.get(trade, 0) + hours
            cost_by_trade[trade] = cost_by_trade.get(trade, 0) + total_cost

    # Process explicit scope items
    for item in scope_items:
        item_type = item.get("type", "").lower()
        item_quantity = item.get("quantity", 1)
        item_unit = item.get("unit", "each")

        labor_key = _map_scope_to_labor(item_type)
        if not labor_key:
            continue

        productivity = LABOR_PRODUCTIVITY.get(labor_key)
        if not productivity:
            continue

        trade = productivity.get("trade", "general")
        base_rate = BASE_LABOR_RATES.get(trade, BASE_LABOR_RATES["general"])
        adjusted_rate = base_rate * regional_multiplier

        hours = _calculate_hours(productivity, item_quantity, item_unit)

        if hours > 0:
            total_cost = hours * adjusted_rate

            labor_items.append(LaborItem(
                task=item.get("description", item_type),
                trade=trade,
                hours=hours,
                hourly_rate=adjusted_rate,
                total_cost=total_cost,
                quantity=item_quantity,
                unit=item_unit
            ))

            hours_by_trade[trade] = hours_by_trade.get(trade, 0) + hours
            cost_by_trade[trade] = cost_by_trade.get(trade, 0) + total_cost

    # Add demo labor if this is a renovation
    if project_type == "renovation" and materials:
        demo_items = _estimate_demo_labor(materials, regional_multiplier)
        for demo_item in demo_items:
            labor_items.append(demo_item)
            hours_by_trade["demo"] = hours_by_trade.get("demo", 0) + demo_item.hours
            cost_by_trade["demo"] = cost_by_trade.get("demo", 0) + demo_item.total_cost

    total_hours = sum(item.hours for item in labor_items)
    total_labor_cost = sum(item.total_cost for item in labor_items)

    estimate = LaborEstimate(
        labor_items=labor_items,
        total_hours=total_hours,
        total_labor_cost=total_labor_cost,
        hours_by_trade=hours_by_trade,
        cost_by_trade=cost_by_trade,
        regional_multiplier=regional_multiplier,
        location=location
    )

    execution_time = (time.time() - start_time) * 1000

    return ToolResult.success_result(
        data=estimate.to_dict(),
        confidence=ConfidenceScore.medium(
            reasoning=f"Estimated {len(labor_items)} labor items, {total_hours:.0f} total hours"
        ),
        tool_name=tool_name,
        metadata={
            "execution_time_ms": execution_time,
            "regional_multiplier": regional_multiplier,
            "trades_involved": list(hours_by_trade.keys())
        }
    )


def _map_material_to_labor(material_name: str) -> Optional[str]:
    """Map material name to labor productivity key."""
    mappings = {
        "hardwood": "flooring_hardwood",
        "laminate": "flooring_laminate",
        "tile": "flooring_tile",
        "carpet": "flooring_carpet",
        "vinyl": "flooring_vinyl",
        "lvp": "flooring_lvp",
        "paint": "paint_walls",
        "wall_paint": "paint_walls",
        "ceiling_paint": "paint_ceiling",
        "drywall": "drywall_install",
        "baseboard": "baseboard",
        "crown_molding": "crown_molding",
        "wall_tile": "tile_wall",
        "backsplash": "tile_backsplash",
        "countertop": "countertop_granite",
        "granite": "countertop_granite",
        "quartz": "countertop_quartz",
        "cabinets": "cabinet_install",
    }
    return mappings.get(material_name)


def _map_scope_to_labor(scope_type: str) -> Optional[str]:
    """Map scope item type to labor productivity key."""
    mappings = {
        "sink": "plumbing_sink",
        "toilet": "plumbing_toilet",
        "faucet": "plumbing_faucet",
        "shower": "plumbing_shower",
        "bathtub": "plumbing_bathtub",
        "disposal": "plumbing_disposal",
        "outlet": "electrical_outlet",
        "switch": "electrical_switch",
        "light_fixture": "electrical_light_fixture",
        "recessed_light": "electrical_recessed_light",
        "appliance": "appliance_install",
    }
    return mappings.get(scope_type)


def _calculate_hours(productivity: Dict[str, Any], quantity: float, unit: str) -> float:
    """Calculate labor hours from productivity rate and quantity."""
    if "hours_per_100sqft" in productivity:
        # Convert to 100sqft units
        return (quantity / 100) * productivity["hours_per_100sqft"]
    elif "hours_per_100lf" in productivity:
        return (quantity / 100) * productivity["hours_per_100lf"]
    elif "hours_per_lf" in productivity:
        return quantity * productivity["hours_per_lf"]
    elif "hours_per_fixture" in productivity:
        return quantity * productivity["hours_per_fixture"]
    elif "hours_per_item" in productivity:
        return quantity * productivity["hours_per_item"]
    elif "hours_per_door" in productivity:
        return quantity * productivity["hours_per_door"]
    elif "hours_per_cabinet" in productivity:
        return quantity * productivity["hours_per_cabinet"]
    return 0


def _estimate_demo_labor(materials: List[Dict[str, Any]], regional_multiplier: float) -> List[LaborItem]:
    """Estimate demolition labor based on materials being replaced."""
    demo_items = []
    demo_rate = BASE_LABOR_RATES["demo"] * regional_multiplier

    for material in materials:
        material_name = material.get("material", "").lower()
        quantity = material.get("quantity", 0)
        unit = material.get("unit", "sqft")

        if "flooring" in material_name or material_name in ["hardwood", "laminate", "tile", "carpet", "vinyl", "lvp"]:
            hours = (quantity / 100) * LABOR_PRODUCTIVITY.get("demo_flooring", {}).get("hours_per_100sqft", 2)
            if hours > 0:
                demo_items.append(LaborItem(
                    task=f"Demo existing {material_name}",
                    trade="demo",
                    hours=hours,
                    hourly_rate=demo_rate,
                    total_cost=hours * demo_rate,
                    quantity=quantity,
                    unit=unit,
                    notes="Removal of existing material"
                ))

        elif "drywall" in material_name:
            hours = (quantity / 100) * LABOR_PRODUCTIVITY.get("demo_drywall", {}).get("hours_per_100sqft", 1.5)
            if hours > 0:
                demo_items.append(LaborItem(
                    task="Demo existing drywall",
                    trade="demo",
                    hours=hours,
                    hourly_rate=demo_rate,
                    total_cost=hours * demo_rate,
                    quantity=quantity,
                    unit=unit
                ))

    return demo_items


async def search_local_labor_rates(
    location: str,
    trades: List[str]
) -> ToolResult:
    """
    Search for local labor rates using Tavily.

    Args:
        location: City/state location
        trades: List of trades to search for

    Returns:
        ToolResult with labor rate data
    """
    start_time = time.time()
    tool_name = "labor_rate_search"

    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        logger.warning("[labor_rates] TAVILY_API_KEY not configured")
        return ToolResult.success_result(
            data={"rates": {}, "source": "default_rates"},
            confidence=ConfidenceScore.low(
                reasoning="Using default rates - Tavily not configured"
            ),
            tool_name=tool_name
        )

    queries = [
        f"{location} contractor labor rates {' '.join(trades[:3])} 2024",
        f"{location} renovation labor costs per hour",
    ]

    all_results = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for query in queries:
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
                all_results.extend(data.get("results", []))
            except Exception as e:
                logger.warning(f"[labor_rates] Search failed: {e}")

    if not all_results:
        return ToolResult.success_result(
            data={"rates": BASE_LABOR_RATES.copy(), "source": "default_rates"},
            confidence=ConfidenceScore.medium(
                reasoning="Using default rates - search returned no results"
            ),
            tool_name=tool_name
        )

    # Use Cerebras to extract rates from search results
    from src.core.llm.provider import LLMProvider

    results_text = "\n\n".join([
        f"Source: {r.get('title', '')}\n{r.get('content', '')}"
        for r in all_results[:5]
    ])

    prompt = f"""Extract hourly labor rates from these search results for {location}:

{results_text}

Return JSON with rates by trade (in USD/hour):
{{
  "plumber": hourly_rate,
  "electrician": hourly_rate,
  "carpenter": hourly_rate,
  "painter": hourly_rate,
  "tile": hourly_rate,
  "general": hourly_rate,
  "source": "search_results"
}}

If a rate isn't found, omit that trade. Only include rates you're confident about."""

    try:
        provider = LLMProvider.for_fast_analysis()
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Extract labor rates from search results. Return JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
            operation_type="labor_rate_extraction"
        )

        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(line for line in lines if not line.startswith("```"))

        rates_data = json.loads(response_text)

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data=rates_data,
            confidence=ConfidenceScore.medium(
                reasoning=f"Extracted rates from {len(all_results)} search results"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[labor_rates] Analysis error: {e}")
        return ToolResult.success_result(
            data={"rates": BASE_LABOR_RATES.copy(), "source": "default_rates"},
            confidence=ConfidenceScore.low(
                reasoning=f"Using default rates - analysis failed: {str(e)}"
            ),
            tool_name=tool_name
        )
