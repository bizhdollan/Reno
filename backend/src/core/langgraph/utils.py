"""
Shared helpers for LangGraph nodes.
"""

def get_message_content(msg) -> tuple[str | None, str]:
    """
    Extract role and content from message.
    
    Supports:
    - plain dicts with role/content
    - LangChain Message objects (human/ai/system)
    """
    if isinstance(msg, dict):
        return msg.get("role"), msg.get("content", "")
    
    role = getattr(msg, "type", None)  # e.g., "human", "ai", "system"
    if role == "human":
        role = "user"
    elif role == "ai":
        role = "assistant"
    content = getattr(msg, "content", "")
    return role, content

