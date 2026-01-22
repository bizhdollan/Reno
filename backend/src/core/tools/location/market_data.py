"""
Market Data Tool

Wraps the existing zip_structured_data_service to provide market intelligence
in the standardized ToolResult format.

Fetches:
- Census data (demographics, housing age, budget indicators)
- Climate data (temperature, considerations)
- Contractor knowledge via Tavily + LLM extraction
"""
import os
import time
from typing import Optional, Dict, Any

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)


async def get_market_data(
    zip_code: str,
    project_type: Optional[str] = None,
    project_id: Optional[str] = None,
    skip_tavily: bool = False
) -> ToolResult:
    """
    Fetch comprehensive market data for a ZIP code.

    This is the main entry point for location-based market intelligence.
    Wraps the existing zip_structured_data_service for consistency.

    Args:
        zip_code: US ZIP code (5 digits)
        project_type: Optional project type for targeted Tavily queries
        project_id: Optional project ID for SSE event broadcasting
        skip_tavily: If True, skip Tavily search (faster, less comprehensive)

    Returns:
        ToolResult containing market data:
        - location: city, state, coordinates
        - budget_indicators: finish_tier, median_income, home_value
        - renovation_context: owner_occupancy, housing_age
        - climate: temperature range, considerations
        - contractor_knowledge: styles, materials, projects (if Tavily enabled)
    """
    start_time = time.time()
    tool_name = "market_data"

    # Import the existing service
    from src.core.services.zip_structured_data_service import (
        get_zip_structured_data,
        get_location_data_only,
        validate_zip
    )

    try:
        validated_zip = validate_zip(zip_code)
    except ValueError as e:
        return ToolResult.error_result(
            error=str(e),
            tool_name=tool_name
        )

    tavily_api_key = os.getenv("TAVILY_API_KEY") if not skip_tavily else None

    try:
        if skip_tavily:
            # Fast path: location data only (no Tavily search)
            logger.info(f"[market_data] Fetching location data only for {validated_zip}")
            data = await get_location_data_only(zip_code=validated_zip)

            execution_time = (time.time() - start_time) * 1000

            return ToolResult.success_result(
                data={
                    "location": data.get("location", {}),
                    "budget_indicators": data.get("budget_indicators", {}),
                    "renovation_context": data.get("renovation_context", {}),
                    "climate": data.get("climate", {}),
                    "contractor_knowledge": None,  # Not fetched
                    "_tavily_pending": True,
                },
                confidence=ConfidenceScore.high(
                    reasoning="Location and Census data retrieved successfully",
                    field_name="market_data"
                ),
                tool_name=tool_name,
                metadata={
                    "execution_time_ms": execution_time,
                    "tavily_enabled": False
                }
            )
        else:
            # Full path: includes Tavily search + LLM extraction
            logger.info(f"[market_data] Fetching full market data for {validated_zip}")
            data = await get_zip_structured_data(
                zip_code=validated_zip,
                tavily_api_key=tavily_api_key,
                project_type=project_type,
                project_id=project_id
            )

            execution_time = (time.time() - start_time) * 1000

            # Determine confidence based on data completeness
            has_census = bool(data.get("budget_indicators", {}).get("finish_tier"))
            has_contractor = bool(data.get("contractor_knowledge", {}).get("popular_styles"))

            if has_census and has_contractor:
                confidence = ConfidenceScore.high(
                    reasoning="Complete market data with contractor knowledge",
                    field_name="market_data"
                )
            elif has_census:
                confidence = ConfidenceScore.medium(
                    reasoning="Census data available but limited contractor knowledge",
                    field_name="market_data"
                )
            else:
                confidence = ConfidenceScore.low(
                    reasoning="Limited market data available",
                    field_name="market_data"
                )

            return ToolResult.success_result(
                data={
                    "location": data.get("location", {}),
                    "budget_indicators": data.get("budget_indicators", {}),
                    "renovation_context": data.get("renovation_context", {}),
                    "climate": data.get("climate", {}),
                    "contractor_knowledge": data.get("contractor_knowledge"),
                    "_sources": data.get("_sources", []),
                },
                confidence=confidence,
                tool_name=tool_name,
                metadata={
                    "execution_time_ms": execution_time,
                    "tavily_enabled": True,
                    "sources_count": len(data.get("_sources", []))
                }
            )

    except Exception as e:
        logger.error(f"[market_data] Error: {e}")
        return ToolResult.error_result(
            error=f"Market data fetch failed: {str(e)}",
            tool_name=tool_name
        )


async def get_market_data_with_search_insights(
    zip_code: str,
    search_insights: Any,  # SearchInsights from smart_search_service
    project_type: Optional[str] = None,
    location_data: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None
) -> ToolResult:
    """
    Fetch market data using smart search queries derived from image analysis.

    This is the advanced entry point that uses image-derived insights
    to build more targeted Tavily search queries.

    Args:
        zip_code: US ZIP code
        search_insights: SearchInsights object from image analysis
        project_type: Optional project type
        location_data: Optional pre-fetched location data (for caching)
        project_id: Optional project ID for SSE events

    Returns:
        ToolResult with enhanced market data based on image context
    """
    start_time = time.time()
    tool_name = "market_data_smart"

    from src.core.services.zip_structured_data_service import (
        get_zip_structured_data,
        validate_zip
    )

    try:
        validated_zip = validate_zip(zip_code)
    except ValueError as e:
        return ToolResult.error_result(error=str(e), tool_name=tool_name)

    tavily_api_key = os.getenv("TAVILY_API_KEY")

    try:
        logger.info(f"[market_data_smart] Fetching with smart queries for {validated_zip}")
        data = await get_zip_structured_data(
            zip_code=validated_zip,
            tavily_api_key=tavily_api_key,
            search_insights=search_insights,
            project_type=project_type,
            location_data=location_data,
            project_id=project_id
        )

        execution_time = (time.time() - start_time) * 1000

        # Determine confidence
        styles_count = len(data.get("contractor_knowledge", {}).get("popular_styles", []))
        materials_count = len(data.get("contractor_knowledge", {}).get("popular_materials", []))

        if styles_count >= 5 and materials_count >= 10:
            confidence = ConfidenceScore.high(
                reasoning=f"Rich contractor knowledge: {styles_count} styles, {materials_count} materials",
                field_name="market_data"
            )
        elif styles_count >= 2 or materials_count >= 5:
            confidence = ConfidenceScore.medium(
                reasoning=f"Moderate contractor knowledge: {styles_count} styles, {materials_count} materials",
                field_name="market_data"
            )
        else:
            confidence = ConfidenceScore.low(
                reasoning="Limited contractor knowledge from search",
                field_name="market_data"
            )

        return ToolResult.success_result(
            data={
                "location": data.get("location", {}),
                "budget_indicators": data.get("budget_indicators", {}),
                "renovation_context": data.get("renovation_context", {}),
                "climate": data.get("climate", {}),
                "contractor_knowledge": data.get("contractor_knowledge"),
                "_sources": data.get("_sources", []),
            },
            confidence=confidence,
            tool_name=tool_name,
            metadata={
                "execution_time_ms": execution_time,
                "smart_queries": True,
                "styles_found": styles_count,
                "materials_found": materials_count
            }
        )

    except Exception as e:
        logger.error(f"[market_data_smart] Error: {e}")
        return ToolResult.error_result(
            error=f"Smart market data fetch failed: {str(e)}",
            tool_name=tool_name
        )


async def extract_contractor_knowledge(
    raw_content: str,
    location: Dict[str, Any],
    budget_tier: str = "mid"
) -> ToolResult:
    """
    Extract contractor knowledge from raw Tavily content using fast LLM.

    Uses LLMProvider.for_fast_analysis() (Cerebras) for quick extraction.

    Args:
        raw_content: Raw content from Tavily search results
        location: Location dict with city, state_abbr
        budget_tier: Budget tier for context (budget/mid/luxury)

    Returns:
        ToolResult with extracted contractor knowledge
    """
    start_time = time.time()
    tool_name = "contractor_knowledge_extraction"

    if not raw_content or len(raw_content.strip()) < 100:
        return ToolResult.error_result(
            error="Insufficient content for extraction",
            tool_name=tool_name
        )

    from src.core.llm.provider import LLMProvider
    import json

    city = location.get("city", "Unknown")
    state_abbr = location.get("state_abbr", "XX")

    # Use Cerebras (fast analysis) for extraction
    provider = LLMProvider.for_fast_analysis()

    prompt = f"""Extract renovation contractor knowledge for {city}, {state_abbr} (budget tier: {budget_tier}) from this content.

CONTENT:
{raw_content[:15000]}  # Truncate for speed

Return JSON with these fields:
{{
  "popular_styles": [
    {{"name": "Style Name", "description": "Brief description", "key_elements": ["element1", "element2"]}}
  ],
  "popular_materials": [
    {{"name": "Material Name", "category": "countertops/flooring/cabinets/etc", "budget_tier": "budget/mid/luxury"}}
  ],
  "budget_expectations": [
    {{"item": "Item name", "insight": "Price range or insight"}}
  ],
  "timeline_expectations": [
    {{"project_type": "Project type", "duration": "X-Y weeks"}}
  ]
}}

Extract as many specific items as found. Return ONLY valid JSON."""

    try:
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Extract contractor knowledge as JSON. Be specific and comprehensive."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=3000,
            operation_type="contractor_knowledge_extraction"
        )

        # Clean and parse response
        response = response.strip()
        if response.startswith('```'):
            lines = response.split('\n')
            response = '\n'.join(line for line in lines if not line.startswith('```'))

        knowledge = json.loads(response.strip())

        execution_time = (time.time() - start_time) * 1000

        styles_count = len(knowledge.get("popular_styles", []))
        materials_count = len(knowledge.get("popular_materials", []))

        logger.info(f"[contractor_knowledge] Extracted {styles_count} styles, {materials_count} materials")

        return ToolResult.success_result(
            data=knowledge,
            confidence=ConfidenceScore.high(
                reasoning=f"Extracted {styles_count} styles, {materials_count} materials",
                field_name="contractor_knowledge"
            ),
            tool_name=tool_name,
            metadata={
                "execution_time_ms": execution_time,
                "styles_count": styles_count,
                "materials_count": materials_count
            }
        )

    except json.JSONDecodeError as e:
        logger.error(f"[contractor_knowledge] JSON parse error: {e}")
        return ToolResult.error_result(
            error=f"Failed to parse LLM response as JSON: {str(e)}",
            tool_name=tool_name
        )
    except Exception as e:
        logger.error(f"[contractor_knowledge] Error: {e}")
        return ToolResult.error_result(
            error=f"Contractor knowledge extraction failed: {str(e)}",
            tool_name=tool_name
        )
