"""
Structural Validation Tool

Deterministic rules for structural compliance validation.
Checks if renovation scope requires structural engineering review.
"""
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from src.core.logger import get_logger
from src.core.tools.base import (
    ToolResult,
    ConfidenceScore,
    HITLQuestion,
    Priority,
    QuestionCategory,
)

logger = get_logger(__name__)


# Structural work categories that require engineering
STRUCTURAL_WORK_CATEGORIES = {
    "wall_removal": {
        "keywords": ["remove wall", "knock down wall", "demolish wall", "take out wall", "open up wall"],
        "requires_engineer": True,
        "description": "Wall removal may affect load-bearing structure"
    },
    "load_bearing_modification": {
        "keywords": ["load-bearing", "load bearing", "structural wall", "bearing wall"],
        "requires_engineer": True,
        "description": "Any modification to load-bearing elements requires engineering"
    },
    "beam_installation": {
        "keywords": ["install beam", "add beam", "new beam", "steel beam", "lvl beam", "header"],
        "requires_engineer": True,
        "description": "Beam installation requires structural calculations"
    },
    "column_work": {
        "keywords": ["remove column", "add column", "move column", "structural column"],
        "requires_engineer": True,
        "description": "Column work affects load path"
    },
    "floor_modification": {
        "keywords": ["cut floor", "floor opening", "staircase opening", "new stairs", "floor joist"],
        "requires_engineer": True,
        "description": "Floor modifications require structural analysis"
    },
    "foundation_work": {
        "keywords": ["foundation", "underpinning", "basement dig", "crawl space"],
        "requires_engineer": True,
        "description": "Foundation work is safety-critical"
    },
    "roof_modification": {
        "keywords": ["roof structure", "raise roof", "roof framing", "skylight structural"],
        "requires_engineer": True,
        "description": "Roof structural changes require engineering"
    },
    "addition": {
        "keywords": ["addition", "extension", "bump out", "expand footprint", "new room"],
        "requires_engineer": True,
        "description": "Building additions require full structural design"
    }
}

# Work that may require engineering depending on scope
CONDITIONAL_STRUCTURAL = {
    "large_opening": {
        "keywords": ["large window", "picture window", "sliding door", "french doors", "widen doorway"],
        "condition": "May require header/beam if in exterior or load-bearing wall",
        "requires_engineer": "conditional"
    },
    "hvac_penetration": {
        "keywords": ["duct through wall", "hvac through floor", "large penetration"],
        "condition": "Required if penetrating structural elements",
        "requires_engineer": "conditional"
    }
}


@dataclass
class StructuralValidationResult:
    """Result of structural validation check."""
    requires_structural_engineer: bool
    requires_permit: bool
    structural_concerns: List[str]
    recommendations: List[str]
    risk_level: str  # low, medium, high
    work_categories_detected: List[str]

    def to_dict(self) -> dict:
        return {
            "requires_structural_engineer": self.requires_structural_engineer,
            "requires_permit": self.requires_permit,
            "structural_concerns": self.structural_concerns,
            "recommendations": self.recommendations,
            "risk_level": self.risk_level,
            "work_categories_detected": self.work_categories_detected
        }


def validate_structural_scope(
    scope_description: str,
    structural_elements: Optional[List[Dict[str, Any]]] = None
) -> ToolResult:
    """
    Validate renovation scope for structural requirements.

    Deterministic rules-based check for structural engineering needs.

    Args:
        scope_description: Description of planned work
        structural_elements: Optional list of detected structural elements from VLM

    Returns:
        ToolResult with StructuralValidationResult
    """
    start_time = time.time()
    tool_name = "structural_validation"

    if not scope_description:
        return ToolResult.error_result(
            error="Scope description is required",
            tool_name=tool_name
        )

    scope_lower = scope_description.lower()

    requires_engineer = False
    requires_permit = False
    concerns = []
    recommendations = []
    detected_categories = []
    risk_level = "low"

    # Check definite structural work
    for category, config in STRUCTURAL_WORK_CATEGORIES.items():
        if any(kw in scope_lower for kw in config["keywords"]):
            requires_engineer = True
            requires_permit = True
            detected_categories.append(category)
            concerns.append(config["description"])

    # Check conditional structural work
    for category, config in CONDITIONAL_STRUCTURAL.items():
        if any(kw in scope_lower for kw in config["keywords"]):
            detected_categories.append(f"{category}_conditional")
            concerns.append(f"{category}: {config['condition']}")

    # Check VLM-detected structural elements
    hitl_questions = []
    if structural_elements:
        for element in structural_elements:
            if element.get("appears_load_bearing", False):
                # Any work near load-bearing elements is high risk
                element_name = element.get("name", "structural element")
                concerns.append(f"Work affects potential load-bearing {element_name}")
                requires_engineer = True

                # Add HITL question for confirmation
                hitl_questions.append(HITLQuestion(
                    question=f"Has the {element_name} been confirmed as load-bearing by a professional?",
                    field_name=f"load_bearing_confirmed_{element_name}",
                    category=QuestionCategory.STRUCTURAL,
                    priority=Priority.CRITICAL,
                    options=["Yes, confirmed by engineer", "No, not yet assessed", "It's not load-bearing"],
                    confidence=ConfidenceScore.low(reasoning="Load-bearing status needs verification")
                ))

    # Determine risk level
    if requires_engineer:
        risk_level = "high"
        recommendations.append("Obtain structural engineering assessment before proceeding")
        recommendations.append("Do not begin demolition until engineering drawings are approved")
    elif detected_categories:
        risk_level = "medium"
        recommendations.append("Consult with contractor about structural implications")
        recommendations.append("Consider getting engineering opinion for peace of mind")
    else:
        risk_level = "low"
        recommendations.append("Standard renovation work - follow local building codes")

    # Add general recommendations
    if requires_permit:
        recommendations.append("Building permit will be required - plan for 4-8 week timeline")

    if "wall_removal" in detected_categories:
        recommendations.append("Do NOT remove any walls until load-bearing status is confirmed")
        recommendations.append("Temporary shoring may be required during construction")

    result = StructuralValidationResult(
        requires_structural_engineer=requires_engineer,
        requires_permit=requires_permit,
        structural_concerns=concerns,
        recommendations=recommendations,
        risk_level=risk_level,
        work_categories_detected=detected_categories
    )

    execution_time = (time.time() - start_time) * 1000

    # Confidence based on detection clarity
    if detected_categories:
        confidence = ConfidenceScore.high(
            reasoning=f"Detected {len(detected_categories)} structural work categories"
        )
    else:
        confidence = ConfidenceScore.medium(
            reasoning="No obvious structural work detected, but recommend professional verification"
        )

    return ToolResult(
        success=True,
        data=result.to_dict(),
        confidence=confidence,
        hitl_questions=hitl_questions,
        tool_name=tool_name,
        execution_time_ms=execution_time,
        metadata={
            "risk_level": risk_level,
            "categories_detected": len(detected_categories)
        }
    )


def check_building_age_requirements(
    building_age: int,
    scope_description: str
) -> ToolResult:
    """
    Check compliance requirements based on building age.

    Args:
        building_age: Year building was constructed
        scope_description: Description of planned work

    Returns:
        ToolResult with age-related compliance requirements
    """
    start_time = time.time()
    tool_name = "building_age_compliance"

    current_year = 2024
    age = current_year - building_age

    requirements = []
    warnings = []
    certifications_needed = []

    # Pre-1978: Lead paint (EPA RRP rule)
    if building_age < 1978:
        requirements.append({
            "requirement": "EPA Lead-Safe Work Practices",
            "reason": f"Building from {building_age} likely contains lead-based paint",
            "certification": "EPA RRP (Renovation, Repair, Painting) certification",
            "applies_to": "Any work disturbing painted surfaces"
        })
        certifications_needed.append("EPA Lead-Safe Certified Renovator")
        warnings.append("Lead paint testing recommended before disturbing any painted surfaces")

    # Pre-1980: Potential asbestos
    if building_age < 1980:
        materials_of_concern = ["floor tiles", "insulation", "popcorn ceiling", "pipe wrap", "roof shingles"]
        requirements.append({
            "requirement": "Asbestos Assessment",
            "reason": f"Pre-1980 building may contain asbestos-containing materials",
            "certification": "Licensed asbestos inspector/abatement contractor",
            "applies_to": ", ".join(materials_of_concern)
        })
        warnings.append("Do NOT disturb suspected asbestos materials without testing")

    # Pre-1960: Electrical concerns
    if building_age < 1960:
        requirements.append({
            "requirement": "Electrical System Evaluation",
            "reason": "Older electrical systems may not meet current code",
            "certification": "Licensed electrician inspection",
            "applies_to": "Any electrical work or panel access"
        })
        warnings.append("May have knob-and-tube wiring - requires careful evaluation")

    # Pre-1940: Multiple concerns
    if building_age < 1940:
        requirements.append({
            "requirement": "Comprehensive Building Assessment",
            "reason": f"Building is {age}+ years old - multiple systems may need evaluation",
            "certification": "Building inspection by qualified professional",
            "applies_to": "Overall structural and systems evaluation"
        })

    execution_time = (time.time() - start_time) * 1000

    if requirements:
        confidence = ConfidenceScore.high(
            reasoning=f"Clear age-based requirements for {building_age} construction"
        )
    else:
        confidence = ConfidenceScore.high(
            reasoning="Building is new enough - no special age-related requirements"
        )

    return ToolResult.success_result(
        data={
            "building_age": building_age,
            "building_age_years": age,
            "requirements": requirements,
            "warnings": warnings,
            "certifications_needed": certifications_needed
        },
        confidence=confidence,
        tool_name=tool_name,
        metadata={"execution_time_ms": execution_time}
    )


def validate_scope_safety(
    scope_description: str,
    room_analysis: Optional[Dict[str, Any]] = None,
    structural_analysis: Optional[Dict[str, Any]] = None
) -> ToolResult:
    """
    Comprehensive safety validation combining multiple checks.

    Args:
        scope_description: Description of planned work
        room_analysis: Optional room analysis results
        structural_analysis: Optional structural detection results

    Returns:
        ToolResult with combined safety validation
    """
    start_time = time.time()
    tool_name = "scope_safety_validation"

    safety_checks = []
    warnings = []
    blockers = []  # Issues that should stop work

    scope_lower = scope_description.lower()

    # Check for dangerous DIY work
    dangerous_diy = [
        ("gas line", "NEVER attempt gas work without licensed professional"),
        ("electrical panel", "Main panel work requires licensed electrician"),
        ("asbestos", "Suspected asbestos must be tested before disturbance"),
        ("structural", "Structural modifications require engineering"),
    ]

    for keyword, warning in dangerous_diy:
        if keyword in scope_lower:
            blockers.append(warning)

    # Check for work requiring permits
    permit_triggers = [
        "wall removal", "electrical", "plumbing", "hvac", "addition",
        "window", "door", "roof", "foundation"
    ]

    permit_needed = any(trigger in scope_lower for trigger in permit_triggers)
    if permit_needed:
        safety_checks.append("Permits likely required - verify with local building department")

    # Check structural analysis for load-bearing concerns
    if structural_analysis:
        elements = structural_analysis.get("elements", [])
        for element in elements:
            if element.get("appears_load_bearing"):
                blockers.append(
                    f"Load-bearing element detected ({element.get('element_type', 'wall')}) - "
                    "requires structural engineer before proceeding"
                )

        hazards = structural_analysis.get("hazards", [])
        for hazard in hazards:
            if hazard.get("severity") == "high":
                warnings.append(
                    f"High-severity hazard: {hazard.get('hazard_type')} - {hazard.get('recommendation')}"
                )

    # Determine overall safety status
    if blockers:
        safety_status = "blocked"
        safety_message = "Work should NOT proceed until blockers are resolved"
    elif warnings:
        safety_status = "warnings"
        safety_message = "Work may proceed with caution after addressing warnings"
    else:
        safety_status = "clear"
        safety_message = "No immediate safety concerns detected"

    execution_time = (time.time() - start_time) * 1000

    return ToolResult.success_result(
        data={
            "safety_status": safety_status,
            "safety_message": safety_message,
            "blockers": blockers,
            "warnings": warnings,
            "safety_checks": safety_checks,
            "permit_likely_required": permit_needed
        },
        confidence=ConfidenceScore.high(
            reasoning="Rule-based safety validation"
        ),
        tool_name=tool_name,
        metadata={
            "execution_time_ms": execution_time,
            "blockers_count": len(blockers),
            "warnings_count": len(warnings)
        }
    )
