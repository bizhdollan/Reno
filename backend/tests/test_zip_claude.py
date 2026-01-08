#!/usr/bin/env python3
"""
Test suite for zip_structured_data_service.py

Dynamic tests for multiple zip codes comparing streamlined vs original approach.
No pytest - individual test functions with clear output.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
load_dotenv()

from src.core.services.zip_structured_data_service import get_zip_structured_data

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ----------------------------
# Test helper
# ----------------------------

def print_test(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n{status}: {test_name}")
    if details:
        print(f"  {details}")


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


# ----------------------------
# Test cases
# ----------------------------

def test_validate_zip():
    """Test: Validate zip code format."""
    from src.core.services.zip_structured_data_service import validate_zip

    try:
        # Valid
        assert validate_zip("90210") == "90210"
        assert validate_zip("10001") == "10001"
        assert validate_zip(" 30252 ") == "30252"

        # Invalid
        try:
            validate_zip("1234")
            return False  # Should have raised
        except ValueError:
            pass

        try:
            validate_zip("abcde")
            return False
        except ValueError:
            pass

        print_test("Validate zip code format", True)
        return True
    except Exception as e:
        print_test("Validate zip code format", False, str(e))
        return False


def test_place_lookup():
    """Test: Place lookup from zip."""
    from src.core.services.zip_structured_data_service import get_place_from_zip

    try:
        place = get_place_from_zip("90210")

        assert place["zip"] == "90210"
        assert place["city"] == "Beverly Hills"
        assert place["state_abbr"] == "CA"
        assert place["latitude"] is not None
        assert place["longitude"] is not None

        print_test("Place lookup from zip", True, f"Found: {place['city']}, {place['state_abbr']}")
        return True
    except Exception as e:
        print_test("Place lookup from zip", False, str(e))
        return False


def test_acs_fetch():
    """Test: Fetch Census ACS data."""
    from src.core.services.zip_structured_data_service import fetch_acs_data

    try:
        acs = fetch_acs_data("10001")  # NYC

        assert "median_household_income" in acs
        assert "median_home_value" in acs
        assert "owner_occupied_units" in acs
        assert acs["median_household_income"] is not None

        print_test("Fetch Census ACS data", True,
                  f"Median income: ${acs['median_household_income']:,}")
        return True
    except Exception as e:
        print_test("Fetch Census ACS data", False, str(e))
        return False


def test_design_insights():
    """Test: Derive design insights from ACS."""
    from src.core.services.zip_structured_data_service import fetch_acs_data, derive_design_insights

    try:
        acs = fetch_acs_data("30252")  # McDonough, GA
        insights = derive_design_insights(acs)

        assert "budget_indicators" in insights
        assert "renovation_context" in insights
        assert insights["budget_indicators"]["finish_tier"] in ["luxury", "upper-mid", "mid"]
        assert insights["renovation_context"]["intensity"] in ["high", "medium", "low"]

        tier = insights["budget_indicators"]["finish_tier"]
        intensity = insights["renovation_context"]["intensity"]

        print_test("Derive design insights from ACS", True,
                  f"Tier: {tier}, Intensity: {intensity}")
        return True
    except Exception as e:
        print_test("Derive design insights from ACS", False, str(e))
        return False


def test_climate_essentials():
    """Test: Fetch climate essentials from NWS."""
    from src.core.services.zip_structured_data_service import get_climate_essentials

    try:
        # Beverly Hills, CA
        climate = get_climate_essentials(lat=34.0736, lon=-118.4004)

        assert "temp_range_f" in climate
        assert "considerations" in climate
        assert isinstance(climate["considerations"], list)

        temp = climate.get("temp_range_f", {})
        considerations = climate.get("considerations", [])

        print_test("Fetch climate essentials from NWS", True,
                  f"Temp range: {temp}, Considerations: {len(considerations)}")
        return True
    except Exception as e:
        print_test("Fetch climate essentials from NWS", False, str(e))
        return False


async def test_full_pipeline_beverly_hills():
    """Test: Full pipeline for Beverly Hills (90210)."""
    try:
        data = await get_zip_structured_data("90210", tavily_api_key=TAVILY_API_KEY)

        # Validate structure
        assert "location" in data
        assert data["location"]["city"] == "Beverly Hills"
        assert data["location"]["state_abbr"] == "CA"

        assert "budget_indicators" in data
        assert "finish_tier" in data["budget_indicators"]

        assert "renovation_context" in data
        assert "intensity" in data["renovation_context"]

        assert "climate" in data

        if TAVILY_API_KEY:
            assert "design_trends" in data
            assert "popular_styles" in data["design_trends"]
            assert "constraints" in data

        # Measure output size
        json_str = json.dumps(data, indent=2)
        size = len(json_str.encode('utf-8'))

        print_test("Full pipeline for Beverly Hills (90210)", True,
                  f"Output size: {format_size(size)}")

        # Print sample of output
        print("\n--- Sample Output (Beverly Hills) ---")
        print(f"Location: {data['location']['city']}, {data['location']['state_abbr']}")
        print(f"Budget Tier: {data['budget_indicators']['finish_tier']}")
        print(f"Renovation Intensity: {data['renovation_context']['intensity']}")
        print(f"Likely Projects: {data['renovation_context']['likely_project_types'][:2]}")

        if data.get("design_trends"):
            styles = data["design_trends"]["popular_styles"][:3]
            print(f"\nTop Design Styles:")
            for style in styles:
                print(f"  - {style['name']} (confidence: {style['confidence']})")
                if style.get('citations'):
                    print(f"    Citation: {style['citations'][0]['title'][:50]}...")

        return True
    except Exception as e:
        print_test("Full pipeline for Beverly Hills (90210)", False, str(e))
        return False


async def test_full_pipeline_nyc():
    """Test: Full pipeline for NYC (10001)."""
    try:
        data = await get_zip_structured_data("10001", tavily_api_key=TAVILY_API_KEY)

        assert "location" in data
        assert data["location"]["city"] == "New York"
        assert data["location"]["state_abbr"] == "NY"

        assert "budget_indicators" in data
        assert "renovation_context" in data
        assert "climate" in data

        json_str = json.dumps(data, indent=2)
        size = len(json_str.encode('utf-8'))

        print_test("Full pipeline for NYC (10001)", True,
                  f"Output size: {format_size(size)}")

        print("\n--- Sample Output (NYC) ---")
        print(f"Location: {data['location']['city']}, {data['location']['state_abbr']}")
        print(f"Budget Tier: {data['budget_indicators']['finish_tier']}")
        print(f"Systems Upgrade Priority: {data['renovation_context']['systems_upgrade_priority']}")

        return True
    except Exception as e:
        print_test("Full pipeline for NYC (10001)", False, str(e))
        return False


async def test_full_pipeline_mcdonough():
    """Test: Full pipeline for McDonough, GA (30252)."""
    try:
        data = await get_zip_structured_data("30252", tavily_api_key=TAVILY_API_KEY)

        assert "location" in data
        assert data["location"]["city"] == "McDonough"
        assert data["location"]["state_abbr"] == "GA"

        assert "budget_indicators" in data
        assert "renovation_context" in data
        assert "climate" in data

        json_str = json.dumps(data, indent=2)
        size = len(json_str.encode('utf-8'))

        print_test("Full pipeline for McDonough, GA (30252)", True,
                  f"Output size: {format_size(size)}")

        print("\n--- Sample Output (McDonough) ---")
        print(f"Location: {data['location']['city']}, {data['location']['state_abbr']}")
        print(f"Median Home Value: ${data['budget_indicators']['median_home_value']:,}")
        print(f"Climate Considerations: {data['climate']['considerations'][:2]}")

        return True
    except Exception as e:
        print_test("Full pipeline for McDonough, GA (30252)", False, str(e))
        return False


async def test_output_completeness():
    """Test: Verify all required fields are present."""
    try:
        data = await get_zip_structured_data("90210", tavily_api_key=TAVILY_API_KEY)

        required_fields = [
            "location",
            "location.zip",
            "location.city",
            "location.state",
            "location.state_abbr",
            "budget_indicators",
            "budget_indicators.finish_tier",
            "budget_indicators.median_household_income",
            "budget_indicators.median_home_value",
            "renovation_context",
            "renovation_context.intensity",
            "renovation_context.owner_occupancy_pct",
            "renovation_context.likely_project_types",
            "renovation_context.systems_upgrade_priority",
            "climate",
            "climate.temp_range_f",
            "climate.considerations",
        ]

        if TAVILY_API_KEY:
            required_fields.extend([
                "design_trends",
                "design_trends.popular_styles",
                "design_trends.popular_materials",
                "constraints",
                "constraints.signals",
            ])

        missing = []
        for field_path in required_fields:
            parts = field_path.split(".")
            current = data
            for part in parts:
                if not isinstance(current, dict) or part not in current:
                    missing.append(field_path)
                    break
                current = current[part]

        if missing:
            print_test("Output completeness check", False, f"Missing fields: {missing}")
            return False

        print_test("Output completeness check", True, f"All {len(required_fields)} required fields present")
        return True
    except Exception as e:
        print_test("Output completeness check", False, str(e))
        return False


async def test_citations_present():
    """Test: Verify citations are present in design trends."""
    if not TAVILY_API_KEY:
        print_test("Citations presence check", True, "Skipped (no Tavily API key)")
        return True

    try:
        data = await get_zip_structured_data("90210", tavily_api_key=TAVILY_API_KEY)

        if not data.get("design_trends"):
            print_test("Citations presence check", False, "No design_trends in output")
            return False

        styles = data["design_trends"]["popular_styles"]
        materials = data["design_trends"]["popular_materials"]

        # Check that top results have citations
        has_citations = False
        for style in styles[:3]:
            if style.get("citations") and len(style["citations"]) > 0:
                has_citations = True
                break

        if not has_citations:
            print_test("Citations presence check", False, "No citations found in top styles")
            return False

        # Count total citations
        total_citations = sum(len(s.get("citations", [])) for s in styles)
        total_citations += sum(len(m.get("citations", [])) for m in materials)

        print_test("Citations presence check", True,
                  f"Found {total_citations} total citations across styles and materials")
        return True
    except Exception as e:
        print_test("Citations presence check", False, str(e))
        return False


async def test_compare_output_size():
    """Test: Compare streamlined output vs original (if available)."""
    try:
        data = await get_zip_structured_data("30252", tavily_api_key=TAVILY_API_KEY)

        streamlined_json = json.dumps(data, indent=2)
        streamlined_size = len(streamlined_json.encode('utf-8'))

        print_test("Output size comparison", True,
                  f"Streamlined output: {format_size(streamlined_size)}")

        # Additional metrics
        print("\n--- Output Metrics ---")
        print(f"Total size: {format_size(streamlined_size)}")

        if data.get("design_trends"):
            style_count = len(data["design_trends"]["popular_styles"])
            material_count = len(data["design_trends"]["popular_materials"])
            print(f"Styles: {style_count}, Materials: {material_count}")

            total_citations = 0
            for s in data["design_trends"]["popular_styles"]:
                total_citations += len(s.get("citations", []))
            for m in data["design_trends"]["popular_materials"]:
                total_citations += len(m.get("citations", []))
            print(f"Total citations: {total_citations}")

            if data.get("constraints"):
                constraint_count = len(data["constraints"]["signals"])
                official_count = len(data["constraints"]["official_sources"])
                print(f"Constraint signals: {constraint_count}")
                print(f"Official sources: {official_count}")

        return True
    except Exception as e:
        print_test("Output size comparison", False, str(e))
        return False


# ----------------------------
# Main test runner
# ----------------------------

async def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("ZIP STRUCTURED DATA SERVICE - TEST SUITE")
    print("=" * 60)

    if not TAVILY_API_KEY:
        print("\n⚠️  WARNING: TAVILY_API_KEY not found in .env")
        print("   Web discovery tests will be limited\n")

    results = []

    # Sync tests
    print("\n--- Basic Function Tests ---")
    results.append(test_validate_zip())
    results.append(test_place_lookup())
    results.append(test_acs_fetch())
    results.append(test_design_insights())
    results.append(test_climate_essentials())

    # Async tests
    print("\n--- Full Pipeline Tests ---")
    results.append(await test_full_pipeline_beverly_hills())
    results.append(await test_full_pipeline_nyc())
    results.append(await test_full_pipeline_mcdonough())

    print("\n--- Integration Tests ---")
    results.append(await test_output_completeness())
    results.append(await test_citations_present())
    results.append(await test_compare_output_size())

    # Summary
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"SUMMARY: {passed}/{total} tests passed")
    if failed > 0:
        print(f"⚠️  {failed} test(s) failed")
        return False
    else:
        print("✓ All tests passed!")
        return True


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
