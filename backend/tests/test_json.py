"""
Test JSON output via prompting.

Run: python tests/test_json.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider
from tests.conftest import ok, fail, parse_json, load_image


async def main():
    print("\n=== JSON Output Tests ===\n")
    
    provider = LLMProvider.for_llm()
    
    # Test 1: Simple JSON
    try:
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Respond with JSON only. No markdown."},
                {"role": "user", "content": 'Return: {"name": "test", "value": 42}'}
            ],
            temperature=0.0,
            max_tokens=50
        )
        data = parse_json(response)
        assert "name" in data and "value" in data
        ok("Simple JSON", str(data))
    except Exception as e:
        fail("Simple JSON", str(e))
    
    # Test 2: Nested JSON
    try:
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Respond with JSON only. No markdown."},
                {"role": "user", "content": 'Return: {"total": 100, "breakdown": {"a": 60, "b": 40}}'}
            ],
            temperature=0.0,
            max_tokens=100
        )
        data = parse_json(response)
        assert "breakdown" in data and isinstance(data["breakdown"], dict)
        ok("Nested JSON", str(data))
    except Exception as e:
        fail("Nested JSON", str(e))
    
    # Test 3: JSON from image
    try:
        image_url = load_image("1.jpeg")
        vlm = LLMProvider.for_vlm()
        
        response = await vlm.complete(
            messages=[
                {"role": "system", "content": "Respond with JSON only. No markdown."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": 'Describe: {"room": string, "colors": [string]}'},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            temperature=0.0,
            max_tokens=150
        )
        data = parse_json(response)
        assert "room" in data or "colors" in data
        ok("JSON from image", str(data)[:80])
    except FileNotFoundError:
        ok("JSON from image", "Skipped - no test image")
    except Exception as e:
        fail("JSON from image", str(e))
    
    print()


if __name__ == "__main__":
    asyncio.run(main())