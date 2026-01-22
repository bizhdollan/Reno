"""
NYC Department of Buildings (DOB) Lookup Tool

Fetches property data from NYC Open Data APIs:
- PLUTO (Primary Land Use Tax Lot Output) for BBL and property info
- DOB permits and violations
- Landmark status from LPC

Uses NYC Open Data SODA API (Socrata Open Data API).
"""
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

import httpx

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)

# NYC Open Data API endpoints
NYC_PLUTO_API = "https://data.cityofnewyork.us/resource/64uk-42ks.json"  # PLUTO 23v3
NYC_DOB_PERMITS_API = "https://data.cityofnewyork.us/resource/ipu4-2vpu.json"  # DOB Permit Issuance
NYC_DOB_VIOLATIONS_API = "https://data.cityofnewyork.us/resource/3h2n-5cm9.json"  # DOB Violations
NYC_LPC_LANDMARKS_API = "https://data.cityofnewyork.us/resource/x3ar-yjn2.json"  # LPC Individual Landmarks

# Borough codes for BBL construction
BOROUGH_CODES = {
    "Manhattan": "1",
    "Bronx": "2",
    "Brooklyn": "3",
    "Queens": "4",
    "Staten Island": "5",
}

# Reverse mapping
BOROUGH_NAMES = {v: k for k, v in BOROUGH_CODES.items()}


@dataclass
class NYCPropertyData:
    """NYC property data from DOB and related sources."""
    bbl: str  # Borough-Block-Lot identifier
    borough: str
    block: str
    lot: str

    # Building info
    address: str
    year_built: Optional[int] = None
    building_class: Optional[str] = None
    building_class_description: Optional[str] = None
    num_floors: Optional[int] = None
    num_units: Optional[int] = None
    lot_area_sqft: Optional[float] = None
    building_area_sqft: Optional[float] = None

    # Zoning
    zoning_district: Optional[str] = None
    zoning_map: Optional[str] = None
    commercial_overlay: Optional[str] = None
    special_district: Optional[str] = None

    # Landmark status
    landmark_status: Optional[str] = None  # None, "Individual", "Historic District", "Interior"
    landmark_name: Optional[str] = None

    # DOB data
    open_violations_count: int = 0
    active_permits_count: int = 0
    recent_permits: List[Dict[str, Any]] = field(default_factory=list)
    recent_violations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "bbl": self.bbl,
            "borough": self.borough,
            "block": self.block,
            "lot": self.lot,
            "address": self.address,
            "year_built": self.year_built,
            "building_class": self.building_class,
            "building_class_description": self.building_class_description,
            "num_floors": self.num_floors,
            "num_units": self.num_units,
            "lot_area_sqft": self.lot_area_sqft,
            "building_area_sqft": self.building_area_sqft,
            "zoning_district": self.zoning_district,
            "zoning_map": self.zoning_map,
            "commercial_overlay": self.commercial_overlay,
            "special_district": self.special_district,
            "landmark_status": self.landmark_status,
            "landmark_name": self.landmark_name,
            "open_violations_count": self.open_violations_count,
            "active_permits_count": self.active_permits_count,
            "recent_permits": self.recent_permits,
            "recent_violations": self.recent_violations,
        }


def _parse_street_address(address: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse street address into number and name components.

    Args:
        address: Full street address (e.g., "123 Main Street")

    Returns:
        Tuple of (street_number, street_name)
    """
    address = address.strip()

    # Pattern: number followed by street name
    match = re.match(r"^(\d+[-\d]*)\s+(.+)$", address)
    if match:
        return match.group(1), match.group(2)

    return None, address


def _normalize_street_name(name: str) -> str:
    """Normalize street name for matching."""
    name = name.lower().strip()

    # Common abbreviations
    replacements = {
        " street": " st",
        " avenue": " ave",
        " boulevard": " blvd",
        " drive": " dr",
        " road": " rd",
        " place": " pl",
        " lane": " ln",
        " court": " ct",
        " terrace": " ter",
        " parkway": " pkwy",
        " east": " e",
        " west": " w",
        " north": " n",
        " south": " s",
    }

    for full, abbrev in replacements.items():
        name = name.replace(full, abbrev)

    return name


async def get_bbl_from_address(
    street_number: str,
    street_name: str,
    borough: str
) -> ToolResult:
    """
    Convert NYC address to BBL (Borough-Block-Lot) via PLUTO API.

    Args:
        street_number: House number (e.g., "123")
        street_name: Street name (e.g., "Main Street")
        borough: NYC borough name

    Returns:
        ToolResult containing BBL string on success
    """
    start_time = time.time()
    tool_name = "bbl_lookup"

    borough_code = BOROUGH_CODES.get(borough)
    if not borough_code:
        return ToolResult.error_result(
            error=f"Invalid borough: {borough}. Must be one of: {list(BOROUGH_CODES.keys())}",
            tool_name=tool_name
        )

    # Normalize street name for query
    normalized_street = _normalize_street_name(street_name)

    logger.info(f"[bbl_lookup] Looking up BBL for {street_number} {street_name}, {borough}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Query PLUTO by address
            params = {
                "$where": f"borocode='{borough_code}' AND lower(address) LIKE '%{street_number}%'",
                "$limit": 10,
                "$select": "bbl,address,borocode,block,lot"
            }

            response = await client.get(NYC_PLUTO_API, params=params)
            response.raise_for_status()
            results = response.json()

        if not results:
            # Try alternate query with house number
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    params = {
                        "$where": f"borocode='{borough_code}'",
                        "$q": f"{street_number} {street_name}",
                        "$limit": 10,
                        "$select": "bbl,address,borocode,block,lot"
                    }
                    response = await client.get(NYC_PLUTO_API, params=params)
                    response.raise_for_status()
                    results = response.json()
            except Exception:
                pass

        if not results:
            return ToolResult.error_result(
                error=f"No property found for {street_number} {street_name}, {borough}",
                tool_name=tool_name
            )

        # Find best match
        best_match = None
        for result in results:
            addr = result.get("address", "").lower()
            if street_number.lower() in addr:
                best_match = result
                break

        if not best_match:
            best_match = results[0]

        bbl = best_match.get("bbl")
        if not bbl:
            return ToolResult.error_result(
                error="BBL not found in PLUTO response",
                tool_name=tool_name
            )

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data={
                "bbl": bbl,
                "matched_address": best_match.get("address"),
                "block": best_match.get("block"),
                "lot": best_match.get("lot"),
            },
            confidence=ConfidenceScore.high(reasoning="BBL found in PLUTO database", field_name="bbl"),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except httpx.TimeoutException:
        return ToolResult.error_result(error="PLUTO API request timed out", tool_name=tool_name)
    except Exception as e:
        logger.error(f"[bbl_lookup] Error: {e}")
        return ToolResult.error_result(error=f"BBL lookup failed: {str(e)}", tool_name=tool_name)


async def get_dob_property_data(bbl: str) -> ToolResult:
    """
    Fetch comprehensive property data from NYC DOB APIs.

    Args:
        bbl: Borough-Block-Lot identifier (10 digits)

    Returns:
        ToolResult containing NYCPropertyData on success
    """
    start_time = time.time()
    tool_name = "dob_property_lookup"

    # Validate BBL format
    bbl = bbl.strip().replace("-", "")
    if not re.match(r"^\d{10}$", bbl):
        return ToolResult.error_result(
            error=f"Invalid BBL format: {bbl}. Expected 10 digits.",
            tool_name=tool_name
        )

    borough_code = bbl[0]
    block = bbl[1:6].lstrip("0") or "0"
    lot = bbl[6:10].lstrip("0") or "0"
    borough_name = BOROUGH_NAMES.get(borough_code, "Unknown")

    logger.info(f"[dob_property_lookup] Fetching data for BBL {bbl} ({borough_name})")

    property_data = NYCPropertyData(
        bbl=bbl,
        borough=borough_name,
        block=block,
        lot=lot,
        address=""
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # 1. Fetch PLUTO data for building info
            pluto_params = {
                "$where": f"bbl='{bbl}'",
                "$limit": 1
            }
            pluto_response = await client.get(NYC_PLUTO_API, params=pluto_params)

            if pluto_response.status_code == 200:
                pluto_data = pluto_response.json()
                if pluto_data:
                    p = pluto_data[0]
                    property_data.address = p.get("address", "")
                    property_data.year_built = int(p.get("yearbuilt")) if p.get("yearbuilt") else None
                    property_data.building_class = p.get("bldgclass")
                    property_data.num_floors = int(p.get("numfloors")) if p.get("numfloors") else None
                    property_data.num_units = int(p.get("unitsres")) if p.get("unitsres") else None
                    property_data.lot_area_sqft = float(p.get("lotarea")) if p.get("lotarea") else None
                    property_data.building_area_sqft = float(p.get("bldgarea")) if p.get("bldgarea") else None
                    property_data.zoning_district = p.get("zonedist1")
                    property_data.zoning_map = p.get("zonemap")
                    property_data.commercial_overlay = p.get("overlay1")
                    property_data.special_district = p.get("spdist1")

                    # Check landmark status from PLUTO
                    if p.get("landmark"):
                        property_data.landmark_status = "Individual"
                        property_data.landmark_name = p.get("landmark")
                    elif p.get("histdist"):
                        property_data.landmark_status = "Historic District"
                        property_data.landmark_name = p.get("histdist")

            # 2. Fetch DOB Violations (open/active)
            violations_params = {
                "$where": f"bin IS NOT NULL AND isn_dob_bis_extract='Y'",
                "$q": bbl,
                "$limit": 20,
                "$order": "issue_date DESC"
            }

            try:
                violations_response = await client.get(NYC_DOB_VIOLATIONS_API, params=violations_params)
                if violations_response.status_code == 200:
                    violations = violations_response.json()

                    # Count open violations
                    open_count = sum(1 for v in violations if v.get("violation_status", "").upper() != "CLOSED")
                    property_data.open_violations_count = open_count

                    # Store recent violations
                    property_data.recent_violations = [
                        {
                            "number": v.get("violation_number"),
                            "type": v.get("violation_type"),
                            "category": v.get("violation_category"),
                            "description": v.get("description"),
                            "status": v.get("violation_status"),
                            "issue_date": v.get("issue_date"),
                        }
                        for v in violations[:5]
                    ]
            except Exception as e:
                logger.warning(f"[dob_property_lookup] Violations fetch failed: {e}")

            # 3. Fetch DOB Permits (recent)
            permits_params = {
                "bbl": bbl,
                "$limit": 20,
                "$order": "issuance_date DESC"
            }

            try:
                permits_response = await client.get(NYC_DOB_PERMITS_API, params=permits_params)
                if permits_response.status_code == 200:
                    permits = permits_response.json()

                    # Count active permits (issued in last 2 years)
                    two_years_ago = datetime.now().year - 2
                    active_count = sum(
                        1 for p in permits
                        if p.get("issuance_date", "")[:4].isdigit() and
                        int(p.get("issuance_date", "0000")[:4]) >= two_years_ago
                    )
                    property_data.active_permits_count = active_count

                    # Store recent permits
                    property_data.recent_permits = [
                        {
                            "job_number": p.get("job__"),
                            "job_type": p.get("job_type"),
                            "work_type": p.get("work_type"),
                            "permit_type": p.get("permit_type"),
                            "filing_status": p.get("filing_status"),
                            "issuance_date": p.get("issuance_date"),
                            "expiration_date": p.get("expiration_date"),
                        }
                        for p in permits[:5]
                    ]
            except Exception as e:
                logger.warning(f"[dob_property_lookup] Permits fetch failed: {e}")

        execution_time = (time.time() - start_time) * 1000

        # Determine confidence
        has_pluto = bool(property_data.address)
        if has_pluto and property_data.year_built:
            confidence = ConfidenceScore.high(reasoning="Full property data from PLUTO", field_name="property_data")
        elif has_pluto:
            confidence = ConfidenceScore.medium(reasoning="Partial property data available", field_name="property_data")
        else:
            confidence = ConfidenceScore.low(reasoning="Limited property data found", field_name="property_data")

        return ToolResult.success_result(
            data=property_data.to_dict(),
            confidence=confidence,
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    except httpx.TimeoutException:
        return ToolResult.error_result(error="DOB API request timed out", tool_name=tool_name)
    except Exception as e:
        logger.error(f"[dob_property_lookup] Error: {e}")
        return ToolResult.error_result(error=f"DOB lookup failed: {str(e)}", tool_name=tool_name)


async def lookup_property_intelligence(
    street_address: str,
    city: str,
    zip_code: str,
    borough: Optional[str] = None
) -> ToolResult:
    """
    Main entry point: Full property intelligence lookup.

    For NYC addresses, fetches DOB data including:
    - Building age and characteristics
    - Zoning information
    - Landmark status
    - Open violations
    - Recent permits

    For non-NYC addresses, returns basic validated address info.

    Args:
        street_address: Street address (e.g., "123 Main St")
        city: City name
        zip_code: ZIP code
        borough: Optional NYC borough (will be detected if not provided)

    Returns:
        ToolResult with property intelligence data
    """
    start_time = time.time()
    tool_name = "property_intelligence"

    # First, validate and geocode the address
    from src.core.tools.domain_1_location.address_validation import validate_address

    address_result = await validate_address(street_address, city, zip_code)

    if not address_result.success:
        return ToolResult.error_result(
            error=f"Address validation failed: {address_result.error}",
            tool_name=tool_name
        )

    address_data = address_result.data
    is_nyc = address_data.get("is_nyc", False)

    if not is_nyc:
        # Non-NYC address: return basic info
        execution_time = (time.time() - start_time) * 1000
        return ToolResult.success_result(
            data={
                "address": address_data,
                "is_nyc": False,
                "dob_data": None,
                "message": "Non-NYC address - DOB data not available"
            },
            confidence=address_result.confidence,
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    # NYC address: get DOB data
    borough = borough or address_data.get("borough")
    if not borough:
        return ToolResult.error_result(
            error="Could not determine NYC borough",
            tool_name=tool_name
        )

    # Parse street address
    street_number, street_name = _parse_street_address(street_address)
    if not street_number:
        return ToolResult.error_result(
            error="Could not parse street number from address",
            tool_name=tool_name
        )

    # Get BBL
    bbl_result = await get_bbl_from_address(street_number, street_name, borough)

    if not bbl_result.success:
        # Return address data without DOB data
        execution_time = (time.time() - start_time) * 1000
        return ToolResult.success_result(
            data={
                "address": address_data,
                "is_nyc": True,
                "dob_data": None,
                "message": f"BBL lookup failed: {bbl_result.error}"
            },
            confidence=ConfidenceScore.medium(reasoning="Address validated but BBL not found"),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    bbl = bbl_result.data.get("bbl")

    # Get DOB property data
    dob_result = await get_dob_property_data(bbl)

    execution_time = (time.time() - start_time) * 1000

    if not dob_result.success:
        return ToolResult.success_result(
            data={
                "address": address_data,
                "is_nyc": True,
                "bbl": bbl,
                "dob_data": None,
                "message": f"DOB lookup failed: {dob_result.error}"
            },
            confidence=ConfidenceScore.medium(reasoning="Address and BBL found but DOB data unavailable"),
            tool_name=tool_name,
            metadata={"execution_time_ms": execution_time}
        )

    # Combine all data
    return ToolResult.success_result(
        data={
            "address": address_data,
            "is_nyc": True,
            "bbl": bbl,
            "dob_data": dob_result.data,
        },
        confidence=dob_result.confidence,
        tool_name=tool_name,
        metadata={
            "execution_time_ms": execution_time,
            "year_built": dob_result.data.get("year_built"),
            "landmark_status": dob_result.data.get("landmark_status"),
            "open_violations": dob_result.data.get("open_violations_count", 0)
        }
    )
