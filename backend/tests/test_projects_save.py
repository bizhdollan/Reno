"""
Test project save endpoint.

Run: python tests/test_projects_save.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from src.db.database import SessionLocal
from src.db.models import Project, ConversationState
from src.utils.token_generator import generate_token
from tests.conftest import ok, fail

BASE_URL = "http://localhost:8000"


def test_save_project_with_email():
    """Test saving a project and receiving email with token"""
    print("\n--- Save Project with Email ---\n")
    
    # First, create a project through chat (or directly in DB)
    db = SessionLocal()
    try:
        # Create a completed project
        project_token = generate_token("PRJ")
        project = Project(
            token=project_token,
            status="completed",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            brief_scope="Full kitchen renovation"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Create conversation state
        conv_state = ConversationState(
            project_id=project.id,
            state={
                "current_stage": "completed",
                "project_title": "Kitchen Renovation",
                "project_type": "kitchen",
                "zip_code": "10001",
                "cost_tiers": [
                    {"id": "low", "total_cost": 30000},
                    {"id": "mid", "total_cost": 45000},
                    {"id": "high", "total_cost": 65000}
                ],
                "selected_tier": "mid"
            }
        )
        db.add(conv_state)
        db.commit()
        
        ok("Created test project", project_token)
        
        # Now test save endpoint
        response = requests.post(
            f"{BASE_URL}/api/v1/projects/save",
            json={
                "project_token": project_token,
                "email": "test@example.com"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            fail("Save project endpoint", f"Status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        assert "token" in data, "Response should include token"
        assert "email_sent" in data, "Response should indicate if email was sent"
        assert data["token"] == project_token, "Token should match"
        
        # Verify email_sent flag updated
        db.refresh(project)
        if project.homeowner_email_sent:
            ok("Email sent flag updated", "homeowner_email_sent=True")
        else:
            fail("Email sent flag", "Not updated in database")
        
        ok("Save project endpoint", f"Token: {data['token']}, Email sent: {data['email_sent']}")
        return True
        
    except Exception as e:
        fail("Save project", str(e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_save_project_invalid_token():
    """Test saving with invalid token"""
    print("\n--- Save Project Invalid Token ---\n")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/projects/save",
            json={
                "project_token": "PRJ-INVALID",
                "email": "test@example.com"
            },
            timeout=10
        )
        
        # Should return 404 or 400
        assert response.status_code in [400, 404], f"Expected 400/404, got {response.status_code}"
        
        ok("Invalid token rejected", f"Status {response.status_code}")
        return True
        
    except Exception as e:
        fail("Invalid token test", str(e))
        return False


def test_save_project_missing_email():
    """Test saving without email"""
    print("\n--- Save Project Missing Email ---\n")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/projects/save",
            json={
                "project_token": "PRJ-TEST01"
            },
            timeout=10
        )
        
        # Should return 422 (validation error) or 400
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        
        ok("Missing email rejected", f"Status {response.status_code}")
        return True
        
    except Exception as e:
        fail("Missing email test", str(e))
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Project Save Endpoint Tests")
    print("="*60)
    print("\n📋 Prerequisites:")
    print("   1. Backend running: python main.py")
    print("   2. PostgreSQL running: docker-compose up -d")
    print("\nPress Enter to continue...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        sys.exit(0)
    
    results = []
    results.append(test_save_project_with_email())
    results.append(test_save_project_invalid_token())
    results.append(test_save_project_missing_email())
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "="*60)
    if passed == total:
        print(f"✓ All tests passed ({passed}/{total})")
        print("\n💡 Note: These tests will fail until you implement the endpoint!")
        print("   Next: Implement POST /api/v1/projects/save")
    else:
        print(f"✗ Some tests failed ({passed}/{total} passed)")
    print("="*60 + "\n")

