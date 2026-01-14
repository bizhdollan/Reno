"""
Entity Detection Service

Uses Vision Language Model to detect room entities (floor, walls, windows, ceiling, etc.)
for targeted renovation image editing.
"""

import json
from typing import Optional
from src.core.logger import get_logger
from src.core.llm.provider import LLMProvider

logger = get_logger(__name__)


ENTITY_DETECTION_PROMPT = """Analyze this room image and identify the distinct visual elements that could be modified in a renovation.

For each detected element, provide:
1. type: A short identifier (e.g., "floor", "walls", "window", "ceiling", "door", "cabinet", "countertop")
2. label: A user-friendly label (e.g., "Hardwood Floor", "Kitchen Cabinets", "Bay Window")
3. confidence: Your confidence score from 0.0 to 1.0

Only include elements that are clearly visible and could reasonably be changed in a renovation.
Focus on major elements like:
- Floor/flooring
- Walls
- Ceiling
- Windows
- Doors
- Cabinets/storage
- Countertops
- Fixtures (sink, toilet, bathtub)
- Major furniture (if applicable)

Return ONLY valid JSON in this format:
{
    "entities": [
        {"type": "floor", "label": "Floor", "confidence": 0.95},
        {"type": "walls", "label": "Walls", "confidence": 0.92},
        ...
    ]
}

Do not include any explanation text, only the JSON object."""


class EntityDetectionService:
    """Service for detecting room entities using VLM."""

    def __init__(self):
        self.provider = LLMProvider.for_vlm()

    async def detect_entities(
        self,
        image_url: str,
        project_id: Optional[str] = None
    ) -> list[dict]:
        """
        Detect entities in a room image.

        Args:
            image_url: URL of the image (can be a data URL or HTTP URL)
            project_id: Optional project ID for cost tracking

        Returns:
            List of detected entities with type, label, and confidence
        """
        # Build message with image
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ENTITY_DETECTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]

        try:
            response = await self.provider.complete(
                messages=messages,
                temperature=0.2,  # Low temperature for consistent results
                max_tokens=500,
                operation_type="entity_detection",
                project_id=project_id
            )

            # Parse JSON response
            try:
                # Try to find JSON in the response
                response_text = response.strip()

                # Handle markdown code blocks
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                data = json.loads(response_text)
                entities = data.get("entities", [])

                # Validate and clean entities
                valid_entities = []
                for entity in entities:
                    if all(key in entity for key in ["type", "label"]):
                        valid_entities.append({
                            "type": entity["type"],
                            "label": entity["label"],
                            "confidence": entity.get("confidence", 0.8)
                        })

                # Sort by confidence (highest first)
                valid_entities.sort(key=lambda x: x["confidence"], reverse=True)

                return valid_entities

            except json.JSONDecodeError as e:
                logger.error(f"[EntityDetection] Failed to parse JSON response: {e}")
                logger.error(f"[EntityDetection] Response was: {response[:500]}")
                # Return default entities as fallback
                return self._get_default_entities()

        except Exception as e:
            logger.error(f"[EntityDetection] Error detecting entities: {e}")
            # Return default entities as fallback
            return self._get_default_entities()

    def _get_default_entities(self) -> list[dict]:
        """Return default entities when detection fails."""
        return [
            {"type": "floor", "label": "Floor", "confidence": 0.8},
            {"type": "walls", "label": "Walls", "confidence": 0.8},
            {"type": "ceiling", "label": "Ceiling", "confidence": 0.8},
            {"type": "window", "label": "Windows", "confidence": 0.7},
        ]


# Singleton instance
_entity_detection_service: Optional[EntityDetectionService] = None


def get_entity_detection_service() -> EntityDetectionService:
    """Get or create the entity detection service singleton."""
    global _entity_detection_service
    if _entity_detection_service is None:
        _entity_detection_service = EntityDetectionService()
    return _entity_detection_service
