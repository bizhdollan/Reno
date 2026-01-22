"""
Unified image analysis - Single VLM call to extract all data.

This replaces 6+ separate VLM calls with 1 comprehensive analysis:
- Room type, materials, measurements, colors
- Fixtures, appliances, style
- Features to retain
- Entity detection (furniture, decor)
- Critical elements for contractors
- Hallucination prevention context

Cost: ~$0.005 per image (vs $0.028 with old approach)
Latency: ~5-8 seconds (vs 30+ seconds with old approach)
"""

from typing import Any
import json
from src.core.llm.provider import LLMProvider
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import (
    load_image_as_base64,
)
from src.core.langgraph.utils import parse_json
from src.core.logger import get_logger

logger = get_logger(__name__)

# Comprehensive JSON schema for all data extraction
UNIFIED_SCHEMA = {
    "type": "object",
    "properties": {
        # Core room analysis
        "room_type": {
            "type": "string",
            "description": "Type of room (bedroom, kitchen, bathroom, living_room, etc.)"
        },
        "room_subtype": {
            "type": "string",
            "description": "Specific subtype (master_bedroom, guest_bathroom, etc.)"
        },
        "dimensions": {
            "type": "object",
            "properties": {
                "length_ft": {"type": "number"},
                "width_ft": {"type": "number"},
                "height_ft": {"type": "number"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
            }
        },

        # Materials and finishes
        "floor": {
            "type": "object",
            "properties": {
                "material": {"type": "string"},
                "condition": {"type": "string"},
                "color": {"type": "string"},
                "estimated_sqft": {"type": "number"}
            }
        },
        "walls": {
            "type": "object",
            "properties": {
                "material": {"type": "string"},
                "condition": {"type": "string"},
                "paint_color": {"type": "string"},
                "has_wallpaper": {"type": "boolean"}
            }
        },
        "ceiling": {
            "type": "object",
            "properties": {
                "material": {"type": "string"},
                "condition": {"type": "string"},
                "height_ft": {"type": "number"}
            }
        },

        # Fixtures and appliances
        "fixtures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "brand": {"type": "string"},
                    "condition": {"type": "string"},
                    "estimated_age_years": {"type": "number"}
                }
            }
        },
        "appliances": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "brand": {"type": "string"},
                    "model": {"type": "string"},
                    "condition": {"type": "string"}
                }
            }
        },

        # Style and aesthetics
        "style": {
            "type": "object",
            "properties": {
                "primary_style": {"type": "string"},
                "color_palette": {"type": "array", "items": {"type": "string"}},
                "lighting_type": {"type": "string"},
                "overall_condition": {"type": "string"}
            }
        },

        # Features to retain (what user might want to keep)
        "features_to_retain": {
            "type": "object",
            "properties": {
                "high_value_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string"},
                            "reason": {"type": "string"},
                            "estimated_value": {"type": "string"}
                        }
                    }
                },
                "architectural_features": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "recommendation": {"type": "string"}
            }
        },

        # Entity detection (furniture, decor, items visible)
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "item": {"type": "string"},
                    "location": {"type": "string"},
                    "removable": {"type": "boolean"}
                }
            }
        },

        # Structural and critical elements
        "structural_elements": {
            "type": "object",
            "properties": {
                "windows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "number"},
                            "type": {"type": "string"},
                            "condition": {"type": "string"}
                        }
                    }
                },
                "doors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "number"},
                            "type": {"type": "string"},
                            "condition": {"type": "string"}
                        }
                    }
                },
                "electrical_outlets": {"type": "number"},
                "hvac_vents": {"type": "number"},
                "visible_issues": {"type": "array", "items": {"type": "string"}}
            }
        },

        # Contractor search context
        "contractor_context": {
            "type": "object",
            "properties": {
                "primary_work_needed": {"type": "array", "items": {"type": "string"}},
                "specialty_required": {"type": "array", "items": {"type": "string"}},
                "urgency_indicators": {"type": "array", "items": {"type": "string"}},
                "search_keywords": {"type": "array", "items": {"type": "string"}}
            }
        },

        # Hallucination prevention
        "confidence_notes": {
            "type": "object",
            "properties": {
                "clearly_visible": {"type": "array", "items": {"type": "string"}},
                "partially_visible": {"type": "array", "items": {"type": "string"}},
                "not_visible": {"type": "array", "items": {"type": "string"}},
                "assumptions_made": {"type": "array", "items": {"type": "string"}}
            }
        }
    },
    "required": ["room_type", "style", "confidence_notes"]
}


UNIFIED_PROMPT = """You are an expert home renovation analyst. Analyze this image comprehensively and extract ALL relevant information in a single response.

**Critical Instructions:**
1. Only describe what you can CLEARLY see in the image - do not make assumptions
2. If something is not visible or unclear, explicitly note it in confidence_notes
3. Be specific about materials, colors, conditions, and measurements
4. Identify both permanent fixtures and removable items
5. Note any visible damage, wear, or issues that would affect renovation

**What to Extract:**

**1. Room Identification:**
- Room type (bedroom, kitchen, bathroom, living room, etc.)
- Room subtype (master bedroom, guest bathroom, etc.)
- Approximate dimensions (length × width × height in feet)

**2. Materials & Finishes:**
- Floor: material, condition, color, estimated square footage
- Walls: material, condition, paint color, wallpaper presence
- Ceiling: material, condition, height

**3. Fixtures & Appliances:**
- List all fixed fixtures (sinks, toilets, tubs, cabinets, countertops, lighting)
- List all appliances (refrigerator, stove, dishwasher, etc.)
- For each: type, brand (if visible), condition, estimated age

**4. Style & Aesthetics:**
- Primary design style (modern, traditional, industrial, farmhouse, etc.)
- Color palette (dominant colors)
- Lighting type and quality
- Overall condition rating

**5. Features Worth Retaining:**
- High-value items that might be worth keeping (custom cabinets, quality fixtures, etc.)
- Architectural features (crown molding, built-ins, original hardwood, etc.)
- Recommendation on what to retain vs. replace

**6. Entities Present (for removal during renovation):**
- Furniture items and their locations
- Decor items (curtains, rugs, artwork, etc.)
- Personal items
- Mark each as removable or built-in

**7. Structural Elements:**
- Windows: count, type, condition
- Doors: count, type, condition
- Electrical outlets visible
- HVAC vents visible
- Any visible structural issues (cracks, water damage, uneven surfaces)

**8. Contractor Context:**
- Primary work needed (flooring, painting, plumbing, electrical, etc.)
- Required specialties (tile work, cabinet installation, etc.)
- Urgency indicators (safety issues, major damage)
- Keywords for contractor search

**9. Confidence Notes:**
- What is clearly visible and certain
- What is partially visible or estimated
- What is NOT visible in this image
- Any assumptions you had to make

Respond with detailed, structured JSON following the schema provided. Be thorough but factual - this data will be used for renovation cost estimation.
"""


async def unified_image_analysis(
    image_url: str,
    project_title: str | None = None,
    project_type: str | None = None,
    additional_context: str | None = None
) -> dict[str, Any]:
    """
    Perform comprehensive image analysis with a single VLM call.

    This replaces multiple separate calls:
    - Entity detection
    - Room analysis
    - Features to retain
    - Critical elements
    - Service analysis

    Args:
        image_url: URL of the image to analyze
        project_title: Optional project title for context
        project_type: Optional project type (renovation, remodel, etc.)
        additional_context: Optional additional context from user

    Returns:
        Comprehensive analysis dict matching UNIFIED_SCHEMA
    """
    # Build context-aware prompt
    context_parts = []
    if project_title:
        context_parts.append(f"Project: {project_title}")
    if project_type:
        context_parts.append(f"Type: {project_type}")
    if additional_context:
        context_parts.append(f"User notes: {additional_context}")

    context_prefix = "\n".join(context_parts) + "\n\n" if context_parts else ""

    final_prompt = context_prefix + UNIFIED_PROMPT

    # Load image as base64
    image_data_url = await load_image_as_base64(image_url)

    # Single VLM call with vision
    provider = LLMProvider.for_vlm()

    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "You are a renovation expert analyzing images. Extract all relevant data comprehensively and accurately. Return JSON only, no markdown."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": final_prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ],
        temperature=0.3,
        max_tokens=3000,  # Large enough for comprehensive response
        operation_type="unified_image_analysis"
    )

    # Parse JSON response
    try:
        result = parse_json(response)
    except Exception as e:
        logger.error(f"[unified_analysis] Failed to parse VLM response: {e}")
        raise ValueError(f"Invalid JSON response from VLM: {e}")

    # Ensure required fields exist
    if not result or not isinstance(result, dict):
        raise ValueError("Empty or invalid response from VLM")

    if "room_type" not in result:
        logger.warning("[unified_analysis] Missing required field: room_type, adding default")
        result["room_type"] = "unknown"

    return result


async def analyze_multiple_images_unified(
    image_urls: list[str],
    project_title: str | None = None,
    project_type: str | None = None,
    additional_context: str | None = None
) -> list[dict[str, Any]]:
    """
    Analyze multiple images in parallel using unified analysis.

    Args:
        image_urls: List of image URLs to analyze
        project_title: Optional project title for context
        project_type: Optional project type
        additional_context: Optional additional context

    Returns:
        List of comprehensive analysis dicts
    """
    import asyncio

    tasks = [
        unified_image_analysis(
            image_url=url,
            project_title=project_title,
            project_type=project_type,
            additional_context=additional_context
        )
        for url in image_urls
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle any errors
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Log error but continue with other images
            print(f"Error analyzing image {i}: {result}")
            continue
        processed_results.append(result)

    return processed_results
