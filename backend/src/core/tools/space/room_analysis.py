"""
Room Analysis Tool

VLM-based room analysis with per-field confidence scores.
Low confidence fields trigger HITL (Human-in-the-Loop) questions.
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
class RoomFeature:
    """A detected room feature with confidence."""
    name: str
    value: Any
    confidence: ConfidenceScore
    category: str  # material, fixture, appliance, structural, dimension
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "confidence": self.confidence.to_dict(),
            "category": self.category,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoomFeature":
        return cls(
            name=data["name"],
            value=data["value"],
            confidence=ConfidenceScore.from_dict(data["confidence"]),
            category=data["category"],
            metadata=data.get("metadata"),
        )


@dataclass
class RoomAnalysis:
    """Complete room analysis result."""
    room_type: RoomFeature
    dimensions: Dict[str, RoomFeature]  # width_ft, length_ft, height_ft
    materials: List[RoomFeature]
    fixtures: List[RoomFeature]
    appliances: List[RoomFeature]
    structural_elements: List[RoomFeature]
    colors: List[RoomFeature]
    condition_notes: List[str]
    overall_confidence: ConfidenceScore
    low_confidence_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "room_type": self.room_type.to_dict(),
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "materials": [m.to_dict() for m in self.materials],
            "fixtures": [f.to_dict() for f in self.fixtures],
            "appliances": [a.to_dict() for a in self.appliances],
            "structural_elements": [s.to_dict() for s in self.structural_elements],
            "colors": [c.to_dict() for c in self.colors],
            "condition_notes": self.condition_notes,
            "overall_confidence": self.overall_confidence.to_dict(),
            "low_confidence_fields": self.low_confidence_fields,
        }

    def get_all_features(self) -> List[RoomFeature]:
        """Get all features as a flat list."""
        features = [self.room_type]
        features.extend(self.dimensions.values())
        features.extend(self.materials)
        features.extend(self.fixtures)
        features.extend(self.appliances)
        features.extend(self.structural_elements)
        features.extend(self.colors)
        return features


VLM_ANALYSIS_PROMPT = """Analyze this room image for a renovation project. For EACH field, provide a confidence score (0.0-1.0).

Confidence scoring guidelines:
- 0.90-1.00: Clearly visible, certain
- 0.70-0.89: Mostly visible, high confidence
- 0.50-0.69: Partially visible, uncertain (will trigger user verification)
- 0.00-0.49: Cannot determine, guessing

Be CONSERVATIVE with confidence. If you can't clearly see something, mark low confidence.

Return a JSON object with this exact structure:
{
  "room_type": {
    "value": "kitchen|bathroom|bedroom|living_room|dining_room|office|laundry|basement|other",
    "confidence": 0.0-1.0,
    "reasoning": "why this confidence level"
  },
  "dimensions": {
    "width_ft": {"value": number or null, "confidence": 0.0-1.0, "reasoning": "..."},
    "length_ft": {"value": number or null, "confidence": 0.0-1.0, "reasoning": "..."},
    "height_ft": {"value": number or null, "confidence": 0.0-1.0, "reasoning": "..."}
  },
  "materials": [
    {"name": "material name", "location": "where in room", "confidence": 0.0-1.0, "reasoning": "..."}
  ],
  "fixtures": [
    {"name": "fixture name", "type": "sink|faucet|toilet|shower|tub|light|outlet|switch|other", "confidence": 0.0-1.0, "reasoning": "..."}
  ],
  "appliances": [
    {"name": "appliance name", "brand": "if visible", "confidence": 0.0-1.0, "reasoning": "..."}
  ],
  "structural_elements": [
    {"name": "element", "type": "wall|window|door|column|beam|other", "appears_load_bearing": true|false, "confidence": 0.0-1.0, "reasoning": "..."}
  ],
  "colors": [
    {"surface": "walls|ceiling|floor|cabinets|etc", "color": "color name", "confidence": 0.0-1.0}
  ],
  "condition_notes": ["any visible damage, wear, or concerns"]
}

IMPORTANT:
- Estimate dimensions based on standard references (door height ~6.8ft, counter height ~3ft, standard appliances)
- Mark dimensions as low confidence if no clear references visible
- For structural elements, be VERY conservative about load-bearing assessments
- Include ALL visible materials, fixtures, and appliances
- Return ONLY valid JSON, no markdown code blocks"""


async def analyze_room(
    image_url: str,
    project_type: Optional[str] = None,
    project_id: Optional[str] = None,
    additional_context: Optional[str] = None
) -> ToolResult:
    """
    Analyze a room image using VLM with per-field confidence scores.

    Args:
        image_url: Base64 data URL of the image
        project_type: Optional project type for context
        project_id: Optional project ID for tracking
        additional_context: Optional additional context for the VLM

    Returns:
        ToolResult containing RoomAnalysis with HITL questions for low-confidence fields
    """
    start_time = time.time()
    tool_name = "room_analysis"

    from src.core.llm.provider import LLMProvider

    # Build prompt with context
    prompt = VLM_ANALYSIS_PROMPT
    if project_type:
        prompt = f"Project type: {project_type} renovation\n\n" + prompt
    if additional_context:
        prompt = f"Additional context: {additional_context}\n\n" + prompt

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
            temperature=0.2,  # Low temperature for consistent analysis
            max_tokens=4000,
            operation_type="room_analysis",
            project_id=project_id
        )

        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(
                line for line in lines if not line.startswith("```")
            )

        analysis_data = json.loads(response_text)

        # Build RoomAnalysis from response
        room_analysis = _build_room_analysis(analysis_data)

        # Generate HITL questions for low confidence fields
        hitl_questions = _generate_hitl_questions(room_analysis)

        execution_time = (time.time() - start_time) * 1000

        return ToolResult(
            success=True,
            data=room_analysis.to_dict(),
            confidence=room_analysis.overall_confidence,
            hitl_questions=hitl_questions,
            tool_name=tool_name,
            execution_time_ms=execution_time,
            metadata={
                "low_confidence_count": len(room_analysis.low_confidence_fields),
                "hitl_questions_count": len(hitl_questions)
            }
        )

    except json.JSONDecodeError as e:
        logger.error(f"[room_analysis] JSON parse error: {e}")
        return ToolResult.error_result(
            error=f"Failed to parse VLM response: {str(e)}",
            tool_name=tool_name
        )
    except Exception as e:
        logger.error(f"[room_analysis] Error: {e}")
        return ToolResult.error_result(
            error=f"Room analysis failed: {str(e)}",
            tool_name=tool_name
        )


def _build_room_analysis(data: dict) -> RoomAnalysis:
    """Build RoomAnalysis from VLM response data."""
    low_confidence_fields = []

    # Room type
    rt_data = data.get("room_type", {})
    room_type = RoomFeature(
        name="room_type",
        value=rt_data.get("value", "unknown"),
        confidence=ConfidenceScore(
            value=float(rt_data.get("confidence", 0.5)),
            reasoning=rt_data.get("reasoning", ""),
            field_name="room_type"
        ),
        category="classification"
    )
    if room_type.confidence.requires_human_input():
        low_confidence_fields.append("room_type")

    # Dimensions
    dimensions = {}
    dims_data = data.get("dimensions", {})
    for dim_name in ["width_ft", "length_ft", "height_ft"]:
        dim_data = dims_data.get(dim_name, {})
        conf_value = float(dim_data.get("confidence", 0.3))
        dimensions[dim_name] = RoomFeature(
            name=dim_name,
            value=dim_data.get("value"),
            confidence=ConfidenceScore(
                value=conf_value,
                reasoning=dim_data.get("reasoning", "Estimated from image"),
                field_name=dim_name
            ),
            category="dimension"
        )
        if conf_value < ConfidenceScore.HITL_THRESHOLD:
            low_confidence_fields.append(dim_name)

    # Materials
    materials = []
    for mat_data in data.get("materials", []):
        conf_value = float(mat_data.get("confidence", 0.7))
        materials.append(RoomFeature(
            name=mat_data.get("name", "unknown"),
            value=mat_data.get("location", ""),
            confidence=ConfidenceScore(
                value=conf_value,
                reasoning=mat_data.get("reasoning", ""),
                field_name=f"material_{mat_data.get('name', 'unknown')}"
            ),
            category="material",
            metadata={"location": mat_data.get("location")}
        ))
        if conf_value < ConfidenceScore.HITL_THRESHOLD:
            low_confidence_fields.append(f"material_{mat_data.get('name')}")

    # Fixtures
    fixtures = []
    for fix_data in data.get("fixtures", []):
        conf_value = float(fix_data.get("confidence", 0.8))
        fixtures.append(RoomFeature(
            name=fix_data.get("name", "unknown"),
            value=fix_data.get("type", ""),
            confidence=ConfidenceScore(
                value=conf_value,
                reasoning=fix_data.get("reasoning", ""),
                field_name=f"fixture_{fix_data.get('name', 'unknown')}"
            ),
            category="fixture",
            metadata={"type": fix_data.get("type")}
        ))

    # Appliances
    appliances = []
    for app_data in data.get("appliances", []):
        conf_value = float(app_data.get("confidence", 0.8))
        appliances.append(RoomFeature(
            name=app_data.get("name", "unknown"),
            value=app_data.get("brand", ""),
            confidence=ConfidenceScore(
                value=conf_value,
                reasoning=app_data.get("reasoning", ""),
                field_name=f"appliance_{app_data.get('name', 'unknown')}"
            ),
            category="appliance",
            metadata={"brand": app_data.get("brand")}
        ))

    # Structural elements
    structural_elements = []
    for struct_data in data.get("structural_elements", []):
        conf_value = float(struct_data.get("confidence", 0.5))
        load_bearing = struct_data.get("appears_load_bearing", False)

        structural_elements.append(RoomFeature(
            name=struct_data.get("name", "unknown"),
            value=struct_data.get("type", ""),
            confidence=ConfidenceScore(
                value=conf_value,
                reasoning=struct_data.get("reasoning", ""),
                field_name=f"structural_{struct_data.get('name', 'unknown')}"
            ),
            category="structural",
            metadata={
                "type": struct_data.get("type"),
                "appears_load_bearing": load_bearing
            }
        ))

        # Always flag load-bearing assessments for HITL
        if load_bearing and conf_value < 0.9:
            low_confidence_fields.append(f"load_bearing_{struct_data.get('name')}")

    # Colors
    colors = []
    for color_data in data.get("colors", []):
        conf_value = float(color_data.get("confidence", 0.85))
        colors.append(RoomFeature(
            name=color_data.get("surface", "unknown"),
            value=color_data.get("color", ""),
            confidence=ConfidenceScore(
                value=conf_value,
                reasoning="",
                field_name=f"color_{color_data.get('surface', 'unknown')}"
            ),
            category="color"
        ))

    # Condition notes
    condition_notes = data.get("condition_notes", [])

    # Calculate overall confidence
    all_confidences = [room_type.confidence.value]
    all_confidences.extend([d.confidence.value for d in dimensions.values()])
    all_confidences.extend([m.confidence.value for m in materials])

    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.5

    overall_confidence = ConfidenceScore(
        value=avg_confidence,
        reasoning=f"Average of {len(all_confidences)} field confidences, {len(low_confidence_fields)} low confidence fields",
        field_name="overall"
    )

    return RoomAnalysis(
        room_type=room_type,
        dimensions=dimensions,
        materials=materials,
        fixtures=fixtures,
        appliances=appliances,
        structural_elements=structural_elements,
        colors=colors,
        condition_notes=condition_notes,
        overall_confidence=overall_confidence,
        low_confidence_fields=low_confidence_fields
    )


def _generate_hitl_questions(analysis: RoomAnalysis) -> List[HITLQuestion]:
    """Generate HITL questions for low confidence fields."""
    questions = []

    # Room type question
    if analysis.room_type.confidence.requires_human_input():
        questions.append(HITLQuestion(
            question=f"What type of room is this? (We detected: {analysis.room_type.value})",
            field_name="room_type",
            category=QuestionCategory.GENERAL,
            priority=Priority.MEDIUM,
            options=["Kitchen", "Bathroom", "Bedroom", "Living Room", "Dining Room", "Office", "Laundry", "Basement"],
            current_value=analysis.room_type.value,
            confidence=analysis.room_type.confidence
        ))

    # Dimension questions
    for dim_name, dim_feature in analysis.dimensions.items():
        if dim_feature.confidence.requires_human_input():
            dim_label = dim_name.replace("_ft", "").replace("_", " ").title()
            current = dim_feature.value or "unknown"

            questions.append(HITLQuestion(
                question=f"What is the room {dim_label} in feet? (We estimated: {current})",
                field_name=dim_name,
                category=QuestionCategory.DIMENSIONS,
                priority=Priority.HIGH,
                current_value=dim_feature.value,
                confidence=dim_feature.confidence,
                metadata={"unit": "feet"}
            ))

    # Structural/load-bearing questions (CRITICAL priority)
    for struct in analysis.structural_elements:
        if struct.metadata and struct.metadata.get("appears_load_bearing"):
            if struct.confidence.value < 0.9:
                questions.append(HITLQuestion(
                    question=f"Is the {struct.name} ({struct.value}) a load-bearing element?",
                    field_name=f"load_bearing_{struct.name}",
                    category=QuestionCategory.STRUCTURAL,
                    priority=Priority.CRITICAL,
                    options=["Yes, load-bearing", "No, not load-bearing", "I'm not sure"],
                    current_value=True,
                    confidence=struct.confidence,
                    metadata={"element_type": struct.value}
                ))

    # Material questions for very low confidence
    for material in analysis.materials:
        if material.confidence.value < 0.5:
            questions.append(HITLQuestion(
                question=f"What material is the {material.metadata.get('location', 'surface')}? (We detected: {material.name})",
                field_name=f"material_{material.name}",
                category=QuestionCategory.MATERIALS,
                priority=Priority.MEDIUM,
                current_value=material.name,
                confidence=material.confidence
            ))

    return questions


async def analyze_room_batch(
    image_urls: List[str],
    project_type: Optional[str] = None,
    project_id: Optional[str] = None
) -> ToolResult:
    """
    Analyze multiple room images.

    Args:
        image_urls: List of base64 data URLs
        project_type: Optional project type
        project_id: Optional project ID

    Returns:
        ToolResult containing list of RoomAnalysis results
    """
    start_time = time.time()
    tool_name = "room_analysis_batch"

    results = []
    all_hitl_questions = []

    for i, url in enumerate(image_urls):
        result = await analyze_room(
            image_url=url,
            project_type=project_type,
            project_id=project_id,
            additional_context=f"Image {i+1} of {len(image_urls)}"
        )

        results.append({
            "image_index": i,
            "success": result.success,
            "data": result.data if result.success else None,
            "error": result.error
        })

        if result.success:
            all_hitl_questions.extend(result.hitl_questions)

    execution_time = (time.time() - start_time) * 1000

    # Calculate overall confidence
    successful = [r for r in results if r["success"]]
    if successful:
        avg_conf = sum(
            r["data"]["overall_confidence"]["value"] for r in successful
        ) / len(successful)
        confidence = ConfidenceScore(
            value=avg_conf,
            reasoning=f"Average of {len(successful)} image analyses"
        )
    else:
        confidence = ConfidenceScore.low(reasoning="No successful analyses")

    return ToolResult(
        success=len(successful) > 0,
        data={"analyses": results, "total_images": len(image_urls)},
        confidence=confidence,
        hitl_questions=all_hitl_questions,
        tool_name=tool_name,
        execution_time_ms=execution_time
    )
