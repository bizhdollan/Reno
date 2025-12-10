import asyncio
import os
import sys
import base64
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider, LLMProviderError


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


def load_image_as_base64(image_path: str) -> str:
    """
    Load image file and convert to base64 data URL.
    
    Args:
        image_path: Path to the image file (relative to test file or absolute)
        
    Returns:
        Base64 encoded data URL string
    """
    # If path is relative, make it relative to the test file directory
    if not Path(image_path).is_absolute():
        image_file = Path(__file__).parent / image_path
    else:
        image_file = Path(image_path)
    
    if not image_file.exists():
        raise FileNotFoundError(f"Image file not found: {image_file}")
    
    with open(image_file, 'rb') as f:
        image_data = f.read()
    
    b64_data = base64.b64encode(image_data).decode('utf-8')
    return f"data:image/jpeg;base64,{b64_data}"


async def test_with_prompt(
    provider: LLMProvider,
    image_url: str,
    prompt: str,
    test_name: str,
    max_tokens: int = 300,
    min_length: int = 1
) -> bool:
    """
    Run a single test with given prompt and image.
    
    Args:
        provider: LLMProvider instance
        image_url: Base64 encoded image data URL
        prompt: Text prompt to send with the image
        test_name: Name of the test
        max_tokens: Maximum tokens for response
        min_length: Minimum response length (default: 1 for short answers)
        
    Returns:
        True if test passed, False otherwise
    """
    try:
        response = await provider.complete(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],
            temperature=0.3,
            max_tokens=max_tokens
        )
        
        # Validate response
        assert isinstance(response, str), "Response should be a string"
        assert len(response) > 0, "Response should not be empty"
        assert len(response) >= min_length, f"Response should be at least {min_length} character(s)"
        
        print_test(test_name, True, f"Response: {response[:200]}...")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def test_general_description(provider: LLMProvider, image_url: str) -> bool:
    """Test 1: General Description"""
    return await test_with_prompt(
        provider=provider,
        image_url=image_url,
        prompt="Describe this room in 2-3 sentences.",
        test_name="Test 1: General Description",
        min_length=20  # Expect substantial response
    )


async def test_room_type_identification(provider: LLMProvider, image_url: str) -> bool:
    """Test 2: Room Type Identification"""
    return await test_with_prompt(
        provider=provider,
        image_url=image_url,
        prompt="What type of room is this? Answer in one word or short phrase.",
        test_name="Test 2: Room Type Identification",
        max_tokens=50,
        min_length=1  # Allow short responses for this test
    )


async def test_color_analysis(provider: LLMProvider, image_url: str) -> bool:
    """Test 3: Color Analysis"""
    return await test_with_prompt(
        provider=provider,
        image_url=image_url,
        prompt="What are the main colors you see in this image? List them.",
        test_name="Test 3: Color Analysis",
        max_tokens=150,
        min_length=20
    )


async def test_appliance_identification(provider: LLMProvider, image_url: str) -> bool:
    """Test 4: Specific Element Identification"""
    return await test_with_prompt(
        provider=provider,
        image_url=image_url,
        prompt="List the major appliances you can see in this kitchen.",
        test_name="Test 4: Appliance Identification",
        max_tokens=200,
        min_length=20
    )


async def test_material_style_analysis(provider: LLMProvider, image_url: str) -> bool:
    """Test 5: Material/Style Analysis"""
    return await test_with_prompt(
        provider=provider,
        image_url=image_url,
        prompt="Describe the cabinet style and island color. Be specific.",
        test_name="Test 5: Material/Style Analysis",
        max_tokens=200,
        min_length=20
    )


async def test_renovation_analysis(provider: LLMProvider, image_url: str) -> bool:
    """Test 6: Renovation-Specific Analysis"""
    return await test_with_prompt(
        provider=provider,
        image_url=image_url,
        prompt="From a renovation perspective, describe the key features of this kitchen including countertops, backsplash, and fixtures. Focus on materials and finishes.",
        test_name="Test 6: Renovation-Specific Analysis",
        max_tokens=400,
        min_length=20
    )


async def test_streaming_with_image(provider: LLMProvider, image_url: str) -> bool:
    """Test 7: Streaming with Image"""
    test_name = "Test 7: Streaming with Image"
    try:
        chunks = []
        async for chunk in provider.complete_stream(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this room in 2-3 sentences."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],
            temperature=0.3,
            max_tokens=300
        ):
            chunks.append(chunk)
        
        full_response = "".join(chunks)
        
        assert len(chunks) > 0, "Should receive at least one chunk"
        assert len(full_response) > 0, "Full response should not be empty"
        assert len(full_response) > 20, "Response should be substantial"
        
        print_test(test_name, True, f"Received {len(chunks)} chunks, response: {full_response[:200]}...")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def test_detailed_kitchen_features(provider: LLMProvider, image_url: str) -> bool:
    """Test 8: Detailed Kitchen Features (Bonus test)"""
    return await test_with_prompt(
        provider=provider,
        image_url=image_url,
        prompt="Identify and describe: 1) The lighting fixtures, 2) The flooring material, 3) The backsplash design behind the stove.",
        test_name="Test 8: Detailed Kitchen Features",
        max_tokens=300,
        min_length=20
    )


async def main():
    """Run all real image vision tests"""
    print("\n" + "="*60)
    print("Real Image Vision Test Suite")
    print("="*60 + "\n")
    
    # Check if environment variables are set
    if not os.getenv("LLM_PROVIDER") or not os.getenv("LLM_MODEL") or not os.getenv("LLM_API_KEY"):
        print("\033[91m✗ Error: Missing environment variables\033[0m")
        print("Please set LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY in your .env file")
        return
    
    # Check if using a vision-capable model
    model_name = os.getenv('LLM_MODEL', '').lower()
    is_vision_model = any(x in model_name for x in [
        'gpt-4o', 'gpt-4-vision', 'gpt-4-turbo', 'gpt-4',
        'claude-3', 'claude-3-5', 'claude-3-opus', 'claude-3-sonnet',
        'gemini', 'gemini-pro', 'gemini-1.5'
    ])
    
    if not is_vision_model:
        print("\033[93m⚠️  Warning: Model may not support vision capabilities\033[0m")
        print(f"Current model: {os.getenv('LLM_MODEL')}")
        print("Vision models include: gpt-4o, claude-3-5-sonnet, gemini-1.5-pro")
        print("\nContinuing anyway...\n")
    
    print(f"Provider: {os.getenv('LLM_PROVIDER')}")
    print(f"Model: {os.getenv('LLM_MODEL')}")
    print("\n" + "-"*60 + "\n")
    
    # Load the real image
    try:
        print("Loading image: 1.jpeg...")
        image_url = load_image_as_base64("1.jpeg")
        print(f"✓ Image loaded successfully ({len(image_url)} chars in base64)\n")
    except FileNotFoundError as e:
        print(f"\033[91m✗ Error: {str(e)}\033[0m")
        print("Make sure 1.jpeg exists in the tests directory")
        return
    except Exception as e:
        print(f"\033[91m✗ Error loading image: {str(e)}\033[0m")
        return
    
    # Initialize provider
    try:
        provider = LLMProvider()
        print(f"✓ LLM Provider initialized\n")
    except Exception as e:
        print(f"\033[91m✗ Error initializing provider: {str(e)}\033[0m")
        return
    
    print("="*60)
    print("Running Vision Tests")
    print("="*60 + "\n")
    
    # Run all tests
    results = []
    
    results.append(await test_general_description(provider, image_url))
    print()
    
    results.append(await test_room_type_identification(provider, image_url))
    print()
    
    results.append(await test_color_analysis(provider, image_url))
    print()
    
    results.append(await test_appliance_identification(provider, image_url))
    print()
    
    results.append(await test_material_style_analysis(provider, image_url))
    print()
    
    results.append(await test_renovation_analysis(provider, image_url))
    print()
    
    results.append(await test_streaming_with_image(provider, image_url))
    print()
    
    results.append(await test_detailed_kitchen_features(provider, image_url))
    print()
    
    # Summary
    print("="*60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"\033[92m✓ All tests passed! ({passed}/{total})\033[0m")
    else:
        print(f"\033[91m✗ Some tests failed: {passed}/{total} passed\033[0m")
    
    print("="*60 + "\n")
    
    # Additional info
    if passed == total:
        print("\033[92m✓ Vision capabilities verified successfully!\033[0m")
        print("The LLM provider can process real images and provide relevant analysis.")
    else:
        print("\033[93m⚠️  Some tests failed. Check the error messages above.\033[0m")
        print("Common issues:")
        print("  - Model doesn't support vision")
        print("  - API key invalid or insufficient credits")
        print("  - Network/API errors")


if __name__ == "__main__":
    asyncio.run(main())
