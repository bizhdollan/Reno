"""
Measurement Estimation Tool

Estimates room dimensions from images using reference objects
and provides area/volume calculations for estimation.
"""
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from src.core.logger import get_logger
from src.core.tools.base import (
    ToolResult,
    ConfidenceScore,
    HITLQuestion,
    Priority,
    QuestionCategory,
)

logger = get_logger(__name__)

# Standard reference dimensions (in feet)
REFERENCE_DIMENSIONS = {
    # Doors
    "standard_door_height": 6.67,  # 80 inches
    "standard_door_width": 2.67,   # 32 inches
    "wide_door_width": 3.0,        # 36 inches

    # Windows
    "standard_window_height": 4.0,
    "standard_window_width": 3.0,

    # Counters and cabinets
    "counter_height": 3.0,         # 36 inches
    "base_cabinet_height": 2.83,   # 34 inches
    "upper_cabinet_height": 2.5,   # 30 inches

    # Appliances
    "refrigerator_height": 5.75,
    "refrigerator_width": 3.0,
    "stove_width": 2.5,
    "dishwasher_width": 2.0,

    # Fixtures
    "toilet_height": 1.25,
    "vanity_height": 2.67,         # 32 inches
    "standard_tub_length": 5.0,

    # Furniture
    "dining_chair_height": 3.0,
    "standard_bed_length": 6.67,   # Queen/King length

    # Ceiling
    "standard_ceiling_height": 8.0,
    "high_ceiling_height": 9.0,
}


@dataclass
class RoomMeasurements:
    """Calculated room measurements."""
    width_ft: Optional[float]
    length_ft: Optional[float]
    height_ft: Optional[float]
    floor_sqft: Optional[float]
    wall_sqft: Optional[float]
    ceiling_sqft: Optional[float]
    volume_cuft: Optional[float]
    perimeter_ft: Optional[float]

    # Confidence tracking
    width_confidence: ConfidenceScore
    length_confidence: ConfidenceScore
    height_confidence: ConfidenceScore

    # References used
    references_detected: List[str]

    def to_dict(self) -> dict:
        return {
            "width_ft": self.width_ft,
            "length_ft": self.length_ft,
            "height_ft": self.height_ft,
            "floor_sqft": self.floor_sqft,
            "wall_sqft": self.wall_sqft,
            "ceiling_sqft": self.ceiling_sqft,
            "volume_cuft": self.volume_cuft,
            "perimeter_ft": self.perimeter_ft,
            "width_confidence": self.width_confidence.to_dict(),
            "length_confidence": self.length_confidence.to_dict(),
            "height_confidence": self.height_confidence.to_dict(),
            "references_detected": self.references_detected,
        }


def calculate_derived_measurements(
    width_ft: Optional[float],
    length_ft: Optional[float],
    height_ft: Optional[float]
) -> Dict[str, Optional[float]]:
    """Calculate derived measurements from dimensions."""
    floor_sqft = None
    wall_sqft = None
    ceiling_sqft = None
    volume_cuft = None
    perimeter_ft = None

    if width_ft and length_ft:
        floor_sqft = round(width_ft * length_ft, 1)
        ceiling_sqft = floor_sqft
        perimeter_ft = round(2 * (width_ft + length_ft), 1)

        if height_ft:
            wall_sqft = round(perimeter_ft * height_ft, 1)
            volume_cuft = round(floor_sqft * height_ft, 1)

    return {
        "floor_sqft": floor_sqft,
        "wall_sqft": wall_sqft,
        "ceiling_sqft": ceiling_sqft,
        "volume_cuft": volume_cuft,
        "perimeter_ft": perimeter_ft,
    }


async def estimate_measurements(
    room_analysis_data: Dict[str, Any],
    user_provided_dimensions: Optional[Dict[str, float]] = None
) -> ToolResult:
    """
    Estimate or refine room measurements.

    Uses VLM-detected dimensions and reference objects to estimate
    room measurements. User-provided dimensions override estimates.

    Args:
        room_analysis_data: Output from room_analysis tool
        user_provided_dimensions: Optional user-provided dimensions
            Format: {"width_ft": 12, "length_ft": 15, "height_ft": 9}

    Returns:
        ToolResult with RoomMeasurements
    """
    start_time = time.time()
    tool_name = "measurement_estimation"

    try:
        # Extract VLM-detected dimensions
        vlm_dimensions = room_analysis_data.get("dimensions", {})

        width_data = vlm_dimensions.get("width_ft", {})
        length_data = vlm_dimensions.get("length_ft", {})
        height_data = vlm_dimensions.get("height_ft", {})

        # Start with VLM estimates
        width_ft = width_data.get("value")
        length_ft = length_data.get("value")
        height_ft = height_data.get("value")

        width_conf = ConfidenceScore(
            value=width_data.get("confidence", {}).get("value", 0.3),
            reasoning=width_data.get("confidence", {}).get("reasoning", "VLM estimate"),
            field_name="width_ft"
        )
        length_conf = ConfidenceScore(
            value=length_data.get("confidence", {}).get("value", 0.3),
            reasoning=length_data.get("confidence", {}).get("reasoning", "VLM estimate"),
            field_name="length_ft"
        )
        height_conf = ConfidenceScore(
            value=height_data.get("confidence", {}).get("value", 0.5),
            reasoning=height_data.get("confidence", {}).get("reasoning", "VLM estimate"),
            field_name="height_ft"
        )

        # Override with user-provided dimensions (confidence = 1.0)
        if user_provided_dimensions:
            if "width_ft" in user_provided_dimensions:
                width_ft = user_provided_dimensions["width_ft"]
                width_conf = ConfidenceScore.user_provided(field_name="width_ft")

            if "length_ft" in user_provided_dimensions:
                length_ft = user_provided_dimensions["length_ft"]
                length_conf = ConfidenceScore.user_provided(field_name="length_ft")

            if "height_ft" in user_provided_dimensions:
                height_ft = user_provided_dimensions["height_ft"]
                height_conf = ConfidenceScore.user_provided(field_name="height_ft")

        # Detect reference objects from room analysis
        references_detected = []

        fixtures = room_analysis_data.get("fixtures", [])
        appliances = room_analysis_data.get("appliances", [])

        for fixture in fixtures:
            name = fixture.get("name", "").lower()
            if "door" in name:
                references_detected.append("standard_door")
            if "window" in name:
                references_detected.append("window")
            if "toilet" in name:
                references_detected.append("toilet")

        for appliance in appliances:
            name = appliance.get("name", "").lower()
            if "refrigerator" in name or "fridge" in name:
                references_detected.append("refrigerator")
            if "stove" in name or "range" in name:
                references_detected.append("stove")

        # Default height if not detected (standard 8ft ceiling)
        if height_ft is None:
            height_ft = REFERENCE_DIMENSIONS["standard_ceiling_height"]
            height_conf = ConfidenceScore(
                value=0.5,
                reasoning="Assumed standard 8ft ceiling",
                field_name="height_ft"
            )

        # Calculate derived measurements
        derived = calculate_derived_measurements(width_ft, length_ft, height_ft)

        measurements = RoomMeasurements(
            width_ft=width_ft,
            length_ft=length_ft,
            height_ft=height_ft,
            floor_sqft=derived["floor_sqft"],
            wall_sqft=derived["wall_sqft"],
            ceiling_sqft=derived["ceiling_sqft"],
            volume_cuft=derived["volume_cuft"],
            perimeter_ft=derived["perimeter_ft"],
            width_confidence=width_conf,
            length_confidence=length_conf,
            height_confidence=height_conf,
            references_detected=references_detected
        )

        # Generate HITL questions for missing/low-confidence dimensions
        hitl_questions = []

        if width_ft is None or width_conf.requires_human_input():
            hitl_questions.append(HITLQuestion(
                question=f"What is the room width in feet? (Estimated: {width_ft or 'unknown'})",
                field_name="width_ft",
                category=QuestionCategory.DIMENSIONS,
                priority=Priority.HIGH,
                current_value=width_ft,
                confidence=width_conf
            ))

        if length_ft is None or length_conf.requires_human_input():
            hitl_questions.append(HITLQuestion(
                question=f"What is the room length in feet? (Estimated: {length_ft or 'unknown'})",
                field_name="length_ft",
                category=QuestionCategory.DIMENSIONS,
                priority=Priority.HIGH,
                current_value=length_ft,
                confidence=length_conf
            ))

        # Calculate overall confidence
        conf_values = [width_conf.value, length_conf.value, height_conf.value]
        avg_conf = sum(conf_values) / len(conf_values)

        overall_confidence = ConfidenceScore(
            value=avg_conf,
            reasoning=f"Average of dimension confidences. References: {len(references_detected)}"
        )

        execution_time = (time.time() - start_time) * 1000

        return ToolResult(
            success=True,
            data=measurements.to_dict(),
            confidence=overall_confidence,
            hitl_questions=hitl_questions,
            tool_name=tool_name,
            execution_time_ms=execution_time,
            metadata={
                "references_count": len(references_detected),
                "user_overrides": list(user_provided_dimensions.keys()) if user_provided_dimensions else []
            }
        )

    except Exception as e:
        logger.error(f"[measurement_estimation] Error: {e}")
        return ToolResult.error_result(
            error=f"Measurement estimation failed: {str(e)}",
            tool_name=tool_name
        )


async def calculate_material_quantities(
    measurements: Dict[str, Any],
    materials_needed: List[str],
    waste_factor: float = 0.10
) -> ToolResult:
    """
    Calculate material quantities based on room measurements.

    Args:
        measurements: RoomMeasurements dict
        materials_needed: List of material types ("flooring", "paint", "tile", etc.)
        waste_factor: Waste factor to add (default 10%)

    Returns:
        ToolResult with material quantities
    """
    start_time = time.time()
    tool_name = "material_quantity_calculation"

    try:
        floor_sqft = measurements.get("floor_sqft")
        wall_sqft = measurements.get("wall_sqft")
        ceiling_sqft = measurements.get("ceiling_sqft")
        perimeter_ft = measurements.get("perimeter_ft")

        quantities = {}

        for material in materials_needed:
            material_lower = material.lower()

            if material_lower in ["flooring", "tile_floor", "hardwood", "carpet", "laminate", "vinyl"]:
                if floor_sqft:
                    qty = floor_sqft * (1 + waste_factor)
                    quantities[material] = {
                        "quantity": round(qty, 1),
                        "unit": "sqft",
                        "base_area": floor_sqft,
                        "waste_factor": waste_factor
                    }

            elif material_lower in ["paint", "wall_paint"]:
                if wall_sqft:
                    # Paint coverage: ~350 sqft per gallon
                    sqft_with_waste = wall_sqft * (1 + waste_factor)
                    gallons = sqft_with_waste / 350
                    quantities[material] = {
                        "quantity": round(gallons, 1),
                        "unit": "gallons",
                        "coverage_sqft": round(sqft_with_waste, 1),
                        "waste_factor": waste_factor
                    }

            elif material_lower in ["ceiling_paint", "ceiling"]:
                if ceiling_sqft:
                    sqft_with_waste = ceiling_sqft * (1 + waste_factor)
                    gallons = sqft_with_waste / 350
                    quantities[material] = {
                        "quantity": round(gallons, 1),
                        "unit": "gallons",
                        "coverage_sqft": round(sqft_with_waste, 1),
                        "waste_factor": waste_factor
                    }

            elif material_lower in ["wall_tile", "backsplash"]:
                if wall_sqft:
                    # Assume backsplash is ~15% of wall area
                    backsplash_sqft = wall_sqft * 0.15 if "backsplash" in material_lower else wall_sqft
                    qty = backsplash_sqft * (1 + waste_factor)
                    quantities[material] = {
                        "quantity": round(qty, 1),
                        "unit": "sqft",
                        "base_area": round(backsplash_sqft, 1),
                        "waste_factor": waste_factor
                    }

            elif material_lower in ["baseboard", "trim", "crown_molding"]:
                if perimeter_ft:
                    qty = perimeter_ft * (1 + waste_factor)
                    quantities[material] = {
                        "quantity": round(qty, 1),
                        "unit": "linear_ft",
                        "base_perimeter": perimeter_ft,
                        "waste_factor": waste_factor
                    }

            elif material_lower in ["drywall"]:
                if wall_sqft:
                    # Standard drywall sheet: 32 sqft (4x8)
                    sqft_with_waste = wall_sqft * (1 + waste_factor)
                    sheets = sqft_with_waste / 32
                    quantities[material] = {
                        "quantity": round(sheets, 0),
                        "unit": "sheets",
                        "coverage_sqft": round(sqft_with_waste, 1),
                        "waste_factor": waste_factor
                    }

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "quantities": quantities,
                "measurements_used": {
                    "floor_sqft": floor_sqft,
                    "wall_sqft": wall_sqft,
                    "ceiling_sqft": ceiling_sqft,
                    "perimeter_ft": perimeter_ft
                }
            },
            confidence=ConfidenceScore.high(
                reasoning="Calculated from room measurements"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[material_quantity_calculation] Error: {e}")
        return ToolResult.error_result(
            error=f"Material quantity calculation failed: {str(e)}",
            tool_name=tool_name
        )
