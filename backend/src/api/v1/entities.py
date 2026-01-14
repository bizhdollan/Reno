"""
Entity Detection API for detecting room elements in images.

Used for targeted renovation editing - detecting floors, walls, windows, etc.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.core.logger import get_logger
from src.core.services.entity_detection_service import get_entity_detection_service

logger = get_logger(__name__)


router = APIRouter(prefix="/api/v1", tags=["entities"])


class DetectEntitiesRequest(BaseModel):
    """Request for entity detection."""
    image_url: str
    project_id: Optional[str] = None


class DetectedEntity(BaseModel):
    """A detected entity in the image."""
    type: str
    label: str
    confidence: float


class DetectEntitiesResponse(BaseModel):
    """Response containing detected entities."""
    entities: list[DetectedEntity]


@router.post("/detect-entities", response_model=DetectEntitiesResponse)
async def detect_entities(request: DetectEntitiesRequest) -> DetectEntitiesResponse:
    """
    Detect entities in a room image.

    Given an image URL (data URL or HTTP URL), uses VLM to analyze
    the image and return a list of detected entities that can be
    modified in a renovation.

    Args:
        request: Contains image_url and optional project_id

    Returns:
        List of detected entities with type, label, and confidence
    """
    if not request.image_url:
        raise HTTPException(status_code=400, detail="image_url is required")

    try:
        service = get_entity_detection_service()
        entities = await service.detect_entities(
            image_url=request.image_url,
            project_id=request.project_id
        )

        return DetectEntitiesResponse(
            entities=[DetectedEntity(**e) for e in entities]
        )

    except Exception as e:
        logger.error(f"[API] Entity detection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect entities: {str(e)}"
        )
