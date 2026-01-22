"""
Domain 2: Space Understanding Tools

Provides room analysis and measurement capabilities:
- VLM-based room analysis with confidence scores
- Dimension estimation using reference objects
- Structural element and hazard detection
- HITL triggers for low-confidence assessments
"""

from .room_analysis import (
    analyze_room,
    analyze_room_batch,
    RoomAnalysis,
    RoomFeature,
)
from .measurement_estimation import (
    estimate_measurements,
    calculate_material_quantities,
    RoomMeasurements,
    REFERENCE_DIMENSIONS,
)
from .structural_detection import (
    detect_structural_elements,
    assess_renovation_risk,
    StructuralElement,
    StructuralAnalysis,
    HazardIndicator,
)

__all__ = [
    # Room analysis
    "analyze_room",
    "analyze_room_batch",
    "RoomAnalysis",
    "RoomFeature",
    # Measurements
    "estimate_measurements",
    "calculate_material_quantities",
    "RoomMeasurements",
    "REFERENCE_DIMENSIONS",
    # Structural
    "detect_structural_elements",
    "assess_renovation_risk",
    "StructuralElement",
    "StructuralAnalysis",
    "HazardIndicator",
]
