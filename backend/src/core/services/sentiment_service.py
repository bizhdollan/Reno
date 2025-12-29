"""
Sentiment Service.

Handles user intent and sentiment classification:
- Detect regeneration mode (additive vs restart)
- Detect regional scope for partial regeneration
- Classify general user intent
"""

from typing import Optional
from src.core.llm.provider import LLMProvider
from src.core.langgraph.utils import parse_json


# Regeneration mode detection prompt
REGENERATION_MODE_PROMPT = """Analyze the user's message to determine their intent regarding the generated image.

User said: "{user_message}"

Classify their intent:

**additive**: User wants to build on the current image by adding or modifying features
Examples:
- "Add a chandelier"
- "Make the walls darker"
- "Change the floor to marble"
- "Can you add some plants?"
- "I like it but add more lighting"

**restart**: User dislikes the current image and wants to try a completely different direction
Examples:
- "I don't like this"
- "This isn't what I had in mind"
- "Let's try something different"
- "Start over"
- "Can we go back to the original?"
- "This style doesn't work for me"

Return JSON:
{{
    "mode": "additive",
    "confidence": 0.9,
    "reasoning": "User wants to add a specific feature to the current design"
}}

Return valid JSON only, no markdown."""


# Regional scope detection prompt
REGIONAL_SCOPE_PROMPT = """Analyze the user's message to determine which room regions they want to change.

User said: "{user_message}"

Available regions:
- **floor**: Flooring, rugs, carpets
- **walls**: Wall color, wallpaper, accent walls, wainscoting
- **ceiling**: Ceiling color, texture, beams, crown molding
- **fixtures**: Light fixtures, faucets, hardware, switches
- **furniture**: Couches, tables, chairs, beds, cabinets
- **lighting**: Overall lighting, lamps, chandeliers

Examples:
- "Change the walls to beige" → ["walls"]
- "Update the floor and ceiling" → ["floor", "ceiling"]
- "Add a chandelier" → ["fixtures", "lighting"]
- "New countertops and cabinets" → ["furniture", "fixtures"]
- "Make everything brighter" → ["lighting", "walls"]

If the change affects the whole room or is unclear, return all regions.

Return JSON:
{{
    "regions": ["walls"],
    "confidence": 0.95,
    "reasoning": "User specifically mentioned walls"
}}

Return valid JSON only, no markdown."""


# Intent classification prompt
INTENT_CLASSIFICATION_PROMPT = """Classify the user's intent from their message.

User said: "{user_message}"

Classify as one of:
- **clarification**: User is asking a question or seeking more information
- **confirmation**: User is confirming, agreeing, or expressing satisfaction
- **correction**: User is correcting previous information or the AI's understanding
- **new_request**: User is making a new request or changing direction
- **feedback**: User is providing feedback on generated content (positive or negative)

Return JSON:
{{
    "intent": "confirmation",
    "confidence": 0.85,
    "reasoning": "User expressed satisfaction with the result"
}}

Return valid JSON only, no markdown."""


class SentimentService:
    """
    Service for analyzing user sentiment and intent.

    Responsibilities:
    - Detect regeneration mode (additive vs restart)
    - Detect regional scope for partial regeneration
    - Classify general user intent
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm = llm_provider or LLMProvider.for_llm()

    async def detect_regeneration_mode(
        self,
        user_message: str
    ) -> str:
        """
        Detect if user wants additive or restart generation.

        Args:
            user_message: The user's message

        Returns:
            "additive" or "restart"
        """
        # Quick keyword check for obvious cases
        restart_keywords = [
            "don't like", "dont like", "start over", "try something different",
            "not what i wanted", "go back", "different style", "hate it",
            "try again", "completely different", "from scratch"
        ]
        message_lower = user_message.lower()
        for keyword in restart_keywords:
            if keyword in message_lower:
                print(f"[SentimentService] Detected restart via keyword: {keyword}")
                return "restart"

        # Use LLM for nuanced cases
        prompt = REGENERATION_MODE_PROMPT.format(user_message=user_message)

        try:
            response = await self.llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You classify user intent for image generation. Return JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            data = parse_json(response)
            mode = data.get("mode", "additive")

            # Validate
            if mode not in ["additive", "restart"]:
                mode = "additive"

            print(f"[SentimentService] Detected mode: {mode} (confidence: {data.get('confidence', 0)})")
            return mode
        except Exception as e:
            print(f"[SentimentService] Failed to detect mode: {e}, defaulting to additive")
            return "additive"

    async def detect_regional_scope(
        self,
        user_message: str
    ) -> list[str]:
        """
        Detect which regions user wants to change.

        Args:
            user_message: The user's message

        Returns:
            List of regions to change (e.g., ["walls", "floor"])
        """
        # Quick keyword mapping for obvious cases
        keyword_regions = {
            "wall": ["walls"],
            "floor": ["floor"],
            "ceiling": ["ceiling"],
            "light": ["lighting", "fixtures"],
            "chandelier": ["fixtures", "lighting"],
            "cabinet": ["furniture"],
            "countertop": ["fixtures", "furniture"],
            "furniture": ["furniture"],
            "rug": ["floor"],
            "carpet": ["floor"],
            "paint": ["walls"],
            "tile": ["floor", "walls"],
        }

        message_lower = user_message.lower()
        detected_regions = set()

        for keyword, regions in keyword_regions.items():
            if keyword in message_lower:
                detected_regions.update(regions)

        if detected_regions:
            print(f"[SentimentService] Detected regions via keywords: {list(detected_regions)}")
            return list(detected_regions)

        # Use LLM for complex cases
        prompt = REGIONAL_SCOPE_PROMPT.format(user_message=user_message)

        try:
            response = await self.llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You identify room regions from user messages. Return JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            data = parse_json(response)
            regions = data.get("regions", [])

            # Validate
            valid_regions = ["floor", "walls", "ceiling", "fixtures", "furniture", "lighting"]
            regions = [r for r in regions if r in valid_regions]

            if not regions:
                # Return all regions if none detected (full change)
                return valid_regions

            print(f"[SentimentService] Detected regions: {regions}")
            return regions
        except Exception as e:
            print(f"[SentimentService] Failed to detect regions: {e}")
            return ["floor", "walls", "ceiling", "fixtures", "furniture", "lighting"]

    async def classify_user_intent(
        self,
        user_message: str
    ) -> dict:
        """
        General intent classification.

        Args:
            user_message: The user's message

        Returns:
            Dictionary with intent and confidence:
            {
                "intent": "confirmation",
                "confidence": 0.85
            }
        """
        # Quick checks for common patterns
        message_lower = user_message.lower().strip()

        # Confirmation patterns
        if message_lower in ["yes", "yep", "yeah", "ok", "okay", "sure", "looks good", "perfect", "great", "love it"]:
            return {"intent": "confirmation", "confidence": 0.95}

        # Question patterns
        if message_lower.endswith("?") or message_lower.startswith(("what", "how", "why", "when", "where", "can you", "could you")):
            return {"intent": "clarification", "confidence": 0.85}

        # Correction patterns
        correction_keywords = ["actually", "no,", "not ", "wrong", "incorrect", "meant to say"]
        if any(kw in message_lower for kw in correction_keywords):
            return {"intent": "correction", "confidence": 0.8}

        # Use LLM for nuanced cases
        prompt = INTENT_CLASSIFICATION_PROMPT.format(user_message=user_message)

        try:
            response = await self.llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You classify user intent. Return JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            data = parse_json(response)
            return {
                "intent": data.get("intent", "new_request"),
                "confidence": data.get("confidence", 0.5)
            }
        except Exception as e:
            print(f"[SentimentService] Failed to classify intent: {e}")
            return {"intent": "new_request", "confidence": 0.5}

    def is_positive_feedback(self, user_message: str) -> bool:
        """Quick check if message contains positive feedback."""
        positive_words = [
            "love", "great", "perfect", "awesome", "amazing", "beautiful",
            "nice", "good", "like it", "looks good", "fantastic", "excellent"
        ]
        message_lower = user_message.lower()
        return any(word in message_lower for word in positive_words)

    def is_negative_feedback(self, user_message: str) -> bool:
        """Quick check if message contains negative feedback."""
        negative_words = [
            "don't like", "dont like", "hate", "ugly", "bad", "terrible",
            "awful", "not good", "doesn't look", "wrong", "too much",
            "not what", "not right"
        ]
        message_lower = user_message.lower()
        return any(word in message_lower for word in negative_words)

    def contains_undo_request(self, user_message: str) -> bool:
        """Check if message requests an undo operation."""
        undo_patterns = [
            "undo", "go back", "revert", "previous", "before that",
            "undo that", "undo last", "take that back", "reverse"
        ]
        message_lower = user_message.lower()
        return any(pattern in message_lower for pattern in undo_patterns)
