#!/usr/bin/env python3
"""
zip_local_reno_profile.py

End-to-end pipeline (no argparse). One-call main().

What it returns (until now):
1) ZIP -> place info (city/state/lat/lon) via Zippopotam.us (free)
2) ZIP (as ZCTA) -> US Census ACS 5-year demographics + housing age (free)
   - with automatic DNS fallback (nslookup + curl --resolve) for api.census.gov
3) Derived "design insights" from ACS (budget tier, renovation intensity, systems risk, etc.)
4) Climate essentials via NWS API (free, no token)
5) Tavily discovery (paid) -> structured outputs:
   - style clusters (probabilistic, evidence-based)
   - materials/finishes signals (basic extraction)
   - project type signals
   - permits/constraints signals (tries to prefer official gov pages)
   - citations and confidence scores

IMPORTANT:
- "Style preferences" are inferred from public web evidence (portfolios/articles) and are not individual preferences.
- Constraints are best-effort summaries; always rely on the cited official sources for final guidance.

Usage:
  from zip_local_reno_profile import main
  data = main("30252", year=2023, tavily_api_key="tvly-...")
  print(json.dumps(data, indent=2))

Dependencies:
  pip install requests
"""

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
import os
from dotenv import load_dotenv
load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ----------------------------
# Constants / endpoints
# ----------------------------

ZIPPOTAM_BASE = "https://api.zippopotam.us/us/{zip}"
CENSUS_BASE = "https://api.census.gov/data/{year}/acs/acs5"

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# NWS documentation: https://www.weather.gov/documentation/services-web-api
NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"

# For NWS requests, they ask for a User-Agent; include a contact (your email) if you want.
DEFAULT_USER_AGENT = "zip-local-reno-profile/1.0 (contact: dev@example.com)"


# ----------------------------
# ACS variables
# ----------------------------

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


# ----------------------------
# Utilities
# ----------------------------

def validate_zip(zip_code: str) -> str:
    z = (zip_code or "").strip()
    if not re.fullmatch(r"\d{5}", z):
        raise ValueError("ZIP code must be 5 digits (e.g., '90210').")
    return z


def safe_div(n: float, d: float, default: float = 0.0) -> float:
    return default if d == 0 else (n / d)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip().lower()


def is_probably_gov_url(url: str) -> bool:
    u = normalize_text(url)
    # This is heuristic. Many cities are .gov, some counties/cities are .org (less ideal).
    return ".gov/" in u or u.endswith(".gov") or ".gov?" in u


def domain_of(url: str) -> str:
    m = re.match(r"^https?://([^/]+)/?", url.strip(), re.I)
    return m.group(1).lower() if m else ""


# ----------------------------
# 1) Zippopotam.us
# ----------------------------

def get_place_from_zip(zip_code: str) -> Dict[str, Any]:
    zip_code = validate_zip(zip_code)
    url = ZIPPOTAM_BASE.format(zip=zip_code)
    resp = requests.get(url, timeout=20)
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
# 2) Census ACS (with DNS fallback)
# ----------------------------

def build_census_acs_url(year: int, zcta: str, var_codes: List[str]) -> str:
    get_part = ",".join(var_codes)
    geo = f"zip code tabulation area:{zcta}"
    return f"{CENSUS_BASE.format(year=year)}?get={quote(get_part)}&for={quote(geo)}"


def try_requests_json(url: str) -> Optional[Any]:
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def nslookup_ip(hostname: str) -> Optional[str]:
    try:
        out = subprocess.check_output(["nslookup", hostname], text=True, stderr=subprocess.STDOUT)
    except Exception:
        return None
    ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", out)
    return ips[-1] if ips else None


def curl_resolve_json(url: str, hostname: str, ip: str) -> Any:
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--fail",
        "--location",
        "--resolve",
        f"{hostname}:443:{ip}",
        url,
    ]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def fetch_acs_structured(zip_code: str, year: int = 2023) -> Dict[str, Any]:
    zcta = validate_zip(zip_code)

    var_map: Dict[str, str] = {}
    var_map.update(ACS_VARS_CORE)
    var_map.update(ACS_VARS_YEAR_BUILT)

    var_codes = list(var_map.keys())
    url = build_census_acs_url(year, zcta=zcta, var_codes=var_codes)

    data = try_requests_json(url)
    used_fallback = False
    ip_used = None

    if data is None:
        hostname = "api.census.gov"
        ip = nslookup_ip(hostname)
        if not ip:
            raise RuntimeError("Could not resolve api.census.gov via nslookup.")
        ip_used = ip
        data = curl_resolve_json(url, hostname=hostname, ip=ip)
        used_fallback = True

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

    housing_age = {name: values.get(name) for name in ACS_VARS_YEAR_BUILT.values()}

    return {
        "source": "US Census ACS 5-year",
        "year": year,
        "zcta": zcta,
        "used_curl_resolve_fallback": used_fallback,
        "resolved_ip": ip_used,
        "values": values,
        "housing_year_built_distribution": housing_age,
    }


# ----------------------------
# 3) Derived design insights from ACS
# ----------------------------

def derive_design_insights(acs_values: Dict[str, Any]) -> Dict[str, Any]:
    owners = int(acs_values.get("owner_occupied_units") or 0)
    renters = int(acs_values.get("renter_occupied_units") or 0)

    total_units = acs_values.get("housing_units_total")
    if total_units is None or int(total_units) <= 0:
        total_units = owners + renters
    total_units = max(1, int(total_units))

    owner_pct = safe_div(owners, total_units)
    renter_pct = safe_div(renters, total_units)

    def s(*keys: str) -> int:
        return sum(int(acs_values.get(k) or 0) for k in keys)

    pre_1980_units = s(
        "built_1970_1979",
        "built_1960_1969",
        "built_1950_1959",
        "built_1940_1949",
        "built_1939_or_earlier",
    )
    pre_1960_units = s(
        "built_1950_1959",
        "built_1940_1949",
        "built_1939_or_earlier",
    )
    pre_1940_units = int(acs_values.get("built_1939_or_earlier") or 0)

    pre_1980_pct = safe_div(pre_1980_units, total_units)
    pre_1960_pct = safe_div(pre_1960_units, total_units)
    pre_1940_pct = safe_div(pre_1940_units, total_units)

    income = float(acs_values.get("median_household_income") or 0)
    home_value = float(acs_values.get("median_home_value") or 0)
    rent = float(acs_values.get("median_gross_rent") or 0)

    income_norm = clamp01(income / 200_000.0)
    value_norm = clamp01(home_value / 2_000_000.0)
    rent_norm = clamp01(rent / 3_000.0)

    renovation_propensity = clamp01(0.50 * owner_pct + 0.50 * pre_1980_pct)
    systems_upgrade_risk = clamp01(pre_1960_pct)
    luxury_finish_likelihood = clamp01(0.45 * income_norm + 0.45 * value_norm + 0.10 * rent_norm)
    historic_character_sensitivity = clamp01(1.15 * pre_1960_pct + 0.35 * pre_1940_pct)

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

    likely_project_types: List[str] = []
    if owner_pct > 0.70:
        likely_project_types += ["kitchen and bathroom renovations", "whole-home refresh / modernization"]
    if pre_1980_pct > 0.60:
        likely_project_types += ["layout modernization", "energy-efficiency upgrades (windows/insulation)"]
    if pre_1960_pct > 0.30:
        likely_project_types += ["electrical and plumbing upgrades", "envelope improvements (roof/moisture/insulation)"]
    if historic_character_sensitivity > 0.55:
        likely_project_types += ["character-preserving remodels / restoration-friendly details"]

    # de-dupe
    seen = set()
    likely_project_types = [x for x in likely_project_types if not (x in seen or seen.add(x))]

    summary = (
        f"Owner-occupancy is ~{owner_pct*100:.1f}% and housing stock skews older "
        f"(pre-1980 ~{pre_1980_pct*100:.1f}%, pre-1960 ~{pre_1960_pct*100:.1f}%). "
        f"Budget signals suggest a {finish_tier} finish tier. Overall renovation intensity is {renovation_intensity}."
    )

    return {
        "ownership": {
            "owner_pct": round(owner_pct, 3),
            "renter_pct": round(renter_pct, 3),
            "owner_units": owners,
            "renter_units": renters,
            "total_units": total_units,
        },
        "housing_age": {
            "pre_1980_pct": round(pre_1980_pct, 3),
            "pre_1960_pct": round(pre_1960_pct, 3),
            "pre_1940_pct": round(pre_1940_pct, 3),
        },
        "scores": {
            "renovation_propensity": round(renovation_propensity, 3),
            "systems_upgrade_risk": round(systems_upgrade_risk, 3),
            "luxury_finish_likelihood": round(luxury_finish_likelihood, 3),
            "historic_character_sensitivity": round(historic_character_sensitivity, 3),
        },
        "interpretation": {
            "renovation_intensity": renovation_intensity,
            "likely_finish_tier": finish_tier,
            "likely_project_types": likely_project_types,
        },
        "recommended_next_questions": [
            "Is the property a single-family home, condo, or apartment?",
            "Do you want to preserve original architectural character or modernize fully?",
            "Is your goal a cosmetic refresh, partial remodel (kitchen/bath), or full remodel?",
            "Do you have an approximate budget range and timeline?",
            "Any constraints: HOA rules, historical designation, or permitting concerns?",
            "Lifestyle needs: kids/pets, accessibility, work-from-home, entertaining?",
        ],
        "summary": summary,
        "notes": [
            "These are area-level priors derived from ACS (ZCTA). They do not represent an individual's taste.",
        ],
    }


# ----------------------------
# 4) Climate essentials via NWS (free, no token)
# ----------------------------

def nws_get_json(url: str, user_agent: str = DEFAULT_USER_AGENT) -> Dict[str, Any]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/geo+json, application/json",
    }
    r = requests.get(url, headers=headers, timeout=25)
    r.raise_for_status()
    return r.json()


def get_climate_essentials(lat: float, lon: float, user_agent: str = DEFAULT_USER_AGENT) -> Dict[str, Any]:
    """
    Uses NWS API to fetch forecast metadata and a 7-day forecast summary.

    Returns essentials useful for design defaults:
    - temperature range (next ~7 days)
    - short forecast descriptors (rain/snow/clear/etc.)
    - simple moisture / heat considerations (heuristics)
    """
    points = nws_get_json(NWS_POINTS_URL.format(lat=lat, lon=lon), user_agent=user_agent)
    props = points.get("properties", {}) or {}

    forecast_url = props.get("forecast")
    grid_url = props.get("forecastGridData")  # can include humidity/precip if populated

    if not forecast_url:
        return {
            "source": "NWS",
            "status": "unavailable",
            "notes": ["NWS points endpoint did not return a forecast URL."],
        }

    forecast = nws_get_json(forecast_url, user_agent=user_agent)
    periods = (forecast.get("properties", {}) or {}).get("periods", []) or []

    # Extract next ~7 days worth of temps and descriptors
    temps_f: List[float] = []
    descriptors: List[str] = []
    for p in periods[:14]:  # day/night pairs
        t = p.get("temperature")
        if isinstance(t, (int, float)):
            temps_f.append(float(t))
        desc = p.get("shortForecast") or ""
        if desc:
            descriptors.append(desc)

    temp_min = min(temps_f) if temps_f else None
    temp_max = max(temps_f) if temps_f else None

    # Heuristic climate notes from forecast text
    desc_joined = " ".join(descriptors).lower()
    moisture_risk = any(k in desc_joined for k in ["rain", "showers", "thunderstorms", "drizzle", "snow", "sleet"])
    heat_risk = temp_max is not None and temp_max >= 90
    cold_risk = temp_min is not None and temp_min <= 32

    considerations: List[str] = []
    if moisture_risk:
        considerations.append("Moisture-prone forecast: prioritize ventilation, moisture-resistant finishes in wet areas, and good entryway/mudroom transitions.")
    if heat_risk:
        considerations.append("Hot forecast: shading, glazing choices, and cooling efficiency may matter more; consider durable heat-friendly flooring.")
    if cold_risk:
        considerations.append("Cold forecast: insulation, air sealing, and warm materials/underfoot comfort become more important.")

    # Optional: pull grid data for extra signals if available (best-effort)
    grid_signals: Dict[str, Any] = {}
    if grid_url:
        try:
            grid = nws_get_json(grid_url, user_agent=user_agent)
            gprops = grid.get("properties", {}) or {}

            # Many fields exist; coverage varies. We'll try a few common ones.
            # Each is typically {"uom": "...", "values": [{"validTime":"...","value":...}, ...]}
            for key in ["relativeHumidity", "probabilityOfPrecipitation", "dewpoint"]:
                if key in gprops and isinstance(gprops[key], dict):
                    vals = (gprops[key].get("values") or [])[:10]
                    extracted = [v.get("value") for v in vals if isinstance(v, dict)]
                    extracted = [x for x in extracted if isinstance(x, (int, float))]
                    if extracted:
                        grid_signals[key] = {
                            "uom": gprops[key].get("uom"),
                            "sample_values": extracted[:5],
                        }
        except Exception:
            pass

    return {
        "source": "NWS",
        "status": "ok",
        "nws_point": {
            "gridId": props.get("gridId"),
            "gridX": props.get("gridX"),
            "gridY": props.get("gridY"),
            "forecastOffice": props.get("cwa"),
        },
        "temperature_next_7ish_days_f": {"min": temp_min, "max": temp_max},
        "forecast_descriptors_sample": descriptors[:8],
        "grid_signals_sample": grid_signals,
        "design_considerations": considerations,
        "notes": [
            "This is a near-term forecast-based summary (not climate normals). For long-term normals, NOAA CDO can be added later.",
        ],
    }


# ----------------------------
# 5) Tavily search + extraction
# ----------------------------

@dataclass
class TavilyResult:
    title: str
    url: str
    content: str
    score: float
    raw_content: Optional[str] = None


def tavily_search(
    api_key: str,
    query: str,
    search_depth: str = "advanced",
    max_results: int = 2,
    include_raw_content: bool = False,
    include_images: bool = False,
    timeout: int = 35,
) -> List[TavilyResult]:
    payload: Dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
    }
    # Tavily supports these flags; not all are mandatory.
    if include_raw_content:
        payload["include_raw_content"] = True
    if include_images:
        payload["include_images"] = True

    r = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=timeout)
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
    seen = set()
    out = []
    for r in results:
        u = (r.url or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(r)
    return out


# ----------------------------
# Extraction vocab
# ----------------------------

STYLE_KEYWORDS: Dict[str, List[str]] = {
    "transitional": ["transitional"],
    "contemporary": ["contemporary", "contemporaries"],
    "modern": ["modern", "minimal", "minimalist", "sleek", "clean lines"],
    "modern_farmhouse": ["modern farmhouse", "farmhouse"],
    "traditional": ["traditional", "classic", "colonial"],
    "mid_century": ["mid-century", "midcentury", "mcm"],
    "coastal": ["coastal", "beachy", "nautical"],
    "industrial": ["industrial", "loft", "exposed brick", "exposed duct"],
    "scandinavian": ["scandinavian", "scandi", "nordic"],
    "bohemian": ["bohemian", "boho"],
}

MATERIAL_KEYWORDS: Dict[str, List[str]] = {
    "quartz": ["quartz"],
    "granite": ["granite"],
    "marble": ["marble", "calacatta", "carrara"],
    "butcher_block": ["butcher block"],
    "subway_tile": ["subway tile"],
    "hardwood": ["hardwood", "oak flooring", "white oak", "walnut"],
    "engineered_wood": ["engineered hardwood", "engineered wood"],
    "lvp": ["lvp", "luxury vinyl", "vinyl plank"],
    "tile_floor": ["porcelain tile", "ceramic tile", "tile flooring"],
    "shiplap": ["shiplap"],
    "brass_hardware": ["brass hardware", "unlacquered brass"],
    "matte_black_hardware": ["matte black", "black hardware"],
    "white_cabinets": ["white cabinets", "white cabinetry"],
    "wood_tone_cabinets": ["wood-tone cabinets", "natural wood", "oak cabinets", "walnut cabinets"],
    "two_tone_cabinets": ["two-tone cabinets", "two tone cabinets"],
}

PROJECT_KEYWORDS: Dict[str, List[str]] = {
    "kitchen_remodel": ["kitchen remodel", "kitchen renovation", "kitchen design"],
    "bath_remodel": ["bath remodel", "bathroom renovation", "bathroom design"],
    "whole_home": ["whole home", "whole-house", "whole house", "full remodel"],
    "addition": ["addition", "home addition"],
    "outdoor_living": ["outdoor living", "patio", "deck", "porch", "screened porch", "pergola"],
    "basement": ["basement finish", "basement renovation"],
    "adu": ["adu", "accessory dwelling unit", "in-law unit", "granny flat"],
    "garage_conversion": ["garage conversion"],
}

CONSTRAINT_KEYWORDS: Dict[str, List[str]] = {
    "permit_required": ["permit required", "requires a permit", "permit is required", "building permit"],
    "electrical_permit": ["electrical permit"],
    "plumbing_permit": ["plumbing permit"],
    "hvac_permit": ["hvac permit", "mechanical permit"],
    "hoa": ["hoa", "homeowners association"],
    "historic_district": ["historic district", "historic preservation", "design guidelines"],
    "adu_rules": ["adu", "accessory dwelling unit", "secondary dwelling", "in-law suite"],
    "setback_zoning": ["setback", "zoning", "variance"],
}


def extract_tags_from_text(text: str, keyword_map: Dict[str, List[str]]) -> List[str]:
    t = normalize_text(text)
    hits: List[str] = []
    for tag, kws in keyword_map.items():
        for kw in kws:
            if kw in t:
                hits.append(tag)
                break
    return hits


def score_source_quality(url: str) -> float:
    """
    Heuristic quality score:
    - gov sites get a boost for constraints
    - established portfolios (no perfect way): treat .com neutrally
    """
    if is_probably_gov_url(url):
        return 1.0
    # slight boost for .edu (rare here)
    if url.lower().endswith(".edu") or ".edu/" in url.lower():
        return 0.8
    return 0.5


def aggregate_evidence(
    results: List[TavilyResult],
    kind: str,
    keyword_map: Dict[str, List[str]],
    max_citations_per_tag: int = 3,
) -> Dict[str, Any]:
    """
    Aggregates tags mentioned across sources.
    Returns:
      {
        "tags": [{"tag": "...", "confidence": 0.0..1.0, "citations":[...]}],
        "raw_sources": [...]
      }
    """
    tag_stats: Dict[str, Dict[str, Any]] = {}
    sources_for_debug: List[Dict[str, Any]] = []

    for r in results:
        text = f"{r.title}\n{r.content}\n{r.raw_content or ''}"
        tags = extract_tags_from_text(text, keyword_map)

        sources_for_debug.append(
            {
                "title": r.title,
                "url": r.url,
                "score": r.score,
                "domain": domain_of(r.url),
            }
        )

        if not tags:
            continue

        q = score_source_quality(r.url)
        # combine Tavily's relevance score with our source quality heuristic
        weight = (0.6 * clamp01(r.score) + 0.4 * q)

        for tag in tags:
            if tag not in tag_stats:
                tag_stats[tag] = {"weight": 0.0, "citations": []}
            tag_stats[tag]["weight"] += weight
            if len(tag_stats[tag]["citations"]) < max_citations_per_tag:
                tag_stats[tag]["citations"].append(
                    {
                        "url": r.url,
                        "title": r.title,
                        "evidence_snippet": (r.content[:240] + "...") if len(r.content) > 240 else r.content,
                        "source_quality": q,
                        "tavily_score": r.score,
                    }
                )

    # Normalize weights to a 0..1-ish confidence by dividing by max weight observed (if any)
    max_w = max((v["weight"] for v in tag_stats.values()), default=0.0)
    tags_out = []
    for tag, meta in sorted(tag_stats.items(), key=lambda kv: kv[1]["weight"], reverse=True):
        conf = 0.0 if max_w == 0 else clamp01(meta["weight"] / max_w)
        tags_out.append({"tag": tag, "confidence": round(conf, 3), "citations": meta["citations"]})

    return {
        "kind": kind,
        "tags": tags_out,
        "raw_sources": sources_for_debug,
        "notes": [
            "Confidence is relative within this run (based on repeated mentions and source quality).",
            "Use citations to verify; do not treat tags as ground truth for individual preferences.",
        ],
    }


def build_tavily_queries(city: str, state_abbr: str, zip_code: str) -> Dict[str, List[str]]:
    """
    Query set tuned for interior design / renovation practice discovery.
    """
    loc = f"{city} {state_abbr}".strip()
    return {
        "style": [
            f'{loc} interior designer portfolio kitchen remodel',
            # f'{loc} interior design portfolio bathroom renovation',
            # f'{loc} residential architect portfolio',
            # f'{loc} home renovation before and after',
            # f'{loc} interior design trends',
        ],
        "constraints": [
            f'{loc} building permit requirements interior remodel electrical plumbing',
            f'{loc} residential remodeling permits guide',
            f'{loc} ADU requirements',
            f'{loc} historic district design guidelines',
            f'ZIP {zip_code} {loc} permit required kitchen remodel',
        ],
    }


def run_tavily_discovery(
    tavily_api_key: str,
    city: str,
    state_abbr: str,
    zip_code: str,
    search_depth: str = "advanced",
    max_results_per_query: int = 6,
) -> Dict[str, Any]:
    queries = build_tavily_queries(city, state_abbr, zip_code)

    all_style: List[TavilyResult] = []
    all_constraints: List[TavilyResult] = []

    # Style: include raw_content to improve extraction (cost/size tradeoff)
    for q in queries["style"]:
        all_style.extend(
            tavily_search(
                api_key=tavily_api_key,
                query=q,
                search_depth=search_depth,
                max_results=max_results_per_query,
                include_raw_content=True,
            )
        )

    # Constraints: raw_content often not needed; we mostly want official pages + snippets
    for q in queries["constraints"]:
        all_constraints.extend(
            tavily_search(
                api_key=tavily_api_key,
                query=q,
                search_depth=search_depth,
                max_results=max_results_per_query,
                include_raw_content=False,
            )
        )

    all_style = dedupe_results(all_style)
    all_constraints = dedupe_results(all_constraints)

    style_profile = {
        "styles": aggregate_evidence(all_style, "styles", STYLE_KEYWORDS),
        "materials_finishes": aggregate_evidence(all_style, "materials_finishes", MATERIAL_KEYWORDS),
        "project_types": aggregate_evidence(all_style, "project_types", PROJECT_KEYWORDS),
    }

    constraints_profile = {
        "constraints_signals": aggregate_evidence(all_constraints, "constraints", CONSTRAINT_KEYWORDS),
        "gov_sources_first": sorted(
            [
                {"title": r.title, "url": r.url, "score": r.score}
                for r in all_constraints
                if is_probably_gov_url(r.url)
            ],
            key=lambda x: x["score"],
            reverse=True,
        )[:8],
        "notes": [
            "Constraints are best-effort. Verify with the cited official sources (ideally .gov).",
            "If gov_sources_first is empty, the location may not publish clear permitting guidance publicly, or search results were noisy.",
        ],
    }

    return {
        "queries_used": queries,
        "style_profile": style_profile,
        "constraints_profile": constraints_profile,
        "meta": {
            "style_sources_count": len(all_style),
            "constraints_sources_count": len(all_constraints),
            "search_depth": search_depth,
            "max_results_per_query": max_results_per_query,
        },
    }


# ----------------------------
# Final main()
# ----------------------------

def main(
    zip_code: str,
    year: int = 2023,
    tavily_api_key: Optional[str] = None,
    tavily_search_depth: str = "advanced",
    tavily_max_results_per_query: int = 6,
    nws_user_agent: str = DEFAULT_USER_AGENT,
) -> Dict[str, Any]:
    """
    One-call pipeline:
      ZIP -> place
          -> ACS (demographics + housing age) + derived design insights
          -> climate essentials (NWS)
          -> tavily discovery -> structured style + constraints evidence
    """
    zip_code = validate_zip(zip_code)

    place = get_place_from_zip(zip_code)
    acs = fetch_acs_structured(zip_code, year=year)
    design_insights = derive_design_insights(acs["values"])

    climate = None
    if place.get("latitude") is not None and place.get("longitude") is not None:
        climate = get_climate_essentials(
            lat=float(place["latitude"]),
            lon=float(place["longitude"]),
            user_agent=nws_user_agent,
        )
    else:
        climate = {
            "source": "NWS",
            "status": "unavailable",
            "notes": ["Missing lat/lon from place lookup; cannot call NWS."],
        }

    tavily_block = None
    if tavily_api_key:
        tavily_block = run_tavily_discovery(
            tavily_api_key=tavily_api_key,
            city=place["city"],
            state_abbr=place["state_abbr"],
            zip_code=zip_code,
            search_depth=tavily_search_depth,
            max_results_per_query=tavily_max_results_per_query,
        )
    else:
        tavily_block = {
            "status": "skipped",
            "notes": ["No tavily_api_key provided. Pass tavily_api_key to enable style/constraints discovery."],
        }

    return {
        "place": place,
        "acs_structured": acs,
        "design_insights": design_insights,
        "climate_essentials": climate,
        "web_discovery": tavily_block,
        "pipeline_notes": [
            "Styles/materials/project types are extracted from web evidence (portfolios/articles) and summarized with confidence and citations.",
            "Constraints are best-effort; prefer official sources and always cite/verify.",
            "If you want stronger constraint accuracy later, add city/county-specific permit open-data APIs where available.",
        ],
    }


# Optional direct run (no argparse)
if __name__ == "__main__":
    # Replace with your key if you want to test interactively.
    # data = main("30252", year=2023, tavily_api_key="tvly-dev-...")
    data = main("30252", year=2023, tavily_api_key=TAVILY_API_KEY)
    print(json.dumps(data, indent=2))
