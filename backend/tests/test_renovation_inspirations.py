"""
Tests for Renovation Inspirations Feature.

Tests the location service and renovation inspiration service including:
- US zip code validation
- Location extraction from zip codes
- Renovation inspiration retrieval
- Database storage and retrieval
- Integration with project_basics_node

Usage:
    python tests/test_renovation_inspirations.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.services.location_service import (
    validate_us_zip_code,
    extract_location_from_zip,
    get_location_display
)
from src.core.services.renovation_inspiration_service import (
    retrieve_renovation_inspirations,
    store_renovation_inspirations,
    retrieve_and_store_inspirations_background
)
from src.db.database import SessionLocal
from src.db.models import Project
from src.utils.token_generator import generate_token


# Test utilities
def print_test(test_name: str, passed: bool = True, message: str = ""):
    """Print test result"""
    status = "✓" if passed else "✗"
    status_text = "PASSED" if passed else "FAILED"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"

    print(f"{color}{status} {test_name} - {status_text}{reset}")
    if message:
        print(f"  {message}")


# =============================================================================
# LOCATION SERVICE TESTS
# =============================================================================

def test_validate_us_zip_code_valid_5_digit():
    """Test validation of standard 5-digit US zip codes."""
    test_name = "test_validate_us_zip_code_valid_5_digit"
    try:
        assert validate_us_zip_code("90210") == True
        assert validate_us_zip_code("10001") == True
        assert validate_us_zip_code("12345") == True
        print_test(test_name, True)
        return True
    except AssertionError as e:
        print_test(test_name, False, str(e))
        return False


def test_validate_us_zip_code_valid_9_digit():
    """Test validation of 5+4 format US zip codes."""
    test_name = "test_validate_us_zip_code_valid_9_digit"
    try:
        assert validate_us_zip_code("90210-1234") == True
        assert validate_us_zip_code("10001-5678") == True
        print_test(test_name, True)
        return True
    except AssertionError as e:
        print_test(test_name, False, str(e))
        return False


def test_validate_us_zip_code_invalid():
    """Test rejection of invalid zip codes."""
    test_name = "test_validate_us_zip_code_invalid"
    try:
        assert validate_us_zip_code("1234") == False  # Too short
        assert validate_us_zip_code("abcde") == False  # Letters
        assert validate_us_zip_code("") == False  # Empty
        assert validate_us_zip_code("123456") == False  # Too long
        assert validate_us_zip_code("12345-") == False  # Incomplete 9-digit
        print_test(test_name, True)
        return True
    except AssertionError as e:
        print_test(test_name, False, str(e))
        return False


async def test_extract_location_from_zip_beverly_hills():
    """Test location extraction for Beverly Hills (90210)."""
    test_name = "test_extract_location_from_zip_beverly_hills"
    try:
        location = await extract_location_from_zip("90210")

        assert location is not None, "Location should not be None"
        assert location.get("city") == "Beverly Hills", f"Expected Beverly Hills, got {location.get('city')}"
        assert location.get("state") == "California", f"Expected California, got {location.get('state')}"
        assert location.get("state_code") == "CA", f"Expected CA, got {location.get('state_code')}"
        assert location.get("zip_code") == "90210", f"Expected 90210, got {location.get('zip_code')}"

        print_test(test_name, True, f"Extracted: {location}")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


async def test_extract_location_from_zip_new_york():
    """Test location extraction for New York (10001)."""
    test_name = "test_extract_location_from_zip_new_york"
    try:
        location = await extract_location_from_zip("10001")

        assert location is not None, "Location should not be None"
        assert location.get("city") == "New York", f"Expected New York, got {location.get('city')}"
        assert location.get("state") == "New York", f"Expected New York, got {location.get('state')}"
        assert location.get("state_code") == "NY", f"Expected NY, got {location.get('state_code')}"

        print_test(test_name, True, f"Extracted: {location}")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


async def test_extract_location_from_zip_invalid():
    """Test that invalid zip codes return None."""
    test_name = "test_extract_location_from_zip_invalid"
    try:
        location = await extract_location_from_zip("invalid")
        assert location is None, "Invalid zip code should return None"
        print_test(test_name, True)
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


def test_get_location_display():
    """Test location display formatting."""
    test_name = "test_get_location_display"
    try:
        location_data = {
            "city": "Los Angeles",
            "state": "California",
            "state_code": "CA",
            "zip_code": "90001"
        }

        display = get_location_display(location_data)
        assert display == "Los Angeles, CA", f"Expected 'Los Angeles, CA', got '{display}'"

        # Test with missing data
        display_none = get_location_display(None)
        assert display_none == "Unknown Location"

        print_test(test_name, True, f"Display: {display}")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


# =============================================================================
# RENOVATION INSPIRATION SERVICE TESTS
# =============================================================================

async def test_retrieve_renovation_inspirations_kitchen():
    """Test retrieving renovation inspirations for a kitchen project."""
    test_name = "test_retrieve_renovation_inspirations_kitchen"
    try:
        inspirations = await retrieve_renovation_inspirations(
            project_type="kitchen",
            zip_code="90210"
        )

        assert inspirations is not None, "Inspirations should not be None"
        assert inspirations.get("project_type") == "kitchen"
        assert "location" in inspirations
        assert "design_styles" in inspirations
        assert "materials" in inspirations
        assert "color_palettes" in inspirations
        assert "layout_trends" in inspirations
        assert "fixtures_features" in inspirations

        # Check that we have actual data
        assert len(inspirations.get("design_styles", [])) > 0, "Should have design styles"
        assert len(inspirations.get("materials", [])) > 0, "Should have materials"

        print_test(test_name, True, f"Retrieved {len(inspirations['design_styles'])} styles, {len(inspirations['materials'])} material categories")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


async def test_retrieve_renovation_inspirations_bathroom():
    """Test retrieving renovation inspirations for a bathroom project."""
    test_name = "test_retrieve_renovation_inspirations_bathroom"
    try:
        inspirations = await retrieve_renovation_inspirations(
            project_type="bathroom",
            zip_code="10001"
        )

        assert inspirations is not None, "Inspirations should not be None"
        assert inspirations.get("project_type") == "bathroom"
        assert inspirations["location"]["state_code"] == "NY"

        print_test(test_name, True, f"Retrieved inspirations for {inspirations['location']['city']}")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


async def test_retrieve_renovation_inspirations_invalid_zip():
    """Test that invalid zip codes return None."""
    test_name = "test_retrieve_renovation_inspirations_invalid_zip"
    try:
        inspirations = await retrieve_renovation_inspirations(
            project_type="kitchen",
            zip_code="invalid"
        )

        assert inspirations is None, "Invalid zip code should return None"
        print_test(test_name, True)
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


async def test_retrieve_renovation_inspirations_with_location_data():
    """Test retrieving inspirations with pre-extracted location data."""
    test_name = "test_retrieve_renovation_inspirations_with_location_data"
    try:
        location_data = {
            "city": "San Francisco",
            "state": "California",
            "state_code": "CA",
            "zip_code": "94102"
        }

        inspirations = await retrieve_renovation_inspirations(
            project_type="bedroom",
            zip_code="94102",
            location_data=location_data
        )

        assert inspirations is not None
        assert inspirations["location"]["city"] == "San Francisco"
        print_test(test_name, True, "Pre-provided location data used successfully")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


# =============================================================================
# DATABASE STORAGE TESTS
# =============================================================================

async def test_store_renovation_inspirations():
    """Test storing renovation inspirations in the database."""
    test_name = "test_store_renovation_inspirations"
    db = SessionLocal()
    test_project = None

    try:
        # Create test project
        test_project = Project(
            token=generate_token("PRJ"),
            status="draft",
            project_type="kitchen",
            zip_code="90210"
        )
        db.add(test_project)
        db.commit()
        db.refresh(test_project)

        # Create test inspirations data
        inspirations = {
            "location": {
                "city": "Beverly Hills",
                "state": "California",
                "state_code": "CA"
            },
            "project_type": "kitchen",
            "design_styles": [
                {
                    "name": "Modern Luxury",
                    "description": "Sleek and sophisticated",
                    "popularity": "high"
                }
            ],
            "materials": [
                {
                    "category": "flooring",
                    "options": [
                        {
                            "name": "Marble",
                            "description": "Premium stone",
                            "tier": "luxury"
                        }
                    ]
                }
            ]
        }

        # Store inspirations
        success = await store_renovation_inspirations(test_project.id, inspirations)
        assert success == True, "Storage should succeed"

        # Verify in database
        db.refresh(test_project)
        assert test_project.renovation_inspirations is not None
        assert test_project.renovation_inspirations["project_type"] == "kitchen"
        assert test_project.renovation_inspirations["location"]["city"] == "Beverly Hills"

        print_test(test_name, True, "Stored and verified in database")
        return True

    except Exception as e:
        print_test(test_name, False, str(e))
        return False
    finally:
        # Cleanup
        if test_project:
            db.delete(test_project)
            db.commit()
        db.close()


async def test_store_renovation_inspirations_invalid_project():
    """Test storing inspirations with invalid project ID returns False."""
    test_name = "test_store_renovation_inspirations_invalid_project"
    try:
        fake_project_id = uuid4()
        inspirations = {"test": "data"}
        success = await store_renovation_inspirations(fake_project_id, inspirations)

        assert success == False, "Should fail for non-existent project"
        print_test(test_name, True)
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

async def test_retrieve_and_store_inspirations_background_full_flow():
    """Test the full background task flow from retrieval to storage."""
    test_name = "test_retrieve_and_store_inspirations_background_full_flow"
    db = SessionLocal()
    test_project = None

    try:
        # Create test project
        test_project = Project(
            token=generate_token("PRJ"),
            status="draft",
            project_type="bathroom",
            zip_code="10001"
        )
        db.add(test_project)
        db.commit()
        db.refresh(test_project)

        # Run background task
        await retrieve_and_store_inspirations_background(
            project_id=test_project.id,
            project_type="bathroom",
            zip_code="10001"
        )

        # Verify data was stored
        db.refresh(test_project)
        assert test_project.renovation_inspirations is not None, "Inspirations should be stored"
        assert test_project.renovation_inspirations.get("project_type") == "bathroom"
        assert test_project.renovation_inspirations.get("location") is not None
        assert "_metadata" in test_project.renovation_inspirations

        # Verify metadata
        metadata = test_project.renovation_inspirations["_metadata"]
        assert metadata["zip_code"] == "10001"
        assert metadata["project_type"] == "bathroom"
        assert "retrieved_at" in metadata

        print_test(test_name, True,
                  f"Full flow completed: {len(test_project.renovation_inspirations.get('design_styles', []))} styles stored")
        return True

    except Exception as e:
        print_test(test_name, False, str(e))
        return False
    finally:
        # Cleanup
        if test_project:
            db.delete(test_project)
            db.commit()
        db.close()


async def test_retrieve_and_store_background_invalid_zip():
    """Test background task with invalid zip code (should handle gracefully)."""
    test_name = "test_retrieve_and_store_background_invalid_zip"
    db = SessionLocal()
    test_project = None

    try:
        # Create test project
        test_project = Project(
            token=generate_token("PRJ"),
            status="draft",
            project_type="kitchen",
            zip_code="invalid"
        )
        db.add(test_project)
        db.commit()
        db.refresh(test_project)

        # Run background task with invalid zip
        await retrieve_and_store_inspirations_background(
            project_id=test_project.id,
            project_type="kitchen",
            zip_code="invalid"
        )

        # Verify no data was stored (failed gracefully)
        db.refresh(test_project)
        assert test_project.renovation_inspirations is None, "Should not store for invalid zip"

        print_test(test_name, True, "Handled invalid zip gracefully")
        return True

    except Exception as e:
        print_test(test_name, False, str(e))
        return False
    finally:
        # Cleanup
        if test_project:
            db.delete(test_project)
            db.commit()
        db.close()


# =============================================================================
# DATA STRUCTURE VALIDATION TESTS
# =============================================================================

async def test_inspiration_data_structure():
    """Test that retrieved inspirations have the expected structure."""
    test_name = "test_inspiration_data_structure"
    try:
        inspirations = await retrieve_renovation_inspirations(
            project_type="kitchen",
            zip_code="90210"
        )

        assert inspirations is not None

        # Required top-level keys
        required_keys = [
            "location", "project_type", "design_styles", "materials",
            "climate_considerations", "color_palettes", "layout_trends",
            "fixtures_features", "regional_notes"
        ]

        for key in required_keys:
            assert key in inspirations, f"Missing required key: {key}"

        # Validate location structure
        location = inspirations["location"]
        assert "city" in location
        assert "state" in location
        assert "state_code" in location

        # Validate design_styles structure
        if inspirations["design_styles"]:
            style = inspirations["design_styles"][0]
            assert "name" in style
            assert "description" in style
            assert "popularity" in style

        # Validate materials structure
        if inspirations["materials"]:
            material = inspirations["materials"][0]
            assert "category" in material
            assert "options" in material
            if material["options"]:
                option = material["options"][0]
                assert "name" in option
                assert "description" in option
                assert "tier" in option

        # Validate color_palettes structure
        if inspirations["color_palettes"]:
            palette = inspirations["color_palettes"][0]
            assert "name" in palette
            assert "colors" in palette
            assert "description" in palette

        print_test(test_name, True, "All required fields and structures validated")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


# =============================================================================
# SUGGESTION INTEGRATION TESTS
# =============================================================================

async def test_suggestions_with_inspirations():
    """Test that generate_expert_suggestions works with inspirations data."""
    test_name = "test_suggestions_with_inspirations"
    try:
        from src.core.langgraph.nodes.image_analysis_generation.intent_detection import generate_expert_suggestions

        # Get inspirations
        inspirations = await retrieve_renovation_inspirations(
            project_type="kitchen",
            zip_code="90210"
        )

        # Generate suggestions WITH inspirations
        suggestions = await generate_expert_suggestions(
            project_type="kitchen",
            current_state_summary="Modern kitchen with white cabinets",
            user_preferences="I want something elegant",
            expertise_level="novice",
            inspirations=inspirations
        )

        assert suggestions is not None
        assert "options" in suggestions
        assert len(suggestions["options"]) >= 2, "Should have at least 2 options"

        # Verify options have required fields
        for option in suggestions["options"]:
            assert "style_name" in option
            assert "key_changes" in option
            assert "budget_tier" in option

        print_test(test_name, True, f"Generated {len(suggestions['options'])} location-aware suggestions")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


async def test_suggestions_without_inspirations():
    """Test that generate_expert_suggestions works WITHOUT inspirations data."""
    test_name = "test_suggestions_without_inspirations"
    try:
        from src.core.langgraph.nodes.image_analysis_generation.intent_detection import generate_expert_suggestions

        # Generate suggestions WITHOUT inspirations (fallback behavior)
        suggestions = await generate_expert_suggestions(
            project_type="kitchen",
            current_state_summary="Modern kitchen with white cabinets",
            user_preferences="I want something elegant",
            expertise_level="novice",
            inspirations=None  # No inspirations provided
        )

        assert suggestions is not None
        assert "options" in suggestions
        assert len(suggestions["options"]) >= 2, "Should have at least 2 options"

        print_test(test_name, True, "Generated generic suggestions without inspirations")
        return True
    except Exception as e:
        print_test(test_name, False, str(e))
        return False


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

async def main():
    """Run all renovation inspiration tests."""
    print("\n" + "="*80)
    print("RENOVATION INSPIRATIONS FEATURE - TEST SUITE")
    print("="*80 + "\n")

    results = []

    # Location Service Tests (Sync)
    print("="*80)
    print("Location Service Tests (Sync)")
    print("="*80 + "\n")

    results.append(test_validate_us_zip_code_valid_5_digit())
    results.append(test_validate_us_zip_code_valid_9_digit())
    results.append(test_validate_us_zip_code_invalid())
    results.append(test_get_location_display())
    print()

    # Location Service Tests (Async)
    print("="*80)
    print("Location Service Tests (Async)")
    print("="*80 + "\n")

    results.append(await test_extract_location_from_zip_beverly_hills())
    results.append(await test_extract_location_from_zip_new_york())
    results.append(await test_extract_location_from_zip_invalid())
    print()

    # Renovation Inspiration Service Tests
    print("="*80)
    print("Renovation Inspiration Service Tests")
    print("="*80 + "\n")

    results.append(await test_retrieve_renovation_inspirations_kitchen())
    results.append(await test_retrieve_renovation_inspirations_bathroom())
    results.append(await test_retrieve_renovation_inspirations_invalid_zip())
    results.append(await test_retrieve_renovation_inspirations_with_location_data())
    print()

    # Database Storage Tests
    print("="*80)
    print("Database Storage Tests")
    print("="*80 + "\n")

    results.append(await test_store_renovation_inspirations())
    results.append(await test_store_renovation_inspirations_invalid_project())
    print()

    # Integration Tests
    print("="*80)
    print("Integration Tests")
    print("="*80 + "\n")

    results.append(await test_retrieve_and_store_inspirations_background_full_flow())
    results.append(await test_retrieve_and_store_background_invalid_zip())
    print()

    # Data Structure Validation Tests
    print("="*80)
    print("Data Structure Validation Tests")
    print("="*80 + "\n")

    results.append(await test_inspiration_data_structure())
    print()

    # Suggestion Integration Tests
    print("="*80)
    print("Suggestion Integration Tests")
    print("="*80 + "\n")

    results.append(await test_suggestions_with_inspirations())
    results.append(await test_suggestions_without_inspirations())
    print()

    # Summary
    print("="*80)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"\033[92m✓ All tests passed! ({passed}/{total})\033[0m")
    else:
        print(f"\033[91m✗ Some tests failed: {passed}/{total} passed\033[0m")

    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
