"""
Simple test script for token generation.

Run with: python test_tokens.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.utils.token_generator import generate_token, validate_token


def test_generate_project_token():
    """Test generating project tokens"""
    print("\n[TEST] Generate project token...")
    try:
        token = generate_token("PRJ")
        
        assert token.startswith("PRJ-"), f"Token should start with PRJ-, got: {token}"
        assert len(token) == 10, f"Token should be 10 chars, got: {len(token)}"
        
        # Check format
        prefix, code = token.split("-")
        assert len(code) == 6, f"Code should be 6 chars, got: {len(code)}"
        
        print(f"   ✅ Generated token: {token}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_generate_unlock_token():
    """Test generating unlock tokens"""
    print("\n[TEST] Generate unlock token...")
    try:
        token = generate_token("UNL")
        
        assert token.startswith("UNL-"), f"Token should start with UNL-, got: {token}"
        assert len(token) == 10, f"Token should be 10 chars, got: {len(token)}"
        
        print(f"   ✅ Generated token: {token}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_token_uniqueness():
    """Test that tokens are unique"""
    print("\n[TEST] Token uniqueness...")
    try:
        tokens = set()
        for _ in range(100):
            token = generate_token("PRJ")
            tokens.add(token)
        
        assert len(tokens) == 100, f"Expected 100 unique tokens, got {len(tokens)}"
        
        print(f"   ✅ Generated 100 unique tokens")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_validate_project_token():
    """Test validating project tokens"""
    print("\n[TEST] Validate project token...")
    try:
        valid, token_type = validate_token("PRJ-ABC123")
        
        assert valid is True, "Token should be valid"
        assert token_type == "project", f"Expected 'project', got: {token_type}"
        
        print(f"   ✅ Validation passed: PRJ-ABC123 -> {token_type}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_validate_unlock_token():
    """Test validating unlock tokens"""
    print("\n[TEST] Validate unlock token...")
    try:
        valid, token_type = validate_token("UNL-XYZ789")
        
        assert valid is True, "Token should be valid"
        assert token_type == "unlock", f"Expected 'unlock', got: {token_type}"
        
        print(f"   ✅ Validation passed: UNL-XYZ789 -> {token_type}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_validate_invalid_tokens():
    """Test validation rejects invalid tokens"""
    print("\n[TEST] Reject invalid tokens...")
    try:
        invalid_tokens = [
            ("BAD-ABC123", "Invalid prefix"),
            ("PRJ-AB", "Too short"),
            ("PRJABC123", "No dash"),
            ("PRJ-abc123", "Lowercase"),
        ]
        
        for token, reason in invalid_tokens:
            valid, _ = validate_token(token)
            assert valid is False, f"Should reject {token} ({reason})"
        
        print(f"   ✅ Correctly rejected {len(invalid_tokens)} invalid tokens")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def run_all_tests():
    """Run all token tests"""
    print("=" * 70)
    print("TOKEN GENERATOR TESTS")
    print("=" * 70)
    
    results = []
    
    # Test token generation
    results.append(test_generate_project_token())
    results.append(test_generate_unlock_token())
    results.append(test_token_uniqueness())
    
    # Test validation
    results.append(test_validate_project_token())
    results.append(test_validate_unlock_token())
    results.append(test_validate_invalid_tokens())
    
    # Summary
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 ALL TESTS PASSED ({passed}/{total})")
        print("=" * 70)
        return True
    else:
        print(f"⚠️ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 70)
        return False


if __name__ == "__main__":
    import sys
    
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted")
        sys.exit(1)

