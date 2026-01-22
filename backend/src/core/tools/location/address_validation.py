"""
Address Validation Tool

Validates and geocodes addresses using Google Maps Geocoding API.
Returns normalized address with coordinates and NYC detection.
"""
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from src.core.logger import get_logger
from src.core.tools.base import ToolResult, ConfidenceScore

logger = get_logger(__name__)

# NYC borough boundaries (approximate bounding boxes)
NYC_BOROUGHS = {
    "Manhattan": {"lat_min": 40.699, "lat_max": 40.882, "lon_min": -74.047, "lon_max": -73.907},
    "Brooklyn": {"lat_min": 40.570, "lat_max": 40.739, "lon_min": -74.042, "lon_max": -73.833},
    "Queens": {"lat_min": 40.541, "lat_max": 40.812, "lon_min": -73.962, "lon_max": -73.700},
    "Bronx": {"lat_min": 40.785, "lat_max": 40.917, "lon_min": -73.933, "lon_max": -73.765},
    "Staten Island": {"lat_min": 40.495, "lat_max": 40.651, "lon_min": -74.259, "lon_max": -74.052},
}


@dataclass
class ValidatedAddress:
    """Validated and geocoded address data."""
    street_address: str
    city: str
    state: str
    zip_code: str
    country: str
    latitude: float
    longitude: float
    formatted_address: str
    is_nyc: bool
    borough: Optional[str] = None  # For NYC addresses
    place_id: Optional[str] = None  # Google Maps place ID

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "street_address": self.street_address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "formatted_address": self.formatted_address,
            "is_nyc": self.is_nyc,
            "borough": self.borough,
            "place_id": self.place_id,
        }


def _detect_nyc_borough(lat: float, lon: float) -> Optional[str]:
    """Detect NYC borough based on coordinates."""
    for borough, bounds in NYC_BOROUGHS.items():
        if (bounds["lat_min"] <= lat <= bounds["lat_max"] and
            bounds["lon_min"] <= lon <= bounds["lon_max"]):
            return borough
    return None


def _is_nyc_from_components(city: str, state: str) -> bool:
    """Check if address is in NYC based on city/state."""
    city_lower = city.lower().strip()
    state_upper = state.upper().strip()

    # NYC indicators
    nyc_cities = {"new york", "new york city", "nyc", "manhattan", "brooklyn", "queens", "bronx", "staten island"}
    return city_lower in nyc_cities and state_upper in {"NY", "NEW YORK"}


async def validate_address(
    street_address: str,
    city: str,
    zip_code: str,
    state: Optional[str] = None
) -> ToolResult:
    """
    Validate and geocode an address using Google Maps Geocoding API.

    Args:
        street_address: Street address (e.g., "123 Main St")
        city: City name
        zip_code: ZIP code
        state: Optional state (will be inferred if not provided)

    Returns:
        ToolResult containing ValidatedAddress on success
    """
    start_time = time.time()
    tool_name = "address_validation"

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return ToolResult.error_result(
            error="GOOGLE_MAPS_API_KEY not configured",
            tool_name=tool_name
        )

    # Build address string
    address_parts = [street_address, city]
    if state:
        address_parts.append(state)
    address_parts.append(zip_code)
    address_query = ", ".join(filter(None, address_parts))

    logger.info(f"[address_validation] Geocoding: {address_query}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "address": address_query,
                    "key": api_key,
                    "components": "country:US"  # Restrict to US
                }
            )
            response.raise_for_status()
            data = response.json()

        if data.get("status") != "OK" or not data.get("results"):
            error_msg = data.get("status", "No results found")
            logger.warning(f"[address_validation] Geocoding failed: {error_msg}")
            return ToolResult.error_result(
                error=f"Address not found: {error_msg}",
                tool_name=tool_name
            )

        # Parse first result
        result = data["results"][0]
        geometry = result.get("geometry", {})
        location = geometry.get("location", {})
        lat = location.get("lat")
        lon = location.get("lng")

        if lat is None or lon is None:
            return ToolResult.error_result(
                error="Could not extract coordinates from geocoding result",
                tool_name=tool_name
            )

        # Extract address components
        components = {}
        for comp in result.get("address_components", []):
            for comp_type in comp.get("types", []):
                components[comp_type] = {
                    "long_name": comp.get("long_name", ""),
                    "short_name": comp.get("short_name", "")
                }

        # Extract normalized address parts
        street_number = components.get("street_number", {}).get("long_name", "")
        route = components.get("route", {}).get("long_name", "")
        normalized_street = f"{street_number} {route}".strip() if street_number or route else street_address

        locality = components.get("locality", {}).get("long_name", "")
        sublocality = components.get("sublocality", {}).get("long_name", "")
        normalized_city = locality or sublocality or city

        admin_area = components.get("administrative_area_level_1", {})
        normalized_state = admin_area.get("short_name", state or "")

        postal_code = components.get("postal_code", {}).get("long_name", zip_code)
        country = components.get("country", {}).get("short_name", "US")

        # NYC detection
        is_nyc = _is_nyc_from_components(normalized_city, normalized_state)
        borough = None

        if is_nyc:
            # Detect borough from coordinates
            borough = _detect_nyc_borough(lat, lon)
            if not borough:
                # Fallback: check if city name is a borough
                city_lower = normalized_city.lower()
                for boro_name in NYC_BOROUGHS.keys():
                    if boro_name.lower() in city_lower:
                        borough = boro_name
                        break
                # Default to Manhattan if NYC but borough unknown
                if not borough:
                    borough = "Manhattan"

            logger.info(f"[address_validation] NYC address detected: {borough}")

        validated = ValidatedAddress(
            street_address=normalized_street,
            city=normalized_city,
            state=normalized_state,
            zip_code=postal_code,
            country=country,
            latitude=lat,
            longitude=lon,
            formatted_address=result.get("formatted_address", address_query),
            is_nyc=is_nyc,
            borough=borough,
            place_id=result.get("place_id")
        )

        # Determine confidence based on match quality
        location_type = geometry.get("location_type", "APPROXIMATE")
        if location_type == "ROOFTOP":
            confidence = ConfidenceScore.high(reasoning="Exact rooftop match", field_name="address")
        elif location_type == "RANGE_INTERPOLATED":
            confidence = ConfidenceScore(value=0.85, reasoning="Interpolated address range", field_name="address")
        elif location_type == "GEOMETRIC_CENTER":
            confidence = ConfidenceScore.medium(reasoning="Geometric center of area", field_name="address")
        else:
            confidence = ConfidenceScore(value=0.65, reasoning="Approximate location", field_name="address")

        execution_time = (time.time() - start_time) * 1000

        return ToolResult.success_result(
            data=validated.to_dict(),
            confidence=confidence,
            tool_name=tool_name,
            metadata={
                "location_type": location_type,
                "google_place_id": result.get("place_id"),
                "execution_time_ms": execution_time
            }
        )

    except httpx.TimeoutException:
        return ToolResult.error_result(
            error="Geocoding request timed out",
            tool_name=tool_name
        )
    except Exception as e:
        logger.error(f"[address_validation] Error: {e}")
        return ToolResult.error_result(
            error=f"Geocoding failed: {str(e)}",
            tool_name=tool_name
        )


async def validate_zip_only(zip_code: str) -> ToolResult:
    """
    Validate just a ZIP code (without full address).
    Returns approximate location data.

    Args:
        zip_code: US ZIP code

    Returns:
        ToolResult with basic location info
    """
    start_time = time.time()
    tool_name = "zip_validation"

    # Validate ZIP format
    if not re.match(r"^\d{5}(-\d{4})?$", zip_code.strip()):
        return ToolResult.error_result(
            error="Invalid ZIP code format. Expected 5 digits (e.g., 90210)",
            tool_name=tool_name
        )

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        # Fallback to Zippopotam.us API
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"https://api.zippopotam.us/us/{zip_code[:5]}")
                response.raise_for_status()
                data = response.json()

            place = data["places"][0]
            city = place.get("place name", "")
            state = place.get("state", "")
            state_abbr = place.get("state abbreviation", "")
            lat = float(place["latitude"]) if place.get("latitude") else None
            lon = float(place["longitude"]) if place.get("longitude") else None

            is_nyc = _is_nyc_from_components(city, state_abbr)
            borough = _detect_nyc_borough(lat, lon) if is_nyc and lat and lon else None

            execution_time = (time.time() - start_time) * 1000

            return ToolResult.success_result(
                data={
                    "city": city,
                    "state": state,
                    "state_abbr": state_abbr,
                    "zip_code": zip_code[:5],
                    "latitude": lat,
                    "longitude": lon,
                    "is_nyc": is_nyc,
                    "borough": borough,
                },
                confidence=ConfidenceScore.medium(
                    reasoning="ZIP code centroid location",
                    field_name="location"
                ),
                tool_name=tool_name,
                metadata={"source": "zippopotam.us", "execution_time_ms": execution_time}
            )

        except Exception as e:
            logger.error(f"[zip_validation] Zippopotam fallback failed: {e}")
            return ToolResult.error_result(
                error=f"ZIP code validation failed: {str(e)}",
                tool_name=tool_name
            )

    # Use Google Maps if API key available
    return await validate_address(
        street_address="",
        city="",
        zip_code=zip_code[:5]
    )
