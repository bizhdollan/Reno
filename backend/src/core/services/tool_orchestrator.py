"""
Tool Orchestrator

Coordinates tool execution across all domains for the renovation estimation workflow.
Manages the flow from project creation through estimate generation.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore
from src.core.services.hitl_manager import HITLManager, load_hitl_manager, save_hitl_manager

# Domain imports
from src.core.tools.location import (
    validate_address,
    validate_zip_only,
    get_market_data,
    lookup_property_intelligence,
)
from src.core.tools.space import (
    analyze_room,
    estimate_measurements,
    detect_structural_elements,
)
from src.core.tools.designer import (
    add_sticky_note,
    get_sticky_notes,
    format_sticky_notes_for_prompt,
    detect_user_intent,
)
from src.core.tools.compliance import (
    detect_permit_requirements,
    validate_structural_scope,
    check_building_age_requirements,
)
from src.core.tools.estimator import (
    calculate_quantities,
    estimate_labor,
    generate_estimate,
)

logger = get_logger(__name__)


@dataclass
class WorkflowState:
    """Tracks the state of the estimation workflow."""
    project_id: str

    # Location data
    location_validated: bool = False
    is_nyc: bool = False
    zip_code: Optional[str] = None
    street_address: Optional[str] = None
    market_data: Optional[Dict[str, Any]] = None
    property_data: Optional[Dict[str, Any]] = None

    # Space analysis
    room_analysis: Optional[Dict[str, Any]] = None
    measurements: Optional[Dict[str, Any]] = None
    structural_analysis: Optional[Dict[str, Any]] = None

    # Design preferences
    sticky_notes: List[Dict[str, Any]] = field(default_factory=list)

    # Compliance
    permit_analysis: Optional[Dict[str, Any]] = None
    structural_validation: Optional[Dict[str, Any]] = None
    building_age: Optional[int] = None

    # Estimation
    quantities: Optional[Dict[str, Any]] = None
    labor_estimate: Optional[Dict[str, Any]] = None
    final_estimate: Optional[Dict[str, Any]] = None

    # HITL tracking
    pending_questions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "location_validated": self.location_validated,
            "is_nyc": self.is_nyc,
            "zip_code": self.zip_code,
            "street_address": self.street_address,
            "has_market_data": self.market_data is not None,
            "has_property_data": self.property_data is not None,
            "has_room_analysis": self.room_analysis is not None,
            "has_measurements": self.measurements is not None,
            "has_structural_analysis": self.structural_analysis is not None,
            "sticky_notes_count": len(self.sticky_notes),
            "has_permit_analysis": self.permit_analysis is not None,
            "has_quantities": self.quantities is not None,
            "has_labor_estimate": self.labor_estimate is not None,
            "has_final_estimate": self.final_estimate is not None,
            "pending_questions_count": len(self.pending_questions),
        }


class ToolOrchestrator:
    """
    Coordinates tool execution across all domains.

    Workflow stages:
    1. Project Start: Location validation + market data
    2. Image Upload: Room analysis + structural detection
    3. Scope Confirmation: Permit requirements + structural validation
    4. Estimate Generation: Quantities + labor + pricing
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.state = WorkflowState(project_id=project_id)
        self.hitl_manager = load_hitl_manager(project_id)

    async def process_project_start(
        self,
        zip_code: str,
        street_address: Optional[str] = None,
        project_type: str = "renovation"
    ) -> ToolResult:
        """
        Process project initialization.

        Domain 1: Location Intelligence
        - Validate address/ZIP
        - Fetch market data
        - Lookup property intelligence (NYC)

        Returns:
            ToolResult with combined location data
        """
        logger.info(f"[orchestrator] Starting project: {self.project_id}, ZIP: {zip_code}")

        self.state.zip_code = zip_code
        self.state.street_address = street_address

        results = {}
        errors = []

        # Step 1: Validate address
        try:
            if street_address:
                # Full address validation
                address_result = await validate_address(
                    street_address=street_address,
                    city=None,  # Will be derived from ZIP
                    zip_code=zip_code
                )
                if address_result.success:
                    results["address"] = address_result.data
                    self.state.is_nyc = address_result.data.get("is_nyc", False)
                    self.state.location_validated = True
                else:
                    errors.append(f"Address validation: {address_result.error}")
            else:
                # ZIP-only validation
                zip_result = await validate_zip_only(zip_code)
                if zip_result.success:
                    results["address"] = zip_result.data
                    self.state.is_nyc = zip_result.data.get("is_nyc", False)
                    self.state.location_validated = True
                else:
                    errors.append(f"ZIP validation: {zip_result.error}")

        except Exception as e:
            logger.error(f"[orchestrator] Address validation error: {e}")
            errors.append(f"Address validation failed: {str(e)}")

        # Step 2: Fetch market data
        try:
            market_result = await get_market_data(
                zip_code=zip_code,
                project_type=project_type
            )
            if market_result.success:
                results["market_data"] = market_result.data
                self.state.market_data = market_result.data
        except Exception as e:
            logger.error(f"[orchestrator] Market data error: {e}")
            errors.append(f"Market data fetch failed: {str(e)}")

        # Step 3: NYC property intelligence (if applicable)
        if self.state.is_nyc and street_address:
            try:
                property_result = await lookup_property_intelligence(
                    street_address=street_address,
                    city="New York",
                    zip_code=zip_code
                )
                if property_result.success:
                    results["property_data"] = property_result.data
                    self.state.property_data = property_result.data
                    self.state.building_age = property_result.data.get("year_built")
            except Exception as e:
                logger.error(f"[orchestrator] Property lookup error: {e}")
                # Non-critical - don't add to errors

        # Determine overall success
        if self.state.location_validated:
            return ToolResult.success_result(
                data={
                    "results": results,
                    "is_nyc": self.state.is_nyc,
                    "location_validated": True,
                    "warnings": errors if errors else None
                },
                confidence=ConfidenceScore.high(
                    reasoning="Location validated successfully"
                ),
                tool_name="project_start"
            )
        else:
            return ToolResult.error_result(
                error="; ".join(errors) if errors else "Location validation failed",
                tool_name="project_start"
            )

    async def process_image_upload(
        self,
        image_url: str,
        project_type: str = "renovation"
    ) -> ToolResult:
        """
        Process uploaded room image.

        Domain 2: Space Understanding
        - Analyze room features
        - Estimate measurements
        - Detect structural elements

        Returns:
            ToolResult with room analysis and HITL questions
        """
        logger.info(f"[orchestrator] Processing image for: {self.project_id}")

        results = {}
        hitl_questions = []

        # Run analyses in parallel
        room_task = analyze_room(
            image_url=image_url,
            project_type=project_type,
            project_id=self.project_id
        )

        structural_task = detect_structural_elements(
            image_url=image_url,
            project_id=self.project_id
        )

        room_result, structural_result = await asyncio.gather(
            room_task, structural_task,
            return_exceptions=True
        )

        # Process room analysis
        if isinstance(room_result, ToolResult) and room_result.success:
            results["room_analysis"] = room_result.data
            self.state.room_analysis = room_result.data
            hitl_questions.extend(room_result.hitl_questions)

            # Add to HITL manager
            self.hitl_manager.add_tool_result(
                domain="space",
                tool_name="room_analysis",
                result=room_result
            )
        elif isinstance(room_result, Exception):
            logger.error(f"[orchestrator] Room analysis error: {room_result}")

        # Process structural analysis
        if isinstance(structural_result, ToolResult) and structural_result.success:
            results["structural_analysis"] = structural_result.data
            self.state.structural_analysis = structural_result.data
            hitl_questions.extend(structural_result.hitl_questions)

            self.hitl_manager.add_tool_result(
                domain="space",
                tool_name="structural_detection",
                result=structural_result
            )
        elif isinstance(structural_result, Exception):
            logger.error(f"[orchestrator] Structural analysis error: {structural_result}")

        # Estimate measurements if room analysis succeeded
        if self.state.room_analysis:
            try:
                ref_objects = self.state.room_analysis.get("reference_objects", [])
                measurement_result = await estimate_measurements(
                    room_analysis=self.state.room_analysis,
                    reference_objects=ref_objects
                )
                if measurement_result.success:
                    results["measurements"] = measurement_result.data
                    self.state.measurements = measurement_result.data
                    hitl_questions.extend(measurement_result.hitl_questions)
            except Exception as e:
                logger.error(f"[orchestrator] Measurement estimation error: {e}")

        # Save HITL state
        save_hitl_manager(self.hitl_manager, self.project_id)

        # Update pending questions
        self.state.pending_questions = [q.to_dict() for q in hitl_questions]

        return ToolResult(
            success=True,
            data={
                "results": results,
                "pending_questions": len(hitl_questions),
                "requires_user_input": len(hitl_questions) > 0
            },
            confidence=ConfidenceScore.medium(
                reasoning=f"Analyzed image, {len(hitl_questions)} questions pending"
            ),
            hitl_questions=hitl_questions,
            tool_name="image_upload"
        )

    async def process_scope_confirmation(
        self,
        scope_description: str,
        materials_to_replace: Optional[List[str]] = None
    ) -> ToolResult:
        """
        Process scope confirmation and check compliance.

        Domain 4: Compliance
        - Validate structural scope
        - Check permit requirements
        - Building age compliance

        Returns:
            ToolResult with compliance analysis
        """
        logger.info(f"[orchestrator] Processing scope for: {self.project_id}")

        results = {}

        # Get location info
        location = "Unknown"
        if self.state.market_data:
            location = f"{self.state.market_data.get('city', '')}, {self.state.market_data.get('state', '')}"

        # Run compliance checks in parallel
        structural_task = validate_structural_scope(
            scope_description=scope_description,
            structural_elements=self.state.structural_analysis.get("elements") if self.state.structural_analysis else None
        )

        permit_task = detect_permit_requirements(
            project_type="renovation",
            scope_description=scope_description,
            location=location,
            building_age=self.state.building_age,
            is_landmark=self.state.property_data.get("landmark_status") if self.state.property_data else False,
            is_nyc=self.state.is_nyc
        )

        structural_result, permit_result = await asyncio.gather(
            structural_task, permit_task,
            return_exceptions=True
        )

        # Process results
        if isinstance(structural_result, ToolResult) and structural_result.success:
            results["structural_validation"] = structural_result.data
            self.state.structural_validation = structural_result.data
        elif isinstance(structural_result, Exception):
            logger.error(f"[orchestrator] Structural validation error: {structural_result}")

        if isinstance(permit_result, ToolResult) and permit_result.success:
            results["permit_analysis"] = permit_result.data
            self.state.permit_analysis = permit_result.data
        elif isinstance(permit_result, Exception):
            logger.error(f"[orchestrator] Permit detection error: {permit_result}")

        # Check building age if available
        if self.state.building_age:
            try:
                age_result = await check_building_age_requirements(
                    building_age=self.state.building_age,
                    scope_description=scope_description
                )
                if age_result.success:
                    results["age_requirements"] = age_result.data
            except Exception as e:
                logger.error(f"[orchestrator] Building age check error: {e}")

        return ToolResult.success_result(
            data={
                "results": results,
                "requires_permits": self.state.permit_analysis.get("permits_required", []) if self.state.permit_analysis else [],
                "structural_risk": self.state.structural_validation.get("risk_level", "unknown") if self.state.structural_validation else "unknown"
            },
            confidence=ConfidenceScore.medium(
                reasoning="Compliance checks completed"
            ),
            tool_name="scope_confirmation"
        )

    async def generate_full_estimate(
        self,
        project_type: str = "renovation",
        materials_to_replace: Optional[List[str]] = None
    ) -> ToolResult:
        """
        Generate complete 3-tier estimate.

        Domain 5: Estimator
        - Calculate quantities
        - Estimate labor
        - Generate pricing

        Returns:
            ToolResult with full estimate
        """
        logger.info(f"[orchestrator] Generating estimate for: {self.project_id}")

        # Ensure we have measurements
        if not self.state.measurements:
            return ToolResult.error_result(
                error="Measurements required to generate estimate. Please upload room images first.",
                tool_name="estimate_generation"
            )

        measurements = self.state.measurements
        width = measurements.get("width_ft", 10)
        length = measurements.get("length_ft", 12)
        height = measurements.get("height_ft", 8)

        # Get materials from room analysis or use provided list
        if not materials_to_replace and self.state.room_analysis:
            detected_materials = self.state.room_analysis.get("materials", [])
            materials_to_replace = [m.get("material") for m in detected_materials if m.get("material")]

        materials_to_replace = materials_to_replace or ["paint", "flooring"]

        # Step 1: Calculate quantities
        quantities_result = calculate_quantities(
            width_ft=width,
            length_ft=length,
            height_ft=height,
            materials_to_replace=materials_to_replace,
            project_type=project_type
        )

        if not quantities_result.success:
            return quantities_result

        self.state.quantities = quantities_result.data

        # Step 2: Estimate labor
        location = "Unknown"
        if self.state.market_data:
            location = f"{self.state.market_data.get('city', '')}, {self.state.market_data.get('state', '')}"

        labor_result = estimate_labor(
            scope_items=[],
            quantities=quantities_result.data,
            location=location,
            project_type=project_type
        )

        if not labor_result.success:
            return labor_result

        self.state.labor_estimate = labor_result.data

        # Step 3: Generate full estimate
        estimate_result = generate_estimate(
            quantities=quantities_result.data,
            labor_estimate=labor_result.data,
            permit_analysis=self.state.permit_analysis,
            project_type=project_type,
            location=location
        )

        if estimate_result.success:
            self.state.final_estimate = estimate_result.data

        return estimate_result

    def add_design_preference(
        self,
        category: str,
        content: str
    ) -> ToolResult:
        """Add a sticky note design preference."""
        result = add_sticky_note(
            project_id=self.project_id,
            category=category,
            content=content,
            notes=self.state.sticky_notes
        )

        if result.success:
            self.state.sticky_notes = result.data.get("notes", [])

        return result

    def get_design_preferences_prompt(self) -> str:
        """Get formatted sticky notes for LLM prompt."""
        return format_sticky_notes_for_prompt(self.state.sticky_notes)

    def get_pending_questions(self) -> List[Dict[str, Any]]:
        """Get pending HITL questions by priority."""
        return self.hitl_manager.get_questions_by_priority()

    def resolve_question(
        self,
        field_name: str,
        user_value: Any
    ) -> bool:
        """Resolve a HITL question with user input."""
        resolved = self.hitl_manager.resolve_question(field_name, user_value)
        if resolved:
            save_hitl_manager(self.hitl_manager, self.project_id)
        return resolved

    def get_workflow_state(self) -> Dict[str, Any]:
        """Get current workflow state."""
        return self.state.to_dict()


async def create_orchestrator(project_id: str) -> ToolOrchestrator:
    """Factory function to create an orchestrator instance."""
    return ToolOrchestrator(project_id=project_id)
