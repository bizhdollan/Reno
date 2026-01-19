"""
Shared utilities for LangGraph nodes.
"""

import json
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)


def get_message_content(msg: Any) -> tuple[str | None, Any]:
    """
    Extract role and content from message (dict or LangChain Message object).

    Args:
        msg: Message object (dict or LangChain Message)

    Returns:
        Tuple of (role, content) where role is 'user', 'assistant', 'system', or None
        Returns (None, "") if message is invalid
    """
    try:
        if msg is None:
            logger.warning("[get_message_content] Received None message")
            return None, ""

        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
            return role, content

        # LangChain Message object
        role = getattr(msg, "type", None)
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"

        content = getattr(msg, "content", "")
        return role, content

    except Exception as e:
        logger.exception(f"[get_message_content] Error extracting message content: {e}")
        return None, ""


def get_latest_user_message(messages: list) -> tuple[str | None, list[str]]:
    """
    Extract the latest user message text and any image URLs.

    Args:
        messages: List of message objects

    Returns:
        Tuple of (text_content, list_of_image_urls)
        Returns (None, []) if no user message found or on error
    """
    try:
        if not messages:
            logger.debug("[get_latest_user_message] Empty messages list")
            return None, []

        if not isinstance(messages, list):
            logger.warning(f"[get_latest_user_message] messages is not a list: {type(messages)}")
            return None, []

        for msg in reversed(messages):
            try:
                role, content = get_message_content(msg)

                if role == "user":
                    if isinstance(content, str):
                        return content, []

                    # Multimodal content
                    text = None
                    images = []

                    if isinstance(content, list):
                        for item in content:
                            try:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        text = item.get("text", "")
                                    elif item.get("type") == "image_url":
                                        url = item.get("image_url", {}).get("url")
                                        if url:
                                            images.append(url)
                            except Exception as e:
                                logger.warning(f"[get_latest_user_message] Error processing content item: {e}")
                                continue

                    return text, images

            except Exception as e:
                logger.warning(f"[get_latest_user_message] Error processing message: {e}")
                continue

        logger.debug("[get_latest_user_message] No user message found")
        return None, []

    except Exception as e:
        logger.exception(f"[get_latest_user_message] Unexpected error: {e}")
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
        ValueError: If response is empty or invalid
    """
    try:
        if not response:
            logger.error("[parse_json] Empty response received")
            raise ValueError("Cannot parse empty response")

        if not isinstance(response, str):
            logger.error(f"[parse_json] Response is not a string: {type(response)}")
            raise ValueError(f"Response must be a string, got {type(response)}")

        content = response.strip()

        if not content:
            logger.error("[parse_json] Response is empty after stripping")
            raise ValueError("Response is empty after stripping whitespace")

        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        if not content:
            logger.error("[parse_json] Response is empty after removing markdown")
            raise ValueError("Response is empty after removing markdown code blocks")

        try:
            result = json.loads(content)
            logger.debug(f"[parse_json] Successfully parsed JSON with {len(result)} keys")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"[parse_json] JSON decode error at line {e.lineno}, col {e.colno}: {e.msg}")
            logger.error(f"[parse_json] Content preview: {content[:200]}...")
            raise

    except json.JSONDecodeError:
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.exception(f"[parse_json] Unexpected error parsing JSON: {e}")
        raise ValueError(f"Unexpected error parsing JSON: {e}")


def format_list_for_display(items: list[dict], fields: list[str]) -> str:
    """
    Format a list of dicts for display to user.

    Args:
        items: List of dictionaries
        fields: Which fields to include in display

    Returns:
        Formatted string. Returns "None identified" if empty or on error.
    """
    try:
        if not items:
            return "None identified"

        if not isinstance(items, list):
            logger.warning(f"[format_list_for_display] items is not a list: {type(items)}")
            return "None identified"

        if not fields or not isinstance(fields, list):
            logger.warning(f"[format_list_for_display] Invalid fields parameter: {fields}")
            return "None identified"

        lines = []
        for i, item in enumerate(items, 1):
            try:
                if not isinstance(item, dict):
                    logger.warning(f"[format_list_for_display] Item {i} is not a dict: {type(item)}")
                    continue

                parts = []
                for field in fields:
                    try:
                        if field in item and item[field]:
                            # Convert to string safely
                            value = str(item[field])
                            parts.append(value)
                    except Exception as e:
                        logger.warning(f"[format_list_for_display] Error processing field '{field}': {e}")
                        continue

                if parts:
                    lines.append(f"  {i}. {' - '.join(parts)}")

            except Exception as e:
                logger.warning(f"[format_list_for_display] Error processing item {i}: {e}")
                continue

        result = "\n".join(lines) if lines else "None identified"
        logger.debug(f"[format_list_for_display] Formatted {len(lines)} items")
        return result

    except Exception as e:
        logger.exception(f"[format_list_for_display] Unexpected error: {e}")
        return "None identified"