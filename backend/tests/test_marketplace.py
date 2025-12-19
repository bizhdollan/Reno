"""
Test marketplace browse endpoint.

Run: python tests/test_marketplace.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from src.db.database import SessionLocal
from src.db.models import Project
from src.utils.token_generator import generate_token
from tests.conftest import ok, fail

BASE_URL = "http://localhost:8000"


def test_marketplace_list_all():
    """Test listing all published projects"""
    print("\n--- Marketplace List All ---\n")
    
    db = SessionLocal()
    try:
        # Create some published projects
        project1 = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            brief_scope="Kitchen renovation",
            homeowner_name="John Doe",
            homeowner_email="john@example.com"
        )
        
        project2 = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="bathroom",
            zip_code="10002",
            total_price=25000.00,
            brief_scope="Bathroom remodel",
            homeowner_name="Jane Doe",
            homeowner_email="jane@example.com"
        )
        
        db.add(project1)
        db.add(project2)
        db.commit()
        
        ok("Created test projects", f"{project1.token}, {project2.token}")
        
        # List all published projects
        response = requests.get(
            f"{BASE_URL}/api/v1/marketplace",
            timeout=10
        )
        
        if response.status_code != 200:
            fail("Marketplace endpoint", f"Status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 2, f"Should have at least 2 projects, got {len(data)}"
        
        # Check structure of first project
        project = data[0]
        assert "token" in project, "Missing token"
        assert "project_type" in project, "Missing project_type"
        assert "zip_code" in project, "Missing zip_code"
        assert "total_price" in project, "Missing total_price"
        assert "status" not in project, "Should not include status (public view)"
        assert "homeowner_email" not in project, "Should not include homeowner email (locked)"
        
        ok("Marketplace list", f"Found {len(data)} projects")
        return True
        
    except Exception as e:
        fail("Marketplace list", str(e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_marketplace_filter_by_zip():
    """Test filtering by zip code"""
    print("\n--- Marketplace Filter by ZIP ---\n")
    
    db = SessionLocal()
    try:
        # Create project in specific zip
        project = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            brief_scope="Test project",
            homeowner_name="Test User",
            homeowner_email="test@example.com"
        )
        db.add(project)
        db.commit()
        
        ok("Created test project", project.token)
        
        # Filter by zip
        response = requests.get(
            f"{BASE_URL}/api/v1/marketplace?zip_code=10001",
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # All results should be in 10001
        for proj in data:
            assert proj["zip_code"] == "10001", f"Expected zip 10001, got {proj['zip_code']}"
        
        ok("Filter by ZIP", f"Found {len(data)} projects in 10001")
        return True
        
    except Exception as e:
        fail("Filter by ZIP", str(e))
        return False
    finally:
        db.close()


def test_marketplace_filter_by_type():
    """Test filtering by project type"""
    print("\n--- Marketplace Filter by Type ---\n")
    
    db = SessionLocal()
    try:
        # Create kitchen project
        project = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            brief_scope="Kitchen project",
            homeowner_name="Test",
            homeowner_email="test@example.com"
        )
        db.add(project)
        db.commit()
        
        # Filter by type
        response = requests.get(
            f"{BASE_URL}/api/v1/marketplace?project_type=kitchen",
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # All results should be kitchens
        for proj in data:
            assert proj["project_type"] == "kitchen", f"Expected kitchen, got {proj['project_type']}"
        
        ok("Filter by type", f"Found {len(data)} kitchen projects")
        return True
        
    except Exception as e:
        fail("Filter by type", str(e))
        return False
    finally:
        db.close()


def test_marketplace_filter_by_price():
    """Test filtering by price range"""
    print("\n--- Marketplace Filter by Price ---\n")
    
    db = SessionLocal()
    try:
        # Create projects with different prices
        project1 = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=30000.00,
            brief_scope="Low price",
            homeowner_name="Test",
            homeowner_email="test@example.com"
        )
        
        project2 = Project(
            token=generate_token("PRJ"),
            status="published",
            project_type="kitchen",
            zip_code="10001",
            total_price=50000.00,
            brief_scope="High price",
            homeowner_name="Test",
            homeowner_email="test2@example.com"
        )
        
        db.add(project1)
        db.add(project2)
        db.commit()
        
        # Filter by price range
        response = requests.get(
            f"{BASE_URL}/api/v1/marketplace?min_price=35000&max_price=55000",
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # All results should be in price range
        for proj in data:
            price = float(proj["total_price"])
            assert price >= 35000, f"Price {price} below min"
            assert price <= 55000, f"Price {price} above max"
        
        ok("Filter by price", f"Found {len(data)} projects in range")
        return True
        
    except Exception as e:
        fail("Filter by price", str(e))
        return False
    finally:
        db.close()


def test_marketplace_pagination():
    """Test pagination with limit and offset"""
    print("\n--- Marketplace Pagination ---\n")
    
    try:
        # Get first page
        response1 = requests.get(
            f"{BASE_URL}/api/v1/marketplace?limit=2&offset=0",
            timeout=10
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Get second page
        response2 = requests.get(
            f"{BASE_URL}/api/v1/marketplace?limit=2&offset=2",
            timeout=10
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Results should be different (if enough projects exist)
        if len(data1) == 2 and len(data2) > 0:
            # Check that results are different
            tokens1 = {p["token"] for p in data1}
            tokens2 = {p["token"] for p in data2}
            assert tokens1 != tokens2 or len(data2) == 0, "Pagination should return different results"
        
        ok("Pagination", f"Page 1: {len(data1)}, Page 2: {len(data2)}")
        return True
        
    except Exception as e:
        fail("Pagination", str(e))
        return False


def test_marketplace_excludes_draft():
    """Test that draft projects are not shown"""
    print("\n--- Marketplace Excludes Draft ---\n")
    
    db = SessionLocal()
    try:
        # Create draft project
        draft_project = Project(
            token=generate_token("PRJ"),
            status="draft",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00
        )
        db.add(draft_project)
        db.commit()
        
        ok("Created draft project", draft_project.token)
        
        # List marketplace
        response = requests.get(
            f"{BASE_URL}/api/v1/marketplace",
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Draft project should not be in results
        tokens = [p["token"] for p in data]
        assert draft_project.token not in tokens, "Draft project should not appear in marketplace"
        
        ok("Draft excluded", "Draft projects not shown")
        return True
        
    except Exception as e:
        fail("Draft exclusion", str(e))
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Marketplace Browse Endpoint Tests")
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
    results.append(test_marketplace_list_all())
    results.append(test_marketplace_filter_by_zip())
    results.append(test_marketplace_filter_by_type())
    results.append(test_marketplace_filter_by_price())
    results.append(test_marketplace_pagination())
    results.append(test_marketplace_excludes_draft())
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "="*60)
    if passed == total:
        print(f"✓ All tests passed ({passed}/{total})")
        print("\n💡 Note: These tests will fail until you implement the endpoint!")
        print("   Next: Implement GET /api/v1/marketplace")
    else:
        print(f"✗ Some tests failed ({passed}/{total} passed)")
    print("="*60 + "\n")

