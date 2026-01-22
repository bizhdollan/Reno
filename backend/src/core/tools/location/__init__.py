"""
Domain 1: Location Intelligence Tools

Provides location-based data and property intelligence:
- Address validation and geocoding
- NYC DOB property lookup (BBL, violations, permits, landmarks)
- Market data (Census, climate, contractor knowledge via Tavily)
"""

from .address_validation import (
    validate_address,
    validate_zip_only,
    ValidatedAddress,
)
from .nyc_dob_lookup import (
    get_bbl_from_address,
    get_dob_property_data,
    lookup_property_intelligence,
    NYCPropertyData,
)
from .market_data import (
    get_market_data,
    get_market_data_with_search_insights,
    extract_contractor_knowledge,
)

__all__ = [
    # Address validation
    "validate_address",
    "validate_zip_only",
    "ValidatedAddress",
    # NYC DOB
    "get_bbl_from_address",
    "get_dob_property_data",
    "lookup_property_intelligence",
    "NYCPropertyData",
    # Market data
    "get_market_data",
    "get_market_data_with_search_insights",
    "extract_contractor_knowledge",
]
