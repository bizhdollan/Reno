"""
Simple test script for health check endpoints.

Run with: python test_health.py
"""
import requests


BASE_URL = "http://localhost:8000"


def test_root_endpoint():
    """Test root endpoint"""
    print("\n[TEST] Root endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        data = response.json()
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert data["status"] == "running", f"Expected running, got {data['status']}"
        assert "endpoints" in data, "Missing endpoints in response"
        
        print("   ✅ Root endpoint working")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_health_endpoint():
    """Test health check endpoint"""
    print("\n[TEST] Health check endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = response.json()
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "status" in data, "Missing status in response"
        assert "database" in data, "Missing database status"
        
        if data["database"] != "connected":
            print(f"   ⚠️ Database status: {data['database']}")
            print("   Make sure PostgreSQL is running: docker-compose up -d")
            return False
        
        print(f"   ✅ Health check passed")
        print(f"      Status: {data['status']}")
        print(f"      Database: {data['database']}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def run_all_tests():
    """Run all health tests"""
    print("=" * 70)
    print("HEALTH CHECK TESTS")
    print("=" * 70)
    
    results = []
    
    # Test 1: Root endpoint
    results.append(test_root_endpoint())
    
    # Test 2: Health endpoint
    results.append(test_health_endpoint())
    
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
    
    print("\n📋 Prerequisites:")
    print("   1. Backend running: python main.py")
    print("   2. PostgreSQL running: docker-compose up -d")
    print("\nPress Enter to continue...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        sys.exit(0)
    
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted")
        sys.exit(1)

