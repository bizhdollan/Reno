"""
Tests for the refactored service layer.

Tests the new DB-backed services for image analysis, generation, and conversation flow.

Usage:
    python tests/test_services.py
"""

import sys
import asyncio
from uuid import uuid4
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, "/Users/chhabi/Desktop/Reno/backend")


def test_session_cache_basic_operations():
    """Test basic cache set/get operations."""
    from src.core.services.session_cache import SessionCache

    cache = SessionCache()
    project_id = uuid4()

    # Test set and get
    cache.set_image_analysis(project_id, {"test": "data"})
    result = cache.get_image_analysis(project_id)
    assert result == {"test": "data"}, f"Expected {{'test': 'data'}}, got {result}"
    print("✓ test_session_cache_basic_operations passed")


def test_session_cache_miss_returns_none():
    """Test that cache miss returns None."""
    from src.core.services.session_cache import SessionCache

    cache = SessionCache()
    result = cache.get_image_analysis(uuid4())
    assert result is None, f"Expected None, got {result}"
    print("✓ test_session_cache_miss_returns_none passed")


def test_session_cache_clear():
    """Test cache clearing."""
    from src.core.services.session_cache import SessionCache

    cache = SessionCache()
    project_id = uuid4()

    cache.set_image_analysis(project_id, {"test": "data"})
    cache.clear()

    result = cache.get_image_analysis(project_id)
    assert result is None, f"Expected None after clear, got {result}"
    print("✓ test_session_cache_clear passed")


def test_session_cache_correction_history():
    """Test correction history caching."""
    from src.core.services.session_cache import SessionCache

    cache = SessionCache()
    project_id = uuid4()

    mock_correction = Mock()
    mock_correction.id = uuid4()
    mock_correction.field_changed = "materials.floor"

    cache.add_correction(project_id, mock_correction)
    corrections = cache.get_corrections(project_id)

    assert len(corrections) == 1, f"Expected 1 correction, got {len(corrections)}"
    assert corrections[0].field_changed == "materials.floor"
    print("✓ test_session_cache_correction_history passed")


def test_sentiment_service_contains_undo_request():
    """Test undo request detection."""
    from src.core.services.sentiment_service import SentimentService

    service = SentimentService()

    assert service.contains_undo_request("undo") is True
    assert service.contains_undo_request("undo that") is True
    assert service.contains_undo_request("go back") is True
    assert service.contains_undo_request("revert") is True
    assert service.contains_undo_request("I love this design") is False
    assert service.contains_undo_request("add marble floor") is False
    print("✓ test_sentiment_service_contains_undo_request passed")


def test_sentiment_service_is_negative_feedback():
    """Test negative feedback detection."""
    from src.core.services.sentiment_service import SentimentService

    service = SentimentService()

    assert service.is_negative_feedback("I don't like this") is True
    assert service.is_negative_feedback("this is ugly") is True
    assert service.is_negative_feedback("that looks bad") is True
    assert service.is_negative_feedback("not what I wanted") is True
    assert service.is_negative_feedback("add a chandelier") is False
    print("✓ test_sentiment_service_is_negative_feedback passed")


def test_sentiment_service_is_positive_feedback():
    """Test positive feedback detection."""
    from src.core.services.sentiment_service import SentimentService

    service = SentimentService()

    assert service.is_positive_feedback("I love it") is True
    assert service.is_positive_feedback("looks great") is True
    assert service.is_positive_feedback("this is perfect") is True
    assert service.is_positive_feedback("I don't like this") is False
    print("✓ test_sentiment_service_is_positive_feedback passed")


def test_budget_context_service_has_budget_keywords():
    """Test budget keyword detection."""
    from src.core.services.budget_context_service import BudgetContextService

    service = BudgetContextService(db=Mock(), llm_provider=Mock())

    assert service.has_budget_keywords("I have a limited budget") is True
    assert service.has_budget_keywords("What can I afford?") is True
    assert service.has_budget_keywords("My budget is $5000") is True
    assert service.has_budget_keywords("affordable options") is True
    assert service.has_budget_keywords("Add marble floor") is False
    print("✓ test_budget_context_service_has_budget_keywords passed")


def test_budget_default_materials():
    """Test default material suggestions by budget level."""
    from src.core.services.budget_context_service import BudgetContextService

    service = BudgetContextService(db=Mock(), llm_provider=Mock())

    # Low budget defaults
    low_materials = service._get_default_materials("low")
    assert "laminate" in low_materials["floor"]
    assert "paint" in low_materials["walls"]

    # High budget defaults
    high_materials = service._get_default_materials("high")
    assert "hardwood" in high_materials["floor"]
    assert "chandeliers" in high_materials["lighting"]
    print("✓ test_budget_default_materials passed")


def test_service_integration_initialization_without_project_id():
    """Test initialization without project_id."""
    from src.core.langgraph.nodes.image_analysis_generation.node_services import (
        ServiceIntegration,
    )

    services = ServiceIntegration()
    assert services.project_id is None
    assert services.is_refactored_mode is False
    print("✓ test_service_integration_initialization_without_project_id passed")


def test_service_integration_initialization_with_project_id():
    """Test initialization with project_id."""
    from src.core.langgraph.nodes.image_analysis_generation.node_services import (
        ServiceIntegration,
    )

    project_id = str(uuid4())
    services = ServiceIntegration(project_id=project_id)

    assert services.project_id == project_id
    assert services.is_refactored_mode is True
    print("✓ test_service_integration_initialization_with_project_id passed")


def test_service_integration_from_state():
    """Test creating ServiceIntegration from state."""
    from src.core.langgraph.nodes.image_analysis_generation.node_services import (
        ServiceIntegration,
    )

    project_id = str(uuid4())
    state = {"project_id": project_id, "messages": []}

    services = ServiceIntegration.from_state(state)

    assert services.project_id == project_id
    assert services.is_refactored_mode is True
    print("✓ test_service_integration_from_state passed")


def test_service_integration_cleanup():
    """Test cleanup releases resources."""
    from src.core.langgraph.nodes.image_analysis_generation.node_services import (
        ServiceIntegration,
    )

    services = ServiceIntegration()
    services.cleanup()

    # Should not raise any errors
    assert services._db is None
    print("✓ test_service_integration_cleanup passed")


def test_create_minimal_state():
    """Test minimal state creation."""
    from src.core.langgraph.state import create_minimal_state

    project_id = str(uuid4())
    state = create_minimal_state(project_id)

    assert state["project_id"] == project_id
    assert state["messages"] == []
    assert state["conversation_phase"] == "analyzing"
    assert state["pending_user_decision"] is None
    assert state["context_cache"] == {}
    print("✓ test_create_minimal_state passed")


def test_create_initial_state_includes_legacy_fields():
    """Test that initial state includes legacy fields for backward compatibility."""
    from src.core.langgraph.state import create_initial_state

    state = create_initial_state()

    # Core fields
    assert "messages" in state
    assert "project_id" in state
    assert "conversation_phase" in state

    # Legacy fields (backward compatibility)
    assert "current_stage" in state
    assert "image_sub_state" in state
    assert "extracted_data" in state
    print("✓ test_create_initial_state_includes_legacy_fields passed")


def test_check_undo_request_true():
    """Test undo request detection returns True."""
    from src.core.langgraph.nodes.image_analysis_generation.node_services import (
        check_undo_request,
    )

    result = asyncio.run(check_undo_request("undo that change"))
    assert result is True
    print("✓ test_check_undo_request_true passed")


def test_check_undo_request_false():
    """Test non-undo request returns False."""
    from src.core.langgraph.nodes.image_analysis_generation.node_services import (
        check_undo_request,
    )

    result = asyncio.run(check_undo_request("add marble floor"))
    assert result is False
    print("✓ test_check_undo_request_false passed")


def test_should_use_services_with_project_id():
    """Test returns True when project_id is set."""
    from src.core.langgraph.nodes.image_analysis_generation.node_services import (
        should_use_services,
    )

    state = {"project_id": str(uuid4())}
    result = asyncio.run(should_use_services(state))
    assert result is True
    print("✓ test_should_use_services_with_project_id passed")


def test_should_use_services_without_project_id():
    """Test returns False when project_id is not set."""
    from src.core.langgraph.nodes.image_analysis_generation.node_services import (
        should_use_services,
    )

    state = {"project_id": None}
    result = asyncio.run(should_use_services(state))
    assert result is False
    print("✓ test_should_use_services_without_project_id passed")


def test_budget_aware_response_prompt_exists():
    """Test budget aware response prompt is defined."""
    from src.core.langgraph.config import BUDGET_AWARE_RESPONSE

    assert "{budget_sentiment}" in BUDGET_AWARE_RESPONSE
    assert "{room_type}" in BUDGET_AWARE_RESPONSE
    assert "{suggested_materials}" in BUDGET_AWARE_RESPONSE
    print("✓ test_budget_aware_response_prompt_exists passed")


def test_regeneration_clarify_prompt_exists():
    """Test regeneration clarification prompt is defined."""
    from src.core.langgraph.config import REGENERATION_CLARIFY_PROMPT

    assert "Add to the current design" in REGENERATION_CLARIFY_PROMPT
    assert "Start fresh" in REGENERATION_CLARIFY_PROMPT
    print("✓ test_regeneration_clarify_prompt_exists passed")


def test_undo_confirmation_prompt_exists():
    """Test undo confirmation prompt is defined."""
    from src.core.langgraph.config import UNDO_CONFIRMATION_PROMPT

    assert "{change_description}" in UNDO_CONFIRMATION_PROMPT
    print("✓ test_undo_confirmation_prompt_exists passed")


def test_multi_image_room_mismatch_prompt_exists():
    """Test multi-image room mismatch prompt is defined."""
    from src.core.langgraph.config import MULTI_IMAGE_ROOM_MISMATCH

    assert "{room_1}" in MULTI_IMAGE_ROOM_MISMATCH
    assert "{room_2}" in MULTI_IMAGE_ROOM_MISMATCH
    print("✓ test_multi_image_room_mismatch_prompt_exists passed")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Running Service Layer Tests")
    print("=" * 60 + "\n")

    tests = [
        # SessionCache tests
        test_session_cache_basic_operations,
        test_session_cache_miss_returns_none,
        test_session_cache_clear,
        test_session_cache_correction_history,
        # SentimentService tests
        test_sentiment_service_contains_undo_request,
        test_sentiment_service_is_negative_feedback,
        test_sentiment_service_is_positive_feedback,
        # BudgetContextService tests
        test_budget_context_service_has_budget_keywords,
        test_budget_default_materials,
        # ServiceIntegration tests
        test_service_integration_initialization_without_project_id,
        test_service_integration_initialization_with_project_id,
        test_service_integration_from_state,
        test_service_integration_cleanup,
        # State tests
        test_create_minimal_state,
        test_create_initial_state_includes_legacy_fields,
        # Async function tests
        test_check_undo_request_true,
        test_check_undo_request_false,
        test_should_use_services_with_project_id,
        test_should_use_services_without_project_id,
        # Prompt tests
        test_budget_aware_response_prompt_exists,
        test_regeneration_clarify_prompt_exists,
        test_undo_confirmation_prompt_exists,
        test_multi_image_room_mismatch_prompt_exists,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((test.__name__, str(e)))
        except Exception as e:
            failed += 1
            errors.append((test.__name__, f"Error: {type(e).__name__}: {e}"))

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if errors:
        print("\nFailed tests:")
        for name, error in errors:
            print(f"  ✗ {name}: {error}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
