#!/usr/bin/env python3
"""
zip_structured_data.py

Library-style module (no CLI/argparse). One-call main().

Call:
  from zip_structured_data import main
  result = main("90210", year=2023)
  print(result)

What it does (free):
1) ZIP -> place info via Zippopotam.us (city/state/lat/lon)
2) ZIP (treated as ZCTA) -> US Census ACS 5-year structured signals
   - with automatic DNS fallback using: nslookup + curl --resolve
3) Derives renovation / interior-design insights:
   - owner/renter %
   - housing age bucket %
   - heuristic scores (0..1) + interpretations + follow-up questions
"""

import json
import re
import subprocess
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests


ZIPPOTAM_BASE = "https://api.zippopotam.us/us/{zip}"
CENSUS_BASE = "https://api.census.gov/data/{year}/acs/acs5"


# Core variables (strong priors for budget & market characteristics)
ACS_VARS_CORE = {
    "B19013_001E": "median_household_income",  # median household income (USD)
    "B25077_001E": "median_home_value",        # median value of owner-occupied housing unit (USD)
    "B25064_001E": "median_gross_rent",        # median gross rent (USD)
    "B25002_002E": "owner_occupied_units",     # count
    "B25002_003E": "renter_occupied_units",    # count
}

# Housing age distribution: units by year built (counts)
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
# Validation / utilities
# ----------------------------

def validate_zip(zip_code: str) -> str:
    """Validate and normalize a US 5-digit ZIP code."""
    z = (zip_code or "").strip()
    if not re.fullmatch(r"\d{5}", z):
        raise ValueError("ZIP code must be 5 digits (e.g., '90210').")
    return z


def safe_div(n: float, d: float, default: float = 0.0) -> float:
    return default if d == 0 else (n / d)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ----------------------------
# Zippopotam.us
# ----------------------------

def get_place_from_zip(zip_code: str) -> Dict[str, Any]:
    """
    Fetch city/state/lat/lon from Zippopotam.us.

    Returns:
      {
        "zip": "90210",
        "city": "Beverly Hills",
        "state": "California",
        "state_abbr": "CA",
        "latitude": 34.0901,
        "longitude": -118.4065
      }
    """
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
# US Census ACS (with DNS fallback)
# ----------------------------

def build_census_acs_url(year: int, zcta: str, var_codes: List[str]) -> str:
    """
    Build an ACS request URL for a ZCTA (ZIP Code Tabulation Area).

    Example:
      https://api.census.gov/data/2022/acs/acs5?get=B19013_001E&for=zip%20code%20tabulation%20area:90210
    """
    get_part = ",".join(var_codes)
    geo = f"zip code tabulation area:{zcta}"
    return f"{CENSUS_BASE.format(year=year)}?get={quote(get_part)}&for={quote(geo)}"


def try_requests_json(url: str) -> Optional[Any]:
    """Try fetching JSON via requests; return None on any failure."""
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def nslookup_ip(hostname: str) -> Optional[str]:
    """
    Resolve hostname to IPv4 using nslookup.
    Returns last IPv4 found (usually the A record for the host).
    """
    try:
        out = subprocess.check_output(["nslookup", hostname], text=True, stderr=subprocess.STDOUT)
    except Exception:
        return None

    ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", out)
    if not ips:
        return None
    return ips[-1]


def curl_resolve_json(url: str, hostname: str, ip: str) -> Any:
    """
    Fetch JSON using curl, bypassing DNS via --resolve.
    Useful when local resolver behavior breaks for api.census.gov.
    """
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


def fetch_acs_structured(zip_code: str, year: int = 2022) -> Dict[str, Any]:
    """
    Fetch structured ACS signals for a ZIP (treated as ZCTA).

    Returns:
      {
        "source": "US Census ACS 5-year",
        "year": 2022,
        "zcta": "90210",
        "used_curl_resolve_fallback": true/false,
        "resolved_ip": "148.129.75.191" or None,
        "values": {...},
        "housing_year_built_distribution": {...}
      }
    """
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

    # Census returns: [ [header...], [row...] ]
    header = data[0]
    row = data[1]

    values: Dict[str, Any] = {}

    for i, col in enumerate(header):
        if col == "zip code tabulation area":
            continue
        key = var_map.get(col, col)
        raw = row[i]

        # Convert numeric strings to int where possible
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
# Derive renovation / design insights
# ----------------------------

def derive_design_insights(acs_values: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert raw ACS values into renovation / interior-design insights.

    Important: These are population-level priors, not individual preferences.
    """

    owners = int(acs_values.get("owner_occupied_units") or 0)
    renters = int(acs_values.get("renter_occupied_units") or 0)

    total_units = acs_values.get("housing_units_total")
    if total_units is None or int(total_units) <= 0:
        total_units = owners + renters
    total_units = max(1, int(total_units))

    owner_pct = safe_div(owners, total_units)
    renter_pct = safe_div(renters, total_units)

    # Age bucket sums
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

    # Market/budget signals
    income = float(acs_values.get("median_household_income") or 0)
    home_value = float(acs_values.get("median_home_value") or 0)
    rent = float(acs_values.get("median_gross_rent") or 0)

    # Heuristic normalization targets (tunable)
    # These are not "truth"; they're just scaling constants to map into 0..1.
    income_norm = clamp01(income / 200_000.0)
    value_norm = clamp01(home_value / 2_000_000.0)
    rent_norm = clamp01(rent / 3_000.0)

    # Scores (0..1) — simple, explainable heuristics
    renovation_propensity = clamp01(0.50 * owner_pct + 0.50 * pre_1980_pct)
    systems_upgrade_risk = clamp01(pre_1960_pct)  # older stock => higher probability of systems work
    luxury_finish_likelihood = clamp01(0.45 * income_norm + 0.45 * value_norm + 0.10 * rent_norm)
    historic_character_sensitivity = clamp01(1.15 * pre_1960_pct + 0.35 * pre_1940_pct)

    # Interpretations
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

    # Owner-heavy areas: more long-horizon remodels
    if owner_pct > 0.70:
        likely_project_types.append("kitchen and bathroom renovations")
        likely_project_types.append("whole-home refresh / modernization")

    # Older stock: more structural/systems
    if pre_1980_pct > 0.60:
        likely_project_types.append("layout modernization (opening up plans, improving flow)")
        likely_project_types.append("window/insulation/energy-efficiency upgrades")

    if pre_1960_pct > 0.30:
        likely_project_types.append("electrical and plumbing upgrades (assessment early in design)")
        likely_project_types.append("envelope improvements (roof, moisture, insulation)")

    if historic_character_sensitivity > 0.55:
        likely_project_types.append("character-preserving remodels (period details, restoration)")

    # Deduplicate while preserving order
    seen = set()
    likely_project_types = [x for x in likely_project_types if not (x in seen or seen.add(x))]

    # Suggested follow-up questions to turn priors into actual preferences
    recommended_questions = [
        "Is the property a single-family home, condo, or apartment?",
        "Do you want to preserve the original architectural character or modernize fully?",
        "Is your goal a cosmetic refresh, partial remodel (kitchen/bath), or full remodel?",
        "Do you have an approximate budget range and timeline?",
        "Any constraints: HOA rules, historical designation, or permitting concerns?",
        "Lifestyle needs: kids/pets, accessibility, work-from-home, entertaining?",
    ]

    # A short narrative summary (useful for UI / logging)
    summary = (
        f"Owner-occupancy is ~{owner_pct*100:.1f}% and housing stock skews older "
        f"(pre-1980 ~{pre_1980_pct*100:.1f}%, pre-1960 ~{pre_1960_pct*100:.1f}%). "
        f"Budget signals suggest a {finish_tier} finish tier. "
        f"Overall renovation intensity is {renovation_intensity}."
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
            "pre_1980_units": pre_1980_units,
            "pre_1960_units": pre_1960_units,
            "pre_1940_units": pre_1940_units,
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
        "recommended_next_questions": recommended_questions,
        "summary": summary,
        "notes": [
            "These are area-level priors derived from ACS (ZCTA). They do not represent an individual's taste.",
            "Use these to choose sensible defaults and ask better follow-up questions.",
        ],
    }


# ----------------------------
# One-call main()
# ----------------------------

def main(zip_code: str, year: int = 2022) -> Dict[str, Any]:
    """
    One-call function:
      ZIP -> place -> ACS -> derived renovation/design insights
    """
    zip_code = validate_zip(zip_code)

    place = get_place_from_zip(zip_code)
    acs = fetch_acs_structured(zip_code, year=year)
    insights = derive_design_insights(acs["values"])

    return {
        "place": place,
        "acs_structured": acs,
        "design_insights": insights,
    }


# Optional direct run (kept simple; no argparse)
if __name__ == "__main__":
    result = main("30252", year=2023)
    print(json.dumps(result, indent=2))
