"""
Test project publish endpoint.

Run: python tests/test_projects_publish.py
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


def test_publish_project():
    """Test publishing a completed project to marketplace"""
    print("\n--- Publish Project to Marketplace ---\n")
    
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
            brief_scope="Full kitchen renovation",
            homeowner_email="test@example.com"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        ok("Created test project", project_token)
        
        # Publish project
        response = requests.post(
            f"{BASE_URL}/api/v1/projects/{project_token}/publish",
            json={
                "homeowner_name": "John Doe",
                "homeowner_email": "john@example.com",
                "homeowner_phone": "(555) 123-4567"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            fail("Publish project endpoint", f"Status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        assert data["status"] == "published", f"Expected published, got {data['status']}"
        assert data["homeowner_name"] == "John Doe", "Homeowner name not saved"
        assert data["homeowner_email"] == "john@example.com", "Homeowner email not saved"
        assert data["homeowner_phone"] == "(555) 123-4567", "Homeowner phone not saved"
        
        # Verify in database
        db.refresh(project)
        assert project.status == "published", "Status not updated in database"
        assert project.homeowner_name == "John Doe", "Name not saved in database"
        
        ok("Publish project endpoint", f"Status: {data['status']}")
        return True
        
    except Exception as e:
        fail("Publish project", str(e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_publish_already_published():
    """Test publishing an already published project"""
    print("\n--- Publish Already Published Project ---\n")
    
    db = SessionLocal()
    try:
        # Create a published project
        project_token = generate_token("PRJ")
        project = Project(
            token=project_token,
            status="published",
            project_type="bathroom",
            zip_code="10002",
            homeowner_email="test@example.com"
        )
        db.add(project)
        db.commit()
        
        ok("Created published project", project_token)
        
        # Try to publish again
        response = requests.post(
            f"{BASE_URL}/api/v1/projects/{project_token}/publish",
            json={
                "homeowner_name": "Jane Doe",
                "homeowner_email": "jane@example.com",
                "homeowner_phone": "(555) 987-6543"
            },
            timeout=10
        )
        
        # Should return 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        ok("Already published rejected", f"Status {response.status_code}")
        return True
        
    except Exception as e:
        fail("Already published test", str(e))
        return False
    finally:
        db.close()


def test_publish_invalid_token():
    """Test publishing with invalid token"""
    print("\n--- Publish Invalid Token ---\n")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/projects/PRJ-INVALID/publish",
            json={
                "homeowner_name": "Test",
                "homeowner_email": "test@example.com",
                "homeowner_phone": "1234567890"
            },
            timeout=10
        )
        
        # Should return 404
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        ok("Invalid token rejected", f"Status {response.status_code}")
        return True
        
    except Exception as e:
        fail("Invalid token test", str(e))
        return False


def test_publish_missing_fields():
    """Test publishing with missing required fields"""
    print("\n--- Publish Missing Fields ---\n")
    
    db = SessionLocal()
    try:
        # Create a completed project
        project_token = generate_token("PRJ")
        project = Project(
            token=project_token,
            status="completed",
            project_type="kitchen",
            zip_code="10001"
        )
        db.add(project)
        db.commit()
        
        # Try to publish without required fields
        response = requests.post(
            f"{BASE_URL}/api/v1/projects/{project_token}/publish",
            json={
                "homeowner_email": "test@example.com"
                # Missing name and phone
            },
            timeout=10
        )
        
        # Should return 422 (validation error)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        
        ok("Missing fields rejected", f"Status {response.status_code}")
        return True
        
    except Exception as e:
        fail("Missing fields test", str(e))
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Project Publish Endpoint Tests")
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
    results.append(test_publish_project())
    results.append(test_publish_already_published())
    results.append(test_publish_invalid_token())
    results.append(test_publish_missing_fields())
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "="*60)
    if passed == total:
        print(f"✓ All tests passed ({passed}/{total})")
    else:
        print(f"✗ Some tests failed ({passed}/{total} passed)")
    print("="*60 + "\n")

