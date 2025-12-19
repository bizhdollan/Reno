"""
Test unlock flow endpoints.

Run: python tests/test_unlock.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from src.db.database import SessionLocal
from src.db.models import Project, Unlock
from src.utils.token_generator import generate_token
from tests.conftest import ok, fail

BASE_URL = "http://localhost:8000"


def test_initiate_unlock():
    """Test initiating unlock process"""
    print("\n--- Initiate Unlock ---\n")
    
    db = SessionLocal()
    try:
        # Create a published project
        project_token = generate_token("PRJ")
        project = Project(
            token=project_token,
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            brief_scope="Kitchen renovation",
            homeowner_name="John Doe",
            homeowner_email="john@example.com",
            homeowner_phone="(555) 123-4567"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        ok("Created published project", project_token)
        
        # Initiate unlock
        response = requests.post(
            f"{BASE_URL}/api/v1/unlocks/initiate",
            json={
                "project_id": str(project.id),
                "contractor_email": "contractor@example.com"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            fail("Initiate unlock endpoint", f"Status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        assert "unlock_token" in data, "Response should include unlock_token"
        assert "checkout_url" in data, "Response should include checkout_url"
        assert data["unlock_token"].startswith("UNL-"), "Token should start with UNL-"
        
        # Verify unlock record created
        unlock = db.query(Unlock).filter(Unlock.unlock_token == data["unlock_token"]).first()
        assert unlock is not None, "Unlock record should be created"
        assert unlock.payment_status == "pending", "Payment status should be pending"
        assert unlock.contractor_email == "contractor@example.com", "Email should be saved"
        
        ok("Initiate unlock", f"Token: {data['unlock_token']}")
        return True
        
    except Exception as e:
        fail("Initiate unlock", str(e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_initiate_unlock_already_unlocked():
    """Test initiating unlock on already unlocked project"""
    print("\n--- Initiate Unlock Already Unlocked ---\n")
    
    db = SessionLocal()
    try:
        # Create published project
        project = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            homeowner_name="Test",
            homeowner_email="test@example.com"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Create active unlock
        unlock = Unlock(
            project_id=project.id,
            unlock_token=generate_token("UNL"),
            contractor_email="contractor1@example.com",
            payment_status="completed",
            is_active=True
        )
        db.add(unlock)
        project.status = "unlocked"
        db.commit()
        
        ok("Created unlocked project", project.token)
        
        # Try to unlock again
        response = requests.post(
            f"{BASE_URL}/api/v1/unlocks/initiate",
            json={
                "project_id": str(project.id),
                "contractor_email": "contractor2@example.com"
            },
            timeout=10
        )
        
        # Should return 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        ok("Already unlocked rejected", f"Status {response.status_code}")
        return True
        
    except Exception as e:
        fail("Already unlocked test", str(e))
        return False
    finally:
        db.close()


def test_initiate_unlock_invalid_project():
    """Test initiating unlock with invalid project ID"""
    print("\n--- Initiate Unlock Invalid Project ---\n")
    
    try:
        import uuid
        fake_id = str(uuid.uuid4())
        
        response = requests.post(
            f"{BASE_URL}/api/v1/unlocks/initiate",
            json={
                "project_id": fake_id,
                "contractor_email": "contractor@example.com"
            },
            timeout=10
        )
        
        # Should return 404
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        ok("Invalid project rejected", f"Status {response.status_code}")
        return True
        
    except Exception as e:
        fail("Invalid project test", str(e))
        return False


def test_save_contractor_details():
    """Test saving contractor details after unlock"""
    print("\n--- Save Contractor Details ---\n")
    
    db = SessionLocal()
    try:
        # Create published project
        project = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            homeowner_name="Test",
            homeowner_email="test@example.com"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Create completed unlock
        unlock_token = generate_token("UNL")
        unlock = Unlock(
            project_id=project.id,
            unlock_token=unlock_token,
            contractor_email="contractor@example.com",
            payment_status="completed",
            is_active=True
        )
        db.add(unlock)
        project.status = "unlocked"
        db.commit()
        
        ok("Created unlocked project", unlock_token)
        
        # Save contractor details
        response = requests.post(
            f"{BASE_URL}/api/v1/unlocks/{unlock_token}/details",
            json={
                "contractor_name": "Mike Smith",
                "contractor_phone": "(555) 987-6543",
                "contractor_company": "Mike's Renovations LLC"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            fail("Save contractor details", f"Status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        assert data["contractor_name"] == "Mike Smith", "Name should be saved"
        assert data["contractor_phone"] == "(555) 987-6543", "Phone should be saved"
        assert data["contractor_company"] == "Mike's Renovations LLC", "Company should be saved"
        assert data["contractor_details_saved"] is True, "Details saved flag should be True"
        
        # Verify in database
        db.refresh(unlock)
        assert unlock.contractor_name == "Mike Smith", "Name not saved in database"
        assert unlock.contractor_details_saved is True, "Flag not updated"
        
        ok("Save contractor details", "Details saved successfully")
        return True
        
    except Exception as e:
        fail("Save contractor details", str(e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_save_contractor_details_before_payment():
    """Test saving details before payment completed"""
    print("\n--- Save Details Before Payment ---\n")
    
    db = SessionLocal()
    try:
        # Create unlock with pending payment
        project = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        unlock_token = generate_token("UNL")
        unlock = Unlock(
            project_id=project.id,
            unlock_token=unlock_token,
            contractor_email="contractor@example.com",
            payment_status="pending",  # Not completed yet
            is_active=False
        )
        db.add(unlock)
        db.commit()
        
        # Try to save details
        response = requests.post(
            f"{BASE_URL}/api/v1/unlocks/{unlock_token}/details",
            json={
                "contractor_name": "Mike Smith",
                "contractor_phone": "(555) 987-6543",
                "contractor_company": "Mike's Renovations"
            },
            timeout=10
        )
        
        # Should return 400 (payment not completed)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        ok("Pending payment rejected", f"Status {response.status_code}")
        return True
        
    except Exception as e:
        fail("Pending payment test", str(e))
        return False
    finally:
        db.close()


def test_get_unlock_details():
    """Test getting unlock details with project info"""
    print("\n--- Get Unlock Details ---\n")
    
    db = SessionLocal()
    try:
        # Create unlocked project with contractor details
        project = Project(
            token=generate_token("PRJ"),
            status="unlocked",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            homeowner_name="John Doe",
            homeowner_email="john@example.com",
            homeowner_phone="(555) 123-4567"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        unlock_token = generate_token("UNL")
        unlock = Unlock(
            project_id=project.id,
            unlock_token=unlock_token,
            contractor_email="contractor@example.com",
            contractor_name="Mike Smith",
            contractor_phone="(555) 987-6543",
            contractor_company="Mike's Renovations",
            contractor_details_saved=True,
            payment_status="completed",
            is_active=True
        )
        db.add(unlock)
        db.commit()
        
        ok("Created unlock with details", unlock_token)
        
        # Get unlock details
        response = requests.get(
            f"{BASE_URL}/api/v1/unlocks/{unlock_token}",
            timeout=10
        )
        
        if response.status_code != 200:
            fail("Get unlock details", f"Status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        assert data["unlock_token"] == unlock_token, "Token should match"
        assert data["contractor_name"] == "Mike Smith", "Contractor name should be included"
        assert "project" in data, "Project details should be included"
        assert data["project"]["homeowner_email"] == "john@example.com", "Homeowner email should be visible"
        
        ok("Get unlock details", "Details retrieved successfully")
        return True
        
    except Exception as e:
        fail("Get unlock details", str(e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Unlock Flow Endpoint Tests")
    print("="*60)
    print("\n📋 Prerequisites:")
    print("   1. Backend running: python main.py")
    print("   2. PostgreSQL running: docker-compose up -d")
    print("   3. Stripe configured (test mode OK)")
    print("\nPress Enter to continue...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        sys.exit(0)
    
    results = []
    results.append(test_initiate_unlock())
    results.append(test_initiate_unlock_already_unlocked())
    results.append(test_initiate_unlock_invalid_project())
    results.append(test_save_contractor_details())
    results.append(test_save_contractor_details_before_payment())
    results.append(test_get_unlock_details())
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "="*60)
    if passed == total:
        print(f"✓ All tests passed ({passed}/{total})")
    else:
        print(f"✗ Some tests failed ({passed}/{total} passed)")
        print("\n💡 Note: These tests will fail until you implement the endpoints!")
        print("   Next: Implement unlock endpoints")
    print("="*60 + "\n")

