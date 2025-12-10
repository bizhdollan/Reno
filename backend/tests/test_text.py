"""
Test text completion.

Run: python tests/test_text.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider
from tests.conftest import ok, fail


async def main():
    print("\n=== Text Completion Tests ===\n")
    
    provider = LLMProvider.for_llm()
    
    # Test 1: Non-streaming
    try:
        response = await provider.complete(
            messages=[{"role": "user", "content": "Say 'hello' only."}],
            max_tokens=20,
            temperature=0.0
        )
        assert len(response) > 0
        ok("Non-streaming", response[:50])
    except Exception as e:
        fail("Non-streaming", str(e))
    
    # Test 2: Streaming
    try:
        chunks = []
        async for chunk in provider.complete_stream(
            messages=[{"role": "user", "content": "Count 1 to 3."}],
            max_tokens=50
        ):
            chunks.append(chunk)
        assert len(chunks) > 1
        ok("Streaming", f"{len(chunks)} chunks")
    except Exception as e:
        fail("Streaming", str(e))
    
    # Test 3: Multi-turn
    try:
        response = await provider.complete(
            messages=[
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Hello Alice!"},
                {"role": "user", "content": "What's my name?"}
            ],
            max_tokens=30
        )
        assert "alice" in response.lower()
        ok("Multi-turn", response[:50])
    except Exception as e:
        fail("Multi-turn", str(e))
    
    print()


if __name__ == "__main__":
    asyncio.run(main())