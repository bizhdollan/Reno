"""
Image Analysis & Generation Node.

This module handles the entire image analysis flow:
1. analyzing - Process uploaded images, extract ALL data
2. confirming_extraction - User reviews/corrects all extracted data at once
3. collecting_vision - OPTIONAL: collect user's renovation vision
4. generating - Generate proposal/preview image
5. confirming_proposal - User reviews generated image

REFACTORED ARCHITECTURE:
- Heavy data stored in database (ImageAnalysis, GenerationHistory, etc.)
- Services handle business logic
- ServiceIntegration provides bridge for gradual migration
"""

from src.core.langgraph.nodes.image_analysis_generation.node import (
    image_analysis_generation_node,
)
from src.core.langgraph.nodes.image_analysis_generation.node_services import (
    ServiceIntegration,
    # analyze_image_with_services,  # DEPRECATED - use analyze_single_image from analysis.py
    should_use_services,
    check_undo_request,
)

__all__ = [
    "image_analysis_generation_node",
    # New refactored architecture
    "ServiceIntegration",
    # "analyze_image_with_services",  # DEPRECATED
    "should_use_services",
    "check_undo_request",
]
