"""
Token generation utility.

Generates unique tokens for projects (PRJ-) and unlocks (UNL-).
"""
import secrets
import string


def generate_token(prefix: str = "PRJ") -> str:
    """
    Generate a unique token with the given prefix.
    
    Format: {PREFIX}-{6 random chars}
    Example: PRJ-7X9K2M, UNL-4B8T3N
    
    Args:
        prefix: Token prefix ("PRJ" for projects, "UNL" for unlocks)
    
    Returns:
        Generated token string
    
    Security:
        Uses secrets module (cryptographically strong randomness)
        Character set: A-Z, 0-9 (36 characters)
        Combinations: 36^6 = 2,176,782,336 (~2.1 billion)
    """
    # Character set: uppercase letters + digits (no lowercase to avoid confusion)
    chars = string.ascii_uppercase + string.digits
    
    # Generate 6 random characters
    random_part = ''.join(secrets.choice(chars) for _ in range(6))
    
    return f"{prefix}-{random_part}"


def validate_token(token: str) -> tuple[bool, str | None]:
    """
    Validate token format.
    
    Args:
        token: Token string to validate
    
    Returns:
        Tuple of (is_valid, token_type)
        token_type is "project", "unlock", or None if invalid
    
    Examples:
        >>> validate_token("PRJ-ABC123")
        (True, "project")
        >>> validate_token("UNL-XYZ789")
        (True, "unlock")
        >>> validate_token("INVALID")
        (False, None)
    """
    if not token or not isinstance(token, str):
        return False, None
    
    parts = token.split("-")
    if len(parts) != 2:
        return False, None
    
    prefix, code = parts
    
    # Check prefix
    if prefix not in ["PRJ", "UNL"]:
        return False, None
    
    # Check code length
    if len(code) != 6:
        return False, None
    
    # Check code characters (uppercase + digits only)
    if not all(c in string.ascii_uppercase + string.digits for c in code):
        return False, None
    
    token_type = "project" if prefix == "PRJ" else "unlock"
    return True, token_type


def generate_unique_token(prefix: str, existing_tokens: set[str]) -> str:
    """
    Generate a token that doesn't exist in the given set.
    
    Useful for testing or batch generation.
    
    Args:
        prefix: Token prefix
        existing_tokens: Set of existing tokens to avoid
    
    Returns:
        Unique token
    
    Note:
        In production, database unique constraint handles uniqueness.
        This is mainly for testing/seeding.
    """
    max_attempts = 100
    for _ in range(max_attempts):
        token = generate_token(prefix)
        if token not in existing_tokens:
            return token
    
    raise RuntimeError(f"Failed to generate unique token after {max_attempts} attempts")
