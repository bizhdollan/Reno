"""Shared test utilities."""

import base64
import json
from pathlib import Path

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def ok(name: str, detail: str = ""):
    print(f"{GREEN}✓ {name}{RESET}" + (f" - {detail}" if detail else ""))


def fail(name: str, detail: str = ""):
    print(f"{RED}✗ {name}{RESET}" + (f" - {detail}" if detail else ""))


def load_image(filename: str) -> str:
    """Load image as base64 data URL."""
    path = Path(__file__).parent / filename
    if not path.exists():
        path = Path(__file__).parent / "assets" / filename
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


def parse_json(response: str) -> dict:
    """Parse JSON, stripping markdown if present."""
    content = response.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())