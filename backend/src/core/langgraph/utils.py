"""
Shared utilities for LangGraph nodes.
"""

import json
from typing import Any


def get_message_content(msg: Any) -> tuple[str | None, Any]:
    """
    Extract role and content from message (dict or LangChain Message object).
    
    Returns:
        Tuple of (role, content) where role is 'user', 'assistant', or 'system'
    """
    if isinstance(msg, dict):
        return msg.get("role"), msg.get("content", "")
    
    # LangChain Message object
    role = getattr(msg, "type", None)
    if role == "human":
        role = "user"
    elif role == "ai":
        role = "assistant"
    
    content = getattr(msg, "content", "")
    return role, content


def get_latest_user_message(messages: list) -> tuple[str | None, list[str]]:
    """
    Extract the latest user message text and any image URLs.
    
    Returns:
        Tuple of (text_content, list_of_image_urls)
    """
    for msg in reversed(messages):
        role, content = get_message_content(msg)
        
        if role == "user":
            if isinstance(content, str):
                return content, []
            
            # Multimodal content
            text = None
            images = []
            
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text = item.get("text", "")
                        elif item.get("type") == "image_url":
                            url = item.get("image_url", {}).get("url")
                            if url:
                                images.append(url)
            
            return text, images
    
    return None, []


def parse_json(response: str) -> dict:
    """
    Parse JSON from LLM response, handling markdown code blocks.
    
    Args:
        response: Raw LLM response string
        
    Returns:
        Parsed JSON as dict
        
    Raises:
        json.JSONDecodeError: If response is not valid JSON
    """
    content = response.strip()
    
    # Remove markdown code blocks if present
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    
    if content.endswith("```"):
        content = content[:-3]
    
    return json.loads(content.strip())


def format_list_for_display(items: list[dict], fields: list[str]) -> str:
    """
    Format a list of dicts for display to user.
    
    Args:
        items: List of dictionaries
        fields: Which fields to include in display
        
    Returns:
        Formatted string
    """
    if not items:
        return "None identified"
    
    lines = []
    for i, item in enumerate(items, 1):
        parts = []
        for field in fields:
            if field in item and item[field]:
                parts.append(f"{item[field]}")
        if parts:
            lines.append(f"  {i}. {' - '.join(parts)}")
    
    return "\n".join(lines) if lines else "None identified"