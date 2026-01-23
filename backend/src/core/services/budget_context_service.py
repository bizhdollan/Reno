"""
Budget Context Service.

Handles budget sentiment detection and material suggestions:
- Detect budget sentiment from user messages (low, medium, high)
- Suggest budget-appropriate materials (NO prices during ideation)
- Get regional costs (only for cost estimation phase)
"""

import json
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.db.models import BudgetContext

logger = get_logger(__name__)
from src.core.llm.provider import LLMProvider
from src.core.langgraph.utils import parse_json
from .session_cache import SessionCache


# Budget sentiment detection prompt
BUDGET_SENTIMENT_PROMPT = """Analyze the user's message for budget sentiment.

User said: "{user_message}"

Classify their budget sentiment as:
- **low**: Limited budget, looking for affordable options, cost-conscious
  Keywords: "limited budget", "affordable", "cheap", "save money", "budget-friendly", "not too expensive"

- **medium**: Reasonable budget, willing to invest but practical
  Keywords: "reasonable budget", "mid-range", "standard", "good value", "balanced"

- **high**: Premium budget, looking for high-end options
  Keywords: "premium", "luxury", "high-end", "best quality", "money is not an issue", "top of the line"

If no clear budget indication, return "medium" as default.

Return JSON:
{{
    "sentiment": "low",
    "confidence": 0.85,
    "reasoning": "User mentioned 'limited budget' indicating cost-consciousness"
}}

Return valid JSON only, no markdown."""


# Material suggestions prompt template
MATERIAL_SUGGESTIONS_PROMPT = """For a {room_type} renovation with {budget_level} budget level:

Suggest appropriate materials for each category. Consider:
- Durability and practicality for the room type
- Aesthetic appeal
- Budget alignment (no need for exact prices)

Budget Guidelines:
- **low**: Affordable, practical materials (laminate, vinyl, paint, basic fixtures)
- **medium**: Mid-range materials (tile, semi-custom cabinets, quality fixtures)
- **high**: Premium materials (marble, hardwood, custom work, designer fixtures)

Return JSON with material options (NO PRICES):
{{
    "floor": ["option1", "option2", "option3"],
    "walls": ["option1", "option2"],
    "countertops": ["option1", "option2"] if applicable,
    "fixtures": ["option1", "option2"],
    "lighting": ["option1", "option2"],
    "recommended_focus": "Brief note on where to prioritize spending"
}}

Return valid JSON only, no markdown."""


class BudgetContextService:
    """
    Service for budget sentiment detection and material suggestions.

    Responsibilities:
    - Detect budget sentiment from user messages
    - Suggest budget-appropriate materials (NO PRICES during ideation)
    - Get regional costs (only for cost estimation phase)
    """

    def __init__(
        self,
        db: Session,
        llm_provider: Optional[LLMProvider] = None,
        cache: Optional[SessionCache] = None
    ):
        self.db = db
        self.llm = llm_provider or LLMProvider.for_llm()
        self.cache = cache or SessionCache()

    async def detect_budget_sentiment(
        self,
        user_message: str,
        project_id: UUID
    ) -> BudgetContext:
        """
        Detect budget sentiment from user message and store in database.

        IMPORTANT: This does NOT return prices. Prices are only shown in
        the cost estimation phase.

        Args:
            user_message: The user's message to analyze
            project_id: UUID of the project

        Returns:
            BudgetContext with sentiment and suggested materials
        """
        logger.info(f"[BudgetContextService] Detecting budget from: {user_message[:50]}...")

        # Format prompt
        prompt = BUDGET_SENTIMENT_PROMPT.format(user_message=user_message)

        # Call LLM
        response = await self.llm.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You analyze user messages for budget sentiment. Return JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )

        # Parse response
        try:
            data = parse_json(response)
            sentiment = data.get("sentiment", "medium")
            confidence = data.get("confidence", 0.5)
        except Exception as e:
            logger.info(f"[BudgetContextService] Failed to parse response: {e}")
            sentiment = "medium"
            confidence = 0.5

        # Validate sentiment
        valid_sentiments = ["low", "medium", "high"]
        if sentiment not in valid_sentiments:
            sentiment = "medium"

        # Get material suggestions based on sentiment
        materials = await self.suggest_materials(
            budget_level=sentiment,
            room_type="room"  # Will be refined when we have room context
        )

        # Create and save context
        context = BudgetContext(
            project_id=project_id,
            budget_sentiment=sentiment,
            detected_from_message=user_message[:500],  # Truncate long messages
            suggested_materials=materials
        )
        self.db.add(context)
        self.db.commit()
        self.db.refresh(context)

        # Cache the context
        self.cache.set_budget_context(project_id, context)

        logger.info(f"[BudgetContextService] Detected sentiment: {sentiment} (confidence: {confidence})")
        return context

    async def suggest_materials(
        self,
        budget_level: str,
        room_type: str
    ) -> dict:
        """
        Suggest budget-appropriate materials.

        IMPORTANT: This does NOT include prices. Material suggestions
        help guide the design conversation without discussing costs.

        Args:
            budget_level: "low", "medium", or "high"
            room_type: Type of room (kitchen, bathroom, bedroom, etc.)

        Returns:
            Dictionary of material suggestions by category
        """
        prompt = MATERIAL_SUGGESTIONS_PROMPT.format(
            room_type=room_type,
            budget_level=budget_level
        )

        try:
            response = await self.llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an interior designer suggesting materials. Return JSON only, NO PRICES."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            return parse_json(response)
        except Exception as e:
            logger.info(f"[BudgetContextService] Failed to suggest materials: {e}")
            # Return defaults based on budget level
            return self._get_default_materials(budget_level)

    def _get_default_materials(self, budget_level: str) -> dict:
        """Get default material suggestions when LLM fails."""
        defaults = {
            "low": {
                "floor": ["laminate", "vinyl plank", "carpet"],
                "walls": ["paint", "basic wallpaper"],
                "fixtures": ["basic chrome", "brushed nickel"],
                "lighting": ["basic LED", "flush mount"],
                "recommended_focus": "Focus on paint and flooring for maximum impact on limited budget."
            },
            "medium": {
                "floor": ["engineered hardwood", "ceramic tile", "luxury vinyl"],
                "walls": ["premium paint", "accent wall", "wainscoting"],
                "fixtures": ["quality chrome", "brushed brass"],
                "lighting": ["pendant lights", "recessed LED"],
                "recommended_focus": "Balance quality flooring with statement lighting."
            },
            "high": {
                "floor": ["hardwood", "marble", "natural stone"],
                "walls": ["designer wallpaper", "custom millwork", "accent stone"],
                "fixtures": ["designer brass", "custom finishes"],
                "lighting": ["chandeliers", "designer pendants", "smart lighting"],
                "recommended_focus": "Premium materials throughout with custom details."
            }
        }
        return defaults.get(budget_level, defaults["medium"])

    async def get_regional_costs(
        self,
        zip_code: str,
        room_type: str
    ) -> dict:
        """
        Get regional cost data for cost estimation phase (WITH PRICES).

        IMPORTANT: This method is ONLY used in the cost_estimation node,
        NOT during ideation/generation phases.

        Args:
            zip_code: User's zip code for regional pricing
            room_type: Type of room being renovated

        Returns:
            Dictionary with low/mid/high tier breakdowns including prices
        """
        logger.info(f"[BudgetContextService] Getting regional costs for {zip_code}, {room_type}")

        prompt = f"""For zip code {zip_code}, provide cost estimates for {room_type} renovation.

Consider regional factors:
- Local labor costs
- Material availability and shipping
- Regional style preferences

Return 3 tiers (low, mid, high) with estimated costs per element.

JSON format:
{{
    "low_tier": {{
        "description": "Budget-friendly renovation",
        "floor": {{"material": "laminate", "cost_range": "$1500-2500"}},
        "walls": {{"material": "paint", "cost_range": "$500-1000"}},
        "fixtures": {{"material": "basic", "cost_range": "$500-800"}},
        "total_estimate": "$3000-5000"
    }},
    "mid_tier": {{
        "description": "Quality mid-range renovation",
        "floor": {{"material": "tile", "cost_range": "$3000-5000"}},
        "walls": {{"material": "premium paint", "cost_range": "$1000-1500"}},
        "fixtures": {{"material": "quality", "cost_range": "$1500-2500"}},
        "total_estimate": "$8000-12000"
    }},
    "high_tier": {{
        "description": "Premium renovation",
        "floor": {{"material": "hardwood", "cost_range": "$6000-10000"}},
        "walls": {{"material": "custom", "cost_range": "$2000-4000"}},
        "fixtures": {{"material": "designer", "cost_range": "$3000-6000"}},
        "total_estimate": "$15000-25000"
    }}
}}

Return valid JSON only."""

        try:
            response = await self.llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a cost estimator for home renovations. Provide realistic regional pricing."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            return parse_json(response)
        except Exception as e:
            logger.info(f"[BudgetContextService] Failed to get regional costs: {e}")
            # Return generic defaults
            return {
                "low_tier": {"total_estimate": "$3000-5000"},
                "mid_tier": {"total_estimate": "$8000-12000"},
                "high_tier": {"total_estimate": "$15000-25000"}
            }

    async def get_budget_context(self, project_id: UUID) -> Optional[BudgetContext]:
        """Get the latest budget context for a project."""
        # Try cache first
        context = self.cache.get_budget_context(project_id)
        if context:
            return context

        # Query database
        context = self.db.query(BudgetContext).filter_by(
            project_id=project_id
        ).order_by(BudgetContext.created_at.desc()).first()

        if context:
            self.cache.set_budget_context(project_id, context)

        return context

    def has_budget_keywords(self, message: str) -> bool:
        """Check if message contains budget-related keywords."""
        keywords = [
            "budget", "cost", "price", "afford", "cheap", "expensive",
            "money", "spend", "investment", "$", "dollar", "thousand",
            "limited", "premium", "luxury", "value"
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in keywords)
