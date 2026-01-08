#!/usr/bin/env python3
"""
Streamlined zip code data service for LLM consumption.

Fetches evidence-based renovation insights from:
- Zippopotam.us (place info)
- US Census ACS (demographics, housing age, budget indicators)
- NWS API (climate considerations)
- Tavily API (design trends, materials, constraints with citations)

Output is optimized for LLM suggestion generation - concise, actionable, with credible sources.

PERFORMANCE OPTIMIZED:
- Census, Climate, Tavily run in PARALLEL
- Census data cached by zip (1 hour TTL)
- Strict timeouts on all API calls (10s max)
- Reduced Tavily results (2 per query)
"""

import asyncio
import json
import re
import subprocess
import threading
import time as time_module
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from urllib.parse import quote
from dataclasses import dataclass

import requests

if TYPE_CHECKING:
    from src.core.services.smart_search_service import SearchInsights

# Event broadcasting for SSE
from src.core.services.event_broadcaster import (
    emit_search_query,
    emit_search_result,
    emit_search_complete,
    emit_context_ready,
)

# ----------------------------
# Caching for Census data (1 hour TTL)
# ----------------------------
_census_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
_census_cache_lock = threading.Lock()
CENSUS_CACHE_TTL = 3600  # 1 hour

# API Timeouts (seconds)
CENSUS_TIMEOUT = 10
CLIMATE_TIMEOUT = 8
TAVILY_TIMEOUT = 15
PLACE_TIMEOUT = 5

# ----------------------------
# Constants
# ----------------------------

ZIPPOTAM_BASE = "https://api.zippopotam.us/us/{zip}"
CENSUS_BASE = "https://api.census.gov/data/{year}/acs/acs5"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
DEFAULT_USER_AGENT = "renovation-tech-service/1.0"

# Census ACS variables
ACS_VARS_CORE = {
    "B19013_001E": "median_household_income",
    "B25077_001E": "median_home_value",
    "B25064_001E": "median_gross_rent",
    "B25002_002E": "owner_occupied_units",
    "B25002_003E": "renter_occupied_units",
}

ACS_VARS_YEAR_BUILT = {
    "B25034_001E": "housing_units_total",
    "B25034_002E": "built_2020_or_later",
    "B25034_003E": "built_2010_2019",
    "B25034_004E": "built_2000_2009",
    "B25034_005E": "built_1990_1999",
    "B25034_006E": "built_1980_1989",
    "B25034_007E": "built_1970_1979",
    "B25034_008E": "built_1960_1969",
    "B25034_009E": "built_1950_1959",
    "B25034_010E": "built_1940_1949",
    "B25034_011E": "built_1939_or_earlier",
}

# No hardcoded keywords - we use LLM extraction for contractor knowledge


# ----------------------------
# Utilities
# ----------------------------

def validate_zip(zip_code: str) -> str:
    """Validate 5-digit US zip code."""
    z = (zip_code or "").strip()
    if not re.fullmatch(r"\d{5}", z):
        raise ValueError("ZIP code must be 5 digits (e.g., '90210').")
    return z


def safe_div(n: float, d: float, default: float = 0.0) -> float:
    """Safe division with default."""
    return default if d == 0 else (n / d)


def clamp01(x: float) -> float:
    """Clamp value to 0-1 range."""
    return max(0.0, min(1.0, x))


def normalize_text(s: Optional[str]) -> str:
    """Normalize text for keyword matching."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip().lower()


def is_probably_gov_url(url: str) -> bool:
    """Check if URL is likely a government website."""
    u = normalize_text(url)
    return ".gov/" in u or u.endswith(".gov") or ".gov?" in u


def domain_of(url: str) -> str:
    """Extract domain from URL."""
    m = re.match(r"^https?://([^/]+)/?", url.strip(), re.I)
    return m.group(1).lower() if m else ""


# ----------------------------
# 1) Place lookup
# ----------------------------

def get_place_from_zip(zip_code: str) -> Dict[str, Any]:
    """Fetch city, state, lat/lon from zip code via Zippopotam.us."""
    zip_code = validate_zip(zip_code)
    url = ZIPPOTAM_BASE.format(zip=zip_code)
    resp = requests.get(url, timeout=PLACE_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    place = data["places"][0]
    return {
        "zip": data.get("post code", zip_code),
        "city": place.get("place name"),
        "state": place.get("state"),
        "state_abbr": place.get("state abbreviation"),
        "latitude": float(place["latitude"]) if place.get("latitude") else None,
        "longitude": float(place["longitude"]) if place.get("longitude") else None,
    }


# ----------------------------
# 2) Census ACS with fallback
# ----------------------------

def build_census_acs_url(year: int, zcta: str, var_codes: List[str]) -> str:
    """Build Census ACS API URL."""
    get_part = ",".join(var_codes)
    geo = f"zip code tabulation area:{zcta}"
    return f"{CENSUS_BASE.format(year=year)}?get={quote(get_part)}&for={quote(geo)}"


def try_requests_json(url: str, timeout: int = CENSUS_TIMEOUT) -> Optional[Any]:
    """Try to fetch JSON via requests with strict timeout."""
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def nslookup_ip(hostname: str) -> Optional[str]:
    """Resolve hostname to IP via nslookup (with timeout)."""
    try:
        out = subprocess.check_output(
            ["nslookup", hostname],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=3  # 3 second timeout for DNS
        )
    except Exception:
        return None
    ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", out)
    return ips[-1] if ips else None


def curl_resolve_json(url: str, hostname: str, ip: str, timeout: int = CENSUS_TIMEOUT) -> Any:
    """Fetch JSON via curl with DNS override and strict timeout."""
    cmd = [
        "curl", "--silent", "--show-error", "--fail", "--location",
        "--max-time", str(timeout),  # Strict timeout
        "--connect-timeout", "5",    # Connection timeout
        "--resolve", f"{hostname}:443:{ip}", url,
    ]
    out = subprocess.check_output(cmd, text=True, timeout=timeout + 2)
    return json.loads(out)


def _get_cached_census(zip_code: str) -> Optional[Dict[str, Any]]:
    """Get Census data from cache if valid."""
    with _census_cache_lock:
        if zip_code in _census_cache:
            data, timestamp = _census_cache[zip_code]
            if time_module.time() - timestamp < CENSUS_CACHE_TTL:
                return data
            # Expired, remove from cache
            del _census_cache[zip_code]
    return None


def _set_cached_census(zip_code: str, data: Dict[str, Any]) -> None:
    """Cache Census data."""
    with _census_cache_lock:
        _census_cache[zip_code] = (data, time_module.time())


def fetch_acs_data(zip_code: str, year: int = 2023) -> Dict[str, Any]:
    """
    Fetch Census ACS data with DNS fallback and caching.

    PERFORMANCE:
    - Checks cache first (1 hour TTL)
    - Strict 10s timeout on all requests
    - Returns empty dict on timeout (graceful degradation)
    """
    zcta = validate_zip(zip_code)

    # Check cache first
    cached = _get_cached_census(zcta)
    if cached is not None:
        print(f"[zip_structured_data] 💾 Census cache hit for {zcta}")
        return cached

    var_map: Dict[str, str] = {}
    var_map.update(ACS_VARS_CORE)
    var_map.update(ACS_VARS_YEAR_BUILT)

    var_codes = list(var_map.keys())
    url = build_census_acs_url(year, zcta=zcta, var_codes=var_codes)

    # Try direct request first with strict timeout
    data = try_requests_json(url, timeout=CENSUS_TIMEOUT)

    # Fallback to DNS resolution if needed (also with timeout)
    if data is None:
        hostname = "api.census.gov"
        ip = nslookup_ip(hostname)
        if not ip:
            print(f"[zip_structured_data] ⚠️  Could not resolve api.census.gov")
            return {}
        try:
            data = curl_resolve_json(url, hostname=hostname, ip=ip, timeout=CENSUS_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"[zip_structured_data] ⚠️  Census API timeout after {CENSUS_TIMEOUT}s")
            return {}
        except Exception as e:
            print(f"[zip_structured_data] ⚠️  Census API error: {e}")
            return {}

    if data is None:
        return {}

    # Parse response
    header = data[0]
    row = data[1]

    values: Dict[str, Any] = {}
    for i, col in enumerate(header):
        if col == "zip code tabulation area":
            continue
        key = var_map.get(col, col)
        raw = row[i]
        if raw is None:
            val: Any = None
        else:
            try:
                val = int(raw)
            except Exception:
                val = raw
        values[key] = val

    # Cache the result
    _set_cached_census(zcta, values)

    return values


# ----------------------------
# 3) Derive design insights
# ----------------------------

def derive_design_insights(acs_values: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive actionable design insights from Census data.
    Returns budget tier, renovation intensity, likely project types.
    """
    owners = int(acs_values.get("owner_occupied_units") or 0)
    renters = int(acs_values.get("renter_occupied_units") or 0)

    total_units = acs_values.get("housing_units_total")
    if total_units is None or int(total_units) <= 0:
        total_units = owners + renters
    total_units = max(1, int(total_units))

    owner_pct = safe_div(owners, total_units)

    def s(*keys: str) -> int:
        return sum(int(acs_values.get(k) or 0) for k in keys)

    # Housing age percentages
    pre_1980_units = s(
        "built_1970_1979", "built_1960_1969", "built_1950_1959",
        "built_1940_1949", "built_1939_or_earlier",
    )
    pre_1960_units = s(
        "built_1950_1959", "built_1940_1949", "built_1939_or_earlier",
    )

    pre_1980_pct = safe_div(pre_1980_units, total_units)
    pre_1960_pct = safe_div(pre_1960_units, total_units)

    # Budget indicators
    income = float(acs_values.get("median_household_income") or 0)
    home_value = float(acs_values.get("median_home_value") or 0)
    rent = float(acs_values.get("median_gross_rent") or 0)

    income_norm = clamp01(income / 200_000.0)
    value_norm = clamp01(home_value / 2_000_000.0)
    rent_norm = clamp01(rent / 3_000.0)

    # Scoring
    renovation_propensity = clamp01(0.50 * owner_pct + 0.50 * pre_1980_pct)
    systems_upgrade_risk = clamp01(pre_1960_pct)
    luxury_finish_likelihood = clamp01(0.45 * income_norm + 0.45 * value_norm + 0.10 * rent_norm)

    # Classification
    if renovation_propensity > 0.65:
        renovation_intensity = "high"
    elif renovation_propensity > 0.40:
        renovation_intensity = "medium"
    else:
        renovation_intensity = "low"

    if luxury_finish_likelihood > 0.70:
        finish_tier = "luxury"
    elif luxury_finish_likelihood > 0.45:
        finish_tier = "upper-mid"
    else:
        finish_tier = "mid"

    # Systems upgrade priority
    if systems_upgrade_risk > 0.50:
        systems_priority = "high"
    elif systems_upgrade_risk > 0.30:
        systems_priority = "medium"
    else:
        systems_priority = "low"

    # Likely project types
    likely_project_types: List[str] = []
    if owner_pct > 0.70:
        likely_project_types.append("kitchen and bathroom renovations")
    if pre_1980_pct > 0.60:
        likely_project_types.append("layout modernization")
        likely_project_types.append("energy-efficiency upgrades")
    if pre_1960_pct > 0.30:
        likely_project_types.append("electrical and plumbing upgrades")

    return {
        "budget_indicators": {
            "finish_tier": finish_tier,
            "median_household_income": int(income),
            "median_home_value": int(home_value),
            "median_gross_rent": int(rent),
        },
        "renovation_context": {
            "intensity": renovation_intensity,
            "owner_occupancy_pct": round(owner_pct, 2),
            "housing_age_pre_1980_pct": round(pre_1980_pct, 2),
            "housing_age_pre_1960_pct": round(pre_1960_pct, 2),
            "likely_project_types": likely_project_types,
            "systems_upgrade_priority": systems_priority,
        },
    }


# ----------------------------
# 4) Climate essentials (NWS)
# ----------------------------

def nws_get_json(url: str, user_agent: str = DEFAULT_USER_AGENT) -> Dict[str, Any]:
    """Fetch JSON from NWS API with strict timeout."""
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/geo+json, application/json",
    }
    r = requests.get(url, headers=headers, timeout=CLIMATE_TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_climate_essentials(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch climate essentials from NWS API.
    Returns only actionable design considerations (no excessive grid signals).
    """
    try:
        points = nws_get_json(NWS_POINTS_URL.format(lat=lat, lon=lon))
        props = points.get("properties", {}) or {}

        forecast_url = props.get("forecast")
        if not forecast_url:
            return {
                "temp_range_f": None,
                "considerations": ["Climate data unavailable"],
            }

        forecast = nws_get_json(forecast_url)
        periods = (forecast.get("properties", {}) or {}).get("periods", []) or []

        # Extract temps and descriptors
        temps_f: List[float] = []
        descriptors: List[str] = []
        for p in periods[:14]:  # ~7 days (day/night pairs)
            t = p.get("temperature")
            if isinstance(t, (int, float)):
                temps_f.append(float(t))
            desc = p.get("shortForecast") or ""
            if desc:
                descriptors.append(desc)

        temp_min = min(temps_f) if temps_f else None
        temp_max = max(temps_f) if temps_f else None

        # Derive design considerations
        desc_joined = " ".join(descriptors).lower()
        moisture_risk = any(k in desc_joined for k in ["rain", "showers", "thunderstorms", "drizzle", "snow", "sleet"])
        heat_risk = temp_max is not None and temp_max >= 90
        cold_risk = temp_min is not None and temp_min <= 32

        considerations: List[str] = []
        if moisture_risk:
            considerations.append("Moisture-prone climate: prioritize ventilation and moisture-resistant finishes in wet areas")
        if heat_risk:
            considerations.append("Hot climate: consider cooling efficiency, shading, and durable heat-friendly flooring")
        if cold_risk:
            considerations.append("Cold climate: emphasize insulation, air sealing, and warm underfoot materials")

        return {
            "temp_range_f": {"min": temp_min, "max": temp_max},
            "considerations": considerations if considerations else ["Moderate climate"],
        }

    except Exception as e:
        return {
            "temp_range_f": None,
            "considerations": [f"Climate data fetch failed: {str(e)}"],
        }


# ----------------------------
# 5) Tavily search
# ----------------------------

@dataclass
class TavilyResult:
    """Tavily search result."""
    title: str
    url: str
    content: str
    score: float
    raw_content: Optional[str] = None


def tavily_search(
    api_key: str,
    query: str,
    search_depth: str = "advanced",
    max_results: int = 2,  # Reduced from 5 to 2 for faster fetching
    include_raw_content: bool = False,
) -> List[TavilyResult]:
    """Execute Tavily search with strict timeout."""
    payload: Dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
    }
    if include_raw_content:
        payload["include_raw_content"] = True

    r = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=TAVILY_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    results = data.get("results", []) or []
    out: List[TavilyResult] = []
    for item in results:
        out.append(
            TavilyResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                content=item.get("content") or "",
                score=float(item.get("score") or 0.0),
                raw_content=item.get("raw_content"),
            )
        )
    return out


def dedupe_results(results: List[TavilyResult]) -> List[TavilyResult]:
    """Deduplicate results by URL."""
    seen = set()
    out = []
    for r in results:
        u = (r.url or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(r)
    return out


def clean_raw_content(raw_content: str) -> str:
    """
    Clean raw content by removing noise: phone numbers, URLs, navigation, footer, etc.
    Reduces token count significantly while keeping useful information.
    """
    if not raw_content:
        return ""

    text = raw_content

    # Remove phone numbers
    text = re.sub(r'\(\d{3}\)\s*\d{3}-\d{4}', '', text)
    text = re.sub(r'\d{3}-\d{3}-\d{4}', '', text)
    text = re.sub(r'tel:\+?\d+', '', text)

    # Remove URLs
    text = re.sub(r'https?://[^\s\)\]]+', '', text)
    text = re.sub(r'www\.[^\s\)\]]+', '', text)

    # Remove empty markdown links
    text = re.sub(r'\[\]\([^\)]*\)', '', text)
    text = re.sub(r'\[[^\]]*\]\(\s*\)', '', text)

    # Remove star ratings
    text = re.sub(r'[★☆]+', '', text)
    text = re.sub(r'\d+\s*out\s*of\s*\d+\s*stars', '', text, flags=re.IGNORECASE)

    # Remove form/validation messages
    form_patterns = [
        r'Sending your message\. Please wait\.\.\.',
        r'There was a problem sending your message.*',
        r'Please complete all the fields.*',
        r'You may only send \d+ messages.*',
        r'The (phone number|email address) is invalid.*',
        r'Thanks for contacting us.*',
        r'Which type of leads are you looking for\?',
        r'Enter your zip.*',
        r'Get matched with.*',
        r'Request a quote',
        r'Reviewed in (January|February|March|April|May|June|July|August|September|October|November|December) \d{4}',
        r'Last update on.*',
    ]
    for pattern in form_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Remove common navigation/CTA patterns
    patterns_to_remove = [
        r'Call Now', r'Get A Quote', r'GET A QUOTE', r'Get a Price', r'CONTACT US',
        r'Sign In', r'Join as a Pro', r'Review Us', r'REVIEW US', r'Learn More',
        r'Read More', r'View all testimonials', r'Menu\s+', r'skip to main content',
        r'© \d{4}', r'All rights reserved', r'Terms of Use', r'Privacy Policy',
        r'Cookie Policy', r'Copyright & Trademark', r'Equal Housing Opportunity',
        r'NMLS \d+', r'Paid Ad', r'Disclosures', r'Software', r'Mobile App',
        r'Expert Support', r'Schedule a Demo', r'Talk to Sales:', r'Credit Cards Accepted',
        r'Business Hours', r'TRUSTED BY.*HOMEOWNERS', r'Verified Reviews for.*',
        r'Average homeowner rating',
    ]
    for pattern in patterns_to_remove:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Remove social media references
    text = re.sub(r'(Facebook|Twitter|X|Instagram|YouTube|LinkedIn|Pinterest|RSS)', '', text, flags=re.IGNORECASE)

    # Remove service area lists
    text = re.sub(r'(Kitchen Remodeling|Bathroom Remodeling|Other services|Services) (also available in|offered in|in):.*?(?=\n\n|\Z)', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Remove zip code lists
    text = re.sub(r'(in|for) .* zip codes?:.*?(?=\n\n|\Z)', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Remove dates in format YYYY-MM-DD
    text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)

    # Remove rating numbers like "5.0", "4.8"
    text = re.sub(r'\b[1-5]\.\d+\b', '', text)

    # Remove excessive whitespace
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = re.sub(r' +', ' ', text)

    # Remove lines that are navigation, headers, or noise
    lines = text.split('\n')
    cleaned_lines = []
    skip_patterns = [
        r'^#+\s*$',  # Empty headers
        r'^\*+$',    # Just asterisks
        r'^-+$',     # Just dashes
        r'^\d+\.\s*$',  # Just numbers
        r'^\[\s*\]',  # Empty brackets
        r'^Find Pros', r'^Interior Design', r'^Kitchen Remodeling$',
        r'^Bathroom Remodeling$', r'^Home Improvement$', r'^Need a pro for',
        r'^Average rating:', r'^\d+ (Reviews?|Verified Hires?|Hires on Houzz)',
        r'^Best of Houzz',
    ]

    for line in lines:
        line = line.strip()
        skip = False
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                skip = True
                break
        if skip:
            continue
        if len(line) > 20:
            cleaned_lines.append(line)
        elif len(line) > 5 and any(c.isalnum() for c in line):
            if not re.match(r'^[\d\s\*\-\[\]\(\)]+$', line):
                cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)
    text = text.strip()

    return text


async def extract_contractor_knowledge_with_llm(
    cleaned_content: str,
    location: Dict[str, Any],
    budget_context: Dict[str, Any],
    climate_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Use LLM to extract contractor knowledge from cleaned Tavily content.
    OPTIMIZED: Concise prompt for faster extraction.
    """
    from src.core.llm.provider import LLMProvider

    city = location.get("city", "Unknown")
    state_abbr = location.get("state_abbr", "XX")
    finish_tier = budget_context.get("finish_tier", "mid")

    # Truncate content only if extremely large (max ~25000 words ≈ 35k tokens)
    # Modern LLMs (GPT-4o, Claude) can handle much larger contexts
    words = cleaned_content.split()
    if len(words) > 25000:
        cleaned_content = " ".join(words[:25000])
        print(f"[zip_structured_data] ⚠️  Truncated content from {len(words)} to 25000 words")

    # OPTIMIZED: Much shorter prompt
    prompt = f"""Extract renovation contractor knowledge for {city}, {state_abbr} (budget tier: {finish_tier}) from this content.

CONTENT:
{cleaned_content}

Return JSON with these fields (be specific, extract ALL mentioned):

{{
  "popular_styles": [
    {{"name": "Style Name", "description": "Brief description", "key_elements": ["element1", "element2"], "color_palette": ["color1", "color2"]}}
  ],
  "popular_materials": [
    {{"name": "Material Name", "category": "countertops/flooring/cabinets/etc", "description": "Brief description", "budget_tier": "budget/mid/luxury"}}
  ],
  "customer_project_examples": ["Project description with materials and budget if mentioned"],
  "code_requirements": ["Local code/permit requirements"],
  "timeline_expectations": [
    {{"project_type": "Kitchen remodel", "duration": "4-6 weeks", "notes": "Optional notes"}}
  ],
  "budget_expectations": [
    {{"item": "Quartz countertops", "insight": "$60-80/sq ft installed"}}
  ]
}}

REQUIREMENTS:
- Extract 5+ styles, 10+ materials, 5+ budget items
- Be SPECIFIC: "white shaker cabinets" not "modern cabinets"
- Include regional details specific to {city}
- Return ONLY valid JSON, no markdown"""

    try:
        provider = LLMProvider.for_llm()

        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Extract contractor knowledge as JSON. Be comprehensive but concise."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Slightly higher for richer descriptions
            max_tokens=5000,  # Increased for comprehensive extraction
            operation_type="contractor_knowledge_extraction"
        )

        # Clean up response
        response = response.strip()
        if response.startswith('```'):
            lines = response.split('\n')
            response = '\n'.join(line for line in lines if not line.startswith('```'))

        knowledge = json.loads(response.strip())

        print(f"[zip_structured_data] ✅ Extracted: {len(knowledge.get('popular_styles', []))} styles, {len(knowledge.get('popular_materials', []))} materials")

        return knowledge

    except Exception as e:
        print(f"[zip_structured_data] LLM extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "popular_styles": [],
            "popular_materials": [],
            "customer_project_examples": [],
            "code_requirements": [],
            "timeline_expectations": [],
            "budget_expectations": []
        }


# ----------------------------
# Async wrappers for parallel execution
# ----------------------------

async def _fetch_census_async(zip_code: str, year: int) -> Tuple[Dict[str, Any], float]:
    """Async wrapper for Census data fetch."""
    start = time_module.time()
    try:
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        acs_values = await loop.run_in_executor(None, lambda: fetch_acs_data(zip_code, year))
        elapsed = time_module.time() - start
        return acs_values, elapsed
    except Exception as e:
        elapsed = time_module.time() - start
        print(f"[zip_structured_data] ❌ Census data failed after {elapsed:.2f}s: {e}")
        return {}, elapsed


async def _fetch_climate_async(lat: float, lon: float) -> Tuple[Optional[Dict[str, Any]], float]:
    """Async wrapper for Climate data fetch."""
    start = time_module.time()
    try:
        loop = asyncio.get_event_loop()
        climate = await loop.run_in_executor(None, lambda: get_climate_essentials(lat, lon))
        elapsed = time_module.time() - start
        return climate, elapsed
    except Exception as e:
        elapsed = time_module.time() - start
        print(f"[zip_structured_data] ❌ Climate data failed after {elapsed:.2f}s: {e}")
        return None, elapsed


async def _fetch_tavily_async(
    api_key: str,
    queries: List[str],
    project_id: Optional[str] = None
) -> Tuple[List[TavilyResult], float]:
    """Async wrapper for Tavily searches - runs queries in parallel."""
    start = time_module.time()
    loop = asyncio.get_event_loop()
    all_results: List[TavilyResult] = []
    total_queries = len(queries)

    async def search_query(q: str, idx: int) -> List[TavilyResult]:
        try:
            # Emit search query event
            if project_id:
                await emit_search_query(project_id, q, idx, total_queries)

            results = await loop.run_in_executor(
                None,
                lambda: tavily_search(
                    api_key=api_key,
                    query=q,
                    search_depth="advanced",
                    max_results=2,  # Reduced to 2 per query
                    include_raw_content=True,
                )
            )
            print(f"[zip_structured_data]   Query '{q[:40]}...' → {len(results)} results")

            # Emit search result events
            if project_id:
                for result in results:
                    await emit_search_result(
                        project_id,
                        title=result.title,
                        url=result.url,
                        snippet=result.content[:150] if result.content else None
                    )

            return results
        except Exception as e:
            print(f"[zip_structured_data] ❌ Tavily query failed for '{q}': {e}")
            return []

    # Run all queries in parallel
    query_results = await asyncio.gather(*[search_query(q, idx) for idx, q in enumerate(queries)])
    for results in query_results:
        all_results.extend(results)

    elapsed = time_module.time() - start
    return all_results, elapsed


# ----------------------------
# Location-only prefetch (fast, no Tavily)
# ----------------------------

async def get_location_data_only(
    zip_code: str,
    year: int = 2023,
) -> Dict[str, Any]:
    """
    Fast location data prefetch without Tavily search.

    Called when user enters zip code. Returns:
    - Location info (city, state, lat/lon)
    - Census data (demographics, housing age)
    - Climate data (temperature range, considerations)

    Does NOT call Tavily - that happens after image analysis with smart queries.

    Returns:
        Dict with location, budget_indicators, renovation_context, climate
    """
    overall_start = time_module.time()
    zip_code = validate_zip(zip_code)

    print(f"[zip_structured_data] 🚀 Prefetching location data for {zip_code} (no Tavily)")

    # 1. Place lookup
    place_start = time_module.time()
    place = get_place_from_zip(zip_code)
    place_time = time_module.time() - place_start
    print(f"[zip_structured_data] Place: {place['city']}, {place['state_abbr']} | {place_time:.2f}s")

    # 2. PARALLEL FETCH: Census + Climate only
    tasks = []

    # Census task
    census_task = _fetch_census_async(zip_code, year)
    tasks.append(census_task)

    # Climate task (only if lat/lon available)
    has_coords = place.get("latitude") is not None and place.get("longitude") is not None
    if has_coords:
        climate_task = _fetch_climate_async(float(place["latitude"]), float(place["longitude"]))
        tasks.append(climate_task)

    # Run in parallel
    print(f"[zip_structured_data] ⚡ Running {len(tasks)} API calls in PARALLEL (Census + Climate)...")
    parallel_start = time_module.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    parallel_time = time_module.time() - parallel_start
    print(f"[zip_structured_data] ⚡ Parallel fetch completed in {parallel_time:.2f}s")

    # Extract results
    acs_values = {}
    census_time = 0
    if not isinstance(results[0], Exception):
        acs_values, census_time = results[0]
        print(f"[zip_structured_data] ⏱️  Census data: {len(acs_values)} fields | {census_time:.2f}s")

    climate = None
    climate_time = 0
    if has_coords and len(results) > 1:
        if not isinstance(results[1], Exception):
            climate, climate_time = results[1]
            print(f"[zip_structured_data] ⏱️  Climate data: {climate.get('temp_range_f') if climate else 'None'} | {climate_time:.2f}s")

    # Derive design insights
    try:
        design_insights = derive_design_insights(acs_values)
        print(f"[zip_structured_data] Budget tier: {design_insights['budget_indicators']['finish_tier']}")
    except Exception as e:
        print(f"[zip_structured_data] ⚠️  Design insights failed: {e}")
        design_insights = {
            "budget_indicators": {"finish_tier": None, "median_household_income": None, "median_home_value": None, "median_gross_rent": None},
            "renovation_context": {"intensity": None, "owner_occupancy_pct": None, "housing_age_pre_1980_pct": None, "housing_age_pre_1960_pct": None, "likely_project_types": [], "systems_upgrade_priority": None}
        }

    result = {
        "location": {
            "zip": place["zip"],
            "city": place["city"],
            "state": place["state"],
            "state_abbr": place["state_abbr"],
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
        },
        "budget_indicators": {
            "finish_tier": design_insights["budget_indicators"]["finish_tier"],
            "median_household_income": design_insights["budget_indicators"]["median_household_income"],
            "median_home_value": design_insights["budget_indicators"]["median_home_value"],
        },
        "renovation_context": {
            "owner_occupancy_pct": design_insights["renovation_context"]["owner_occupancy_pct"],
            "housing_age_pre_1980_pct": design_insights["renovation_context"]["housing_age_pre_1980_pct"],
            "housing_age_pre_1960_pct": design_insights["renovation_context"]["housing_age_pre_1960_pct"],
        },
        "climate": {
            "temp_range_f": climate.get("temp_range_f") if climate else None,
            "considerations": climate.get("considerations", []) if climate else [],
        },
        "_tavily_pending": True,  # Flag indicating Tavily search still needed
    }

    total_time = time_module.time() - overall_start
    print(f"[zip_structured_data] ✅ Location prefetch completed in {total_time:.2f}s")

    return result


# ----------------------------
# Main function
# ----------------------------

async def get_zip_structured_data(
    zip_code: str,
    tavily_api_key: Optional[str] = None,
    year: int = 2023,
    search_insights: Optional["SearchInsights"] = None,
    project_type: Optional[str] = None,
    location_data: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main function to fetch all structured data for a zip code.

    PERFORMANCE OPTIMIZED:
    - Census, Climate, Tavily run in PARALLEL (not sequential!)
    - Census data cached for 1 hour
    - Strict timeouts on all API calls
    - Reduced Tavily results (2 per query)

    NEW: Smart queries from image insights
    - If search_insights is provided, builds contextual queries based on image analysis
    - If location_data is provided, skips Census/Climate fetch (already cached)

    Args:
        zip_code: US zip code
        tavily_api_key: Tavily API key (required for web search)
        year: Census year
        search_insights: Optional SearchInsights from image analysis for smart queries
        project_type: Optional project type for query building
        location_data: Optional pre-fetched location data (from get_location_data_only)

    Returns streamlined output with contractor knowledge extracted by LLM:
    - Location info
    - Budget indicators (finish tier, income, home value)
    - Renovation context (owner occupancy, housing age)
    - Climate (temperature range)
    - Contractor knowledge (styles, materials, projects, budgets, timelines) - LLM extracted!
    """
    overall_start = time_module.time()

    zip_code = validate_zip(zip_code)

    # Determine if we're using smart queries from image insights
    using_smart_queries = search_insights is not None and search_insights.has_useful_context()
    mode_label = "SMART QUERY mode" if using_smart_queries else "PARALLEL mode"
    print(f"[zip_structured_data] 🚀 Fetching structured data for {zip_code} ({mode_label})")

    # 1. Place lookup (use cached if available)
    if location_data and location_data.get("location"):
        place = location_data["location"]
        print(f"[zip_structured_data] Using cached location: {place.get('city')}, {place.get('state_abbr')}")
        place_time = 0
    else:
        place_start = time_module.time()
        place = get_place_from_zip(zip_code)
        place_time = time_module.time() - place_start
        print(f"[zip_structured_data] Place: {place['city']}, {place['state_abbr']} | {place_time:.2f}s")

    # 2. Build queries - smart or generic
    loc = f"{place.get('city', '')} {place.get('state_abbr', '')}".strip()
    ptype = project_type or "home renovation"

    if using_smart_queries:
        # Import and use smart query builder
        from src.core.services.smart_search_service import build_smart_queries
        queries = build_smart_queries(
            insights=search_insights,
            project_type=ptype,
            city=place.get("city", ""),
            state_abbr=place.get("state_abbr", "")
        )
        print(f"[zip_structured_data] 🎯 Smart queries built from image insights:")
        for i, q in enumerate(queries):
            print(f"[zip_structured_data]   {i+1}. {q}")
    else:
        # Generic fallback queries
        queries = [
            f'{loc} {ptype} remodel contractor portfolio',
            f'{loc} {ptype} renovation before after',
            f'{loc} home renovation design trends materials',
        ]

    # Build parallel tasks based on what we need
    tasks = []
    task_names = []  # Track what each task is for result extraction

    # Check if we have cached location data (Census/Climate already fetched)
    has_cached_location = location_data is not None and location_data.get("budget_indicators") is not None

    if not has_cached_location:
        # Need to fetch Census data
        census_task = _fetch_census_async(zip_code, year)
        tasks.append(census_task)
        task_names.append("census")

        # Need to fetch Climate data (only if lat/lon available)
        has_coords = place.get("latitude") is not None and place.get("longitude") is not None
        if has_coords:
            climate_task = _fetch_climate_async(float(place["latitude"]), float(place["longitude"]))
            tasks.append(climate_task)
            task_names.append("climate")
    else:
        has_coords = False  # Skip climate extraction from results

    # Tavily task (only if API key provided)
    if tavily_api_key:
        tavily_task = _fetch_tavily_async(tavily_api_key, queries, project_id)
        tasks.append(tavily_task)
        task_names.append("tavily")

    # Run all in parallel (or just Tavily if location cached)
    if tasks:
        print(f"[zip_structured_data] ⚡ Running {len(tasks)} API calls in PARALLEL: {task_names}...")
        parallel_start = time_module.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        parallel_time = time_module.time() - parallel_start
        print(f"[zip_structured_data] ⚡ Parallel fetch completed in {parallel_time:.2f}s")
    else:
        results = []
        parallel_time = 0

    # Extract results based on task_names
    result_idx = 0

    # Census result (or use cached)
    acs_values = {}
    census_time = 0
    if "census" in task_names:
        if not isinstance(results[result_idx], Exception):
            acs_values, census_time = results[result_idx]
            print(f"[zip_structured_data] ⏱️  Census data: {len(acs_values)} fields | {census_time:.2f}s")
        else:
            print(f"[zip_structured_data] ❌ Census failed: {results[result_idx]}")
        result_idx += 1

    # Climate result (or use cached)
    climate = None
    climate_time = 0
    if "climate" in task_names:
        if not isinstance(results[result_idx], Exception):
            climate, climate_time = results[result_idx]
            print(f"[zip_structured_data] ⏱️  Climate data: {climate.get('temp_range_f') if climate else 'None'} | {climate_time:.2f}s")
        else:
            print(f"[zip_structured_data] ❌ Climate failed: {results[result_idx]}")
        result_idx += 1
    elif has_cached_location and location_data.get("climate"):
        climate = location_data["climate"]
        print(f"[zip_structured_data] Using cached climate data")

    # Tavily result
    all_tavily_results: List[TavilyResult] = []
    tavily_time = 0
    if "tavily" in task_names:
        if not isinstance(results[result_idx], Exception):
            all_tavily_results, tavily_time = results[result_idx]
            print(f"[zip_structured_data] ⏱️  Tavily searches: {len(all_tavily_results)} results | {tavily_time:.2f}s")
        else:
            print(f"[zip_structured_data] ❌ Tavily failed: {results[result_idx]}")

    # 3. Design insights from Census data (or use cached)
    if has_cached_location:
        # Use cached design insights
        design_insights = {
            "budget_indicators": location_data.get("budget_indicators", {}),
            "renovation_context": location_data.get("renovation_context", {}),
        }
        print(f"[zip_structured_data] Using cached design insights: tier={design_insights['budget_indicators'].get('finish_tier')}")
    else:
        try:
            design_insights = derive_design_insights(acs_values)
            print(f"[zip_structured_data] Budget tier: {design_insights['budget_indicators']['finish_tier']}")
        except Exception as e:
            print(f"[zip_structured_data] ❌ Design insights failed: {e}")
            design_insights = {
                "budget_indicators": {
                    "finish_tier": None,
                    "median_household_income": None,
                    "median_home_value": None,
                    "median_gross_rent": None,
                },
                "renovation_context": {
                    "intensity": None,
                    "owner_occupancy_pct": None,
                    "housing_age_pre_1980_pct": None,
                    "housing_age_pre_1960_pct": None,
                    "likely_project_types": [],
                    "systems_upgrade_priority": None,
                }
            }

    # 4. Contractor knowledge via LLM extraction (from Tavily results)
    contractor_knowledge = {
        "popular_styles": [],
        "popular_materials": [],
        "customer_project_examples": [],
        "code_requirements": [],
        "timeline_expectations": [],
        "budget_expectations": []
    }

    llm_time = 0
    if all_tavily_results:
        all_tavily_results = dedupe_results(all_tavily_results)
        print(f"[zip_structured_data] Found {len(all_tavily_results)} unique sources")

        # Clean and combine content
        clean_start = time_module.time()
        combined_content = []
        for result in all_tavily_results:
            if result.raw_content:
                cleaned = clean_raw_content(result.raw_content)
                if cleaned:
                    combined_content.append(f"=== Source: {result.title} ===\n{cleaned}\n")

        full_content = "\n\n".join(combined_content)
        clean_time = time_module.time() - clean_start
        word_count = len(full_content.split())
        print(f"[zip_structured_data] ⏱️  Content cleaning: {clean_time:.2f}s | {word_count} words")
        with open("debug_cleaned_content.txt", "w", encoding="utf-8") as f:
            f.write(full_content)
        # Extract contractor knowledge using LLM
        llm_start = time_module.time()
        contractor_knowledge = await extract_contractor_knowledge_with_llm(
            cleaned_content=full_content,
            location=place,
            budget_context=design_insights["budget_indicators"],
            climate_context=climate if climate else {}
        )
        llm_time = time_module.time() - llm_start
        print(f"[zip_structured_data] ⏱️  LLM extraction: {llm_time:.2f}s")
    elif tavily_api_key:
        print(f"[zip_structured_data] ⚠️  No Tavily results found")

    # Extract sources from Tavily results for citation
    sources = []
    for tr in all_tavily_results[:10]:  # Limit to 10 sources
        if tr.url and tr.title:
            sources.append({
                "title": tr.title,
                "url": tr.url,
                "snippet": (tr.raw_content[:200] + "...") if tr.raw_content and len(tr.raw_content) > 200 else (tr.raw_content or "")
            })

    # Construct final output - streamlined for use in suggestions, images, cost estimation
    result = {
        "location": {
            "zip": place["zip"],
            "city": place["city"],
            "state": place["state"],
            "state_abbr": place["state_abbr"],
        },
        "budget_indicators": {
            "finish_tier": design_insights["budget_indicators"]["finish_tier"],
            "median_household_income": design_insights["budget_indicators"]["median_household_income"],
            "median_home_value": design_insights["budget_indicators"]["median_home_value"],
        },
        "renovation_context": {
            "owner_occupancy_pct": design_insights["renovation_context"]["owner_occupancy_pct"],
            "housing_age_pre_1980_pct": design_insights["renovation_context"]["housing_age_pre_1980_pct"],
            "housing_age_pre_1960_pct": design_insights["renovation_context"]["housing_age_pre_1960_pct"],
        },
        "climate": {
            "temp_range_f": climate.get("temp_range_f") if climate else None,
        },
        "contractor_knowledge": contractor_knowledge,
        "_sources": sources  # Sources for citation in frontend
    }

    total_time = time_module.time() - overall_start
    styles_count = len(contractor_knowledge.get('popular_styles', []))
    materials_count = len(contractor_knowledge.get('popular_materials', []))

    print(f"[zip_structured_data] ✅ Successfully compiled structured data with {styles_count} styles, {materials_count} materials")
    print(f"[zip_structured_data] ⏱️  TOTAL TIME: {total_time:.2f}s (Census: {census_time:.2f}s, Climate: {climate_time:.2f}s, Tavily: {tavily_time:.2f}s, LLM: {llm_time:.2f}s)")

    # Emit completion events for SSE streaming
    if project_id:
        await emit_search_complete(
            project_id=project_id,
            total_sources=len(sources),
            styles_found=styles_count,
            materials_found=materials_count
        )
        await emit_context_ready(project_id)

    return result
