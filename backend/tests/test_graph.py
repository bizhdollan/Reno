"""
Test the LangGraph conversation flow.

Run: python tests/test_graph.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.langgraph import create_initial_state, run_conversation
from tests.conftest import ok, fail, load_image


async def test_project_basics_flow():
    """Test collecting project basics one at a time."""
    print("\n--- Project Basics Flow ---\n")
    
    project_id = "test_001"
    state = create_initial_state()
    
    # Turn 1: Start - should ask for title
    state, response = await run_conversation(project_id, "Hi, I want to renovate", state)
    print(f"AI: {response}\n")
    assert "title" in response.lower() or "call" in response.lower()
    ok("Asked for project title")
    
    # Turn 2: Give title - should ask for type
    state, response = await run_conversation(project_id, "Kitchen Makeover", state)
    print(f"AI: {response}\n")
    assert state.get("project_title") is not None
    ok("Captured title", state.get("project_title"))
    
    # Turn 3: Give type - should ask for zip
    state, response = await run_conversation(project_id, "It's a kitchen", state)
    print(f"AI: {response}\n")
    assert state.get("project_type") is not None
    ok("Captured type", state.get("project_type"))
    
    # Turn 4: Give zip - should move to visual collection
    state, response = await run_conversation(project_id, "94102", state)
    print(f"AI: {response}\n")
    assert state.get("zip_code") is not None
    assert state.get("current_stage") == "visual_collection"
    ok("Moved to visual_collection stage")
    
    return state


async def test_visual_collection_flow(state):
    """Test image upload and confirmation."""
    print("\n--- Visual Collection Flow ---\n")
    
    project_id = "test_001"
    
    # Load test image
    try:
        image_url = load_image("1.jpeg")
    except FileNotFoundError:
        print("⚠ No test image, skipping visual collection test")
        return state
    
    # Upload image
    multimodal_message = [
        {"type": "text", "text": "Here's a photo of my kitchen"},
        {"type": "image_url", "image_url": {"url": image_url}}
    ]
    
    state, response = await run_conversation(project_id, multimodal_message, state)
    print(f"AI: {response[:300]}...\n")
    
    assert len(state.get("images", [])) > 0
    ok("Image processed", f"{len(state.get('images', []))} images")
    
    # Continue to next stage
    state, response = await run_conversation(project_id, "Looks good, continue", state)
    print(f"AI: {response}\n")
    
    ok("Visual collection done", f"Stage: {state.get('current_stage')}")
    
    return state


async def test_quick_flow():
    """Quick test: provide all info at once."""
    print("\n--- Quick Flow Test ---\n")
    
    project_id = "test_quick"
    state = create_initial_state()
    
    # Provide all basics at once
    state, response = await run_conversation(
        project_id, 
        "I want to do a kitchen renovation in 94102, call it Kitchen Refresh",
        state
    )
    print(f"AI: {response}\n")
    
    # Check if extracted
    print(f"Title: {state.get('project_title')}")
    print(f"Type: {state.get('project_type')}")
    print(f"Zip: {state.get('zip_code')}")
    print(f"Stage: {state.get('current_stage')}")
    
    if state.get("project_title") and state.get("project_type") and state.get("zip_code"):
        ok("Extracted all basics from single message")
    else:
        fail("Did not extract all basics")


async def main():
    print("\n" + "=" * 50)
    print("LangGraph Flow Tests")
    print("=" * 50)
    
    try:
        await test_quick_flow()
        state = await test_project_basics_flow()
        await test_visual_collection_flow(state)
        print("\n" + "=" * 50)
        ok("All tests completed!")
        print("=" * 50 + "\n")
    except Exception as e:
        fail("Test failed", str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())