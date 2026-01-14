"""
Perspective Service.

Handles camera perspective detection and tracking:
- Detect camera angle (front, side, top-down, close-up)
- Store perspective metadata
- Build perspective constraints for generation prompts
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.db.models import ImageMetadata, ImageAnalysis

logger = get_logger(__name__)
from src.core.llm.provider import LLMProvider
from src.core.langgraph.utils import parse_json
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import load_image_as_base64
from .session_cache import SessionCache


# Perspective detection prompt
PERSPECTIVE_DETECTION_PROMPT = """Analyze the camera perspective of this room image.

Classify the perspective as one of:
- **front**: Straight-on view of the room, typically from the entrance or main viewing angle
- **side**: Angled side view of the room, showing walls at an angle
- **top_down**: Overhead view looking down at the room (rare for interior photos)
- **close_up**: Detail shot focused on a specific element or area

Consider:
1. The angle of walls and floor lines
2. What elements are most prominent
3. The overall framing of the shot

Return JSON:
{
    "perspective": "front",
    "confidence": 0.9,
    "reasoning": "The image shows a straight-on view of the kitchen from the entrance, with parallel lines on the countertops and symmetric wall placement."
}

Return valid JSON only, no markdown."""


class PerspectiveService:
    """
    Service for detecting and managing camera perspectives.

    Responsibilities:
    - Detect camera perspective using VLM
    - Store perspective metadata in database
    - Build perspective constraints for generation prompts
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

    async def detect_perspective(
        self,
        image_url: str,
        image_analysis_id: UUID,
        project_id: UUID
    ) -> ImageMetadata:
        """
        Detect camera perspective using VLM and store in database.

        Args:
            image_url: URL or base64 data URL of the image
            image_analysis_id: UUID of the related ImageAnalysis
            project_id: UUID of the project

        Returns:
            ImageMetadata with perspective_type and confidence
        """
        logger.info(f"[PerspectiveService] Detecting perspective for image: {image_url[:50]}...")

        # Load image as base64
        image_data = await load_image_as_base64(image_url)

        # Call VLM
        response = await self.llm.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing camera angles and perspectives. Return JSON only."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PERSPECTIVE_DETECTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_data}}
                    ]
                }
            ],
            temperature=0.2,
            max_tokens=300
        )

        # Parse response
        try:
            data = parse_json(response)
            perspective_type = data.get("perspective", "front")
            confidence = data.get("confidence", 0.5)
            reasoning = data.get("reasoning", "")
        except Exception as e:
            logger.info(f"[PerspectiveService] Failed to parse response: {e}")
            perspective_type = "front"
            confidence = 0.5
            reasoning = "Detection failed, defaulting to front view"

        # Validate perspective type
        valid_types = ["front", "side", "top_down", "close_up"]
        if perspective_type not in valid_types:
            perspective_type = "front"
            confidence = 0.5

        # Create and save metadata
        metadata = ImageMetadata(
            project_id=project_id,
            image_analysis_id=image_analysis_id,
            image_url=image_url,
            perspective_type=perspective_type,
            perspective_confidence=confidence,
            room_consistency_hash=None  # Could be computed from analysis features
        )
        self.db.add(metadata)
        self.db.commit()
        self.db.refresh(metadata)

        # Cache the metadata
        self.cache.set_image_metadata(metadata.id, metadata)

        logger.info(f"[PerspectiveService] Detected: {perspective_type} (confidence: {confidence})")
        return metadata

    def build_perspective_constraint(
        self,
        perspective_type: str,
        confidence: float,
        min_confidence: float = 0.7
    ) -> str:
        """
        Build perspective constraint for generation prompt.

        Args:
            perspective_type: The detected perspective type
            confidence: Confidence score of the detection
            min_confidence: Minimum confidence to include constraint

        Returns:
            Constraint string or empty if confidence too low
        """
        if confidence < min_confidence:
            logger.info(f"[PerspectiveService] Confidence {confidence} below threshold {min_confidence}, skipping constraint")
            return ""

        perspective_descriptions = {
            "front": "Generate the image from the same front-facing angle as the original, with walls and surfaces shown straight-on.",
            "side": "Generate the image from the same angled side view as the original, showing depth and multiple walls.",
            "top_down": "Generate the image from the same overhead perspective as the original, looking down at the room.",
            "close_up": "Generate the image with the same close-up focus on the specific area shown in the original."
        }

        description = perspective_descriptions.get(
            perspective_type,
            "Maintain the same camera angle and perspective as the original image."
        )

        return f"PERSPECTIVE CONSTRAINT: {description}"

    async def get_metadata_for_analysis(
        self,
        analysis_id: UUID
    ) -> Optional[ImageMetadata]:
        """Get metadata for a specific image analysis."""
        # Try cache first
        metadata = self.cache.get_metadata_by_analysis(analysis_id)
        if metadata:
            return metadata

        # Query database
        metadata = self.db.query(ImageMetadata).filter_by(
            image_analysis_id=analysis_id
        ).first()

        if metadata:
            self.cache.set_image_metadata(metadata.id, metadata)

        return metadata

    async def get_or_create_metadata(
        self,
        image_url: str,
        image_analysis_id: UUID,
        project_id: UUID
    ) -> ImageMetadata:
        """Get existing metadata or create new by detecting perspective."""
        # Check if metadata already exists
        existing = await self.get_metadata_for_analysis(image_analysis_id)
        if existing:
            return existing

        # Detect and create new metadata
        return await self.detect_perspective(image_url, image_analysis_id, project_id)

    async def validate_perspective_consistency(
        self,
        metadata_ids: list[UUID]
    ) -> tuple[bool, str]:
        """
        Check if all images have consistent perspectives (optional validation).

        This is less strict than room type validation - different perspectives
        of the same room are generally acceptable.

        Returns:
            (is_valid, warning_message)
        """
        if len(metadata_ids) <= 1:
            return True, ""

        perspectives = []
        for meta_id in metadata_ids:
            metadata = self.cache.get_image_metadata(meta_id)
            if not metadata:
                metadata = self.db.query(ImageMetadata).filter_by(id=meta_id).first()
            if metadata:
                perspectives.append(metadata.perspective_type)

        unique = set(perspectives)
        if len(unique) > 2:
            return True, f"Note: Images show different perspectives: {', '.join(unique)}. This is fine for multiple angles of the same room."

        return True, ""
