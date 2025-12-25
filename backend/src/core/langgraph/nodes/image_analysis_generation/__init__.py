"""
Image Analysis & Generation Node.

This module handles the entire image analysis flow:
1. analyzing - Process uploaded images, extract ALL data
2. confirming_extraction - User reviews/corrects all extracted data at once
3. collecting_vision - OPTIONAL: collect user's renovation vision
4. generating - Generate proposal/preview image
5. confirming_proposal - User reviews generated image
"""

from src.core.langgraph.nodes.image_analysis_generation.node import (
    image_analysis_generation_node,
)

__all__ = ["image_analysis_generation_node"]
