#!/usr/bin/env python3
"""
Integration Tests for Multi-Agent Tool System

Simple test runner that calls real APIs (Tavily + Cerebras).
Run with: python tests/test_multi_agent_tools.py
"""
import asyncio
import os
import sys
import warnings
from pathlib import Path

# Suppress third-party deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="litellm")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="aiohttp")
warnings.filterwarnings("ignore", message=".*coroutine.*was never awaited.*")

# Setup path and load environment
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(override=True)


# =============================================================================
# Test Runner
# =============================================================================

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def run(self, name: str, test_func):
        """Run a single test."""
        try:
            if asyncio.iscoroutinefunction(test_func):
                asyncio.run(test_func())
            else:
                test_func()
            print(f"  ✅ {name}")
            self.passed += 1
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
            self.failed += 1
            self.errors.append((name, str(e)))
        except Exception as e:
            print(f"  ❌ {name}: {type(e).__name__}: {e}")
            self.failed += 1
            self.errors.append((name, f"{type(e).__name__}: {e}"))

    def summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed")
        if self.errors:
            print(f"\nFailed tests:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# Base Class Tests
# =============================================================================

def test_success_result():
    """Test creating a successful tool result."""
    from src.core.tools.base import ToolResult, ConfidenceScore

    result = ToolResult.success_result(
        data={"key": "value"},
        confidence=ConfidenceScore.high(reasoning="Test"),
        tool_name="test_tool"
    )

    assert result.success is True
    assert result.data == {"key": "value"}
    assert result.confidence.value >= 0.8
    assert result.error is None


def test_error_result():
    """Test creating an error result."""
    from src.core.tools.base import ToolResult

    result = ToolResult.error_result(
        error="Something went wrong",
        tool_name="test_tool"
    )

    assert result.success is False
    assert result.error == "Something went wrong"
    assert result.confidence.value == 0.0


def test_confidence_levels():
    """Test confidence score levels."""
    from src.core.tools.base import ConfidenceScore

    low = ConfidenceScore.low(reasoning="Unclear")
    medium = ConfidenceScore.medium(reasoning="Somewhat clear")
    high = ConfidenceScore.high(reasoning="Very clear")

    assert low.value < medium.value < high.value
    assert low.requires_human_input() is True
    assert medium.requires_human_input() is False
    assert high.requires_human_input() is False


def test_hitl_question():
    """Test HITL question creation."""
    from src.core.tools.base import HITLQuestion, QuestionCategory, Priority, ConfidenceScore

    question = HITLQuestion(
        question="What is the room width?",
        field_name="room_width",
        category=QuestionCategory.DIMENSIONS,
        priority=Priority.HIGH,
        confidence=ConfidenceScore.low(reasoning="Cannot see clearly")
    )

    assert question.priority == Priority.HIGH
    assert question.category == QuestionCategory.DIMENSIONS
    assert question.resolved is False

    data = question.to_dict()
    assert data["question"] == "What is the room width?"
    assert data["priority"] == Priority.HIGH.value


# =============================================================================
# Location Tools Tests
# =============================================================================

def test_validate_zip_code():
    """Test ZIP code validation."""
    from src.core.services.zip_structured_data_service import validate_zip

    assert validate_zip("10001") == "10001"
    assert validate_zip(" 90210 ") == "90210"

    try:
        validate_zip("1234")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    try:
        validate_zip("abcde")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


async def test_get_location_data():
    """Test fetching real location data (Census + Climate)."""
    from src.core.services.zip_structured_data_service import get_location_data_only

    result = await get_location_data_only(zip_code="10001")

    assert result is not None
    assert result["location"]["city"] == "New York City"
    assert result["location"]["state_abbr"] == "NY"
    print(f"    → Location: {result['location']['city']}, {result['location']['state_abbr']}")


# =============================================================================
# Estimator Tools Tests
# =============================================================================

def test_calculate_quantities():
    """Test quantity takeoff calculations."""
    from src.core.tools.estimator import calculate_quantities

    result = calculate_quantities(
        width_ft=10,
        length_ft=12,
        height_ft=8,
        materials_to_replace=["hardwood", "paint"],
        project_type="renovation"
    )

    assert result.success is True
    data = result.data

    assert data["room_sqft"] == 120
    assert data["perimeter_ft"] == 44

    materials = {m["material"]: m for m in data["materials"]}
    assert "hardwood" in materials
    assert materials["hardwood"]["quantity"] > 120


def test_calculate_quantities_invalid():
    """Test error handling for invalid dimensions."""
    from src.core.tools.estimator import calculate_quantities

    result = calculate_quantities(
        width_ft=0,
        length_ft=12,
        height_ft=8,
        materials_to_replace=["hardwood"],
        project_type="renovation"
    )

    assert result.success is False


def test_waste_factors():
    """Test waste factors for different materials."""
    from src.core.tools.estimator import get_waste_factor

    assert get_waste_factor("tile") == 0.15
    assert get_waste_factor("carpet") == 0.05
    assert get_waste_factor("unknown") == 0.10


def test_estimate_labor():
    """Test labor estimation."""
    from src.core.tools.estimator import estimate_labor

    quantities = {
        "room_sqft": 120,
        "wall_sqft": 280,
        "perimeter_ft": 44,
        "materials": [
            {"material": "hardwood", "quantity": 132, "unit": "sqft"},
            {"material": "paint", "quantity": 2, "unit": "gallons"}
        ]
    }

    result = estimate_labor(
        scope_items=[],
        quantities=quantities,
        location="New York, NY",
        project_type="renovation"
    )

    assert result.success is True
    data = result.data

    assert data["total_hours"] > 0
    assert data["total_labor_cost"] > 0
    assert data["regional_multiplier"] > 1.0
    print(f"    → Labor: {data['total_hours']} hrs, ${data['total_labor_cost']:,.0f}")


def test_regional_multipliers():
    """Test regional labor rate multipliers."""
    from src.core.tools.estimator import get_regional_multiplier

    assert get_regional_multiplier("New York, NY") > 1.0
    assert get_regional_multiplier("Manhattan") > get_regional_multiplier("Queens")
    assert get_regional_multiplier("Phoenix, AZ") < 1.0
    assert get_regional_multiplier("Unknown City") == 1.0


def test_generate_estimate():
    """Test three-tier estimate generation."""
    from src.core.tools.estimator import generate_estimate

    quantities = {
        "room_sqft": 120,
        "materials": [
            {"material": "hardwood", "quantity": 132, "unit": "sqft"},
            {"material": "paint", "quantity": 2, "unit": "gallons"}
        ]
    }

    labor_estimate = {"total_hours": 24, "total_labor_cost": 1800}

    result = generate_estimate(
        quantities=quantities,
        labor_estimate=labor_estimate,
        project_type="renovation",
        location="Chicago, IL"
    )

    assert result.success is True
    data = result.data

    assert "low" in data["tiers"]
    assert "mid" in data["tiers"]
    assert "high" in data["tiers"]
    assert data["tiers"]["low"]["total"] < data["tiers"]["mid"]["total"] < data["tiers"]["high"]["total"]
    print(f"    → Estimates: Low ${data['tiers']['low']['total']:,.0f} | Mid ${data['tiers']['mid']['total']:,.0f} | High ${data['tiers']['high']['total']:,.0f}")


def test_cost_per_sqft():
    """Test cost per sqft calculation."""
    from src.core.tools.estimator import calculate_cost_per_sqft

    estimate = {"room_sqft": 100, "tiers": {"mid": {"total": 15000}}}
    assert calculate_cost_per_sqft(estimate, "mid") == 150.0


# =============================================================================
# Compliance Tools Tests
# =============================================================================

def test_structural_validation_wall_removal():
    """Test structural validation detects wall removal."""
    from src.core.tools.compliance import validate_structural_scope

    result = validate_structural_scope(
        scope_description="Remove wall between kitchen and living room for open concept",
        structural_elements=None
    )

    assert result.success is True
    data = result.data

    assert data["requires_structural_engineer"] is True
    assert data["requires_permit"] is True
    assert data["risk_level"] == "high"
    print(f"    → Risk: {data['risk_level']}, Requires PE: {data['requires_structural_engineer']}")


def test_structural_validation_cosmetic():
    """Test structural validation for cosmetic-only work."""
    from src.core.tools.compliance import validate_structural_scope

    result = validate_structural_scope(
        scope_description="Paint walls and replace cabinet hardware",
        structural_elements=None
    )

    assert result.success is True
    assert result.data["requires_structural_engineer"] is False
    assert result.data["risk_level"] == "low"


def test_building_age_requirements():
    """Test building age requirements for lead paint."""
    from src.core.tools.compliance import check_building_age_requirements

    result = check_building_age_requirements(
        building_age=1965,
        scope_description="Paint walls and replace trim"
    )

    assert result.success is True
    data = result.data

    assert len(data["requirements"]) > 0
    assert any("lead" in r["requirement"].lower() for r in data["requirements"])
    print(f"    → Found {len(data['requirements'])} requirements for pre-1978 building")


# =============================================================================
# Designer Tools Tests
# =============================================================================

def test_sticky_note_categories():
    """Test sticky note category constants."""
    from src.core.tools.designer.sticky_notes import StickyNoteCategory

    assert hasattr(StickyNoteCategory, 'STYLE')
    assert hasattr(StickyNoteCategory, 'MATERIAL')
    assert hasattr(StickyNoteCategory, 'AVOID')
    assert hasattr(StickyNoteCategory, 'MUST_HAVE')


def test_format_sticky_notes():
    """Test formatting sticky notes for LLM prompt."""
    from src.core.tools.designer import format_sticky_notes_for_prompt

    notes = [
        {"category": "style", "content": "Modern farmhouse"},
        {"category": "avoid", "content": "Brass fixtures"},
        {"category": "must_have", "content": "White shaker cabinets"}
    ]

    prompt = format_sticky_notes_for_prompt(notes)

    assert "Modern farmhouse" in prompt
    assert "Brass fixtures" in prompt
    assert "White shaker cabinets" in prompt


# =============================================================================
# HITL Manager Tests
# =============================================================================

def test_hitl_manager():
    """Test adding and resolving HITL questions."""
    from src.core.services.hitl_manager import HITLManager
    from src.core.tools.base import (
        ToolResult, ConfidenceScore, HITLQuestion,
        QuestionCategory, Priority
    )

    manager = HITLManager(project_id="test_project")

    result = ToolResult(
        success=True,
        data={"room_width": 10},
        confidence=ConfidenceScore.low(reasoning="Cannot see clearly"),
        hitl_questions=[
            HITLQuestion(
                question="What is the room width?",
                field_name="room_width",
                category=QuestionCategory.DIMENSIONS,
                priority=Priority.HIGH,
                confidence=ConfidenceScore.low(reasoning="Unclear")
            )
        ],
        tool_name="test"
    )

    manager.add_tool_result(domain="space", tool_result=result)

    questions = manager.get_questions_by_priority()
    assert len(questions) == 1
    assert questions[0].field_name == "room_width"

    resolved = manager.resolve_question(questions[0].id, 12)
    assert resolved is True

    assert len(manager.get_unresolved_questions()) == 0


# =============================================================================
# Tavily + Cerebras Integration Tests
# =============================================================================

async def test_market_data_with_tavily():
    """Test fetching market data with real Tavily search + Cerebras."""
    from src.core.tools.location.market_data import get_market_data

    result = await get_market_data(
        zip_code="10001",
        project_type="kitchen",
        skip_tavily=False
    )

    assert result.success is True
    data = result.data

    assert data["location"]["city"] == "New York City"
    assert data["location"]["state_abbr"] == "NY"

    if data.get("contractor_knowledge"):
        knowledge = data["contractor_knowledge"]
        styles = len(knowledge.get('popular_styles', []))
        materials = len(knowledge.get('popular_materials', []))
        print(f"    → Cerebras extracted: {styles} styles, {materials} materials")


async def test_permit_detection_with_tavily():
    """Test permit detection with real Tavily search + Cerebras analysis."""
    from src.core.tools.compliance import detect_permit_requirements

    result = await detect_permit_requirements(
        project_type="kitchen",
        scope_description="Remove wall between kitchen and dining room, relocate plumbing for island sink",
        location="New York, NY",
        building_age=1960,
        is_nyc=True
    )

    assert result.success is True
    data = result.data

    permits = data.get("permits_required", [])
    sources = data.get("sources", [])

    print(f"    → Detected {len(permits)} permits, {len(sources)} Tavily sources")


async def test_contractor_knowledge_extraction():
    """Test contractor knowledge extraction with Cerebras."""
    from src.core.tools.location.market_data import extract_contractor_knowledge

    raw_content = """
    Kitchen Renovation Trends in New York City 2024

    Popular styles in NYC include:
    - Modern minimalist with clean lines and handleless cabinets
    - Classic transitional blending traditional and contemporary
    - Industrial loft style popular in Brooklyn

    Top materials:
    - Quartz countertops ($60-80/sqft installed)
    - Porcelain tile backsplash
    - White shaker cabinets
    - Luxury vinyl plank flooring

    Average kitchen remodel costs in Manhattan:
    - Budget: $25,000-40,000
    - Mid-range: $50,000-80,000
    - High-end: $100,000+
    """

    result = await extract_contractor_knowledge(
        raw_content=raw_content,
        location={"city": "New York City", "state_abbr": "NY"},
        budget_tier="mid"
    )

    assert result.success is True
    data = result.data

    styles = len(data.get('popular_styles', []))
    materials = len(data.get('popular_materials', []))

    print(f"    → Cerebras extracted: {styles} styles, {materials} materials")
    assert styles > 0 or materials > 0


# =============================================================================
# Full Workflow Test
# =============================================================================

async def test_complete_workflow():
    """Test complete estimation workflow with real APIs."""
    from src.core.services.tool_orchestrator import ToolOrchestrator

    orchestrator = ToolOrchestrator(project_id="test_workflow")

    # Step 1: Start project
    start_result = await orchestrator.process_project_start(
        zip_code="60601",
        project_type="kitchen"
    )

    assert start_result.success is True
    assert orchestrator.state.location_validated is True
    print(f"    → Location: {orchestrator.state.market_data.get('city', 'Unknown')}")

    # Step 2: Set measurements
    orchestrator.state.measurements = {
        "width_ft": 12,
        "length_ft": 15,
        "height_ft": 9
    }

    # Step 3: Generate estimate
    estimate_result = await orchestrator.generate_full_estimate(
        project_type="kitchen",
        materials_to_replace=["hardwood", "paint", "tile"]
    )

    assert estimate_result.success is True
    assert orchestrator.state.final_estimate is not None

    estimate = orchestrator.state.final_estimate
    print(f"    → Estimates: Low ${estimate['tiers']['low']['total']:,.0f} | Mid ${estimate['tiers']['mid']['total']:,.0f} | High ${estimate['tiers']['high']['total']:,.0f}")


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all tests."""
    print("=" * 60)
    print("Multi-Agent Tool System - Integration Tests")
    print("=" * 60)

    # Check API keys
    if not os.getenv("TAVILY_API_KEY"):
        print("\n❌ TAVILY_API_KEY not set in .env")
        return False
    if not os.getenv("CEREBRAS_API_KEY"):
        print("\n❌ CEREBRAS_API_KEY not set in .env")
        return False

    print(f"\n✓ TAVILY_API_KEY configured")
    print(f"✓ CEREBRAS_API_KEY configured")

    runner = TestRunner()

    # Base Classes
    print("\n📦 Base Classes")
    runner.run("ToolResult success", test_success_result)
    runner.run("ToolResult error", test_error_result)
    runner.run("Confidence levels", test_confidence_levels)
    runner.run("HITL question", test_hitl_question)

    # Location Tools
    print("\n📍 Location Tools")
    runner.run("ZIP validation", test_validate_zip_code)
    runner.run("Location data (Census)", test_get_location_data)

    # Estimator Tools
    print("\n💰 Estimator Tools")
    runner.run("Calculate quantities", test_calculate_quantities)
    runner.run("Invalid dimensions", test_calculate_quantities_invalid)
    runner.run("Waste factors", test_waste_factors)
    runner.run("Labor estimation", test_estimate_labor)
    runner.run("Regional multipliers", test_regional_multipliers)
    runner.run("3-tier estimate", test_generate_estimate)
    runner.run("Cost per sqft", test_cost_per_sqft)

    # Compliance Tools
    print("\n📋 Compliance Tools")
    runner.run("Structural - wall removal", test_structural_validation_wall_removal)
    runner.run("Structural - cosmetic", test_structural_validation_cosmetic)
    runner.run("Building age (lead paint)", test_building_age_requirements)

    # Designer Tools
    print("\n🎨 Designer Tools")
    runner.run("Sticky note categories", test_sticky_note_categories)
    runner.run("Format sticky notes", test_format_sticky_notes)

    # HITL Manager
    print("\n👤 HITL Manager")
    runner.run("Add and resolve questions", test_hitl_manager)

    # Tavily + Cerebras Integration
    print("\n🔍 Tavily + Cerebras Integration")
    runner.run("Market data (Tavily → Cerebras)", test_market_data_with_tavily)
    runner.run("Permit detection (Tavily → Cerebras)", test_permit_detection_with_tavily)
    runner.run("Knowledge extraction (Cerebras)", test_contractor_knowledge_extraction)

    # Full Workflow
    print("\n🚀 Full Workflow")
    runner.run("Complete estimation flow", test_complete_workflow)

    return runner.summary()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
