"""
Location service for US zip code validation and location extraction.

Provides utilities for:
- Validating US zip codes
- Extracting city and state information from zip codes
"""

import re
from typing import Optional, Dict
from src.core.logger import get_logger
from src.core.llm.provider import LLMProvider

logger = get_logger(__name__)


def validate_us_zip_code(zip_code: str) -> bool:
    """
    Validate if the provided zip code is a valid US zip code format.

    Supports:
    - 5-digit format (e.g., "90210")
    - 5+4 digit format (e.g., "90210-1234")

    Args:
        zip_code: The zip code string to validate

    Returns:
        True if valid US zip code format, False otherwise
    """
    if not zip_code:
        return False

    # Remove whitespace
    zip_code = zip_code.strip()

    # Match 5-digit or 5+4 format
    pattern = r'^\d{5}(-\d{4})?$'
    return bool(re.match(pattern, zip_code))


async def extract_location_from_zip(zip_code: str) -> Optional[Dict[str, str]]:
    """
    Extract location information (city, state) from a US zip code using LLM.

    Args:
        zip_code: Valid US zip code (should be validated first)

    Returns:
        Dictionary with keys:
        - city: City name
        - state: State name (full name)
        - state_code: State abbreviation (e.g., "CA")
        - zip_code: The input zip code

        Returns None if extraction fails
    """
    # First validate
    if not validate_us_zip_code(zip_code):
        return None

    # Extract just the 5-digit portion for lookup
    zip_5 = zip_code.split('-')[0]

    # Use LLM to extract location info
    provider = LLMProvider.for_llm()

    prompt = f"""What is the city and state for the US zip code {zip_5}?

Return ONLY a JSON object with this exact format (no additional text):
{{
    "city": "City Name",
    "state": "Full State Name",
    "state_code": "ST",
    "zip_code": "{zip_5}"
}}

If the zip code is invalid or you don't know the location, return:
{{
    "city": null,
    "state": null,
    "state_code": null,
    "zip_code": "{zip_5}"
}}"""

    try:
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "You are a US zip code lookup assistant. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=150,
            operation_type="location_extraction"
        )

        # Parse JSON response
        import json
        # Clean up response - remove markdown code blocks if present
        response = response.strip()
        if response.startswith('```'):
            # Remove markdown code blocks
            lines = response.split('\n')
            response = '\n'.join(line for line in lines if not line.startswith('```'))

        location_data = json.loads(response.strip())

        # Validate that we got actual data
        if location_data.get('city') and location_data.get('state'):
            return location_data
        else:
            return None

    except Exception as e:
        logger.error(f"[location_service] Failed to extract location from zip {zip_code}: {e}")
        return None


def get_location_display(location_data: Optional[Dict[str, str]]) -> str:
    """
    Format location data for display.

    Args:
        location_data: Dictionary from extract_location_from_zip

    Returns:
        Formatted string like "Los Angeles, CA" or just the zip code if no data
    """
    if not location_data:
        return "Unknown Location"

    city = location_data.get('city')
    state_code = location_data.get('state_code')

    if city and state_code:
        return f"{city}, {state_code}"
    elif city:
        return city
    else:
        return location_data.get('zip_code', 'Unknown Location')
