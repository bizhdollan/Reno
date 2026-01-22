"""
Quantity Takeoff Tool

Calculates material quantities from room measurements with waste factors.
Provides itemized quantities for cost estimation.
"""
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)

# Standard waste factors by material type
WASTE_FACTORS = {
    # Flooring
    "hardwood": 0.10,
    "laminate": 0.10,
    "tile": 0.15,  # Higher due to cuts
    "carpet": 0.05,
    "vinyl": 0.08,
    "lvp": 0.10,  # Luxury Vinyl Plank

    # Wall materials
    "drywall": 0.10,
    "paint": 0.05,
    "wallpaper": 0.15,
    "tile_wall": 0.15,

    # Trim
    "baseboard": 0.10,
    "crown_molding": 0.12,
    "door_casing": 0.08,

    # Countertops
    "granite": 0.05,
    "quartz": 0.05,
    "marble": 0.08,
    "butcher_block": 0.05,
    "laminate_counter": 0.05,

    # Default
    "default": 0.10
}

# Standard material unit conversions
MATERIAL_UNITS = {
    "paint": {"coverage_sqft_per_gallon": 350, "unit": "gallons"},
    "primer": {"coverage_sqft_per_gallon": 300, "unit": "gallons"},
    "drywall": {"sheet_sqft": 32, "unit": "sheets"},  # 4x8 sheets
    "plywood": {"sheet_sqft": 32, "unit": "sheets"},
    "cement_board": {"sheet_sqft": 24, "unit": "sheets"},  # 4x6 sheets
}


@dataclass
class MaterialQuantity:
    """A calculated material quantity."""
    material: str
    quantity: float
    unit: str
    base_measurement: float
    base_unit: str
    waste_factor: float
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "material": self.material,
            "quantity": round(self.quantity, 2),
            "unit": self.unit,
            "base_measurement": round(self.base_measurement, 2),
            "base_unit": self.base_unit,
            "waste_factor": self.waste_factor,
            "notes": self.notes
        }


@dataclass
class QuantityTakeoff:
    """Complete quantity takeoff result."""
    room_sqft: float
    wall_sqft: float
    ceiling_sqft: float
    perimeter_ft: float
    materials: List[MaterialQuantity]
    total_items: int

    def to_dict(self) -> dict:
        return {
            "room_sqft": round(self.room_sqft, 1),
            "wall_sqft": round(self.wall_sqft, 1),
            "ceiling_sqft": round(self.ceiling_sqft, 1),
            "perimeter_ft": round(self.perimeter_ft, 1),
            "materials": [m.to_dict() for m in self.materials],
            "total_items": self.total_items
        }


def calculate_quantities(
    width_ft: float,
    length_ft: float,
    height_ft: float,
    materials_to_replace: List[str],
    project_type: str = "renovation"
) -> ToolResult:
    """
    Calculate material quantities with waste factors.

    Args:
        width_ft: Room width in feet
        length_ft: Room length in feet
        height_ft: Room/ceiling height in feet
        materials_to_replace: List of materials needed
        project_type: Type of project for context

    Returns:
        ToolResult with QuantityTakeoff
    """
    start_time = time.time()
    tool_name = "quantity_takeoff"

    if not width_ft or not length_ft or not height_ft:
        return ToolResult.error_result(
            error="All dimensions (width, length, height) are required",
            tool_name=tool_name
        )

    if width_ft <= 0 or length_ft <= 0 or height_ft <= 0:
        return ToolResult.error_result(
            error="Dimensions must be positive numbers",
            tool_name=tool_name
        )

    # Calculate base measurements
    floor_sqft = width_ft * length_ft
    ceiling_sqft = floor_sqft
    perimeter_ft = 2 * (width_ft + length_ft)
    wall_sqft = perimeter_ft * height_ft

    # Subtract for typical door/window openings (rough estimate)
    # Assume 1 door (20 sqft) and windows proportional to floor size
    window_sqft = floor_sqft * 0.05  # 5% of floor area as windows
    door_sqft = 20  # Standard door opening
    net_wall_sqft = max(wall_sqft - window_sqft - door_sqft, wall_sqft * 0.8)

    materials = []

    for material in materials_to_replace:
        material_lower = material.lower().replace(" ", "_")
        waste_factor = WASTE_FACTORS.get(material_lower, WASTE_FACTORS["default"])

        # Flooring materials
        if material_lower in ["hardwood", "laminate", "tile", "carpet", "vinyl", "lvp", "flooring"]:
            qty = floor_sqft * (1 + waste_factor)
            materials.append(MaterialQuantity(
                material=material,
                quantity=qty,
                unit="sqft",
                base_measurement=floor_sqft,
                base_unit="floor_sqft",
                waste_factor=waste_factor
            ))

        # Paint
        elif material_lower in ["paint", "wall_paint"]:
            paint_sqft = net_wall_sqft * (1 + waste_factor)
            gallons = paint_sqft / MATERIAL_UNITS["paint"]["coverage_sqft_per_gallon"]
            # Round up to nearest half gallon
            gallons = round(gallons * 2) / 2
            materials.append(MaterialQuantity(
                material=material,
                quantity=max(gallons, 1),
                unit="gallons",
                base_measurement=net_wall_sqft,
                base_unit="wall_sqft",
                waste_factor=waste_factor,
                notes=f"Covers {paint_sqft:.0f} sqft at 350 sqft/gallon"
            ))

        elif material_lower in ["ceiling_paint"]:
            ceiling_paint_sqft = ceiling_sqft * (1 + waste_factor)
            gallons = ceiling_paint_sqft / MATERIAL_UNITS["paint"]["coverage_sqft_per_gallon"]
            gallons = round(gallons * 2) / 2
            materials.append(MaterialQuantity(
                material=material,
                quantity=max(gallons, 1),
                unit="gallons",
                base_measurement=ceiling_sqft,
                base_unit="ceiling_sqft",
                waste_factor=waste_factor
            ))

        elif material_lower == "primer":
            primer_sqft = net_wall_sqft * (1 + waste_factor)
            gallons = primer_sqft / MATERIAL_UNITS["primer"]["coverage_sqft_per_gallon"]
            gallons = round(gallons * 2) / 2
            materials.append(MaterialQuantity(
                material=material,
                quantity=max(gallons, 1),
                unit="gallons",
                base_measurement=net_wall_sqft,
                base_unit="wall_sqft",
                waste_factor=waste_factor
            ))

        # Drywall
        elif material_lower == "drywall":
            drywall_sqft = net_wall_sqft * (1 + waste_factor)
            sheets = drywall_sqft / MATERIAL_UNITS["drywall"]["sheet_sqft"]
            materials.append(MaterialQuantity(
                material=material,
                quantity=round(sheets + 0.5),  # Round up
                unit="sheets (4x8)",
                base_measurement=net_wall_sqft,
                base_unit="wall_sqft",
                waste_factor=waste_factor
            ))

        # Wall tile
        elif material_lower in ["wall_tile", "backsplash", "tile_wall"]:
            # Backsplash typically 18" high, full walls otherwise
            if "backsplash" in material_lower:
                tile_sqft = perimeter_ft * 1.5 * (1 + waste_factor)  # 18" = 1.5 ft
            else:
                tile_sqft = net_wall_sqft * (1 + waste_factor)
            materials.append(MaterialQuantity(
                material=material,
                quantity=tile_sqft,
                unit="sqft",
                base_measurement=tile_sqft / (1 + waste_factor),
                base_unit="wall_sqft",
                waste_factor=waste_factor
            ))

        # Trim/Molding
        elif material_lower in ["baseboard", "base_molding"]:
            trim_ft = perimeter_ft * (1 + waste_factor)
            materials.append(MaterialQuantity(
                material=material,
                quantity=trim_ft,
                unit="linear_ft",
                base_measurement=perimeter_ft,
                base_unit="perimeter_ft",
                waste_factor=waste_factor
            ))

        elif material_lower in ["crown_molding", "crown"]:
            crown_ft = perimeter_ft * (1 + waste_factor)
            materials.append(MaterialQuantity(
                material=material,
                quantity=crown_ft,
                unit="linear_ft",
                base_measurement=perimeter_ft,
                base_unit="perimeter_ft",
                waste_factor=waste_factor
            ))

        # Countertops (kitchen specific)
        elif material_lower in ["countertop", "granite", "quartz", "marble", "butcher_block", "laminate_counter"]:
            # Estimate countertop as 25" deep around 60% of perimeter
            counter_depth_ft = 25 / 12  # 25 inches in feet
            counter_length_ft = perimeter_ft * 0.6  # Estimate
            counter_sqft = counter_depth_ft * counter_length_ft * (1 + waste_factor)
            materials.append(MaterialQuantity(
                material=material,
                quantity=counter_sqft,
                unit="sqft",
                base_measurement=counter_sqft / (1 + waste_factor),
                base_unit="estimated_counter_area",
                waste_factor=waste_factor,
                notes="Estimate based on 60% perimeter coverage, 25\" depth"
            ))

        # Cabinets (linear feet)
        elif material_lower in ["cabinets", "kitchen_cabinets", "base_cabinets", "upper_cabinets"]:
            # Estimate cabinet linear feet
            cabinet_lf = perimeter_ft * 0.5  # Rough estimate
            materials.append(MaterialQuantity(
                material=material,
                quantity=cabinet_lf,
                unit="linear_ft",
                base_measurement=cabinet_lf,
                base_unit="estimated_linear_ft",
                waste_factor=0,
                notes="Estimate based on 50% perimeter coverage"
            ))

        # Underlayment
        elif material_lower == "underlayment":
            under_sqft = floor_sqft * (1 + waste_factor)
            materials.append(MaterialQuantity(
                material=material,
                quantity=under_sqft,
                unit="sqft",
                base_measurement=floor_sqft,
                base_unit="floor_sqft",
                waste_factor=waste_factor
            ))

        # Default - treat as sqft material
        else:
            materials.append(MaterialQuantity(
                material=material,
                quantity=floor_sqft * (1 + waste_factor),
                unit="sqft",
                base_measurement=floor_sqft,
                base_unit="floor_sqft",
                waste_factor=waste_factor,
                notes="Default calculation based on floor area"
            ))

    takeoff = QuantityTakeoff(
        room_sqft=floor_sqft,
        wall_sqft=net_wall_sqft,
        ceiling_sqft=ceiling_sqft,
        perimeter_ft=perimeter_ft,
        materials=materials,
        total_items=len(materials)
    )

    execution_time = (time.time() - start_time) * 1000

    return ToolResult.success_result(
        data=takeoff.to_dict(),
        confidence=ConfidenceScore.high(
            reasoning=f"Calculated quantities for {len(materials)} materials"
        ),
        tool_name=tool_name,
        metadata={
            "execution_time_ms": execution_time,
            "room_dimensions": f"{width_ft}x{length_ft}x{height_ft}"
        }
    )


def get_waste_factor(material: str) -> float:
    """Get waste factor for a material type."""
    material_lower = material.lower().replace(" ", "_")
    return WASTE_FACTORS.get(material_lower, WASTE_FACTORS["default"])


def calculate_paint_gallons(sqft: float, coats: int = 2) -> float:
    """Calculate gallons of paint needed."""
    coverage = MATERIAL_UNITS["paint"]["coverage_sqft_per_gallon"]
    gallons = (sqft * coats) / coverage
    # Round up to nearest half gallon
    return round(gallons * 2) / 2
