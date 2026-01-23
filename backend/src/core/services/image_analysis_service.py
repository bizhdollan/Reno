"""
Image Analysis Service.

NOTE: VLM analysis methods have been DEPRECATED as of 2026-01-22.
Image analysis is now performed via comprehensive_analysis.py during the chat flow.

The following methods have been deprecated:
- analyze_image() - VLM call now handled by comprehensive_image_analysis()
- extract_critical_elements() - Now part of comprehensive analysis
- _build_analysis_prompt() - Replaced by comprehensive_analysis.py prompt

Migration:
    OLD: await image_analysis_service.analyze_image(url, project_id, project_type)
    NEW: result = await comprehensive_image_analysis(url, project_title, project_type)
         (called automatically in analyze_single_image in analysis.py)

KEPT (still active):
- validate_room_consistency() - Multi-image validation
- detect_perspective_conflicts() - Conflict detection across images
- get_analysis_by_id() - DB retrieval
- get_analyses_for_project() - DB retrieval
- _calculate_confidence() - Confidence scoring
"""

import json
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.db.models import ImageAnalysis, ImageMetadata

logger = get_logger(__name__)
from src.core.llm.provider import LLMProvider
from src.core.langgraph.utils import parse_json
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import load_image_as_base64
from src.core.langgraph.config import build_extraction_prompt_section, build_extraction_json_schema
from .session_cache import SessionCache


class ImageAnalysisService:
    """
    Service for analyzing images and extracting renovation-relevant features.

    NOTE: VLM analysis methods have been deprecated. Image analysis now uses
    comprehensive_image_analysis() from comprehensive_analysis.py during the chat flow.

    Active Responsibilities:
    - Validate room type consistency across multiple images
    - Detect perspective conflicts
    - DB retrieval methods

    Deprecated (commented out):
    - analyze_image() - Use comprehensive_image_analysis() instead
    - extract_critical_elements() - Now part of comprehensive analysis
    """

    def __init__(
        self,
        db: Session,
        llm_provider: Optional[LLMProvider] = None,
        cache: Optional[SessionCache] = None
    ):
        self.db = db
        self.llm = llm_provider or LLMProvider.for_vlm()
        self.cache = cache or SessionCache()

    # =========================================================================
    # DEPRECATED METHODS - VLM analysis now done via comprehensive_analysis.py
    # =========================================================================

    # async def analyze_image(
    #     self,
    #     image_url: str,
    #     project_id: UUID,
    #     project_type: str = "renovation"
    # ) -> ImageAnalysis:
    #     """
    #     DEPRECATED: Use comprehensive_image_analysis() from comprehensive_analysis.py instead.
    #
    #     Analyze a single image and store results in database.
    #
    #     Args:
    #         image_url: URL or base64 data URL of the image
    #         project_id: UUID of the project
    #         project_type: Type of renovation (kitchen, bathroom, etc.)
    #
    #     Returns:
    #         ImageAnalysis object with extracted_features and critical_elements
    #     """
    #     logger.info(f"[ImageAnalysisService] Analyzing image: {image_url[:50]}...")
    #
    #     # Load image as base64
    #     image_data = await load_image_as_base64(image_url)
    #
    #     # Build prompt
    #     prompt = self._build_analysis_prompt(project_type)
    #
    #     # Call VLM
    #     response = await self.llm.complete(
    #         messages=[
    #             {
    #                 "role": "system",
    #                 "content": "You are a renovation expert. Analyze images thoroughly. Return JSON only, no markdown."
    #             },
    #             {
    #                 "role": "user",
    #                 "content": [
    #                     {"type": "text", "text": prompt},
    #                     {"type": "image_url", "image_url": {"url": image_data}}
    #                 ]
    #             }
    #         ],
    #         temperature=0.2,
    #         max_tokens=2000
    #     )
    #
    #     # Parse response
    #     try:
    #         features = parse_json(response)
    #     except Exception as e:
    #         logger.info(f"[ImageAnalysisService] Failed to parse response: {e}")
    #         features = {}
    #
    #     # Extract room type
    #     room_type = features.get("room_type") or features.get("style", {}).get("room_type")
    #
    #     # Extract critical elements
    #     critical = await self.extract_critical_elements(features, image_data)
    #
    #     # Calculate confidence
    #     confidence = self._calculate_confidence(features)
    #
    #     # Save to database
    #     analysis = ImageAnalysis(
    #         project_id=project_id,
    #         image_url=image_url,
    #         room_type=room_type,
    #         extracted_features=features,
    #         critical_elements=critical,
    #         confidence_score=confidence
    #     )
    #     self.db.add(analysis)
    #     self.db.commit()
    #     self.db.refresh(analysis)
    #
    #     # Cache the analysis
    #     self.cache.set_image_analysis(analysis.id, analysis)
    #     self.cache.set_critical_elements(analysis.id, critical)
    #
    #     logger.info(f"[ImageAnalysisService] Analysis complete: room_type={room_type}, confidence={confidence}")
    #     return analysis

    # async def extract_critical_elements(
    #     self,
    #     extracted_features: dict,
    #     image_data: Optional[str] = None
    # ) -> dict:
    #     """
    #     DEPRECATED: Critical elements are now extracted as part of comprehensive_image_analysis().
    #     See comprehensive_result["structural_elements"] and comprehensive_result["features_to_retain"].
    #
    #     Identify critical structural elements that must be preserved.
    #
    #     Args:
    #         extracted_features: Already extracted features from image
    #         image_data: Optional base64 image data for additional analysis
    #
    #     Returns:
    #         Dictionary of critical elements with confidence scores
    #     """
    #     prompt = f"""Given these extracted features from a room image:
    # {json.dumps(extracted_features, indent=2)[:2000]}
    #
    # Identify CRITICAL structural elements that MUST be preserved in renovations.
    # Focus on elements that are:
    # 1. Structural (load-bearing walls, ceiling height)
    # 2. Fixed installations (windows, doors, built-ins)
    # 3. Important for room layout (columns, alcoves, stairs)
    #
    # Return JSON with confidence scores (0.0-1.0) for each element.
    # Only include elements with confidence > 0.5.
    #
    # Format:
    # {{
    #     "windows": {{"count": 2, "wall": "east", "type": "casement", "confidence": 0.9}},
    #     "doors": {{"count": 1, "wall": "north", "type": "standard", "confidence": 0.85}},
    #     "load_bearing_walls": ["north", "south"],
    #     "ceiling_height": "10ft",
    #     "built_in_features": []
    # }}
    #
    # Return valid JSON only, no markdown."""
    #
    #     messages = [
    #         {
    #             "role": "system",
    #             "content": "You are an architect identifying structural features. Return JSON only."
    #         },
    #         {"role": "user", "content": prompt}
    #     ]
    #
    #     # If we have image data, add it for more accurate detection
    #     if image_data:
    #         messages[1] = {
    #             "role": "user",
    #             "content": [
    #                 {"type": "text", "text": prompt},
    #                 {"type": "image_url", "image_url": {"url": image_data}}
    #             ]
    #         }
    #
    #     try:
    #         response = await self.llm.complete(
    #             messages=messages,
    #             temperature=0.2,
    #             max_tokens=800
    #         )
    #         return parse_json(response)
    #     except Exception as e:
    #         logger.info(f"[ImageAnalysisService] Failed to extract critical elements: {e}")
    #         return {}

    # =========================================================================
    # ACTIVE METHODS - Still in use
    # =========================================================================

    async def validate_room_consistency(
        self,
        image_ids: list[UUID]
    ) -> tuple[bool, str]:
        """
        Validate that all images are of the same room type.

        Args:
            image_ids: List of ImageAnalysis IDs to validate

        Returns:
            (is_valid, error_message)
        """
        if len(image_ids) <= 1:
            return True, ""

        analyses = []
        for img_id in image_ids:
            # Try cache first
            analysis = self.cache.get_image_analysis(img_id)
            if not analysis:
                analysis = self.db.query(ImageAnalysis).filter_by(id=img_id).first()
                if analysis:
                    self.cache.set_image_analysis(img_id, analysis)
            if analysis:
                analyses.append(analysis)

        if len(analyses) < 2:
            return True, ""

        room_types = [a.room_type for a in analyses if a.room_type]
        unique_types = set(room_types)

        if len(unique_types) > 1:
            return False, f"Please upload images of a single room only. Detected: {', '.join(unique_types)}"

        return True, ""

    async def detect_perspective_conflicts(
        self,
        image_ids: list[UUID]
    ) -> list[dict]:
        """
        Compare features across perspectives to detect conflicts.

        Args:
            image_ids: List of ImageAnalysis IDs to compare

        Returns:
            List of conflicts with resolution questions:
            [
                {
                    "field": "floor_material",
                    "values": ["marble", "hardwood"],
                    "image_ids": [uuid1, uuid2],
                    "question": "Image 1 shows marble floor, Image 2 shows hardwood. Which is correct?"
                }
            ]
        """
        if len(image_ids) <= 1:
            return []

        analyses = []
        for img_id in image_ids:
            analysis = self.cache.get_image_analysis(img_id)
            if not analysis:
                analysis = self.db.query(ImageAnalysis).filter_by(id=img_id).first()
                if analysis:
                    self.cache.set_image_analysis(img_id, analysis)
            if analysis:
                analyses.append(analysis)

        if len(analyses) < 2:
            return []

        conflicts = []

        # Compare floor materials
        floor_data = []
        for i, a in enumerate(analyses):
            materials = a.extracted_features.get("materials", [])
            floor = next(
                (m for m in materials if m.get("name", "").lower() == "floor"),
                None
            )
            if floor:
                floor_data.append((floor.get("type"), a.id, i + 1))

        if len(floor_data) > 1:
            types = set(f[0] for f in floor_data if f[0])
            if len(types) > 1:
                conflicts.append({
                    "field": "floor_material",
                    "values": list(types),
                    "image_ids": [f[1] for f in floor_data],
                    "question": f"I see different flooring in your images: {', '.join(types)}. Which is correct?"
                })

        # Compare wall colors
        wall_data = []
        for i, a in enumerate(analyses):
            colors = a.extracted_features.get("colors", [])
            wall = next(
                (c for c in colors if c.get("element", "").lower() in ["wall", "walls"]),
                None
            )
            if wall:
                wall_data.append((wall.get("color"), a.id, i + 1))

        if len(wall_data) > 1:
            colors_set = set(w[0] for w in wall_data if w[0])
            if len(colors_set) > 1:
                conflicts.append({
                    "field": "wall_color",
                    "values": list(colors_set),
                    "image_ids": [w[1] for w in wall_data],
                    "question": f"I see different wall colors in your images: {', '.join(colors_set)}. Which is correct?"
                })

        return conflicts

    # =========================================================================
    # DEPRECATED HELPER - Only used by deprecated analyze_image()
    # =========================================================================

    # def _build_analysis_prompt(self, project_type: str) -> str:
    #     """
    #     DEPRECATED: Now using comprehensive_analysis.py prompt instead.
    #
    #     Build the full image analysis prompt.
    #     """
    #     categories_section = build_extraction_prompt_section()
    #     json_schema = build_extraction_json_schema()
    #
    #     return f"""You are a renovation expert analyzing an image for a {project_type} renovation project.
    #
    # Analyze this image comprehensively and extract ALL renovation-relevant information.
    #
    # ## What to Extract
    #
    # {categories_section}
    #
    # ## Instructions
    #
    # - Only include categories where you can actually identify relevant items
    # - Be specific and accurate in your descriptions
    # - For measurements, provide estimates based on visual cues (doorways, standard fixture sizes, etc.)
    # - Note the condition of items where visible (excellent, good, fair, poor)
    # - Identify the room type (kitchen, bathroom, bedroom, living_room, etc.)
    #
    # ## Response Format
    #
    # Return JSON only with this structure:
    # {json_schema}
    #
    # Only include categories where you found relevant items. Return valid JSON, no markdown."""

    def _calculate_confidence(self, features: dict) -> float:
        """Calculate overall confidence based on extracted features."""
        if not features:
            return 0.0

        # Count non-empty categories
        categories = ["materials", "measurements", "colors", "fixtures", "appliances", "style"]
        found = sum(1 for cat in categories if features.get(cat))

        # Base confidence on coverage
        coverage = found / len(categories)

        # Check for critical elements
        has_measurements = bool(features.get("measurements"))
        has_materials = bool(features.get("materials"))

        if has_measurements and has_materials:
            return min(0.95, coverage + 0.2)
        elif has_measurements or has_materials:
            return min(0.85, coverage + 0.1)
        else:
            return min(0.7, coverage)

    async def get_analysis_by_id(self, analysis_id: UUID) -> Optional[ImageAnalysis]:
        """Get analysis by ID, using cache if available."""
        analysis = self.cache.get_image_analysis(analysis_id)
        if not analysis:
            analysis = self.db.query(ImageAnalysis).filter_by(id=analysis_id).first()
            if analysis:
                self.cache.set_image_analysis(analysis_id, analysis)
        return analysis

    async def get_analyses_for_project(self, project_id: UUID) -> list[ImageAnalysis]:
        """Get all analyses for a project."""
        # Check cache first
        cached = self.cache.get_image_analyses_by_project(project_id)
        if cached:
            return cached

        # Query database
        analyses = self.db.query(ImageAnalysis).filter_by(project_id=project_id).all()

        # Cache results
        for a in analyses:
            self.cache.set_image_analysis(a.id, a)

        return analyses
