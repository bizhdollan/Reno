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
    """
    detected_era: Optional[str] = None          # "1970s", "1990s", "2000s", "modern"
    style_assessment: Optional[str] = None      # "dated traditional", "90s contemporary"
    problem_areas: list[str] = field(default_factory=list)  # ["dated countertops", "poor lighting"]
    renovation_scope: Optional[str] = None      # "cosmetic", "moderate", "full renovation"
    material_indicators: list[str] = field(default_factory=list)  # ["laminate counters", "vinyl flooring"]

    def has_useful_context(self) -> bool:
        """Check if we have enough context to build smart queries."""
        return bool(
            self.detected_era or
            self.style_assessment or
            self.problem_areas or
            self.material_indicators
        )


def extract_search_insights(extracted_data: dict) -> SearchInsights:
    """
    Extract search-relevant insights from image analysis data.

    Args:
        extracted_data: The full extraction result from image analysis

    Returns:
        SearchInsights dataclass with relevant context
    """
    search_context = extracted_data.get("search_context", {})

    return SearchInsights(
        detected_era=search_context.get("detected_era"),
        style_assessment=search_context.get("style_assessment"),
        problem_areas=search_context.get("problem_areas", []),
        renovation_scope=search_context.get("renovation_scope"),
        material_indicators=search_context.get("material_age_indicators", [])
    )


def build_smart_queries(
    insights: SearchInsights,
    project_type: str,
    city: str,
    state_abbr: str,
    max_queries: int = 4
) -> list[str]:
    """
    Build contextual Tavily search queries from image insights.

    Creates targeted queries that combine:
    - Location context (city, state)
    - Project type (kitchen, bathroom, etc.)
    - Image-derived insights (era, style, problems, materials)

    Args:
        insights: SearchInsights from image analysis
        project_type: Type of renovation project
        city: City name
        state_abbr: State abbreviation (e.g., "MD")
        max_queries: Maximum number of queries to generate

    Returns:
        List of search query strings optimized for Tavily
    """
    loc = f"{city} {state_abbr}"
    queries = []

    # Query 1: Era-based transformation (if we know the era)
    # Example: "Baltimore MD 1970s kitchen modern renovation"
    if insights.detected_era:
        era_query = f"{loc} {insights.detected_era} {project_type} modern renovation before after"
        queries.append(era_query)

    # Query 2: Style-based upgrade
    # Example: "Baltimore MD dated traditional kitchen contemporary update"
    if insights.style_assessment:
        style_query = f"{loc} {insights.style_assessment} {project_type} contemporary update ideas"
        queries.append(style_query)

    # Query 3: Problem-specific solutions (first problem area)
    # Example: "Baltimore MD kitchen dated countertops replacement options"
    if insights.problem_areas:
        problem = insights.problem_areas[0]
        problem_query = f"{loc} {project_type} {problem} replacement options contractor"
        queries.append(problem_query)

        # If multiple problems, add second problem query
        if len(insights.problem_areas) > 1 and len(queries) < max_queries:
            problem2 = insights.problem_areas[1]
            queries.append(f"{loc} {project_type} {problem2} upgrade solutions")

    # Query 4: Material replacement ideas
    # Example: "Baltimore MD laminate counters quartz replacement cost"
    if insights.material_indicators and len(queries) < max_queries:
        material = insights.material_indicators[0]
        material_query = f"{loc} {material} modern replacement {project_type}"
        queries.append(material_query)

    # Query 5: Scope-appropriate examples (fallback)
    # Example: "Baltimore MD moderate kitchen renovation contractor portfolio"
    if insights.renovation_scope and len(queries) < max_queries:
        scope_query = f"{loc} {insights.renovation_scope} {project_type} renovation contractor portfolio"
        queries.append(scope_query)

    # Fallback: If no insights, use generic queries
    if not queries:
        queries = [
            f"{loc} {project_type} renovation design trends 2024",
            f"{loc} {project_type} remodel before after examples",
            f"{loc} {project_type} contractor portfolio materials",
        ]

    # Ensure we don't exceed max_queries
    return queries[:max_queries]


def build_fallback_queries(project_type: str, city: str, state_abbr: str) -> list[str]:
    """
    Build generic queries when no image insights are available.
    Used as fallback if image analysis doesn't produce search context.

    Args:
        project_type: Type of renovation project
        city: City name
        state_abbr: State abbreviation

    Returns:
        List of generic search queries
    """
    loc = f"{city} {state_abbr}"
    return [
        f"{loc} {project_type} remodel contractor portfolio",
        f"{loc} {project_type} renovation before after",
        f"{loc} home renovation design trends materials",
        f"{loc} {project_type} renovation cost guide 2024"
    ]


def format_queries_for_logging(queries: list[str]) -> str:
    """Format queries for debug logging."""
    return "\n".join([f"  {i+1}. {q}" for i, q in enumerate(queries)])
