from typing import Any


# JSON Schema for expected output (used for validation)
COMPREHENSIVE_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        # Room identification
        "room_type": {
            "type": "string",
            "description": "Type of room: bedroom, kitchen, bathroom, living_room, dining_room, office, laundry, garage, basement, attic, hallway, closet, other"
        },
        "room_subtype": {
            "type": ["string", "null"],
            "description": "Specific subtype: master_bedroom, guest_bedroom, kids_room, master_bathroom, guest_bathroom, half_bath, etc."
        },

        # === NEW: Estimated Dimensions ===
        "estimated_dimensions": {
            "type": "object",
            "description": "Estimated room and element dimensions based on visual cues",
            "properties": {
                "room": {
                    "type": "object",
                    "properties": {
                        "width_ft": {"type": ["number", "null"]},
                        "length_ft": {"type": ["number", "null"]},
                        "height_ft": {"type": ["number", "null"]},
                        "area_sqft": {"type": ["number", "null"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "visual_cues_used": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "elements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "element_type": {"type": "string"},
                            "element_id": {"type": "string"},
                            "width_inches": {"type": ["number", "null"]},
                            "height_inches": {"type": ["number", "null"]},
                            "depth_inches": {"type": ["number", "null"]},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "visual_cue": {"type": "string"}
                        }
                    }
                }
            }
        },

        # Materials & surfaces
        "floor": {
            "type": "object",
            "properties": {
                "material": {"type": "string"},
                "condition": {"type": "string"},
                "color": {"type": "string"},
                "pattern": {"type": ["string", "null"]},
                "estimated_sqft": {"type": ["number", "null"]}
            }
        },
        "walls": {
            "type": "object",
            "properties": {
                "material": {"type": "string"},
                "condition": {"type": "string"},
                "paint_color": {"type": "string"},
                "has_wallpaper": {"type": "boolean"},
                "texture": {"type": "string"},
                "estimated_wall_sqft": {"type": ["number", "null"]}
            }
        },
        "ceiling": {
            "type": "object",
            "properties": {
                "material": {"type": "string"},
                "condition": {"type": "string"},
                "has_crown_molding": {"type": "boolean"},
                "has_lighting_fixtures": {"type": "boolean"},
                "height_ft": {"type": ["number", "null"]}
            }
        },

        # Fixtures & appliances
        "fixtures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "location": {"type": "string"},
                    "brand": {"type": ["string", "null"]},
                    "condition": {"type": "string"},
                    "style": {"type": "string"},
                    "estimated_age_years": {"type": ["number", "null"]}
                }
            }
        },
        "appliances": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "brand": {"type": ["string", "null"]},
                    "condition": {"type": "string"},
                    "estimated_age_years": {"type": ["number", "null"]},
                    "energy_star_visible": {"type": "boolean"}
                }
            }
        },

        # Style assessment
        "style": {
            "type": "object",
            "properties": {
                "primary_style": {"type": "string"},
                "secondary_style": {"type": ["string", "null"]},
                "color_palette": {"type": "array", "items": {"type": "string"}},
                "lighting_type": {"type": "string"},
                "overall_condition": {"type": "string"}
            }
        },

        # Structural elements
        "structural_elements": {
            "type": "object",
            "properties": {
                "windows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "count": {"type": "integer"},
                            "type": {"type": "string"},
                            "wall_location": {"type": "string"},
                            "condition": {"type": "string"},
                            "width_inches": {"type": ["number", "null"]},
                            "height_inches": {"type": ["number", "null"]}
                        }
                    }
                },
                "doors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "count": {"type": "integer"},
                            "type": {"type": "string"},
                            "wall_location": {"type": "string"},
                            "condition": {"type": "string"},
                            "width_inches": {"type": ["number", "null"]},
                            "height_inches": {"type": ["number", "null"]}
                        }
                    }
                },
                "electrical_outlets": {"type": "integer"},
                "light_switches": {"type": "integer"},
                "hvac_vents": {"type": "integer"}
            }
        },

        # === NEW: MEP Details ===
        "mep_details": {
            "type": "object",
            "description": "Mechanical, Electrical, Plumbing details",
            "properties": {
                "electrical": {
                    "type": "object",
                    "properties": {
                        "outlet_type": {"type": "string", "description": "standard, gfci, usb, smart"},
                        "visible_wiring": {"type": "boolean"},
                        "estimated_era": {"type": ["string", "null"]},
                        "notes": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "plumbing": {
                    "type": "object",
                    "properties": {
                        "visible_pipes": {"type": "boolean"},
                        "pipe_material": {"type": ["string", "null"], "description": "copper, pvc, galvanized, pex"},
                        "fixture_connections": {"type": "array", "items": {"type": "string"}},
                        "notes": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "hvac": {
                    "type": "object",
                    "properties": {
                        "vent_type": {"type": ["string", "null"], "description": "floor, ceiling, wall, baseboard"},
                        "thermostat_type": {"type": ["string", "null"], "description": "manual, programmable, smart"},
                        "radiators_visible": {"type": "boolean"},
                        "notes": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        },

        # === NEW: Potential Hazards ===
        "potential_hazards": {
            "type": "array",
            "description": "Potential hazards based on visual cues and era",
            "items": {
                "type": "object",
                "properties": {
                    "hazard_type": {"type": "string", "description": "asbestos_risk, lead_paint_risk, mold_risk, structural_concern, electrical_hazard, water_damage"},
                    "indicator": {"type": "string"},
                    "location": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "recommendation": {"type": "string"}
                }
            }
        },

        # === NEW: Load Bearing Indicators ===
        "load_bearing_indicators": {
            "type": "object",
            "properties": {
                "potential_load_bearing_walls": {"type": "array", "items": {"type": "string"}},
                "visible_beams": {"type": "array", "items": {"type": "string"}},
                "structural_columns": {"type": "array", "items": {"type": "string"}},
                "confidence_notes": {"type": "string"}
            }
        },

        # === NEW: Natural Lighting ===
        "natural_lighting": {
            "type": "object",
            "properties": {
                "light_quality": {"type": "string", "description": "bright, moderate, dim, dark"},
                "primary_light_direction": {"type": ["string", "null"], "description": "north, south, east, west"},
                "window_orientation_guess": {"type": ["string", "null"]},
                "shadows_indicate": {"type": ["string", "null"]},
                "artificial_lighting_on": {"type": "boolean"}
            }
        },

        # === NEW: Accessibility Features ===
        "accessibility_features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feature_type": {"type": "string", "description": "grab_bar, wide_doorway, ramp, lever_handle, roll_in_shower, lowered_counter, accessible_outlet"},
                    "location": {"type": "string"},
                    "condition": {"type": "string"}
                }
            }
        },

        # === NEW: Furniture Details ===
        "furniture_details": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "style": {"type": "string"},
                    "condition": {"type": "string"},
                    "estimated_value": {"type": "string", "description": "budget, mid-range, high-end, antique"},
                    "removable": {"type": "boolean"},
                    "location": {"type": "string"}
                }
            }
        },

        # === NEW: Eco/Tech Features ===
        "eco_tech_features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feature_type": {"type": "string", "description": "smart_thermostat, usb_outlet, led_lighting, energy_star_appliance, low_flow_fixture, solar_tube, smart_switch"},
                    "location": {"type": "string"},
                    "brand": {"type": ["string", "null"]}
                }
            }
        },

        # === NEW: Image Quality Assessment ===
        "image_quality": {
            "type": "object",
            "properties": {
                "overall_quality": {"type": "string", "description": "excellent, good, fair, poor"},
                "lighting_quality": {"type": "string"},
                "coverage_adequate": {"type": "boolean"},
                "recommendations": {"type": "array", "items": {"type": "string"}}
            }
        },

        # Image scope (critical for VGM)
        "image_scope": {
            "type": "object",
            "properties": {
                "frame_type": {
                    "type": "string",
                    "enum": ["corner_view", "wall_view", "full_room", "detail_closeup"]
                },
                "room_coverage_pct": {"type": "integer", "minimum": 10, "maximum": 100},
                "camera_angle": {
                    "type": "string",
                    "enum": ["eye_level", "low_angle", "high_angle"]
                },
                "camera_position": {"type": "string"}
            }
        },

        # Visible elements (critical for VGM)
        "visible_elements": {
            "type": "object",
            "properties": {
                "walls": {"type": "string"},
                "floor": {"type": "string"},
                "windows": {"type": "string"},
                "doors": {"type": "string"},
                "fixtures": {"type": "array", "items": {"type": "string"}},
                "furniture": {"type": "array", "items": {"type": "string"}},
                "ceiling": {"type": "string"}
            }
        },

        # VGM constraints
        "must_not_add": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of things NOT to add during image generation"
        },
        "features_to_retain": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Structural features to preserve during renovation"
        },

        # Entities (for UI overlay)
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "label": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "category": {"type": "string"},
                    "location": {"type": "string"},
                    "removable": {"type": "boolean"},
                    "has_dimensions": {"type": "boolean"}
                }
            }
        },

        # Visible issues
        "visible_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "location": {"type": "string"},
                    "severity": {"type": "string", "enum": ["minor", "moderate", "severe"]}
                }
            }
        },

        # Contractor search context
        "contractor_context": {
            "type": "object",
            "properties": {
                "detected_era": {"type": ["string", "null"]},
                "style_assessment": {"type": "string"},
                "primary_work_needed": {"type": "array", "items": {"type": "string"}},
                "specialty_required": {"type": "array", "items": {"type": "string"}},
                "urgency_indicators": {"type": "array", "items": {"type": "string"}},
                "search_keywords": {"type": "array", "items": {"type": "string"}},
                "problem_areas": {"type": "array", "items": {"type": "string"}},
                "renovation_scope": {
                    "type": "string",
                    "enum": ["cosmetic", "moderate", "full_renovation"]
                },
                "estimated_budget_tier": {"type": "string", "description": "budget, mid-range, high-end"}
            }
        },

        # UI summary
        "summary": {
            "type": "object",
            "properties": {
                "brief_description": {"type": "string"},
                "room_vibe": {"type": "string"}
            }
        },

        # Confidence notes
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
    "required": [
        "room_type",
        "floor",
        "walls",
        "style",
        "image_scope",
        "visible_elements",
        "must_not_add",
        "entities",
        "summary",
        "confidence_notes"
    ]
}


COMPREHENSIVE_ANALYSIS_PROMPT = """You are an expert home renovation analyst. Analyze this image COMPREHENSIVELY and extract ALL relevant information in a single structured response.

## CRITICAL INSTRUCTIONS

1. **ONLY describe what you can CLEARLY SEE** - Do NOT assume or imagine elements outside the visible frame
2. **Be CONSERVATIVE** - If something is unclear or not visible, explicitly state it
3. **Be SPECIFIC** - Use precise terms for materials, colors, conditions
4. **Focus on renovation-relevant details** - This data is used for cost estimation and image generation
5. **Estimate dimensions CONSERVATIVELY** - Use standard references (doors ~80" tall, outlets ~12" from floor) and note confidence

---

## SECTION 1: ROOM IDENTIFICATION

Identify the room type and subtype:
- **room_type**: bedroom, kitchen, bathroom, living_room, dining_room, office, laundry, garage, basement, hallway, closet, other
- **room_subtype**: master_bedroom, guest_bedroom, kids_room, master_bathroom, guest_bathroom, half_bath, powder_room, en_suite, walk_in_closet, pantry, mudroom, etc. (null if not determinable)

---

## SECTION 2: ESTIMATED DIMENSIONS (CRITICAL FOR COST ESTIMATION)

Estimate dimensions using visual reference cues. Be conservative - only provide estimates when you have reasonable visual cues.

**Standard References to Use:**
- Interior doors: ~80" tall, ~32-36" wide
- Electrical outlets: ~12-18" from floor
- Light switches: ~48" from floor
- Standard ceiling: 8-9 ft
- Double-hung windows: typically 24-36" wide, 36-72" tall
- Kitchen counters: ~36" high, ~25" deep

**Room Dimensions:**
- width_ft, length_ft, height_ft: Estimates based on visible cues (null if not determinable)
- area_sqft: Calculated estimate (null if can't estimate)
- confidence: 0.0-1.0 (be honest - if uncertain, use low confidence)
- visual_cues_used: List what you used to estimate (e.g., "Door height as 80-inch reference", "3 floor tiles visible, assuming 12x12 inch tiles")

**Element Dimensions:**
For each measurable element (windows, doors, counters, etc.), provide:
- element_type: window, door, counter, cabinet, etc.
- element_id: Unique ID (e.g., "window_1", "door_main")
- width_inches, height_inches, depth_inches: Estimates (null if not visible)
- confidence: 0.0-1.0
- visual_cue: What you used to estimate

---

## SECTION 3: MATERIALS & SURFACES

**Floor:**
- material: hardwood, tile, carpet, laminate, vinyl, concrete, stone, bamboo, cork, linoleum
- condition: excellent, good, fair, poor, damaged, worn
- color: describe the color (e.g., "dark oak", "beige", "gray slate")
- pattern: herringbone, straight, diagonal, random, basketweave, or null if none
- estimated_sqft: Rough square footage estimate if determinable (null otherwise)

**Walls:**
- material: drywall, plaster, brick, concrete, wood_panel, tile, stone
- condition: excellent, good, fair, poor, damaged
- paint_color: describe the color (e.g., "off-white", "light gray", "sage green")
- has_wallpaper: true/false
- texture: smooth, textured, knockdown, orange_peel, popcorn, skip_trowel
- estimated_wall_sqft: Rough visible wall area estimate (null otherwise)

**Ceiling:**
- material: drywall, plaster, popcorn, beamed, coffered, drop_ceiling, exposed
- condition: excellent, good, fair, poor, damaged
- has_crown_molding: true/false
- has_lighting_fixtures: true/false
- height_ft: Estimated ceiling height (null if not determinable)

---

## SECTION 4: FIXTURES & APPLIANCES

**Fixtures** (permanent installations):
For each fixture: type, location, brand (if visible), condition, style, estimated_age_years (null if unknown)

Types: sink, toilet, bathtub, shower, faucet, vanity, cabinet, countertop, light_fixture, ceiling_fan, range_hood, built_in_shelving, fireplace, radiator

**Appliances** (removable/replaceable):
For each appliance: type, brand (if visible), condition, estimated_age_years (null if unknown), energy_star_visible (true/false)

Types: refrigerator, stove, oven, microwave, dishwasher, washer, dryer, water_heater, hvac_unit

---

## SECTION 5: STYLE ASSESSMENT

- **primary_style**: modern, contemporary, traditional, transitional, farmhouse, industrial, mid_century_modern, bohemian, minimalist, rustic, coastal, scandinavian, art_deco, victorian, craftsman
- **secondary_style**: (if applicable, otherwise null)
- **color_palette**: List 3-5 dominant colors in the space
- **lighting_type**: natural, recessed, pendant, chandelier, track, sconce, floor_lamp, table_lamp, under_cabinet, mixed
- **overall_condition**: move_in_ready, needs_minor_updates, needs_updates, needs_renovation, needs_major_renovation, gut_job

---

## SECTION 6: STRUCTURAL ELEMENTS

**Windows** (for each visible):
- id: Unique identifier (e.g., "window_1")
- count: number of windows
- type: double_hung, casement, picture, sliding, bay, skylight, awning, fixed, transom
- wall_location: north, south, east, west, or descriptive (e.g., "left wall")
- condition: excellent, good, fair, poor
- width_inches, height_inches: Estimates based on visual cues (null if unclear)

**Doors** (for each visible):
- id: Unique identifier (e.g., "door_main")
- count: number of doors
- type: entry, interior, closet, french, sliding, pocket, barn, bi_fold, dutch
- wall_location: descriptive position
- condition: excellent, good, fair, poor
- width_inches, height_inches: Estimates (standard interior door ~32x80 inches)

**Also count:**
- electrical_outlets: number visible
- light_switches: number visible
- hvac_vents: number visible

---

## SECTION 7: MEP DETAILS (Mechanical, Electrical, Plumbing)

**Electrical:**
- outlet_type: standard, gfci, usb, smart (based on what's visible)
- visible_wiring: true/false (exposed wiring visible?)
- estimated_era: Based on outlet style (e.g., "1970s", "modern")
- notes: Any observations (e.g., "GFCI outlets suggest modern electrical", "Cloth-covered wire visible suggests pre-1960s")

**Plumbing:**
- visible_pipes: true/false
- pipe_material: copper, pvc, galvanized, pex, or null if not visible
- fixture_connections: List visible connections (e.g., "supply lines under sink")
- notes: Any observations

**HVAC:**
- vent_type: floor, ceiling, wall, baseboard, or null
- thermostat_type: manual, programmable, smart, or null if not visible
- radiators_visible: true/false
- notes: Any observations

---

## SECTION 8: POTENTIAL HAZARDS

Based on visual cues and detected era, list potential hazards requiring professional assessment:

For each hazard:
- hazard_type: asbestos_risk, lead_paint_risk, mold_risk, structural_concern, electrical_hazard, water_damage
- indicator: What visual cue suggests this (e.g., "Popcorn ceiling in home appearing pre-1980s")
- location: Where in the image
- confidence: 0.0-1.0 (how confident are you this hazard exists?)
- recommendation: What to do (e.g., "Professional asbestos testing recommended before ceiling work")

Common indicators:
- Popcorn ceiling + pre-1980 era → asbestos_risk
- Multiple paint layers + pre-1978 era → lead_paint_risk
- Water stains, discoloration → mold_risk, water_damage
- Cracks, sagging → structural_concern
- Old outlets, cloth wiring → electrical_hazard

---

## SECTION 9: LOAD-BEARING INDICATORS

Note visual clues that might indicate load-bearing structures (professional assessment always required):

- potential_load_bearing_walls: List walls that might be load-bearing based on visual clues (e.g., "Wall running parallel to roof ridge", "Thick wall at center of home")
- visible_beams: List any visible beams (e.g., "Exposed beam running east-west across ceiling")
- structural_columns: List any visible columns
- confidence_notes: State uncertainty (e.g., "Cannot determine load-bearing status from image - professional assessment required for any wall removal")

---

## SECTION 10: NATURAL LIGHTING

- light_quality: bright, moderate, dim, dark
- primary_light_direction: north, south, east, west (based on shadow direction, null if unclear)
- window_orientation_guess: Best guess of window facing direction based on light
- shadows_indicate: What time of day/direction shadows suggest (null if no clear shadows)
- artificial_lighting_on: true/false

---

## SECTION 11: ACCESSIBILITY FEATURES

List any accessibility features visible:
- feature_type: grab_bar, wide_doorway, ramp, lever_handle, roll_in_shower, lowered_counter, accessible_outlet, handrail
- location: Where in the image
- condition: excellent, good, fair, poor

---

## SECTION 12: FURNITURE DETAILS

For each visible furniture piece:
- type: bed, dresser, nightstand, sofa, chair, table, desk, bookshelf, etc.
- style: modern, traditional, rustic, mid-century, etc.
- condition: excellent, good, fair, poor
- estimated_value: budget, mid-range, high-end, antique
- removable: true (can be moved for renovation)
- location: Where in the room

---

## SECTION 13: ECO/TECH FEATURES

List any sustainable or smart home features visible:
- feature_type: smart_thermostat, usb_outlet, led_lighting, energy_star_appliance, low_flow_fixture, solar_tube, smart_switch, motion_sensor
- location: Where in the image
- brand: If visible

---

## SECTION 14: IMAGE QUALITY ASSESSMENT

- overall_quality: excellent, good, fair, poor
- lighting_quality: well_lit, adequate, underexposed, overexposed
- coverage_adequate: true if image shows enough for good analysis
- recommendations: List suggestions for better photos if needed (e.g., "Recommend additional photo of opposite wall", "Ceiling not visible - consider upward angle shot")

---

## SECTION 15: IMAGE SCOPE ANALYSIS (CRITICAL FOR RENOVATION PREVIEW)

This section is CRITICAL for preventing AI hallucination during image generation.

**frame_type**:
- "corner_view": Shows a corner where 2 walls meet (~15-30% of room)
- "wall_view": Shows one wall/side (~30-60% of room)
- "full_room": Wide shot showing most of room (~60-100% of room)
- "detail_closeup": Zoomed in on small area (<15% of room)

**room_coverage_pct**: Estimate what percentage of the total room is visible (10-100)

**camera_angle**:
- "eye_level": Standard standing height view
- "low_angle": Shot from below eye level
- "high_angle": Shot from above eye level

**camera_position**: Describe where the photographer is standing (e.g., "standing at doorway looking in", "corner of room facing opposite corner")

---

## SECTION 16: VISIBLE ELEMENTS INVENTORY (CRITICAL)

For each category, describe what IS visible OR explicitly state "Not visible in frame":

- **walls**: Describe visible walls (e.g., "2 cream-colored walls meeting at corner, minor scuff marks")
- **floor**: Describe visible floor (e.g., "Dark hardwood flooring, some scratches near doorway")
- **windows**: "X windows on [wall]" OR "Not visible in frame"
- **doors**: "X doors - [types] on [walls]" OR "Not visible in frame"
- **fixtures**: List visible fixtures OR ["None visible"]
- **furniture**: List visible furniture OR ["None visible"]
- **ceiling**: Describe OR "Not visible in frame"

---

## SECTION 17: MUST NOT ADD (HALLUCINATION PREVENTION)

Based on what you DO NOT see in the image, list what should NOT be added during renovation image generation:

Examples:
- "Do not add windows (none visible in original image)"
- "Do not add doors (none visible in original image)"
- "Do not add furniture or beds (none visible in original)"
- "Do not expand beyond the visible corner/frame"
- "Do not add ceiling fixtures (ceiling not visible)"
- "Do not change room layout or add architectural features"

Be comprehensive - this prevents the AI from hallucinating elements.

---

## SECTION 18: FEATURES TO RETAIN

List structural and architectural features that should be PRESERVED during renovation:
- "Corner angle between walls"
- "Window position on east wall"
- "Door frame location"
- "Electrical outlet positions"
- "Room proportions and perspective"
- "Natural lighting direction"

---

## SECTION 19: ENTITIES (FOR UI INTERACTION)

List all distinct visual elements that could be selected/modified in a renovation UI.

For each entity provide:
- **type**: floor, walls, ceiling, window, door, cabinet, countertop, sink, toilet, bathtub, shower, light_fixture, appliance, furniture_[specific], decor_[specific]
- **label**: User-friendly name (e.g., "Hardwood Floor", "Kitchen Cabinets", "Pendant Light")
- **confidence**: Your confidence score 0.0-1.0
- **category**: structural, fixture, appliance, furniture, decor
- **location**: Where in the image (e.g., "center", "left wall", "above island")
- **removable**: true if can be removed during renovation, false if structural
- **has_dimensions**: true if you provided dimension estimates for this element

Focus on major elements, not every small item.

---

## SECTION 20: VISIBLE ISSUES

List any problems or damage visible that would affect renovation planning:
- **type**: water_damage, crack, stain, mold, mildew, peeling_paint, chipped_tile, scratched_floor, broken_fixture, outdated_wiring, rust, rot, discoloration
- **location**: Where in the image
- **severity**: minor, moderate, severe

---

## SECTION 21: CONTRACTOR SEARCH CONTEXT

Extract information useful for finding appropriate contractors:

- **detected_era**: Estimate when the space was built/last renovated (e.g., "1950s", "1970s", "1990s", "2000s", "2010s", "modern/recent") or null if unknown
- **style_assessment**: Brief description of current style for contractor context
- **primary_work_needed**: List main work types needed (e.g., ["flooring", "painting", "cabinet_refinishing"])
- **specialty_required**: Specific trades needed (e.g., ["tile_installer", "electrician", "plumber", "carpenter"])
- **urgency_indicators**: Any urgent issues (e.g., ["water damage requires immediate attention"])
- **search_keywords**: Keywords for contractor search (e.g., ["bathroom remodel", "tile installation", "modern fixtures"])
- **problem_areas**: Specific problems to address (e.g., ["outdated vanity", "poor lighting", "worn flooring"])
- **renovation_scope**: "cosmetic" (paint, minor updates), "moderate" (new fixtures, flooring), "full_renovation" (gut and rebuild)
- **estimated_budget_tier**: Based on current finishes and needed work: "budget", "mid-range", "high-end"

---

## SECTION 22: UI SUMMARY

- **brief_description**: 2-3 sentence conversational summary of the room. Be natural and descriptive, not technical. Example: "A cozy bedroom featuring warm hardwood floors and large windows that flood the space with natural light. The walls have a fresh coat of light gray paint, giving it a modern feel."
- **room_vibe**: Single word describing the overall feel: modern, traditional, cozy, bright, dark, dated, fresh, industrial, minimal, cluttered, spacious, cramped, warm, cold, elegant, casual

---

## SECTION 23: CONFIDENCE NOTES

Track what you're certain about vs. uncertain:

- **clearly_visible**: List elements you can see clearly and are confident about
- **partially_visible**: List elements that are partially visible or you're less certain about
- **not_visible**: List elements that are NOT visible in this image (important for must_not_add)
- **assumptions_made**: List any assumptions you made (e.g., "Assumed standard 8ft ceiling height based on door proportions", "Estimated room width using door as 32-inch reference")

---

## RESPONSE FORMAT

**CRITICAL: Return ONLY a valid JSON object with the EXACT keys shown below. Do NOT use "SECTION X" as keys. Use the actual field names.**

Return a JSON object with these TOP-LEVEL keys (not nested under section names):

```json
{
  "room_type": "bedroom|kitchen|bathroom|living_room|...",
  "room_subtype": "master_bedroom|guest_bathroom|..." or null,
  "estimated_dimensions": {
    "room": {"width_ft": number, "length_ft": number, "height_ft": number, "area_sqft": number, "confidence": 0.0-1.0, "visual_cues_used": []},
    "elements": [{"element_type": "window", "element_id": "window_1", "width_inches": number, "height_inches": number, "depth_inches": number, "confidence": 0.0-1.0, "visual_cue": "..."}]
  },
  "floor": {"material": "...", "condition": "...", "color": "...", "pattern": null, "estimated_sqft": null},
  "walls": {"material": "...", "condition": "...", "paint_color": "...", "has_wallpaper": false, "texture": "...", "estimated_wall_sqft": null},
  "ceiling": {"material": "...", "condition": "...", "has_crown_molding": false, "has_lighting_fixtures": false, "height_ft": null},
  "fixtures": [{"type": "...", "location": "...", "brand": null, "condition": "...", "style": "...", "estimated_age_years": null}],
  "appliances": [],
  "style": {"primary_style": "...", "secondary_style": null, "color_palette": [], "lighting_type": "...", "overall_condition": "..."},
  "structural_elements": {"windows": [], "doors": [], "electrical_outlets": 0, "light_switches": 0, "hvac_vents": 0},
  "mep_details": {
    "electrical": {"outlet_type": "standard", "visible_wiring": false, "estimated_era": null, "notes": []},
    "plumbing": {"visible_pipes": false, "pipe_material": null, "fixture_connections": [], "notes": []},
    "hvac": {"vent_type": null, "thermostat_type": null, "radiators_visible": false, "notes": []}
  },
  "potential_hazards": [{"hazard_type": "...", "indicator": "...", "location": "...", "confidence": 0.0-1.0, "recommendation": "..."}],
  "load_bearing_indicators": {"potential_load_bearing_walls": [], "visible_beams": [], "structural_columns": [], "confidence_notes": "..."},
  "natural_lighting": {"light_quality": "...", "primary_light_direction": null, "window_orientation_guess": null, "shadows_indicate": null, "artificial_lighting_on": false},
  "accessibility_features": [],
  "furniture_details": [],
  "eco_tech_features": [],
  "image_quality": {"overall_quality": "...", "lighting_quality": "...", "coverage_adequate": true, "recommendations": []},
  "image_scope": {"frame_type": "corner_view|wall_view|full_room|detail_closeup", "room_coverage_pct": 10-100, "camera_angle": "eye_level|low_angle|high_angle", "camera_position": "..."},
  "visible_elements": {"walls": "...", "floor": "...", "windows": "...", "doors": "...", "fixtures": [], "furniture": [], "ceiling": "..."},
  "must_not_add": ["Do not add X (reason)", "..."],
  "features_to_retain": ["Feature 1", "..."],
  "entities": [{"type": "floor|walls|window|door|...", "label": "User-friendly name", "confidence": 0.0-1.0, "category": "structural|fixture|appliance|furniture", "location": "...", "removable": true|false, "has_dimensions": true|false}],
  "visible_issues": [{"type": "water_damage|crack|...", "location": "...", "severity": "minor|moderate|severe"}],
  "contractor_context": {"detected_era": null, "style_assessment": "...", "primary_work_needed": [], "specialty_required": [], "urgency_indicators": [], "search_keywords": [], "problem_areas": [], "renovation_scope": "cosmetic|moderate|full_renovation", "estimated_budget_tier": "budget|mid-range|high-end"},
  "summary": {"brief_description": "2-3 sentence natural description", "room_vibe": "modern|dated|cozy|..."},
  "confidence_notes": {"clearly_visible": [], "partially_visible": [], "not_visible": [], "assumptions_made": []}
}
```

**IMPORTANT**:
- Use EXACTLY these key names at the top level
- Do NOT wrap the response in section objects like "SECTION 1", "SECTION 2", etc.
- For missing/unknown values: use null for numbers, "unknown" for strings, [] for arrays
- Return ONLY the JSON object, no markdown code blocks, no explanations"""


def get_comprehensive_analysis_prompt(
    project_title: str | None = None,
    project_type: str | None = None,
    additional_context: str | None = None
) -> str:
    """
    Get the comprehensive analysis prompt with optional context.

    Args:
        project_title: Optional project title for context
        project_type: Optional project type (bedroom, kitchen, etc.)
        additional_context: Optional additional user-provided context

    Returns:
        The full prompt string with context prepended
    """
    context_parts = []

    if project_title:
        context_parts.append(f"**Project:** {project_title}")
    if project_type:
        context_parts.append(f"**Project Type:** {project_type} renovation")
    if additional_context:
        context_parts.append(f"**Additional Context:** {additional_context}")

    if context_parts:
        context_section = "## PROJECT CONTEXT\n\n" + "\n".join(context_parts) + "\n\n---\n\n"
        return context_section + COMPREHENSIVE_ANALYSIS_PROMPT

    return COMPREHENSIVE_ANALYSIS_PROMPT
