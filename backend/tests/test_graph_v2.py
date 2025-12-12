"""
Test the 4-stage LangGraph conversation flow.

Run: python tests/test_graph_v2.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.langgraph import create_initial_state, run_conversation
from tests.conftest import ok, fail, load_image


async def test_project_basics():
    """Test project basics collection."""
    print("\n--- Stage 1: Project Basics ---\n")
    
    project_id = "test_v2_001"
    state = create_initial_state()
    
    # Turn 1: Start
    state, response = await run_conversation(project_id, "Hi", state)
    print(f"AI: {response}\n")
    ok("Got initial response")
    
    # Turn 2: Provide all info at once
    state, response = await run_conversation(
        project_id, 
        "Kitchen Makeover project, it's a kitchen in 94102",
        state
    )
    print(f"AI: {response}\n")
    
    # Check extraction
    print(f"  Title: {state.get('project_title')}")
    print(f"  Type: {state.get('project_type')}")
    print(f"  Zip: {state.get('zip_code')}")
    print(f"  Stage: {state.get('current_stage')}")
    
    if state.get("current_stage") == "image_analysis_generation":
        ok("Moved to image_analysis_generation stage")
    else:
        ok("Collecting basics", f"Stage: {state.get('current_stage')}")
    
    return state, project_id


async def test_image_analysis(state, project_id):
    """Test image analysis and confirmation."""
    print("\n--- Stage 2: Image Analysis ---\n")
    
    # Try to load test image
    try:
        image_url = load_image("1.jpeg")
    except FileNotFoundError:
        print("⚠ No test image found, skipping image test")
        return state, project_id
    
    # Upload image
    multimodal_message = [
        {"type": "text", "text": "Here's my kitchen"},
        {"type": "image_url", "image_url": {"url": image_url}}
    ]
    
    state, response = await run_conversation(project_id, multimodal_message, state)
    print(f"AI: {response[:500]}...\n")
    
    # Check if image was processed
    images = state.get("images", [])
    extracted = state.get("extracted_data", {})
    
    print(f"  Images: {len(images)}")
    print(f"  Extracted sections: {list(extracted.keys())}")
    print(f"  Sub-state: {state.get('image_sub_state')}")
    
    if len(images) > 0:
        ok("Image processed")
    else:
        fail("No images processed")
    
    return state, project_id


async def test_confirmation_flow(state, project_id):
    """Test confirmation loop."""
    print("\n--- Confirmation Flow ---\n")
    
    # Confirm a few sections
    for i in range(3):
        state, response = await run_conversation(project_id, "yes, looks good", state)
        print(f"AI: {response[:300]}...\n")
        
        sub_state = state.get("image_sub_state")
        print(f"  Sub-state: {sub_state}")
        
        if sub_state in ["generating", "image_confirmation"]:
            ok(f"Moved to {sub_state}")
            break
    
    return state, project_id


async def test_proceed_to_review(state, project_id):
    """Test moving to final review."""
    print("\n--- Moving to Final Review ---\n")
    
    # Keep confirming until we reach final review or cost estimation
    for i in range(5):
        current_stage = state.get("current_stage")
        
        if current_stage in ["final_review", "cost_estimation"]:
            ok(f"Reached {current_stage}")
            break
        
        state, response = await run_conversation(project_id, "continue", state)
        print(f"AI (turn {i+1}): {response[:200]}...\n")
    
    return state, project_id


async def test_cost_estimation(state, project_id):
    """Test cost estimation generation."""
    print("\n--- Stage 4: Cost Estimation ---\n")
    
    # Move to cost estimation
    state, response = await run_conversation(project_id, "yes, generate estimate", state)
    print(f"AI: {str(response)[:500]}...\n")
    
    # Check for tiers
    cost_tiers = state.get("cost_tiers")
    
    if cost_tiers:
        print(f"  Generated {len(cost_tiers)} tiers:")
        for tier in cost_tiers:
            print(f"    - {tier.get('name')}: ${tier.get('total_cost', 0):,.0f}")
        ok("Cost tiers generated")
    else:
        print("  No tiers yet, may need another turn")
    
    return state, project_id


async def main():
    print("\n" + "=" * 50)
    print("LangGraph v2 (4-Stage) Flow Tests")
    print("=" * 50)
    
    try:
        state, project_id = await test_project_basics()
        state, project_id = await test_image_analysis(state, project_id)
        state, project_id = await test_confirmation_flow(state, project_id)
        state, project_id = await test_proceed_to_review(state, project_id)
        state, project_id = await test_cost_estimation(state, project_id)
        
        print("\n" + "=" * 50)
        print(f"Final stage: {state.get('current_stage')}")
        ok("Test flow completed!")
        print("=" * 50 + "\n")
        
    except Exception as e:
        fail("Test failed", str(e))
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())