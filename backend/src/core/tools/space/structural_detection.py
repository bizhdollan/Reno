"""
Structural Detection Tool

Detects and classifies structural elements in room images.
Flags potential load-bearing walls and hazardous conditions.
Always triggers HITL for load-bearing assessments.
"""
import json
import time
from dataclasses import dataclass, field
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


@dataclass
class StructuralElement:
    """A detected structural element."""
    element_type: str  # wall, beam, column, header, window, door
    location: str  # description of location in image
    appears_load_bearing: bool
    load_bearing_indicators: List[str]
    confidence: ConfidenceScore
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "element_type": self.element_type,
            "location": self.location,
            "appears_load_bearing": self.appears_load_bearing,
            "load_bearing_indicators": self.load_bearing_indicators,
            "confidence": self.confidence.to_dict(),
            "notes": self.notes,
        }


@dataclass
class HazardIndicator:
    """A detected potential hazard."""
    hazard_type: str  # asbestos_risk, lead_paint_risk, water_damage, mold, electrical, structural_damage
    description: str
    severity: str  # low, medium, high
    location: str
    confidence: ConfidenceScore
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "hazard_type": self.hazard_type,
            "description": self.description,
            "severity": self.severity,
            "location": self.location,
            "confidence": self.confidence.to_dict(),
            "recommendation": self.recommendation,
        }


@dataclass
class StructuralAnalysis:
    """Complete structural analysis result."""
    elements: List[StructuralElement]
    hazards: List[HazardIndicator]
    load_bearing_walls_detected: int
    requires_structural_engineer: bool
    overall_assessment: str
    confidence: ConfidenceScore

    def to_dict(self) -> dict:
        return {
            "elements": [e.to_dict() for e in self.elements],
            "hazards": [h.to_dict() for h in self.hazards],
            "load_bearing_walls_detected": self.load_bearing_walls_detected,
            "requires_structural_engineer": self.requires_structural_engineer,
            "overall_assessment": self.overall_assessment,
            "confidence": self.confidence.to_dict(),
        }


STRUCTURAL_ANALYSIS_PROMPT = """Analyze this room image for structural elements and potential hazards.

STRUCTURAL ELEMENTS TO IDENTIFY:
1. Walls - Are they likely load-bearing? Look for:
   - Wall thickness (thicker walls more likely load-bearing)
   - Perpendicular to floor joists
   - Running parallel to roof ridge
   - Supporting beams or headers above openings
   - Located in center of building vs perimeter

2. Beams and Headers - Above windows/doors, exposed ceiling beams

3. Columns - Structural posts or decorative

4. Windows/Doors - Note header condition

LOAD-BEARING INDICATORS:
- Thick walls (>4 inches)
- Walls running perpendicular to ceiling joists
- Walls directly below/above other walls
- Visible headers or beams above openings
- Central location in building

HAZARDS TO IDENTIFY:
- Water damage (stains, bubbling, warping)
- Mold (discoloration, black spots)
- Structural cracks (diagonal cracks, separation)
- Electrical hazards (old wiring, overloaded outlets)
- Age indicators suggesting asbestos/lead paint risk (pre-1980 materials)

Return JSON:
{
  "structural_elements": [
    {
      "element_type": "wall|beam|column|header|window|door",
      "location": "description of where in image",
      "appears_load_bearing": true|false,
      "load_bearing_indicators": ["indicator 1", "indicator 2"],
      "confidence": 0.0-1.0,
      "notes": "additional observations"
    }
  ],
  "hazards": [
    {
      "hazard_type": "water_damage|mold|structural_crack|electrical|asbestos_risk|lead_paint_risk",
      "description": "what was observed",
      "severity": "low|medium|high",
      "location": "where in image",
      "confidence": 0.0-1.0,
      "recommendation": "what should be done"
    }
  ],
  "overall_assessment": "summary of structural condition",
  "requires_structural_engineer": true|false
}

CRITICAL RULES:
1. Be CONSERVATIVE with load-bearing assessments - when unsure, mark appears_load_bearing: true
2. Any wall you're uncertain about should have low confidence
3. Pre-1980 buildings should flag asbestos_risk for popcorn ceilings, floor tiles, insulation
4. Pre-1978 buildings should flag lead_paint_risk for painted surfaces
5. ALWAYS recommend professional verification for load-bearing walls

Return ONLY valid JSON."""


async def detect_structural_elements(
    image_url: str,
    building_year: Optional[int] = None,
    project_id: Optional[str] = None
) -> ToolResult:
    """
    Detect structural elements and hazards in a room image.

    Args:
        image_url: Base64 data URL of the image
        building_year: Optional year building was constructed (for hazard assessment)
        project_id: Optional project ID for tracking

    Returns:
        ToolResult with StructuralAnalysis and HITL questions for load-bearing assessments
    """
    start_time = time.time()
    tool_name = "structural_detection"

    from src.core.llm.provider import LLMProvider

    # Add building year context if provided
    prompt = STRUCTURAL_ANALYSIS_PROMPT
    if building_year:
        year_context = f"\nBuilding Year: {building_year}\n"
        if building_year < 1978:
            year_context += "Note: Pre-1978 building - high lead paint risk on painted surfaces.\n"
        if building_year < 1980:
            year_context += "Note: Pre-1980 building - possible asbestos in insulation, floor tiles, popcorn ceilings.\n"
        if building_year < 1960:
            year_context += "Note: Pre-1960 building - likely outdated electrical, possible knob-and-tube wiring.\n"
        prompt = year_context + "\n" + prompt

    try:
        provider = LLMProvider.for_vlm()

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]

        response = await provider.complete(
            messages=messages,
            temperature=0.1,  # Very low temperature for safety-critical analysis
            max_tokens=3000,
            operation_type="structural_detection",
            project_id=project_id
        )

        # Parse response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(line for line in lines if not line.startswith("```"))

        data = json.loads(response_text)

        # Build StructuralAnalysis
        elements = []
        load_bearing_count = 0

        for elem_data in data.get("structural_elements", []):
            is_load_bearing = elem_data.get("appears_load_bearing", False)
            if is_load_bearing:
                load_bearing_count += 1

            elements.append(StructuralElement(
                element_type=elem_data.get("element_type", "unknown"),
                location=elem_data.get("location", ""),
                appears_load_bearing=is_load_bearing,
                load_bearing_indicators=elem_data.get("load_bearing_indicators", []),
                confidence=ConfidenceScore(
                    value=float(elem_data.get("confidence", 0.5)),
                    reasoning=", ".join(elem_data.get("load_bearing_indicators", [])),
                    field_name=f"structural_{elem_data.get('element_type')}"
                ),
                notes=elem_data.get("notes")
            ))

        # Build hazards
        hazards = []
        for haz_data in data.get("hazards", []):
            hazards.append(HazardIndicator(
                hazard_type=haz_data.get("hazard_type", "unknown"),
                description=haz_data.get("description", ""),
                severity=haz_data.get("severity", "low"),
                location=haz_data.get("location", ""),
                confidence=ConfidenceScore(
                    value=float(haz_data.get("confidence", 0.5)),
                    reasoning=haz_data.get("description", ""),
                    field_name=f"hazard_{haz_data.get('hazard_type')}"
                ),
                recommendation=haz_data.get("recommendation", "")
            ))

        analysis = StructuralAnalysis(
            elements=elements,
            hazards=hazards,
            load_bearing_walls_detected=load_bearing_count,
            requires_structural_engineer=data.get("requires_structural_engineer", load_bearing_count > 0),
            overall_assessment=data.get("overall_assessment", ""),
            confidence=ConfidenceScore(
                value=0.5,  # Structural assessments always conservative
                reasoning="Structural assessment requires professional verification"
            )
        )

        # Generate HITL questions for ALL load-bearing assessments
        hitl_questions = []

        for element in elements:
            if element.appears_load_bearing:
                # ALWAYS ask about load-bearing walls - CRITICAL priority
                hitl_questions.append(HITLQuestion(
                    question=f"Is the {element.element_type} at {element.location} load-bearing? This is critical for safety.",
                    field_name=f"load_bearing_{element.element_type}_{len(hitl_questions)}",
                    category=QuestionCategory.STRUCTURAL,
                    priority=Priority.CRITICAL,
                    options=[
                        "Yes, confirmed load-bearing",
                        "No, not load-bearing",
                        "Unknown - need structural engineer",
                        "I'll have it professionally assessed"
                    ],
                    current_value=True,
                    confidence=element.confidence,
                    metadata={
                        "element_type": element.element_type,
                        "location": element.location,
                        "indicators": element.load_bearing_indicators
                    }
                ))

        # HITL for high-severity hazards
        for hazard in hazards:
            if hazard.severity == "high":
                hitl_questions.append(HITLQuestion(
                    question=f"We detected potential {hazard.hazard_type.replace('_', ' ')} at {hazard.location}. Are you aware of this condition?",
                    field_name=f"hazard_{hazard.hazard_type}",
                    category=QuestionCategory.STRUCTURAL,
                    priority=Priority.CRITICAL,
                    options=[
                        "Yes, I'm aware and will address it",
                        "No, I wasn't aware - please note this",
                        "It has already been professionally assessed"
                    ],
                    current_value=hazard.description,
                    confidence=hazard.confidence,
                    metadata={
                        "hazard_type": hazard.hazard_type,
                        "severity": hazard.severity,
                        "recommendation": hazard.recommendation
                    }
                ))

        execution_time = (time.time() - start_time) * 1000

        return ToolResult(
            success=True,
            data=analysis.to_dict(),
            confidence=analysis.confidence,
            hitl_questions=hitl_questions,
            tool_name=tool_name,
            execution_time_ms=execution_time,
            metadata={
                "load_bearing_walls": load_bearing_count,
                "hazards_detected": len(hazards),
                "requires_engineer": analysis.requires_structural_engineer
            }
        )

    except json.JSONDecodeError as e:
        logger.error(f"[structural_detection] JSON parse error: {e}")
        return ToolResult.error_result(
            error=f"Failed to parse structural analysis: {str(e)}",
            tool_name=tool_name
        )
    except Exception as e:
        logger.error(f"[structural_detection] Error: {e}")
        return ToolResult.error_result(
            error=f"Structural detection failed: {str(e)}",
            tool_name=tool_name
        )


def assess_renovation_risk(
    structural_analysis: Dict[str, Any],
    project_type: str,
    scope_description: str
) -> ToolResult:
    """
    Assess renovation risk based on structural analysis and project scope.

    Args:
        structural_analysis: Output from detect_structural_elements
        project_type: Type of renovation (kitchen, bathroom, etc.)
        scope_description: Description of planned work

    Returns:
        ToolResult with risk assessment
    """
    start_time = time.time()
    tool_name = "renovation_risk_assessment"

    try:
        load_bearing_count = structural_analysis.get("load_bearing_walls_detected", 0)
        hazards = structural_analysis.get("hazards", [])
        requires_engineer = structural_analysis.get("requires_structural_engineer", False)

        # Risk factors
        risk_factors = []
        risk_level = "low"

        # Check for wall removal in scope
        wall_work_keywords = ["remove wall", "knock down", "open up", "combine rooms", "open concept"]
        has_wall_work = any(kw in scope_description.lower() for kw in wall_work_keywords)

        if has_wall_work and load_bearing_count > 0:
            risk_factors.append("Potential load-bearing wall removal detected")
            risk_level = "high"

        # Check hazards
        high_severity_hazards = [h for h in hazards if h.get("severity") == "high"]
        if high_severity_hazards:
            risk_factors.extend([
                f"High-severity hazard: {h.get('hazard_type')}" for h in high_severity_hazards
            ])
            risk_level = "high"

        medium_severity_hazards = [h for h in hazards if h.get("severity") == "medium"]
        if medium_severity_hazards and risk_level != "high":
            risk_level = "medium"
            risk_factors.extend([
                f"Medium-severity hazard: {h.get('hazard_type')}" for h in medium_severity_hazards
            ])

        # Professional requirements
        professionals_needed = []
        if requires_engineer or (has_wall_work and load_bearing_count > 0):
            professionals_needed.append("Licensed Structural Engineer")

        asbestos_risk = any(h.get("hazard_type") == "asbestos_risk" for h in hazards)
        lead_risk = any(h.get("hazard_type") == "lead_paint_risk" for h in hazards)

        if asbestos_risk:
            professionals_needed.append("Licensed Asbestos Abatement Contractor")
        if lead_risk:
            professionals_needed.append("Lead-Safe Certified Renovator")

        # Recommendations
        recommendations = []
        if risk_level == "high":
            recommendations.append("Obtain professional structural assessment before proceeding")
        if asbestos_risk:
            recommendations.append("Have suspected materials tested before any disturbance")
        if lead_risk:
            recommendations.append("Follow EPA RRP (Renovation, Repair, Painting) rule requirements")

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "professionals_needed": professionals_needed,
                "recommendations": recommendations,
                "permits_likely_required": risk_level in ["medium", "high"],
                "structural_engineer_required": requires_engineer or (has_wall_work and load_bearing_count > 0)
            },
            confidence=ConfidenceScore(
                value=0.7,
                reasoning="Risk assessment based on detected elements and project scope"
            ),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except Exception as e:
        logger.error(f"[renovation_risk_assessment] Error: {e}")
        return ToolResult.error_result(
            error=f"Risk assessment failed: {str(e)}",
            tool_name=tool_name
        )
