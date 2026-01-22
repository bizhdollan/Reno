"""
Domain 5: Estimator Tools

Provides cost estimation capabilities:
- Quantity takeoff calculations
- Labor hour estimation by trade
- Local pricing via Tavily + Cerebras
- 3-tier estimate generation
"""

from .quantity_takeoff import (
    calculate_quantities,
    get_waste_factor,
    calculate_paint_gallons,
    QuantityTakeoff,
    MaterialQuantity,
)
from .labor_estimation import (
    estimate_labor,
    search_local_labor_rates,
    get_regional_multiplier,
    LaborEstimate,
    LaborItem,
)
from .pricing_engine import (
    search_local_pricing,
    generate_estimate,
    calculate_cost_per_sqft,
    format_estimate_summary,
    FullEstimate,
    EstimateTier,
    LineItem,
)

__all__ = [
    # Quantity takeoff
    "calculate_quantities",
    "get_waste_factor",
    "calculate_paint_gallons",
    "QuantityTakeoff",
    "MaterialQuantity",
    # Labor estimation
    "estimate_labor",
    "search_local_labor_rates",
    "get_regional_multiplier",
    "LaborEstimate",
    "LaborItem",
    # Pricing engine
    "search_local_pricing",
    "generate_estimate",
    "calculate_cost_per_sqft",
    "format_estimate_summary",
    "FullEstimate",
    "EstimateTier",
    "LineItem",
]
