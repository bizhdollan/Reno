"""
Smart Search Service

Builds contextual Tavily search queries from image analysis insights.
This enables more relevant search results by using image-derived context.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchInsights:
    """
    Search-relevant insights extracted from image analysis.
    Used to build contextual Tavily queries.

    Maps to VLM's contractor_context output.
    """
    detected_era: Optional[str] = None          # "1970s", "1990s", "2000s", "modern"
    style_assessment: Optional[str] = None      # "dated traditional", "90s contemporary"
    problem_areas: list[str] = field(default_factory=list)  # ["dated countertops", "poor lighting"]
    renovation_scope: Optional[str] = None      # "cosmetic", "moderate", "full renovation"
    material_indicators: list[str] = field(default_factory=list)  # ["laminate counters", "vinyl flooring"]
    # NEW fields from contractor_context
    search_keywords: list[str] = field(default_factory=list)  # VLM-generated search keywords
    primary_work_needed: list[str] = field(default_factory=list)  # ["flooring", "painting", "cabinet_refinishing"]
    specialty_required: list[str] = field(default_factory=list)  # ["tile_installer", "electrician", "plumber"]
    estimated_budget_tier: Optional[str] = None  # "budget", "mid-range", "high-end"

    def has_useful_context(self) -> bool:
        """Check if we have enough context to build smart queries."""
        return bool(
            self.detected_era or
            self.style_assessment or
            self.problem_areas or
            self.material_indicators or
            self.search_keywords or
            self.primary_work_needed or
            self.specialty_required
        )


def extract_search_insights(extracted_data: dict) -> SearchInsights:
    """
    Extract search-relevant insights from image analysis data.

    Checks both contractor_context (VLM comprehensive output) and
    search_context (legacy format) for backward compatibility.

    Args:
        extracted_data: The full extraction result from image analysis

    Returns:
        SearchInsights dataclass with relevant context
    """
    # Check for contractor_context first (comprehensive format), then search_context (legacy format)
    search_context = extracted_data.get("contractor_context") or extracted_data.get("search_context", {})

    return SearchInsights(
        detected_era=search_context.get("detected_era"),
        style_assessment=search_context.get("style_assessment"),
        problem_areas=search_context.get("problem_areas", []),
        renovation_scope=search_context.get("renovation_scope"),
        material_indicators=search_context.get("material_age_indicators", []),
        # NEW fields
        search_keywords=search_context.get("search_keywords", []),
        primary_work_needed=search_context.get("primary_work_needed", []),
        specialty_required=search_context.get("specialty_required", []),
        estimated_budget_tier=search_context.get("estimated_budget_tier"),
    )


def build_smart_queries(
    insights: SearchInsights,
    project_type: str,
    city: str,
    state_abbr: str,
    street_address: Optional[str] = None,
    max_queries: int = 10
) -> list[str]:
    """
    Build contextual Tavily search queries from image insights.

    Creates targeted queries that combine:
    - Location context (street address if available, otherwise city/state)
    - Project type (kitchen, bathroom, etc.)
    - Image-derived insights (era, style, problems, materials, keywords)

    Args:
        insights: SearchInsights from image analysis
        project_type: Type of renovation project
        city: City name
        state_abbr: State abbreviation (e.g., "MD")
        street_address: Full street address if user granted location permission
        max_queries: Maximum number of queries to generate (default 10)

    Returns:
        List of search query strings optimized for Tavily
    """
    # Use specific address for local searches if available
    if street_address:
        loc_specific = street_address  # e.g., "123 Main St, Baltimore MD"
        loc_general = f"{city} {state_abbr}"
    else:
        loc_specific = f"{city} {state_abbr}"
        loc_general = loc_specific

    queries = []

    # === CONTRACTOR/LOCAL SEARCHES (use specific location) ===

    # Query 1: Local contractor search
    queries.append(f"{loc_specific} {project_type} renovation contractor near me")

    # Query 2: Contractor reviews
    queries.append(f"{loc_general} best {project_type} remodel contractor reviews 2024")

    # === ERA-BASED QUERIES ===
    if insights.detected_era:
        # Query 3: Era transformation
        queries.append(f"{loc_general} {insights.detected_era} {project_type} modern renovation before after")
        # Query 4: Era-specific update ideas
        queries.append(f"{insights.detected_era} home {project_type} update ideas contemporary")

    # === STYLE-BASED QUERIES ===
    if insights.style_assessment:
        # Query 5: Style makeover
        queries.append(f"{loc_general} {insights.style_assessment} {project_type} makeover transformation")
        # Query 6: Style upgrade
        queries.append(f"{project_type} {insights.style_assessment} to modern upgrade ideas")

    # === PROBLEM-SPECIFIC QUERIES ===
    for i, problem in enumerate(insights.problem_areas[:3]):
        # Query 7-9: Problem solutions
        queries.append(f"{loc_general} {project_type} {problem} fix contractor cost")

    # === VLM SEARCH KEYWORDS (high value) ===
    if insights.search_keywords:
        # Query 10: Combined keywords search
        kw_query = " ".join(insights.search_keywords[:3])
        queries.append(f"{loc_general} {kw_query}")

    # === SPECIALTY TRADES ===
    for spec in insights.specialty_required[:2]:
        queries.append(f"{loc_specific} {spec} for {project_type} renovation")

    # === WORK-SPECIFIC QUERIES ===
    for work in insights.primary_work_needed[:2]:
        queries.append(f"{loc_general} {project_type} {work} cost estimate 2024")

    # === MATERIAL REPLACEMENT ===
    if insights.material_indicators:
        material = insights.material_indicators[0]
        queries.append(f"{loc_general} {material} modern replacement {project_type}")

    # === SCOPE-BASED QUERIES ===
    if insights.renovation_scope:
        queries.append(f"{loc_general} {insights.renovation_scope} {project_type} renovation portfolio examples")

    # === BUDGET TIER QUERIES ===
    if insights.estimated_budget_tier:
        queries.append(f"{loc_general} {insights.estimated_budget_tier} {project_type} renovation ideas")

    # === FALLBACK QUERIES (if not enough from insights) ===
    fallback_queries = [
        f"{loc_general} {project_type} renovation design trends 2024",
        f"{loc_general} {project_type} remodel before after examples",
        f"{loc_general} {project_type} contractor portfolio materials",
        f"{loc_general} best {project_type} renovation ideas",
        f"{project_type} renovation cost guide {state_abbr} 2024",
        f"{loc_general} home improvement {project_type} inspiration",
    ]

    # Add fallback queries if we don't have enough
    while len(queries) < max_queries and fallback_queries:
        queries.append(fallback_queries.pop(0))

    # Deduplicate while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        q_normalized = q.lower().strip()
        if q_normalized not in seen:
            seen.add(q_normalized)
            unique_queries.append(q)

    # Ensure we don't exceed max_queries
    return unique_queries[:max_queries]


def build_fallback_queries(
    project_type: str,
    city: str,
    state_abbr: str,
    street_address: Optional[str] = None
) -> list[str]:
    """
    Build generic queries when no image insights are available.
    Used as fallback if image analysis doesn't produce search context.

    Args:
        project_type: Type of renovation project
        city: City name
        state_abbr: State abbreviation
        street_address: Optional street address for local searches

    Returns:
        List of generic search queries
    """
    if street_address:
        loc_specific = street_address
        loc_general = f"{city} {state_abbr}"
    else:
        loc_specific = f"{city} {state_abbr}"
        loc_general = loc_specific

    return [
        f"{loc_specific} {project_type} renovation contractor near me",
        f"{loc_general} {project_type} remodel contractor portfolio",
        f"{loc_general} {project_type} renovation before after",
        f"{loc_general} home renovation design trends materials 2024",
        f"{loc_general} {project_type} renovation cost guide 2024",
        f"{loc_general} best {project_type} remodel ideas",
        f"{project_type} renovation inspiration gallery",
        f"{loc_general} {project_type} contractor reviews",
        f"{loc_general} home improvement {project_type}",
        f"{project_type} makeover ideas modern",
    ]


def format_queries_for_logging(queries: list[str]) -> str:
    """Format queries for debug logging."""
    return "\n".join([f"  {i+1}. {q}" for i, q in enumerate(queries)])
