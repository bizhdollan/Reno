"""
Permit Requirements Tool

Detects permit requirements using Tavily search + Cerebras analysis.
Searches real building code data and extracts structured requirements.
"""
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import httpx

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)

# Keywords that indicate permit-triggering work
PERMIT_TRIGGER_KEYWORDS = {
    "structural": ["load-bearing", "wall removal", "knock down wall", "open concept", "structural", "beam", "column", "foundation"],
    "electrical": ["electrical", "wiring", "panel", "outlets", "circuits", "220v", "240v", "breaker"],
    "plumbing": ["plumbing", "pipes", "drain", "water heater", "gas line", "sewer", "fixture relocation"],
    "hvac": ["hvac", "ductwork", "furnace", "air conditioning", "heating", "ventilation"],
    "building": ["addition", "extension", "square footage", "new room", "egress", "window enlargement"],
}


@dataclass
class PermitRequirement:
    """A detected permit requirement."""
    permit_type: str  # building, electrical, plumbing, mechanical, etc.
    required: bool
    trigger_reason: str
    timeline_weeks: Optional[int] = None
    fee_range: Optional[tuple] = None  # (min, max)
    professional_required: Optional[str] = None  # PE, RA, licensed contractor
    source_url: Optional[str] = None
    confidence: float = 0.7

    def to_dict(self) -> dict:
        return {
            "permit_type": self.permit_type,
            "required": self.required,
            "trigger_reason": self.trigger_reason,
            "timeline_weeks": self.timeline_weeks,
            "fee_range": list(self.fee_range) if self.fee_range else None,
            "professional_required": self.professional_required,
            "source_url": self.source_url,
            "confidence": self.confidence
        }


@dataclass
class PermitAnalysis:
    """Complete permit analysis result."""
    permits_required: List[PermitRequirement]
    total_permit_timeline_weeks: int
    jurisdiction_notes: str
    landmark_review_required: bool
    professional_certifications_needed: List[str]
    estimated_total_fees: Optional[tuple] = None  # (min, max)
    sources: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "permits_required": [p.to_dict() for p in self.permits_required],
            "total_permit_timeline_weeks": self.total_permit_timeline_weeks,
            "jurisdiction_notes": self.jurisdiction_notes,
            "landmark_review_required": self.landmark_review_required,
            "professional_certifications_needed": self.professional_certifications_needed,
            "estimated_total_fees": list(self.estimated_total_fees) if self.estimated_total_fees else None,
            "sources": self.sources
        }


async def search_building_codes(
    scope_description: str,
    location: str,
    project_type: str
) -> List[Dict[str, Any]]:
    """
    Search for relevant building code information using Tavily.

    Args:
        scope_description: Description of renovation work
        location: City/state location
        project_type: Type of project

    Returns:
        List of search results with title, url, content
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        logger.warning("[permit_search] TAVILY_API_KEY not configured")
        return []

    # Build targeted queries
    queries = [
        f"{location} building permit requirements {project_type} renovation",
        f"{location} DOB permit filing requirements residential",
        f"{location} {project_type} renovation permit timeline fees",
    ]

    # Add scope-specific queries
    scope_lower = scope_description.lower()
    for category, keywords in PERMIT_TRIGGER_KEYWORDS.items():
        if any(kw in scope_lower for kw in keywords):
            queries.append(f"{location} {category} permit requirements residential")

    all_results = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for query in queries[:4]:  # Limit to 4 queries
            try:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": tavily_api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": 3,
                        "include_raw_content": False
                    }
                )
                response.raise_for_status()
                data = response.json()

                for result in data.get("results", []):
                    all_results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "score": result.get("score", 0)
                    })

            except Exception as e:
                logger.warning(f"[permit_search] Query failed: {query[:50]}... - {e}")

    # Deduplicate by URL
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    return unique_results


async def analyze_permit_requirements(
    scope_description: str,
    search_results: List[Dict[str, Any]],
    building_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze search results to determine permit requirements using Cerebras.

    Args:
        scope_description: Description of renovation work
        search_results: Tavily search results
        building_context: Building info (year_built, location, is_landmark)

    Returns:
        Structured permit analysis
    """
    from src.core.llm.provider import LLMProvider

    # Format search results
    results_text = "\n\n".join([
        f"Source: {r.get('title', 'Unknown')}\nURL: {r.get('url', '')}\n{r.get('content', '')}"
        for r in search_results[:8]
    ])

    location = building_context.get("location", "Unknown location")
    year_built = building_context.get("year_built", "Unknown")
    is_landmark = building_context.get("is_landmark", False)

    prompt = f"""Based on the following building code search results and project scope, determine permit requirements.

PROJECT SCOPE:
{scope_description}

BUILDING CONTEXT:
- Location: {location}
- Year Built: {year_built}
- Landmark Status: {"Yes" if is_landmark else "No"}

SEARCH RESULTS:
{results_text}

Analyze the scope and search results to determine what permits are required.

Return JSON:
{{
  "permits_required": [
    {{
      "permit_type": "building|electrical|plumbing|mechanical|demolition",
      "required": true|false,
      "trigger_reason": "specific reason from scope that triggers this permit",
      "timeline_weeks": estimated weeks,
      "fee_range": [min_fee, max_fee],
      "professional_required": "PE|RA|Licensed Contractor|None",
      "source_reference": "URL or code section if found"
    }}
  ],
  "landmark_review_required": true|false,
  "total_timeline_weeks": max of all permits,
  "jurisdiction_notes": "any important local requirements or caveats",
  "professional_certifications_needed": ["list of required professionals"]
}}

RULES:
- Only mark required=true if the scope CLEARLY triggers that permit type
- Be conservative - if unsure, mark as required
- Include source references when available
- For NYC, mention DOB filing types (ALT1, ALT2, ALT3) if applicable"""

    try:
        provider = LLMProvider.for_fast_analysis()

        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Analyze building permit requirements from search results. Return JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2000,
            operation_type="permit_analysis"
        )

        # Parse response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(line for line in lines if not line.startswith("```"))

        return json.loads(response_text)

    except json.JSONDecodeError as e:
        logger.error(f"[permit_analysis] JSON parse error: {e}")
        return {
            "permits_required": [],
            "landmark_review_required": is_landmark,
            "total_timeline_weeks": 0,
            "jurisdiction_notes": "Analysis failed - please consult local building department",
            "professional_certifications_needed": []
        }
    except Exception as e:
        logger.error(f"[permit_analysis] Error: {e}")
        return {
            "permits_required": [],
            "landmark_review_required": is_landmark,
            "total_timeline_weeks": 0,
            "jurisdiction_notes": f"Analysis error: {str(e)}",
            "professional_certifications_needed": []
        }


async def detect_permit_requirements(
    project_type: str,
    scope_description: str,
    location: str,
    building_age: Optional[int] = None,
    is_landmark: bool = False,
    is_nyc: bool = False
) -> ToolResult:
    """
    Detect permit requirements for a renovation project.

    Uses Tavily search + Cerebras analysis for intelligent detection.

    Args:
        project_type: Type of project (kitchen, bathroom, etc.)
        scope_description: Description of planned work
        location: City, State location
        building_age: Year built (for code compliance)
        is_landmark: Whether building is landmarked
        is_nyc: Whether in NYC (for DOB-specific rules)

    Returns:
        ToolResult with PermitAnalysis
    """
    start_time = time.time()
    tool_name = "permit_requirements"

    if not scope_description:
        return ToolResult.error_result(
            error="Scope description is required",
            tool_name=tool_name
        )

    if not location:
        return ToolResult.error_result(
            error="Location is required",
            tool_name=tool_name
        )

    try:
        # Step 1: Search for building codes
        logger.info(f"[permit_requirements] Searching building codes for {location}")
        search_results = await search_building_codes(
            scope_description=scope_description,
            location=location,
            project_type=project_type
        )

        logger.info(f"[permit_requirements] Found {len(search_results)} search results")

        # Step 2: Analyze with Cerebras
        building_context = {
            "location": location,
            "year_built": building_age,
            "is_landmark": is_landmark,
            "is_nyc": is_nyc
        }

        analysis_data = await analyze_permit_requirements(
            scope_description=scope_description,
            search_results=search_results,
            building_context=building_context
        )

        # Step 3: Build PermitAnalysis
        permits = []
        for p in analysis_data.get("permits_required", []):
            permits.append(PermitRequirement(
                permit_type=p.get("permit_type", "building"),
                required=p.get("required", False),
                trigger_reason=p.get("trigger_reason", ""),
                timeline_weeks=p.get("timeline_weeks"),
                fee_range=tuple(p.get("fee_range")) if p.get("fee_range") else None,
                professional_required=p.get("professional_required"),
                source_url=p.get("source_reference"),
                confidence=0.7 if search_results else 0.5
            ))

        # Add rule-based checks
        permits = _apply_rule_based_checks(permits, scope_description, building_age, is_nyc)

        # Calculate totals
        total_timeline = analysis_data.get("total_timeline_weeks", 0)
        if not total_timeline and permits:
            timelines = [p.timeline_weeks for p in permits if p.timeline_weeks]
            total_timeline = max(timelines) if timelines else 4

        # Fee estimation
        min_fees = sum(p.fee_range[0] for p in permits if p.fee_range)
        max_fees = sum(p.fee_range[1] for p in permits if p.fee_range)
        total_fees = (min_fees, max_fees) if min_fees or max_fees else None

        analysis = PermitAnalysis(
            permits_required=permits,
            total_permit_timeline_weeks=total_timeline,
            jurisdiction_notes=analysis_data.get("jurisdiction_notes", ""),
            landmark_review_required=analysis_data.get("landmark_review_required", is_landmark),
            professional_certifications_needed=analysis_data.get("professional_certifications_needed", []),
            estimated_total_fees=total_fees,
            sources=[{"title": r["title"], "url": r["url"]} for r in search_results[:5]]
        )

        execution_time = (time.time() - start_time) * 1000

        # Determine confidence
        required_permits = [p for p in permits if p.required]
        if search_results and required_permits:
            confidence = ConfidenceScore(
                value=0.75,
                reasoning=f"Found {len(search_results)} sources, detected {len(required_permits)} required permits"
            )
        elif required_permits:
            confidence = ConfidenceScore(
                value=0.6,
                reasoning=f"Rule-based detection of {len(required_permits)} permits (limited search results)"
            )
        else:
            confidence = ConfidenceScore(
                value=0.5,
                reasoning="Limited permit information found - recommend verifying with local building department"
            )

        return ToolResult.success_result(
            data=analysis.to_dict(),
            confidence=confidence,
            tool_name=tool_name,
            metadata={
                "execution_time_ms": execution_time,
                "search_results_count": len(search_results),
                "required_permits_count": len(required_permits),
                "is_nyc": is_nyc
            }
        )

    except Exception as e:
        logger.error(f"[permit_requirements] Error: {e}")
        return ToolResult.error_result(
            error=f"Permit detection failed: {str(e)}",
            tool_name=tool_name
        )


def _apply_rule_based_checks(
    permits: List[PermitRequirement],
    scope_description: str,
    building_age: Optional[int],
    is_nyc: bool
) -> List[PermitRequirement]:
    """Apply deterministic rule-based permit checks."""
    scope_lower = scope_description.lower()

    existing_types = {p.permit_type for p in permits}

    # Structural work always needs building permit
    structural_keywords = ["wall removal", "load-bearing", "knock down", "open concept", "structural"]
    if any(kw in scope_lower for kw in structural_keywords):
        if "building" not in existing_types:
            permits.append(PermitRequirement(
                permit_type="building",
                required=True,
                trigger_reason="Structural work detected (wall removal/modification)",
                timeline_weeks=4 if not is_nyc else 8,
                professional_required="PE or RA",
                confidence=0.9
            ))

    # Electrical work
    electrical_keywords = ["electrical", "wiring", "panel", "outlets", "circuits"]
    if any(kw in scope_lower for kw in electrical_keywords):
        if "electrical" not in existing_types:
            permits.append(PermitRequirement(
                permit_type="electrical",
                required=True,
                trigger_reason="Electrical work detected",
                timeline_weeks=2,
                professional_required="Licensed Electrician",
                confidence=0.9
            ))

    # Plumbing work
    plumbing_keywords = ["plumbing", "pipes", "drain", "water heater", "gas line", "fixture relocation"]
    if any(kw in scope_lower for kw in plumbing_keywords):
        if "plumbing" not in existing_types:
            permits.append(PermitRequirement(
                permit_type="plumbing",
                required=True,
                trigger_reason="Plumbing work detected",
                timeline_weeks=2,
                professional_required="Licensed Plumber",
                confidence=0.9
            ))

    # Pre-1978 buildings - lead paint considerations
    if building_age and building_age < 1978:
        # Not a permit, but important note
        has_lead_note = any("lead" in p.trigger_reason.lower() for p in permits)
        if not has_lead_note:
            permits.append(PermitRequirement(
                permit_type="lead_certification",
                required=True,
                trigger_reason=f"Building from {building_age} - EPA RRP rule requires lead-safe practices",
                professional_required="EPA Lead-Safe Certified Renovator",
                confidence=0.95
            ))

    return permits


def check_scope_for_permits(scope_description: str) -> Dict[str, bool]:
    """
    Quick check if scope likely requires permits (without API calls).

    Args:
        scope_description: Description of work

    Returns:
        Dict mapping permit types to whether they're likely required
    """
    scope_lower = scope_description.lower()
    likely_required = {}

    for category, keywords in PERMIT_TRIGGER_KEYWORDS.items():
        likely_required[category] = any(kw in scope_lower for kw in keywords)

    return likely_required
