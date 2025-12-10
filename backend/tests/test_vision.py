"""
Test vision/multimodal.

Run: python tests/test_vision.py

Requires: tests/1.jpeg
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider, UnsupportedImageFormatError
from tests.conftest import ok, fail, load_image


async def main():
    print("\n=== Vision Tests ===\n")
    
    provider = LLMProvider.for_vlm()
    
    # Load test image
    try:
        image_url = load_image("1.jpeg")
        ok("Image loaded")
    except FileNotFoundError:
        fail("Image not found", "Place 1.jpeg in tests/")
        return
    
    # Test 1: Image description
    try:
        response = await provider.complete(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What room is this? One word."},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }],
            max_tokens=20
        )
        assert len(response) > 0
        ok("Image description", response[:50])
    except Exception as e:
        fail("Image description", str(e))
    
    # Test 2: Image streaming
    try:
        chunks = []
        async for chunk in provider.complete_stream(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "List 3 colors you see."},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }],
            max_tokens=50
        ):
            chunks.append(chunk)
        assert len(chunks) > 1
        ok("Image streaming", f"{len(chunks)} chunks")
    except Exception as e:
        fail("Image streaming", str(e))
    
    # Test 3: Invalid format rejection
    try:
        await provider.complete(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe."},
                    {"type": "image_url", "image_url": {"url": "data:image/gif;base64,xxx"}}
                ]
            }],
            max_tokens=20
        )
        fail("Format validation", "Should have rejected GIF")
    except UnsupportedImageFormatError:
        ok("Format validation", "Rejected GIF correctly")
    except Exception as e:
        fail("Format validation", str(e))
    
    print()


if __name__ == "__main__":
    asyncio.run(main())