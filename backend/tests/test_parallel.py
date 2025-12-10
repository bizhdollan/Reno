"""
Test parallel requests.

Run: python tests/test_parallel.py
"""

import asyncio
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider
from tests.conftest import ok, fail


async def main():
    print("\n=== Parallel Request Tests ===\n")
    
    # Test 1: 3 parallel requests
    try:
        providers = [LLMProvider.for_llm() for _ in range(3)]
        
        start = time.time()
        results = await asyncio.gather(*[
            p.complete(
                messages=[{"role": "user", "content": f"Say '{i}'"}],
                max_tokens=10
            )
            for i, p in enumerate(providers)
        ])
        elapsed = time.time() - start
        
        assert len(results) == 3
        assert all(len(r) > 0 for r in results)
        ok("3 parallel", f"{elapsed:.2f}s")
    except Exception as e:
        fail("3 parallel", str(e))
    
    # Test 2: No interference
    try:
        p1, p2 = LLMProvider.for_llm(), LLMProvider.for_llm()
        
        r1, r2 = await asyncio.gather(
            p1.complete(
                messages=[
                    {"role": "system", "content": "Only say ALPHA"},
                    {"role": "user", "content": "Speak"}
                ],
                max_tokens=10
            ),
            p2.complete(
                messages=[
                    {"role": "system", "content": "Only say BETA"},
                    {"role": "user", "content": "Speak"}
                ],
                max_tokens=10
            )
        )
        
        assert "alpha" in r1.lower() or "beta" in r2.lower()
        ok("No interference", f"'{r1[:20]}' / '{r2[:20]}'")
    except Exception as e:
        fail("No interference", str(e))
    
    # Test 3: Parallel streaming
    try:
        async def stream(msg):
            p = LLMProvider.for_llm()
            chunks = []
            async for c in p.complete_stream(
                messages=[{"role": "user", "content": msg}],
                max_tokens=30
            ):
                chunks.append(c)
            return "".join(chunks)
        
        results = await asyncio.gather(
            stream("Say A"),
            stream("Say B")
        )
        assert len(results) == 2
        ok("Parallel streaming", "2 streams completed")
    except Exception as e:
        fail("Parallel streaming", str(e))
    
    print()


if __name__ == "__main__":
    asyncio.run(main())