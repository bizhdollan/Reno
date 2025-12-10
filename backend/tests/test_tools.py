"""
Test tool/function calling.

Run: python tests/test_tools.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider
from tests.conftest import ok, fail


CALC_TOOL = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Do math",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
                "op": {"type": "string", "enum": ["add", "multiply"]}
            },
            "required": ["a", "b", "op"]
        }
    }
}


async def main():
    print("\n=== Tool Calling Tests ===\n")
    
    provider = LLMProvider.for_llm()
    
    # Test 1: Tool call triggered
    try:
        response = await provider.complete_with_tools(
            messages=[{"role": "user", "content": "What is 7 * 8? Use calculator."}],
            tools=[CALC_TOOL],
            max_tokens=200
        )
        
        tool_calls = getattr(response.choices[0].message, "tool_calls", None)
        assert tool_calls and len(tool_calls) > 0
        
        call = tool_calls[0]
        args = json.loads(call.function.arguments)
        ok("Tool triggered", f"{call.function.name}({args})")
    except Exception as e:
        fail("Tool triggered", str(e))
    
    # Test 2: Full round-trip
    try:
        # Initial call
        messages = [{"role": "user", "content": "What is 5 + 3?"}]
        response = await provider.complete_with_tools(
            messages=messages,
            tools=[CALC_TOOL],
            max_tokens=200
        )
        
        assistant_msg = response.choices[0].message
        tool_calls = getattr(assistant_msg, "tool_calls", None)
        
        if tool_calls:
            # Execute and follow up
            call = tool_calls[0]
            messages.append(assistant_msg.model_dump(exclude_none=True))
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "name": call.function.name,
                "content": "8"  # 5 + 3
            })
            
            final = await provider.complete_with_tools(
                messages=messages,
                tools=[],
                max_tokens=100
            )
            result = final.choices[0].message.content
            assert "8" in result
            ok("Round-trip", result[:50])
        else:
            ok("Round-trip", "Model answered directly")
    except Exception as e:
        fail("Round-trip", str(e))
    
    print()


if __name__ == "__main__":
    asyncio.run(main())