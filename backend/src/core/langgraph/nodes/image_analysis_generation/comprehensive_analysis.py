from typing import Any

from src.core.logger import get_logger
from src.core.llm.provider import LLMProvider
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import (
    load_image_as_base64,
)
from src.core.langgraph.utils import parse_json
from src.core.langgraph.prompts.comprehensive_analysis import (
    get_comprehensive_analysis_prompt,
    COMPREHENSIVE_ANALYSIS_SCHEMA,
)

logger = get_logger(__name__)


# Mapping from SECTION X format to expected flat keys
SECTION_KEY_MAPPING = {
    "SECTION 1": {
        "room_type": "room_type",
        "room_subtype": "room_subtype",
    },
    "SECTION 2": {
        "Room Dimensions": "estimated_dimensions.room",
        "Element Dimensions": "estimated_dimensions.elements",
    },
    "SECTION 3": {
        "Floor": "floor",
        "Walls": "walls",
        "Ceiling": "ceiling",
    },
    "SECTION 4": {
        "Fixtures": "fixtures",
        "Appliances": "appliances",
    },
    "SECTION 5": "_style",  # Direct mapping to style
    "SECTION 6": {
        "Windows": "structural_elements.windows",
        "Doors": "structural_elements.doors",
        "electrical_outlets": "structural_elements.electrical_outlets",
        "light_switches": "structural_elements.light_switches",
        "hvac_vents": "structural_elements.hvac_vents",
    },
    "SECTION 7": {
        "Electrical": "mep_details.electrical",
        "Plumbing": "mep_details.plumbing",
        "HVAC": "mep_details.hvac",
    },
    "SECTION 8": {
        "hazards": "potential_hazards",
    },
    "SECTION 9": "_load_bearing_indicators",  # Direct mapping
    "SECTION 10": "_natural_lighting",  # Direct mapping
    "SECTION 11": {
        "accessibility_features": "accessibility_features",
    },
    "SECTION 12": {
        "furniture": "furniture_details",
    },
    "SECTION 13": {
        "eco_tech_features": "eco_tech_features",
    },
    "SECTION 14": "_image_quality",  # Direct mapping
    "SECTION 15": "_image_scope",  # Direct mapping
    "SECTION 16": "_visible_elements",  # Direct mapping
    "SECTION 17": {
        "must_not_add": "must_not_add",
    },
    "SECTION 18": {
        "features_to_retain": "features_to_retain",
    },
    "SECTION 19": {
        "entities": "entities",
    },
    "SECTION 20": {
        "visible_issues": "visible_issues",
    },
    "SECTION 21": "_contractor_context",  # Direct mapping
    "SECTION 22": "_summary",  # Direct mapping
    "SECTION 23": "_confidence_notes",  # Direct mapping
}


def _normalize_section_format(raw_result: dict) -> dict:
    """
    Normalize VLM response from SECTION X format to expected flat format.

    If the response uses "SECTION 1", "SECTION 2", etc. as keys,
    convert it to the expected flat structure with proper key names.

    Args:
        raw_result: Raw VLM response (may be in SECTION format or correct format)

    Returns:
        Normalized dict with correct key names
    """
    # Check if it's already in the correct format (has room_type at top level)
    if "room_type" in raw_result:
        logger.info("[comprehensive_analysis] Response already in correct format")
        return raw_result

    # Check if it's in SECTION format
    if not any(key.startswith("SECTION") for key in raw_result.keys()):
        logger.warning("[comprehensive_analysis] Unknown response format, returning as-is")
        return raw_result

    logger.info("[comprehensive_analysis] Converting SECTION format to flat format")
    normalized = {}

    # Process each section
    for section_key, section_value in raw_result.items():
        if not section_key.startswith("SECTION"):
            # Unknown key, keep as-is
            normalized[section_key] = section_value
            continue

        mapping = SECTION_KEY_MAPPING.get(section_key)
        if not mapping:
            logger.warning(f"[comprehensive_analysis] Unknown section: {section_key}")
            continue

        # Handle direct mapping (starts with _)
        if isinstance(mapping, str) and mapping.startswith("_"):
            target_key = mapping[1:]  # Remove leading underscore
            normalized[target_key] = section_value
            continue

        # Handle dict mapping
        if isinstance(mapping, dict) and isinstance(section_value, dict):
            for src_key, target_path in mapping.items():
                value = section_value.get(src_key)
                if value is None:
                    continue

                # Handle nested paths like "estimated_dimensions.room"
                if "." in target_path:
                    parts = target_path.split(".")
                    parent_key = parts[0]
                    child_key = parts[1]

                    if parent_key not in normalized:
                        normalized[parent_key] = {}
                    normalized[parent_key][child_key] = value
                else:
                    normalized[target_path] = value

    return normalized


def _ensure_required_fields(result: dict) -> dict:
    """
    Ensure all required fields exist in the analysis result.
    Adds sensible defaults for missing fields.

    Args:
        result: The raw analysis result from VLM

    Returns:
        Result with all required fields present
    """
    # Room identification defaults
    if "room_type" not in result:
        logger.warning("[comprehensive_analysis] Missing room_type, adding default")
        result["room_type"] = "unknown"

    if "room_subtype" not in result:
        result["room_subtype"] = None

    # Materials defaults
    if "floor" not in result:
        result["floor"] = {
            "material": "unknown",
            "condition": "unknown",
            "color": "unknown",
            "pattern": None
        }

    if "walls" not in result:
        result["walls"] = {
            "material": "unknown",
            "condition": "unknown",
            "paint_color": "unknown",
            "has_wallpaper": False,
            "texture": "unknown"
        }

    if "ceiling" not in result:
        result["ceiling"] = {
            "material": "unknown",
            "condition": "unknown",
            "has_crown_molding": False,
            "has_lighting_fixtures": False
        }

    # Arrays defaults
    if "fixtures" not in result:
        result["fixtures"] = []

    if "appliances" not in result:
        result["appliances"] = []

    if "entities" not in result:
        result["entities"] = []

    if "visible_issues" not in result:
        result["visible_issues"] = []

    # Style defaults
    if "style" not in result:
        result["style"] = {
            "primary_style": "unknown",
            "secondary_style": None,
            "color_palette": [],
            "lighting_type": "unknown",
            "overall_condition": "unknown"
        }

    # Structural elements defaults
    if "structural_elements" not in result:
        result["structural_elements"] = {
            "windows": [],
            "doors": [],
            "electrical_outlets": 0,
            "light_switches": 0,
            "hvac_vents": 0
        }

    # Image scope defaults (critical for VGM)
    if "image_scope" not in result:
        logger.warning("[comprehensive_analysis] Missing image_scope, adding default full_room")
        result["image_scope"] = {
            "frame_type": "full_room",
            "room_coverage_pct": 100,
            "camera_angle": "eye_level",
            "camera_position": "unknown"
        }

    # Visible elements defaults (critical for VGM)
    if "visible_elements" not in result:
        logger.warning("[comprehensive_analysis] Missing visible_elements, adding defaults")
        result["visible_elements"] = {
            "walls": "Not analyzed",
            "floor": "Not analyzed",
            "windows": "Not analyzed",
            "doors": "Not analyzed",
            "fixtures": [],
            "furniture": [],
            "ceiling": "Not analyzed"
        }

    # VGM constraints defaults (critical)
    if "must_not_add" not in result:
        logger.warning("[comprehensive_analysis] Missing must_not_add, generating defaults")
        result["must_not_add"] = _generate_default_must_not_add(result.get("visible_elements", {}))

    if "features_to_retain" not in result:
        result["features_to_retain"] = []

    # Contractor context defaults
    if "contractor_context" not in result:
        result["contractor_context"] = {
            "detected_era": None,
            "style_assessment": "",
            "primary_work_needed": [],
            "specialty_required": [],
            "urgency_indicators": [],
            "search_keywords": [],
            "problem_areas": [],
            "renovation_scope": "moderate"
        }

    # Summary defaults
    if "summary" not in result:
        room_type = result.get("room_type", "room")
        result["summary"] = {
            "brief_description": f"A {room_type} space.",
            "room_vibe": "neutral"
        }

    # Confidence notes defaults
    if "confidence_notes" not in result:
        result["confidence_notes"] = {
            "clearly_visible": [],
            "partially_visible": [],
            "not_visible": [],
            "assumptions_made": []
        }

    # === NEW FIELDS ===

    # Estimated dimensions defaults
    if "estimated_dimensions" not in result:
        result["estimated_dimensions"] = {
            "room": {
                "width_ft": None,
                "length_ft": None,
                "height_ft": None,
                "area_sqft": None,
                "confidence": 0.0,
                "visual_cues_used": []
            },
            "elements": []
        }

    # MEP details defaults
    if "mep_details" not in result:
        result["mep_details"] = {
            "electrical": {
                "outlet_type": "unknown",
                "visible_wiring": False,
                "estimated_era": None,
                "notes": []
            },
            "plumbing": {
                "visible_pipes": False,
                "pipe_material": None,
                "fixture_connections": [],
                "notes": []
            },
            "hvac": {
                "vent_type": None,
                "thermostat_type": None,
                "radiators_visible": False,
                "notes": []
            }
        }

    # Potential hazards defaults
    if "potential_hazards" not in result:
        result["potential_hazards"] = []

    # Load bearing indicators defaults
    if "load_bearing_indicators" not in result:
        result["load_bearing_indicators"] = {
            "potential_load_bearing_walls": [],
            "visible_beams": [],
            "structural_columns": [],
            "confidence_notes": "Cannot determine load-bearing status from image alone"
        }

    # Natural lighting defaults
    if "natural_lighting" not in result:
        result["natural_lighting"] = {
            "light_quality": "unknown",
            "primary_light_direction": None,
            "window_orientation_guess": None,
            "shadows_indicate": None,
            "artificial_lighting_on": False
        }

    # Accessibility features defaults
    if "accessibility_features" not in result:
        result["accessibility_features"] = []

    # Furniture details defaults
    if "furniture_details" not in result:
        result["furniture_details"] = []

    # Eco/tech features defaults
    if "eco_tech_features" not in result:
        result["eco_tech_features"] = []

    # Image quality defaults
    if "image_quality" not in result:
        result["image_quality"] = {
            "overall_quality": "unknown",
            "lighting_quality": "unknown",
            "coverage_adequate": True,
            "recommendations": []
        }

    return result


def _generate_default_must_not_add(visible_elements: dict) -> list[str]:
    """
    Generate must_not_add list based on what's NOT visible in visible_elements.

    Args:
        visible_elements: Dict describing what's visible in the image

    Returns:
        List of constraints for VGM
    """
    must_not_add = []

    # Check windows
    windows = visible_elements.get("windows", "")
    if not windows or "not visible" in str(windows).lower() or "none" in str(windows).lower():
        must_not_add.append("Do not add windows (none visible in original image)")

    # Check doors
    doors = visible_elements.get("doors", "")
    if not doors or "not visible" in str(doors).lower() or "none" in str(doors).lower():
        must_not_add.append("Do not add doors (none visible in original image)")

    # Check furniture
    furniture = visible_elements.get("furniture", [])
    if not furniture or (isinstance(furniture, list) and len(furniture) == 0):
        must_not_add.append("Do not add furniture, beds, or couches (none visible in original)")
    elif isinstance(furniture, str) and ("none" in furniture.lower() or "not visible" in furniture.lower()):
        must_not_add.append("Do not add furniture, beds, or couches (none visible in original)")

    # Check ceiling
    ceiling = visible_elements.get("ceiling", "")
    if not ceiling or "not visible" in str(ceiling).lower():
        must_not_add.append("Do not add ceiling fixtures (ceiling not visible)")

    # Always include frame constraint
    must_not_add.append("Do not expand beyond the visible frame of the original image")
    must_not_add.append("Do not change the room layout or add architectural features not in original")

    return must_not_add


def _convert_to_legacy_extracted_data(comprehensive: dict) -> dict:
    """
    Convert comprehensive analysis to legacy extracted_data format.

    This maintains backward compatibility with existing code that expects
    the old format (materials list, measurements dict, etc.)

    Args:
        comprehensive: The comprehensive analysis result

    Returns:
        Legacy format extracted_data dict
    """
    legacy = {}

    # Materials (convert floor/walls to materials list)
    materials = []
    if comprehensive.get("floor"):
        floor = comprehensive["floor"]
        materials.append({
            "name": "Floor",
            "type": floor.get("material", "Unknown"),
            "finish": floor.get("color", ""),
            "condition": floor.get("condition", "")
        })
    if comprehensive.get("walls"):
        walls = comprehensive["walls"]
        materials.append({
            "name": "Walls",
            "type": walls.get("material", "Unknown"),
            "finish": walls.get("paint_color", ""),
            "condition": walls.get("condition", "")
        })
    if comprehensive.get("ceiling"):
        ceiling = comprehensive["ceiling"]
        materials.append({
            "name": "Ceiling",
            "type": ceiling.get("material", "Unknown"),
            "finish": "",
            "condition": ceiling.get("condition", "")
        })
    if materials:
        legacy["materials"] = materials

    # Note: measurements are NOT extracted - user provides manually
    # legacy["measurements"] = {} - intentionally omitted

    # Colors (extract from materials)
    colors = []
    if comprehensive.get("floor", {}).get("color"):
        colors.append({
            "element": "Floor",
            "color": comprehensive["floor"]["color"]
        })
    if comprehensive.get("walls", {}).get("paint_color"):
        colors.append({
            "element": "Walls",
            "color": comprehensive["walls"]["paint_color"]
        })
    if colors:
        legacy["colors"] = colors

    # Fixtures
    if comprehensive.get("fixtures"):
        legacy["fixtures"] = [
            {
                "name": f.get("type", "Unknown"),
                "type": f.get("type", "Unknown"),
                "condition": f.get("condition", ""),
                "style": f.get("style", "")
            }
            for f in comprehensive["fixtures"]
        ]

    # Appliances
    if comprehensive.get("appliances"):
        legacy["appliances"] = [
            {
                "name": a.get("type", "Unknown"),
                "type": a.get("type", "Unknown"),
                "brand": a.get("brand", "")
            }
            for a in comprehensive["appliances"]
        ]

    # Style
    if comprehensive.get("style"):
        style = comprehensive["style"]
        legacy["style"] = {
            "overall_style": style.get("primary_style", ""),
            "condition": style.get("overall_condition", "")
        }

    # Search context (from contractor_context)
    if comprehensive.get("contractor_context"):
        ctx = comprehensive["contractor_context"]
        legacy["search_context"] = {
            "detected_era": ctx.get("detected_era"),
            "style_assessment": ctx.get("style_assessment"),
            "problem_areas": ctx.get("problem_areas", []),
            "renovation_scope": ctx.get("renovation_scope"),
            "material_indicators": ctx.get("primary_work_needed", []),
            "search_keywords": ctx.get("search_keywords", [])
        }

    # Entities
    if comprehensive.get("entities"):
        legacy["entities"] = comprehensive["entities"]

    # Features to retain
    if comprehensive.get("features_to_retain"):
        legacy["features_to_retain"] = comprehensive["features_to_retain"]

    return legacy


async def comprehensive_image_analysis(
    image_url: str,
    project_title: str | None = None,
    project_type: str | None = None,
    additional_context: str | None = None
) -> dict[str, Any]:
    """
    Perform comprehensive image analysis with a SINGLE VLM call.

    This function extracts ALL required data from a room image:
    - Room identification
    - Materials & surfaces
    - Fixtures & appliances
    - Style assessment
    - Structural elements
    - Image scope (critical for VGM)
    - Visible elements inventory
    - Must not add constraints (hallucination prevention)
    - Features to retain
    - Entities (for UI overlay)
    - Visible issues
    - Contractor search context
    - UI summary
    - Confidence notes

    Args:
        image_url: URL of the image to analyze (can be file path or data URL)
        project_title: Optional project title for context
        project_type: Optional project type (bedroom, kitchen, etc.)
        additional_context: Optional additional user-provided context

    Returns:
        Comprehensive analysis dict with all extracted data

    Raises:
        ValueError: If the VLM response is invalid or cannot be parsed
    """
    logger.info(f"[comprehensive_analysis] Starting analysis for image: {image_url[:80]}...")

    # Build the prompt with context
    prompt = get_comprehensive_analysis_prompt(
        project_title=project_title,
        project_type=project_type,
        additional_context=additional_context
    )

    # Load image as base64
    try:
        image_data_url = await load_image_as_base64(image_url)
        logger.info("[comprehensive_analysis] Image loaded successfully")
    except Exception as e:
        logger.error(f"[comprehensive_analysis] Failed to load image: {e}")
        raise ValueError(f"Failed to load image: {e}") from e

    # Single VLM call
    provider = LLMProvider.for_vlm()

    logger.info("[comprehensive_analysis] Calling VLM for comprehensive analysis...")

    try:
        response = await provider.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert renovation analyst. Analyze the image comprehensively and return structured JSON. Be thorough, accurate, and conservative - only describe what you can clearly see."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]
                }
            ],
            temperature=0.2,  # Low temperature for consistent, accurate extraction
            max_tokens=15000,  # Large enough for comprehensive response
            operation_type="comprehensive_image_analysis"
        )
    except Exception as e:
        logger.error(f"[comprehensive_analysis] VLM call failed: {e}")
        raise ValueError(f"VLM analysis failed: {e}") from e

    # Parse JSON response
    try:
        result = parse_json(response)
        with open("comprehensive_analysis_response.json", "w") as f:
            import json
            json.dump(result, f, indent=2)
    except Exception as e:
        logger.error(f"[comprehensive_analysis] Failed to parse VLM response: {e}")
        logger.error(f"[comprehensive_analysis] Raw response: {response[:500]}...")
        raise ValueError(f"Invalid JSON response from VLM: {e}") from e

    # Validate result
    if not result or not isinstance(result, dict):
        logger.error("[comprehensive_analysis] Empty or invalid response from VLM")
        raise ValueError("Empty or invalid response from VLM")

    # Normalize SECTION format to flat format if needed
    result = _normalize_section_format(result)

    # Ensure all required fields exist
    result = _ensure_required_fields(result)

    # Log key findings
    logger.info(f"[comprehensive_analysis] Room type: {result.get('room_type')}")
    logger.info(f"[comprehensive_analysis] Image scope: {result.get('image_scope', {}).get('frame_type')} "
                f"(~{result.get('image_scope', {}).get('room_coverage_pct', 0)}% coverage)")
    logger.info(f"[comprehensive_analysis] Entities found: {len(result.get('entities', []))}")
    logger.info(f"[comprehensive_analysis] Must NOT add: {len(result.get('must_not_add', []))} constraints")
    logger.info(f"[comprehensive_analysis] Features to retain: {len(result.get('features_to_retain', []))}")
    logger.info(f"[comprehensive_analysis] Visible issues: {len(result.get('visible_issues', []))}")
    logger.info(f"[comprehensive_analysis] Summary: {result.get('summary', {}).get('brief_description', '')[:100]}...")

    return result


async def analyze_image_comprehensive(
    image_url: str,
    project_title: str | None = None,
    project_type: str | None = None,
    additional_context: str | None = None
) -> tuple[dict, dict]:
    """
    Analyze image and return both comprehensive and legacy formats.

    This is a convenience function that returns both the full comprehensive
    analysis and the legacy extracted_data format for backward compatibility.

    Args:
        image_url: URL of the image to analyze
        project_title: Optional project title for context
        project_type: Optional project type
        additional_context: Optional additional context

    Returns:
        Tuple of (comprehensive_result, legacy_extracted_data)
    """
    comprehensive = await comprehensive_image_analysis(
        image_url=image_url,
        project_title=project_title,
        project_type=project_type,
        additional_context=additional_context
    )

    legacy = _convert_to_legacy_extracted_data(comprehensive)

    return comprehensive, legacy
