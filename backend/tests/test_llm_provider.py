"""
Test suite for LLM Provider

Run this script directly: python -m tests.test_llm_provider
"""

import asyncio
import os
import sys
import base64
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider, UnsupportedImageFormatError, LLMProviderError


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


def create_test_image_base64() -> str:
    """Create a simple test image in base64 format (1x1 red PNG)"""
    # 1x1 red pixel PNG
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(png_bytes).decode('utf-8')


async def test_text_completion():
    """Test 1: Simple text completion (non-streaming)"""
    test_name = "Text completion (non-streaming)"
    try:
        provider = LLMProvider()
        
        response = await provider.complete(
            messages=[
                {"role": "user", "content": "Say 'Hello' and nothing else."}
            ],
            max_tokens=50,
            temperature=0.0
        )
        
        assert isinstance(response, str), "Response should be a string"
        assert len(response) > 0, "Response should not be empty"
        
        print_test(test_name, True, f"Response: {response[:100]}")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def test_streaming_completion():
    """Test 2: Streaming text completion"""
    test_name = "Text completion (streaming)"
    try:
        provider = LLMProvider()
        
        chunks = []
        async for chunk in provider.complete_stream(
            messages=[
                {"role": "user", "content": "Count from 1 to 5."}
            ],
            max_tokens=100,
            temperature=0.0
        ):
            chunks.append(chunk)
        
        full_response = "".join(chunks)
        
        assert len(chunks) > 0, "Should receive at least one chunk"
        assert len(full_response) > 0, "Full response should not be empty"
        
        print_test(test_name, True, f"Received {len(chunks)} chunks, total length: {len(full_response)}")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def test_multimodal_completion():
    """Test 3: Multimodal completion with image"""
    test_name = "Multimodal completion (text + image)"
    try:
        provider = LLMProvider()
        
        # Create a test image
        test_image_b64 = create_test_image_base64()
        
        response = await provider.complete(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What color is in this image? Reply with just the color name."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{test_image_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=50,
            temperature=0.0
        )
        
        assert isinstance(response, str), "Response should be a string"
        assert len(response) > 0, "Response should not be empty"
        
        print_test(test_name, True, f"Response: {response[:100]}")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def test_multimodal_streaming():
    """Test 4: Multimodal streaming with image"""
    test_name = "Multimodal streaming (text + image)"
    try:
        provider = LLMProvider()
        
        # Create a test image
        test_image_b64 = create_test_image_base64()
        
        chunks = []
        async for chunk in provider.complete_stream(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image briefly."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{test_image_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=100,
            temperature=0.0
        ):
            chunks.append(chunk)
        
        full_response = "".join(chunks)
        
        assert len(chunks) > 0, "Should receive at least one chunk"
        assert len(full_response) > 0, "Full response should not be empty"
        
        print_test(test_name, True, f"Received {len(chunks)} chunks")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def test_unsupported_image_format():
    """Test 5: Unsupported image format validation"""
    test_name = "Unsupported image format validation"
    try:
        provider = LLMProvider()
        
        # Try to use an unsupported format (GIF)
        test_image_b64 = create_test_image_base64()
        
        try:
            await provider.complete(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What's in this image?"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/gif;base64,{test_image_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=50
            )
            
            # Should not reach here
            print_test(test_name, False, "Expected UnsupportedImageFormatError but none was raised")
            return False
            
        except UnsupportedImageFormatError as e:
            # Expected error
            print_test(test_name, True, f"Correctly raised error: {str(e)}")
            return True
            
    except Exception as e:
        print_test(test_name, False, f"Unexpected error: {str(e)}")
        return False


async def test_invalid_data_url():
    """Test 6: Invalid data URL format"""
    test_name = "Invalid data URL format validation"
    try:
        provider = LLMProvider()
        
        try:
            await provider.complete(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What's in this image?"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "not-a-data-url"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=50
            )
            
            # Should not reach here
            print_test(test_name, False, "Expected UnsupportedImageFormatError but none was raised")
            return False
            
        except UnsupportedImageFormatError as e:
            # Expected error
            print_test(test_name, True, f"Correctly raised error: {str(e)}")
            return True
            
    except Exception as e:
        print_test(test_name, False, f"Unexpected error: {str(e)}")
        return False


async def test_provider_override():
    """Test 7: Provider configuration override"""
    test_name = "Provider configuration override"
    try:
        # Get default config
        default_provider = LLMProvider()
        default_model = default_provider.model
        
        # Try to override (note: won't actually call API with different model)
        # Just testing that the configuration is accepted
        custom_provider = LLMProvider(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            api_key=os.getenv("LLM_API_KEY", "test-key")
        )
        
        assert custom_provider.model is not None, "Custom provider should have a model"
        
        print_test(test_name, True, f"Default model: {default_model}, Custom provider initialized")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def test_parallel_calls():
    """Test 8: Multiple parallel requests (no shared state)"""
    test_name = "Parallel requests (no shared state)"
    try:
        provider1 = LLMProvider()
        provider2 = LLMProvider()
        provider3 = LLMProvider()
        
        # Make 3 parallel requests
        results = await asyncio.gather(
            provider1.complete(
                messages=[{"role": "user", "content": "Say 'Request 1'"}],
                max_tokens=20,
                temperature=0.0
            ),
            provider2.complete(
                messages=[{"role": "user", "content": "Say 'Request 2'"}],
                max_tokens=20,
                temperature=0.0
            ),
            provider3.complete(
                messages=[{"role": "user", "content": "Say 'Request 3'"}],
                max_tokens=20,
                temperature=0.0
            ),
        )
        
        assert len(results) == 3, "Should receive 3 responses"
        assert all(isinstance(r, str) and len(r) > 0 for r in results), "All responses should be non-empty strings"
        
        print_test(test_name, True, f"Successfully completed {len(results)} parallel requests")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def test_conversation():
    """Test 9: Multi-turn conversation"""
    test_name = "Multi-turn conversation"
    try:
        provider = LLMProvider()
        
        response = await provider.complete(
            messages=[
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Hello Alice! Nice to meet you."},
                {"role": "user", "content": "What is my name?"}
            ],
            max_tokens=50,
            temperature=0.0
        )
        
        assert isinstance(response, str), "Response should be a string"
        assert len(response) > 0, "Response should not be empty"
        
        print_test(test_name, True, f"Response: {response[:100]}")
        return True
        
    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("LLM Provider Test Suite")
    print("="*60 + "\n")
    
    # Check if environment variables are set
    if not os.getenv("LLM_PROVIDER") or not os.getenv("LLM_MODEL") or not os.getenv("LLM_API_KEY"):
        print("\033[91m✗ Error: Missing environment variables\033[0m")
        print("Please set LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY in your .env file")
        print("\nExample:")
        print("  LLM_PROVIDER=openai")
        print("  LLM_MODEL=gpt-4o")
        print("  LLM_API_KEY=sk-...")
        return
    
    print(f"Provider: {os.getenv('LLM_PROVIDER')}")
    print(f"Model: {os.getenv('LLM_MODEL')}")
    print("\n" + "-"*60 + "\n")
    
    # Run tests
    results = []
    
    # Basic text tests
    results.append(await test_text_completion())
    results.append(await test_streaming_completion())
    results.append(await test_conversation())
    
    # Multimodal tests (only if vision model)
    model_name = os.getenv('LLM_MODEL', '').lower()
    is_vision_model = any(x in model_name for x in ['gpt-4o', 'gpt-4-vision', 'claude-3', 'gemini', 'vision'])
    
    if is_vision_model:
        print("\n" + "-"*60)
        print("Vision Model Detected - Running Multimodal Tests")
        print("-"*60 + "\n")
        results.append(await test_multimodal_completion())
        results.append(await test_multimodal_streaming())
    else:
        print("\n" + "-"*60)
        print("Non-Vision Model - Skipping Multimodal Tests")
        print("-"*60 + "\n")
    
    # Validation tests
    results.append(await test_unsupported_image_format())
    results.append(await test_invalid_data_url())
    
    # Configuration tests
    results.append(await test_provider_override())
    
    # Parallel test
    results.append(await test_parallel_calls())
    
    # Summary
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"\033[92m✓ All tests passed! ({passed}/{total})\033[0m")
    else:
        print(f"\033[91m✗ Some tests failed: {passed}/{total} passed\033[0m")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
