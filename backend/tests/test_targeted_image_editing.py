"""
Test file for Targeted Image Editing with Gemini

Purpose: Test whether prompt engineering alone can achieve targeted editing
         (e.g., only change the floor, keep everything else identical)

Test Cases:
1. Entity Detection - Identify all entities in the room
2. Single Change - Add tiles to floor only
3. Sequential Changes - Floor → Windows → Ceiling (one after another)

Usage:
    cd backend
    python tests/test_targeted_image_editing.py
"""

import os
import sys
import base64
import asyncio
from datetime import datetime
from pathlib import Path
from io import BytesIO

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from PIL import Image

# Import the existing LLMProvider
from src.core.llm.provider import LLMProvider

# =============================================================================
# CONFIGURATION
# =============================================================================

# Input image path - place your test image here
INPUT_IMAGE_PATH = Path(__file__).parent / "bedroom.webp"

# Output directory for generated images
OUTPUT_DIR = Path(__file__).parent / "targeted_editing_output"
OUTPUT_DIR.mkdir(exist_ok=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def encode_image_to_base64(image_path: Path) -> str:
    """Encode image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


def get_mime_type(image_path: Path) -> str:
    """Get MIME type from file extension."""
    ext = image_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


def save_image_from_result(result: dict, output_name: str) -> bool:
    """
    Save image from LLMProvider.generate_image() result.
    Returns True if image was saved, False otherwise.
    """
    try:
        if result.get("image_data"):
            img = Image.open(BytesIO(result["image_data"]))
            output_path = OUTPUT_DIR / output_name
            img.save(output_path)
            print(f"    ✅ Image saved: {output_path}")
            return True
        else:
            print("    ⚠️ No image data in result")
            return False
    except Exception as e:
        print(f"    ❌ Error saving image: {e}")
        return False


async def generate_image_with_prompt(
    prompt: str,
    image_path: Path,
    output_name: str,
    temperature: float = 0.3
) -> dict:
    """
    Generate an image using LLMProvider.for_vgm().generate_image().

    Returns:
        dict with keys: success, text_response, image_saved, output_path
    """
    print(f"\n{'='*60}")
    print(f"📸 Generating: {output_name}")
    print(f"{'='*60}")
    print(f"Prompt: {prompt[:200]}..." if len(prompt) > 200 else f"Prompt: {prompt}")

    try:
        # Get VGM provider (uses correct model from config)
        provider = LLMProvider.for_vgm()
        print(f"    Using model: {provider.model}")

        # Encode image
        base64_image = encode_image_to_base64(image_path)
        mime_type = get_mime_type(image_path)

        # Build messages in the format expected by generate_image
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
            ]
        }]

        # Call generate_image
        result = await provider.generate_image(
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
            operation_type="targeted_editing_test"
        )

        # Extract text response
        text_response = result.get("description", "")
        print(f"\n📝 Response:\n{text_response[:500]}..." if len(text_response) > 500 else f"\n📝 Response:\n{text_response}")

        # Save image
        image_saved = save_image_from_result(result, output_name)

        return {
            "success": True,
            "text_response": text_response,
            "image_saved": image_saved,
            "output_path": str(OUTPUT_DIR / output_name) if image_saved else None
        }

    except Exception as e:
        print(f"    ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "text_response": str(e),
            "image_saved": False,
            "output_path": None
        }


# Sync wrapper for async function
def generate_image_sync(prompt: str, image_path: Path, output_name: str, temperature: float = 0.3) -> dict:
    """Synchronous wrapper for generate_image_with_prompt."""
    return asyncio.run(generate_image_with_prompt(prompt, image_path, output_name, temperature))


# =============================================================================
# TEST 1: ENTITY DETECTION
# =============================================================================

def test_entity_detection():
    """
    Test: Ask Gemini to identify all entities/elements in the room.
    This helps us understand what the model "sees" in the image.
    """
    print("\n" + "="*80)
    print("🔍 TEST 1: ENTITY DETECTION")
    print("="*80)

    prompt = """
    Analyze this room image and identify ALL distinct entities/elements present.

    For each entity, provide:
    1. Entity name (e.g., "window", "floor", "wall")
    2. Location in the image (e.g., "right side", "center", "bottom")
    3. Current condition/appearance

    Format your response as a structured list.

    DO NOT generate an image - only analyze and describe.
    """

    result = generate_image_sync(
        prompt=prompt,
        image_path=INPUT_IMAGE_PATH,
        output_name="01_entity_detection.png",
        temperature=0.2
    )

    return result


# =============================================================================
# TEST 2: SINGLE CHANGE - FLOOR TILES ONLY
# =============================================================================

def test_single_change_floor():
    """
    Test: Change ONLY the floor to tiles, keep everything else identical.
    This is the core test for targeted editing.
    """
    print("\n" + "="*80)
    print("🎯 TEST 2: SINGLE CHANGE - FLOOR TILES ONLY")
    print("="*80)

    prompt = """
    I need you to modify ONLY ONE element in this room image.

    CHANGE ONLY THIS:
    - FLOOR: Replace the current damaged concrete floor with beautiful white marble tiles
      with subtle gray veining. The tiles should be large format (24x24 inch look).

    CRITICAL - DO NOT CHANGE ANYTHING ELSE:
    ❌ DO NOT change the walls (keep the worn plaster exactly as is)
    ❌ DO NOT change the windows (keep the white frames exactly as is)
    ❌ DO NOT change the ceiling (keep it exactly as is)
    ❌ DO NOT change the radiator
    ❌ DO NOT change the hanging light bulb
    ❌ DO NOT add any furniture or objects
    ❌ DO NOT change the lighting or shadows
    ❌ DO NOT change the perspective or room layout

    The ONLY visible difference should be the new marble tile floor.
    Everything else must remain EXACTLY identical to the original image.

    Generate the modified image now.
    """

    result = generate_image_sync(
        prompt=prompt,
        image_path=INPUT_IMAGE_PATH,
        output_name="02_floor_tiles_only.png",
        temperature=0.3
    )

    return result


def test_single_change_floor_v2():
    """
    Test: Alternative prompt style - more concise.
    """
    print("\n" + "="*80)
    print("🎯 TEST 2B: SINGLE CHANGE - FLOOR (CONCISE PROMPT)")
    print("="*80)

    prompt = """
    TASK: Photorealistic image editing

    EDIT: Replace the damaged floor with polished dark hardwood flooring.

    PRESERVE EXACTLY: walls, windows, ceiling, radiator, light bulb, room layout.

    Generate the edited room image.
    """

    result = generate_image_sync(
        prompt=prompt,
        image_path=INPUT_IMAGE_PATH,
        output_name="02b_floor_hardwood_concise.png",
        temperature=0.3
    )

    return result


# =============================================================================
# TEST 3: SINGLE CHANGE - WINDOWS ONLY
# =============================================================================

def test_single_change_windows():
    """
    Test: Change ONLY the windows, keep everything else identical.
    """
    print("\n" + "="*80)
    print("🎯 TEST 3: SINGLE CHANGE - WINDOWS ONLY")
    print("="*80)

    prompt = """
    I need you to modify ONLY the WINDOWS in this room image.

    CHANGE ONLY THIS:
    - WINDOWS: Replace the current old white-framed windows with modern black
      aluminum-framed windows. Same window openings and positions, just update
      the frames to sleek black metal with larger glass panes.

    CRITICAL - DO NOT CHANGE ANYTHING ELSE:
    ❌ DO NOT change the floor (keep the damaged concrete exactly as is)
    ❌ DO NOT change the walls (keep the worn plaster exactly as is)
    ❌ DO NOT change the ceiling
    ❌ DO NOT change the radiator
    ❌ DO NOT change the hanging light bulb
    ❌ DO NOT add any furniture or objects

    The ONLY visible difference should be the new black-framed windows.
    Everything else must remain EXACTLY identical to the original image.

    Generate the modified image now.
    """

    result = generate_image_sync(
        prompt=prompt,
        image_path=INPUT_IMAGE_PATH,
        output_name="03_windows_black_frame.png",
        temperature=0.3
    )

    return result


# =============================================================================
# TEST 4: SINGLE CHANGE - WALLS ONLY
# =============================================================================

def test_single_change_walls():
    """
    Test: Change ONLY the walls, keep everything else identical.
    """
    print("\n" + "="*80)
    print("🎯 TEST 4: SINGLE CHANGE - WALLS ONLY")
    print("="*80)

    prompt = """
    I need you to modify ONLY the WALLS in this room image.

    CHANGE ONLY THIS:
    - WALLS: Replace the current damaged plaster walls with freshly painted
      smooth walls in a warm beige/cream color. Clean, modern finish.

    CRITICAL - DO NOT CHANGE ANYTHING ELSE:
    ❌ DO NOT change the floor (keep the damaged concrete exactly as is)
    ❌ DO NOT change the windows (keep the white frames exactly as is)
    ❌ DO NOT change the ceiling
    ❌ DO NOT change the radiator
    ❌ DO NOT change the hanging light bulb
    ❌ DO NOT add any furniture or objects

    The ONLY visible difference should be the freshly painted walls.
    Everything else must remain EXACTLY identical to the original image.

    Generate the modified image now.
    """

    result = generate_image_sync(
        prompt=prompt,
        image_path=INPUT_IMAGE_PATH,
        output_name="04_walls_painted.png",
        temperature=0.3
    )

    return result


# =============================================================================
# TEST 5: SINGLE CHANGE - CEILING/LIGHTING ONLY
# =============================================================================

def test_single_change_ceiling():
    """
    Test: Change ONLY the ceiling/lighting, keep everything else identical.
    """
    print("\n" + "="*80)
    print("🎯 TEST 5: SINGLE CHANGE - CEILING/LIGHTING ONLY")
    print("="*80)

    prompt = """
    I need you to modify ONLY the CEILING and LIGHTING in this room image.

    CHANGE ONLY THIS:
    - CEILING: Clean, freshly painted white ceiling
    - LIGHTING: Replace the bare hanging bulb with a modern pendant light fixture
      (simple black dome pendant with warm light)

    CRITICAL - DO NOT CHANGE ANYTHING ELSE:
    ❌ DO NOT change the floor (keep the damaged concrete exactly as is)
    ❌ DO NOT change the walls (keep the worn plaster exactly as is)
    ❌ DO NOT change the windows (keep them exactly as is)
    ❌ DO NOT change the radiator
    ❌ DO NOT add any furniture or objects

    The ONLY visible differences should be the clean ceiling and new pendant light.
    Everything else must remain EXACTLY identical to the original image.

    Generate the modified image now.
    """

    result = generate_image_sync(
        prompt=prompt,
        image_path=INPUT_IMAGE_PATH,
        output_name="05_ceiling_lighting.png",
        temperature=0.3
    )

    return result


# =============================================================================
# TEST 6: SEQUENTIAL CHANGES (Simulating User Flow)
# =============================================================================

def test_sequential_changes():
    """
    Test: Sequential changes like a real user would do.

    Step 1: Start with original → Change floor
    Step 2: Take Step 1 result → Change windows
    Step 3: Take Step 2 result → Change walls
    Step 4: Take Step 3 result → Change ceiling

    This simulates: User makes one change, sees result, then asks for next change.
    """
    print("\n" + "="*80)
    print("🔄 TEST 6: SEQUENTIAL CHANGES (SIMULATING USER FLOW)")
    print("="*80)

    # We'll use the original image for each step since we can't guarantee
    # the previous step's image will be available. In production, you'd
    # use the actual output from the previous step.

    current_image = INPUT_IMAGE_PATH
    results = []

    # Step 1: Floor
    print("\n📍 STEP 1/4: Changing Floor")
    step1_prompt = """
    Starting renovation of this room.

    FIRST CHANGE - FLOOR ONLY:
    Replace the damaged concrete floor with light oak hardwood flooring.

    Keep everything else EXACTLY as is (walls, windows, ceiling, radiator, light).

    Generate the image with only the floor changed.
    """
    step1_result = generate_image_sync(
        prompt=step1_prompt,
        image_path=current_image,
        output_name="06_seq_step1_floor.png"
    )
    results.append(("Step 1 - Floor", step1_result))

    # For sequential test, ideally use previous output
    # But for now, we use original + cumulative prompt

    # Step 2: Floor + Windows
    print("\n📍 STEP 2/4: Adding Window Changes")
    step2_prompt = """
    Continue renovation of this room.

    CHANGES TO APPLY:
    1. FLOOR: Light oak hardwood flooring (already planned)
    2. WINDOWS: Modern double-pane windows with slim black frames

    Keep everything else EXACTLY as is (walls, ceiling, radiator).

    Generate the image with floor and windows changed.
    """
    step2_result = generate_image_sync(
        prompt=step2_prompt,
        image_path=current_image,
        output_name="06_seq_step2_floor_windows.png"
    )
    results.append(("Step 2 - Floor + Windows", step2_result))

    # Step 3: Floor + Windows + Walls
    print("\n📍 STEP 3/4: Adding Wall Changes")
    step3_prompt = """
    Continue renovation of this room.

    CHANGES TO APPLY:
    1. FLOOR: Light oak hardwood flooring
    2. WINDOWS: Modern windows with black frames
    3. WALLS: Fresh white paint with smooth finish

    Keep ceiling and radiator as is.

    Generate the image with floor, windows, and walls changed.
    """
    step3_result = generate_image_sync(
        prompt=step3_prompt,
        image_path=current_image,
        output_name="06_seq_step3_floor_windows_walls.png"
    )
    results.append(("Step 3 - Floor + Windows + Walls", step3_result))

    # Step 4: Complete Renovation
    print("\n📍 STEP 4/4: Final - Adding Ceiling/Lighting")
    step4_prompt = """
    Final step of room renovation.

    ALL CHANGES TO APPLY:
    1. FLOOR: Light oak hardwood flooring
    2. WINDOWS: Modern windows with black frames
    3. WALLS: Fresh white paint with smooth finish
    4. CEILING: Clean white painted ceiling
    5. LIGHTING: Modern minimalist pendant light (replace bare bulb)

    The radiator can stay or be replaced with a sleek modern one.

    Generate the fully renovated room image.
    """
    step4_result = generate_image_sync(
        prompt=step4_prompt,
        image_path=current_image,
        output_name="06_seq_step4_complete.png"
    )
    results.append(("Step 4 - Complete", step4_result))

    return results


# =============================================================================
# TEST 7: NEGATIVE TEST - What happens with vague prompt?
# =============================================================================

def test_vague_prompt():
    """
    Test: What happens when we give a vague prompt without strict constraints?
    This helps us understand the baseline behavior.
    """
    print("\n" + "="*80)
    print("⚠️ TEST 7: VAGUE PROMPT (BASELINE)")
    print("="*80)

    prompt = """
    Make this room look better. Add nice flooring.

    Generate the improved room image.
    """

    result = generate_image_sync(
        prompt=prompt,
        image_path=INPUT_IMAGE_PATH,
        output_name="07_vague_prompt_baseline.png",
        temperature=0.5
    )

    return result


# =============================================================================
# TEST 8: EXTREME CONSTRAINT PROMPT
# =============================================================================

def test_extreme_constraint():
    """
    Test: Very strict constraint prompt to see maximum preservation.
    """
    print("\n" + "="*80)
    print("🔒 TEST 8: EXTREME CONSTRAINT PROMPT")
    print("="*80)

    prompt = """
    ⚠️ CRITICAL IMAGE EDITING TASK - READ CAREFULLY ⚠️

    You are performing SURGICAL image editing. This is NOT a full renovation.

    ═══════════════════════════════════════════════════════════════════════
    CHANGE EXACTLY ONE THING:
    ═══════════════════════════════════════════════════════════════════════

    FLOOR → Replace with herringbone pattern light wood flooring

    ═══════════════════════════════════════════════════════════════════════
    PRESERVE WITH 100% PIXEL ACCURACY:
    ═══════════════════════════════════════════════════════════════════════

    ✓ Walls - IDENTICAL damaged plaster, same colors, same textures
    ✓ Windows - IDENTICAL white frames, same glass, same position
    ✓ Ceiling - IDENTICAL condition, same cracks if any
    ✓ Radiator - IDENTICAL white radiator under window
    ✓ Light bulb - IDENTICAL hanging bare bulb with wire
    ✓ Room dimensions - IDENTICAL perspective and proportions
    ✓ Lighting/shadows - IDENTICAL natural light from windows
    ✓ Wall outlets - IDENTICAL position and appearance

    If ANY element besides the floor looks different, the task has FAILED.

    Generate the image now with ONLY the floor changed.
    """

    result = generate_image_sync(
        prompt=prompt,
        image_path=INPUT_IMAGE_PATH,
        output_name="08_extreme_constraint.png",
        temperature=0.2
    )

    return result


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_all_tests():
    """Run all tests and generate summary report."""

    print("\n" + "🚀"*40)
    print("\n    TARGETED IMAGE EDITING - PROMPT ENGINEERING TEST SUITE")
    print(f"    Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    Input Image: {INPUT_IMAGE_PATH}")
    print(f"    Output Directory: {OUTPUT_DIR}")
    print("\n" + "🚀"*40)

    # Check if input image exists
    if not INPUT_IMAGE_PATH.exists():
        print(f"\n❌ ERROR: Input image not found at {INPUT_IMAGE_PATH}")
        print("Please place your test image (bedroom.webp) in the tests folder.")
        return

    results = {}

    # Run tests
    print("\n\n" + "="*80)
    print("RUNNING TESTS...")
    print("="*80)

    # Test 1: Entity Detection (no image generation expected, but might still generate)
    results["entity_detection"] = test_entity_detection()

    # Test 2: Single Change - Floor
    results["floor_tiles"] = test_single_change_floor()
    results["floor_tiles_v2"] = test_single_change_floor_v2()

    # Test 3: Single Change - Windows
    results["windows"] = test_single_change_windows()

    # Test 4: Single Change - Walls
    results["walls"] = test_single_change_walls()

    # Test 5: Single Change - Ceiling
    results["ceiling"] = test_single_change_ceiling()

    # Test 6: Sequential Changes
    results["sequential"] = test_sequential_changes()

    # Test 7: Vague Prompt (baseline)
    results["vague"] = test_vague_prompt()

    # Test 8: Extreme Constraint
    results["extreme"] = test_extreme_constraint()

    # Summary
    print("\n\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)

    for test_name, result in results.items():
        if isinstance(result, list):  # Sequential test returns list
            print(f"\n{test_name}:")
            for step_name, step_result in result:
                status = "✅" if step_result.get("image_saved") else "❌"
                print(f"  {status} {step_name}")
        else:
            status = "✅" if result.get("image_saved") else "⚠️ (no image)"
            print(f"{status} {test_name}")

    print(f"\n\n📁 Output images saved to: {OUTPUT_DIR}")
    print(f"⏱️  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Instructions for evaluation
    print("\n" + "="*80)
    print("📋 EVALUATION CHECKLIST")
    print("="*80)
    print("""
    For each generated image, check:

    1. ✓ Did the requested element change correctly?
    2. ✓ Did OTHER elements stay EXACTLY the same?
    3. ✓ Is the perspective/layout preserved?
    4. ✓ Is the lighting consistent?
    5. ✓ Any unwanted additions (furniture, objects)?

    Key questions:
    - Does strict prompting prevent hallucinations?
    - Is single-element editing reliable?
    - Does prompt style (verbose vs concise) matter?
    """)


def run_single_test(test_name: str):
    """Run a single test by name."""

    if not INPUT_IMAGE_PATH.exists():
        print(f"❌ ERROR: Input image not found at {INPUT_IMAGE_PATH}")
        return

    tests = {
        "entity": test_entity_detection,
        "floor": test_single_change_floor,
        "floor_v2": test_single_change_floor_v2,
        "windows": test_single_change_windows,
        "walls": test_single_change_walls,
        "ceiling": test_single_change_ceiling,
        "sequential": test_sequential_changes,
        "vague": test_vague_prompt,
        "extreme": test_extreme_constraint,
    }

    if test_name not in tests:
        print(f"❌ Unknown test: {test_name}")
        print(f"Available tests: {', '.join(tests.keys())}")
        return

    return tests[test_name]()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        run_single_test(test_name)
    else:
        # Run all tests
        run_all_tests()
