"""
Demonstrates tool/function calling with LLMProvider using a simple calculator tool.
Run: python -m tests.test_tool_calls
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm.provider import LLMProvider


def print_test(test_name: str, passed: bool = True, message: str = ""):
    status = "✓" if passed else "✗"
    status_text = "PASSED" if passed else "FAILED"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{status} {test_name} - {status_text}{reset}")
    if message:
        print(f"  {message}")


# Simple calculator tool definition (OpenAI-style tool schema)
calculator_tool = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Perform basic arithmetic operations",
        "parameters": {
            "type": "object",
            "properties": {
                "op": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "Operation to perform",
                },
                "a": {"type": "number", "description": "First operand"},
                "b": {"type": "number", "description": "Second operand"},
            },
            "required": ["op", "a", "b"],
        },
    },
}


def execute_calculator(args: dict) -> str:
    op = args.get("op")
    a = args.get("a")
    b = args.get("b")
    if op == "add":
        return str(a + b)
    if op == "subtract":
        return str(a - b)
    if op == "multiply":
        return str(a * b)
    if op == "divide":
        try:
            return str(a / b)
        except ZeroDivisionError:
            return "Division by zero"
    return "Unsupported operation"


async def test_tool_call_round_trip() -> bool:
    test_name = "Tool call round-trip"
    try:
        provider = LLMProvider.for_llm()

        base_messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. Use the provided calculator tool if math is needed.",
            },
            {
                "role": "user",
                "content": "What is 7.5 * 4.2? Please use the calculator tool.",
            },
        ]

        # Initial call asking model to use the calculator (non-streaming)
        response = await provider.complete_with_tools(
            messages=base_messages,
            tools=[calculator_tool],
            max_tokens=200,
        )

        # Check response structure
        if not response or not getattr(response, "choices", None):
            print_test(test_name, False, "No choices returned by model")
            return False

        assistant_msg = response.choices[0].message
        tool_calls = getattr(assistant_msg, "tool_calls", None)
        if not tool_calls:
            print_test(test_name, False, "No tool_calls returned by model")
            return False

        # Execute each tool call
        tool_results_messages = []
        for call in tool_calls:
            name = call.function.name
            args_json = call.function.arguments
            try:
                args = json.loads(args_json)
            except json.JSONDecodeError:
                print_test(test_name, False, f"Invalid tool call arguments: {args_json}")
                return False
            result = None
            if name == "calculator":
                result = execute_calculator(args)
            else:
                result = f"Unknown tool: {name}"

            tool_results_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": result,
                }
            )

        # Recreate the assistant message as a dict for follow-up
        assistant_msg_dict = assistant_msg.model_dump(exclude_none=True)

        # Follow-up call: include the assistant message with tool_calls, then tool results
        followup_messages = [
            *base_messages,
            assistant_msg_dict,
            *tool_results_messages,
        ]

        final_response = await provider.complete_with_tools(
            messages=followup_messages,
            tools=[],  # No new tools; just finalize
            max_tokens=200,
        )

        if not final_response or not getattr(final_response, "choices", None):
            print_test(test_name, False, "No choices returned in final response")
            return False

        final_text = final_response.choices[0].message.content
        assert isinstance(final_text, str) and len(final_text) > 0
        print_test(test_name, True, f"Final answer: {final_text[:120]}...")
        return True

    except Exception as e:
        print_test(test_name, False, f"Error: {str(e)}")
        return False


async def main():
    if not os.getenv("LLM_PROVIDER") or not os.getenv("LLM_MODEL") or not os.getenv("LLM_API_KEY"):
        print("\033[91m✗ Missing env vars: LLM_PROVIDER, LLM_MODEL, LLM_API_KEY\033[0m")
        return

    print("\n" + "=" * 60)
    print("Tool Call Test")
    print("=" * 60 + "\n")

    results = []
    results.append(await test_tool_call_round_trip())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"\033[92m✓ All tests passed! ({passed}/{total})\033[0m")
    else:
        print(f"\033[91m✗ Some tests failed: {passed}/{total}\033[0m")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
