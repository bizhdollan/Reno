#!/usr/bin/env python3
"""
Test script to fetch structured zip data with LLM-based contractor knowledge extraction.
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
load_dotenv()

from src.core.services.zip_structured_data_service import (
    get_place_from_zip,
    fetch_acs_data,
    derive_design_insights,
    get_climate_essentials,
    tavily_search,
    dedupe_results,
    TavilyResult,
)

from src.core.llm.provider import LLMProvider

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


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
        r'Call Now',
        r'Get A Quote',
        r'GET A QUOTE',
        r'Get a Price',
        r'CONTACT US',
        r'Sign In',
        r'Join as a Pro',
        r'Review Us',
        r'REVIEW US',
        r'Learn More',
        r'Read More',
        r'View all testimonials',
        r'Menu\s+',
        r'skip to main content',
        r'© \d{4}',
        r'All rights reserved',
        r'Terms of Use',
        r'Privacy Policy',
        r'Cookie Policy',
        r'Copyright & Trademark',
        r'Equal Housing Opportunity',
        r'NMLS \d+',
        r'Paid Ad',
        r'Disclosures',
        r'Software',
        r'Mobile App',
        r'Expert Support',
        r'Schedule a Demo',
        r'Talk to Sales:',
        r'Credit Cards Accepted',
        r'Business Hours',
        r'TRUSTED BY.*HOMEOWNERS',
        r'Verified Reviews for.*',
        r'Average homeowner rating',
    ]

    for pattern in patterns_to_remove:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Remove social media references
    text = re.sub(r'(Facebook|Twitter|X|Instagram|YouTube|LinkedIn|Pinterest|RSS)', '', text, flags=re.IGNORECASE)

    # Remove service area lists (navigation sections)
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
        r'^Find Pros',
        r'^Interior Design',
        r'^Kitchen Remodeling$',
        r'^Bathroom Remodeling$',
        r'^Home Improvement$',
        r'^Need a pro for',
        r'^Average rating:',
        r'^\d+ (Reviews?|Verified Hires?|Hires on Houzz)',
        r'^Best of Houzz',
    ]

    for line in lines:
        line = line.strip()

        # Skip if matches any skip pattern
        skip = False
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                skip = True
                break

        if skip:
            continue

        # Keep lines with substantial content
        if len(line) > 20:
            cleaned_lines.append(line)
        elif len(line) > 5 and any(c.isalnum() for c in line):
            # Keep short lines if they look meaningful (not just symbols/numbers)
            if not re.match(r'^[\d\s\*\-\[\]\(\)]+$', line):
                cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)

    # Final cleanup
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

    Args:
        cleaned_content: Cleaned content from all Tavily results
        location: Location info (city, state)
        budget_context: Budget tier, income, home value
        climate_context: Temperature range

    Returns:
        Structured contractor knowledge
    """

    city = location.get("city", "Unknown")
    state_abbr = location.get("state_abbr", "XX")
    finish_tier = budget_context.get("finish_tier", "mid")
    median_income = budget_context.get("median_household_income", 0)
    median_value = budget_context.get("median_home_value", 0)
    temp_range = climate_context.get("temp_range_f", {})

    # Build context strings
    budget_tier_str = finish_tier if finish_tier else "Unknown"
    income_str = f"${median_income:,}" if median_income else "Unknown"
    value_str = f"${median_value:,}" if median_value else "Unknown"
    temp_min = temp_range.get('min', 'N/A')
    temp_max = temp_range.get('max', 'N/A')

    prompt = f"""You are an expert renovation contractor analyzing web content to extract comprehensive regional knowledge about renovation trends, materials, and practices in {city}, {state_abbr}.

**Location Context:**
- City: {city}, {state_abbr}
- Budget Tier: {budget_tier_str}
- Median Household Income: {income_str}
- Median Home Value: {value_str}
- Temperature Range: {temp_min}°F - {temp_max}°F

**Your Task:**
Extract COMPREHENSIVE contractor knowledge from the content below. This knowledge will be used for:
1. Generating detailed renovation suggestions
2. Creating ACCURATE renovation images (requires specific visual details)
3. Estimating realistic project costs and timelines

**CRITICAL REQUIREMENTS:**
- Extract **MINIMUM 5-7 popular styles** (extract ALL styles mentioned, not just a few)
- Extract **MINIMUM 10-15 popular materials** (include countertops, flooring, cabinets, hardware, fixtures, tiles, etc.)
- Be EXTREMELY SPECIFIC: Instead of "clean lines", extract "white shaker cabinets with brass hardware and quartz countertops"
- Capture REGIONAL CHARACTER: What makes {city} renovations unique? Climate considerations? Local architectural styles?
- Extract EXACT details: specific color names, brand names, dimensions, patterns, finishes
- DON'T be conservative - if the content mentions it, extract it!

**Content from Local Contractors and Design Sources:**
{cleaned_content}

**Extract and return ONLY valid JSON with this exact structure:**

{{
  "popular_styles": [
    {{
      "name": "Specific style name (e.g., 'Modern Farmhouse', 'Industrial Loft', 'Coastal Contemporary')",
      "description": "Detailed description of what this style is and WHY it's popular in {city}, {state_abbr} specifically",
      "key_elements": ["SPECIFIC element with details (e.g., 'white subway tile backsplash', 'reclaimed barn wood beams', 'matte black faucets')"],
      "typical_applications": "Exactly where/how this style is used (e.g., 'Open-concept kitchens in 1960s ranch homes', 'Master bathroom remodels')",
      "color_palette": ["Exact color names (e.g., 'Benjamin Moore White Dove', 'warm gray', 'navy blue accents')"]
    }}
    // EXTRACT 5-7 MINIMUM - Don't stop at 2-3!
  ],
  "popular_materials": [
    {{
      "name": "Specific material name with details (e.g., 'Carrara marble', 'Engineered oak hardwood', 'Large-format porcelain tile')",
      "category": "countertops/flooring/walls/cabinets/hardware/fixtures/backsplash/etc",
      "description": "Detailed properties, why contractors recommend it, performance in {city} climate",
      "pairs_well_with": ["Specific materials (e.g., 'stainless steel appliances', 'white shaker cabinets', 'brass hardware')"],
      "budget_tier": "budget/mid/upper-mid/luxury",
      "maintenance": "Specific maintenance requirements (e.g., 'Seal every 12 months', 'Clean with pH-neutral cleaner')"
    }}
    // EXTRACT 10-15 MINIMUM across ALL categories - countertops, flooring, cabinets, hardware, tiles, fixtures, etc.
  ],
  "customer_project_examples": [
    "EXACT project descriptions from testimonials (e.g., 'Renovated 1929 Colonial kitchen with white quartz countertops, gray shaker cabinets, and subway tile backsplash - $45K budget')"
    // Extract ALL project examples mentioned - should have 5-10 examples
  ],
  "code_requirements": [
    "SPECIFIC local code/permit requirements (e.g., 'Philadelphia requires permits for electrical work over $500', 'Egress window required for basement bedrooms per {state_abbr} code')"
    // Extract ALL code/permit mentions - don't leave this empty if content has ANY regulatory info
  ],
  "timeline_expectations": [
    {{
      "project_type": "Specific project type",
      "duration": "SPECIFIC duration (e.g., '4-6 weeks', '8-12 weeks', NOT 'several months')",
      "notes": "Specific timing factors (e.g., 'Add 2 weeks if structural work needed', 'Permit processing takes 1-2 weeks')"
    }}
    // Extract 3-5 timeline expectations
  ],
  "budget_expectations": [
    {{
      "item": "Specific item/service",
      "insight": "SPECIFIC budget insight with numbers if mentioned (e.g., 'Quartz countertops $60-80/sq ft installed in {city}', 'Full kitchen remodel $40K-80K for 200 sq ft')"
    }}
    // Extract 5-10 budget insights with as much detail as possible
  ]
}}

**EXTRACTION RULES - READ CAREFULLY:**
1. **QUANTITY MATTERS**: Extract ALL information available - don't stop early!
   - Styles: minimum 5-7 (extract every style mentioned)
   - Materials: minimum 10-15 (countertops, floors, cabinets, hardware, tiles, fixtures, etc.)
   - Projects: 5-10 examples
   - Budget insights: 5-10 items
   - Timeline expectations: 3-5 project types

2. **SPECIFICITY MATTERS**: Extract exact details for image generation:
   - ❌ BAD: "modern fixtures"
   - ✅ GOOD: "matte black rainfall showerhead and matching towel bars"
   - ❌ BAD: "neutral colors"
   - ✅ GOOD: "warm white walls (Benjamin Moore Simply White) with gray island (Chelsea Gray)"

3. **REGIONAL CHARACTER**: Capture what makes {city} unique:
   - Local architectural styles (e.g., "Victorian rowhouses in Philadelphia")
   - Climate considerations (e.g., "Heated floors popular due to cold winters")
   - Local preferences and trends

4. **DON'T LEAVE FIELDS EMPTY**: If you have 20K tokens of content and extract empty arrays, you're not doing your job!
   - Only use empty arrays [] if the content truly has ZERO information for that category
   - Code requirements, budget expectations, timelines - these should almost never be empty

5. **SYNTHESIZE INFORMATION**: If content mentions "we use quartz in most kitchens" and later mentions "popular white and gray countertops", combine this into: "Quartz countertops in white and gray tones"

6. **EXACT PROJECT EXAMPLES**: Extract real customer testimonials verbatim:
   - Include specific details: year built, materials used, budget if mentioned
   - Keep the before/after transformation details

**OUTPUT FORMAT:**
Return ONLY the JSON object. No markdown code blocks, no explanations, no preamble. Just pure JSON.

Begin comprehensive extraction:"""

    try:
        provider = LLMProvider.for_llm()

        response = await provider.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are a contractor knowledge extraction expert. Extract structured, actionable renovation insights from web content. Be comprehensive and extract ALL available information. Return only valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Slightly higher for more creative synthesis
            max_tokens=4096,  # Increased for comprehensive extraction
            operation_type="contractor_knowledge_extraction"
        )

        # Clean up response
        response = response.strip()
        if response.startswith('```'):
            lines = response.split('\n')
            response = '\n'.join(line for line in lines if not line.startswith('```'))

        knowledge = json.loads(response.strip())

        print(f"[LLM Extraction] Successfully extracted contractor knowledge")
        print(f"  - Styles: {len(knowledge.get('popular_styles', []))}")
        print(f"  - Materials: {len(knowledge.get('popular_materials', []))}")
        print(f"  - Projects: {len(knowledge.get('customer_project_examples', []))}")

        return knowledge

    except Exception as e:
        print(f"[LLM Extraction] Failed: {e}")
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


def save_cleaned_content_to_file(zip_code: str, results_by_category: dict):
    """Save cleaned raw content to file for review."""
    output_dir = Path(__file__).parent / "tavily_cleaned_content"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{zip_code}_{timestamp}_cleaned.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Cleaned Content from Tavily for ZIP: {zip_code}\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("=" * 80 + "\n\n")

        for category, results in results_by_category.items():
            f.write(f"## {category.upper()}\n\n")
            f.write(f"Total results: {len(results)}\n\n")

            for i, result in enumerate(results, 1):
                f.write(f"### Result {i}: {result.title}\n\n")
                f.write(f"**URL:** {result.url}\n\n")
                f.write(f"**Score:** {result.score}\n\n")

                if result.raw_content:
                    cleaned = clean_raw_content(result.raw_content)
                    f.write(f"**Cleaned Content:**\n")
                    f.write("-" * 80 + "\n")
                    f.write(cleaned)
                    f.write("\n" + "-" * 80 + "\n\n")

                    # Calculate reduction
                    original_words = len(result.raw_content.split())
                    cleaned_words = len(cleaned.split())
                    reduction_pct = ((original_words - cleaned_words) / original_words * 100) if original_words > 0 else 0

                    f.write(f"*Original: {original_words} words, Cleaned: {cleaned_words} words, Reduction: {reduction_pct:.1f}%*\n\n")
                else:
                    f.write("**Raw Content:** Not available\n\n")

                f.write("\n" + "=" * 80 + "\n\n")

    print(f"\n✓ Cleaned content saved to: {output_file}")
    return output_file


async def fetch_structured_data(zip_code: str):
    """Fetch all structured data for a zip code with LLM-based extraction."""

    print(f"\n{'='*80}")
    print(f"Fetching structured data for: {zip_code}")
    print(f"{'='*80}\n")

    # 1. Place lookup
    print("[1/5] Fetching place info...")
    place = get_place_from_zip(zip_code)
    print(f"  ✓ Found: {place['city']}, {place['state_abbr']}")

    # 2. Census ACS
    print("[2/5] Fetching Census ACS data...")
    try:
        acs_values = fetch_acs_data(zip_code)
        print(f"  ✓ Got ACS data: {len(acs_values)} fields")
    except Exception as e:
        print(f"  ⚠️  Census data failed: {e}")
        print(f"  → Using None for missing values")
        # Use None for values we don't have - be truthful
        acs_values = {
            "median_household_income": None,
            "median_home_value": None,
            "median_gross_rent": None,
            "owner_occupied_units": None,
            "renter_occupied_units": None,
            "housing_units_total": None,
            "built_2000_2009": None,
            "built_1990_1999": None,
            "built_1980_1989": None,
            "built_1970_1979": None,
            "built_1960_1969": None,
            "built_1950_1959": None,
            "built_1940_1949": None,
            "built_1939_or_earlier": None,
        }

    # 3. Design insights
    print("[3/5] Deriving design insights...")
    try:
        design_insights = derive_design_insights(acs_values)
        print(f"  ✓ Budget tier: {design_insights['budget_indicators']['finish_tier']}")
    except Exception as e:
        print(f"  ⚠️  Design insights failed: {e}")
        print(f"  → Using None for missing values")
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

    # 4. Climate
    print("[4/5] Fetching climate data...")
    climate = None
    if place.get("latitude") and place.get("longitude"):
        try:
            climate = get_climate_essentials(
                lat=float(place["latitude"]),
                lon=float(place["longitude"]),
            )
            print(f"  ✓ Temperature range: {climate.get('temp_range_f', {})}")
        except Exception as e:
            print(f"  ⚠️  Climate data failed: {e}")
            print(f"  → Continuing without climate data")
            climate = None

    # 5. Tavily discovery
    print("[5/5] Running Tavily discovery...")

    if not TAVILY_API_KEY:
        print("  ⚠️  No Tavily API key - skipping web discovery")
        return {
            "location": place,
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
            "contractor_knowledge": {}
        }

    city = place["city"]
    state_abbr = place["state_abbr"]
    loc = f"{city} {state_abbr}".strip()

    # Search for contractor knowledge
    print(f"  → Searching for contractor insights in {loc}...")
    queries = [
        f'{loc} kitchen remodel contractor portfolio',
        f'{loc} bathroom renovation before after',
        f'{loc} home renovation design trends materials',
    ]

    all_results = []
    for q in queries:
        try:
            results = tavily_search(
                api_key=TAVILY_API_KEY,
                query=q,
                search_depth="advanced",
                max_results=5,
                include_raw_content=True,
            )
            all_results.extend(results)
        except Exception as e:
            print(f"  ⚠️  Tavily search failed for query '{q}': {e}")
            continue

    if not all_results:
        print(f"  ⚠️  No Tavily results found")
        return {
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
            "contractor_knowledge": {
                "popular_styles": [],
                "popular_materials": [],
                "customer_project_examples": [],
                "code_requirements": [],
                "timeline_expectations": [],
                "budget_expectations": []
            }
        }

    all_results = dedupe_results(all_results)
    print(f"  ✓ Found {len(all_results)} sources")

    # Clean and combine all content
    print("\n[Cleaning] Removing noise from raw content...")
    save_cleaned_content_to_file(zip_code, {"contractor_sources": all_results})

    combined_content = []
    for result in all_results:
        if result.raw_content:
            cleaned = clean_raw_content(result.raw_content)
            if cleaned:
                combined_content.append(f"=== Source: {result.title} ===\n{cleaned}\n")

    full_content = "\n\n".join(combined_content)
    print(f"  ✓ Combined content: {len(full_content.split())} words")

    # Extract contractor knowledge using LLM
    print("\n[LLM Extraction] Extracting contractor knowledge...")
    contractor_knowledge = await extract_contractor_knowledge_with_llm(
        cleaned_content=full_content,
        location=place,
        budget_context=design_insights["budget_indicators"],
        climate_context=climate if climate else {}
    )

    # Build final response (streamlined)
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
        "contractor_knowledge": contractor_knowledge
    }

    return result


async def test_zip(zip_code: str, project_type: str = "kitchen"):
    """Test a single zip code and print the output."""
    print("\n" + "="*80)
    print(f"Testing: {zip_code} - {project_type}")
    print("="*80)

    try:
        data = await fetch_structured_data(zip_code)

        print("\n" + "="*80)
        print("FINAL JSON OUTPUT")
        print("="*80 + "\n")
        print(json.dumps(data, indent=2))

        # Save to file
        output_dir = Path(__file__).parent / "final_output"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = output_dir / f"{zip_code}_{timestamp}_final.json"

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"\n✓ Final JSON output saved to: {json_file}")

        return data

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run tests for different zip codes."""

    test_cases = [
        # ("30252", "kitchen"),      # McDonough, GA
        # ("60614", "bathroom"),    # Chicago, IL
        # ("98109", "basement"),     # Seattle, WA
        ("73301", "living_room"),  # Austin, TX (Test error handling)
        # ("19103", "kitchen"),      # Philadelphia, PA
    ]

    for zip_code, project_type in test_cases:
        await test_zip(zip_code, project_type)
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
