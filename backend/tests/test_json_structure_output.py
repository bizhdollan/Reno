"""
Test JSON output via prompting.

Run: python -m tests.test_json_output
"""

import asyncio
import json
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider


def parse_llm_json(response: str) -> dict:
    """Parse JSON from LLM response, handling markdown blocks."""
    content = response.strip()
    
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    
    if content.endswith("```"):
        content = content[:-3]
    
    return json.loads(content.strip())


def print_result(name: str, passed: bool, detail: str = ""):
    symbol = "✓" if passed else "✗"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{symbol} {name}{reset}")
    if detail:
        print(f"  {detail}")


async def test_text_to_json():
    """Test: text prompt -> JSON response"""
    provider = LLMProvider.for_llm()
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "Respond with valid JSON only. No markdown, no explanation."
            },
            {
                "role": "user",
                "content": 'Return a cost estimate: {"total": number, "currency": string}'
            }
        ],
        temperature=0.0,
        max_tokens=100
    )
    
    data = parse_llm_json(response)
    assert isinstance(data, dict)
    assert "total" in data or "currency" in data
    
    return data


async def test_image_to_json():
    """Test: image + prompt -> JSON response"""
    image_path = Path(__file__).parent / "1.jpeg"
    if not image_path.exists():
        raise FileNotFoundError(f"Test image not found: {image_path}")
    
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    data_url = f"data:image/jpeg;base64,{b64}"
    
    provider = LLMProvider.for_vlm()
    
    response = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": "Respond with valid JSON only. No markdown, no explanation."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": 'Describe this image: {"scene": string, "colors": [string]}'
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    }
                ]
            }
        ],
        temperature=0.0,
        max_tokens=150
    )
    
    data = parse_llm_json(response)
    assert isinstance(data, dict)
    
    return data


async def main():
    if not os.getenv("LLM_API_KEY"):
        print("\033[91mMissing LLM_API_KEY\033[0m")
        return
    
    print("\n" + "=" * 40)
    print("JSON Output Tests")
    print("=" * 40 + "\n")
    
    results = []
    
    # Test 1: Text to JSON
    try:
        data = await test_text_to_json()
        print_result("Text -> JSON", True, f"{data}")
        results.append(True)
    except Exception as e:
        print_result("Text -> JSON", False, str(e))
        results.append(False)
    
    # Test 2: Image to JSON
    try:
        data = await test_image_to_json()
        print_result("Image -> JSON", True, f"{data}")
        results.append(True)
    except Exception as e:
        print_result("Image -> JSON", False, str(e))
        results.append(False)
    
    # Summary
    print("\n" + "=" * 40)
    passed = sum(results)
    total = len(results)
    color = "\033[92m" if passed == total else "\033[91m"
    print(f"{color}Results: {passed}/{total} passed\033[0m")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    asyncio.run(main())