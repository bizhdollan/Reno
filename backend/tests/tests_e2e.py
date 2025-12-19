"""
End-to-end test of the core flow.

Run: python tests/test_e2e.py
Prereqs:
  - Backend running: python main.py
  - PostgreSQL running: docker-compose up -d
  - Stripe webhook secret optional (mocked if absent)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from datetime import datetime, UTC
from src.db.database import SessionLocal
from src.db.models import Project, Unlock, ConversationState
from src.utils.token_generator import generate_token
from tests.conftest import ok, fail

BASE_URL = "http://localhost:8000"


def e2e_flow():
    print("\n" + "="*60)
    print("END-TO-END FLOW")
    print("="*60)

    db = SessionLocal()
    try:
        # 1) Create completed project in DB
        project_token = generate_token("PRJ")
        project = Project(
            token=project_token,
            status="completed",
            project_type="kitchen",
            zip_code="10001",
            total_price=45000.00,
            brief_scope="Full kitchen renovation",
            homeowner_email="homeowner@example.com"
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # Conversation state
        state = ConversationState(
            project_id=project.id,
            state={
                "current_stage": "completed",
                "project_title": "Kitchen Renovation",
                "project_type": "kitchen",
                "zip_code": "10001",
                "cost_tiers": [
                    {"id": "low", "total_cost": 30000},
                    {"id": "mid", "total_cost": 45000},
                    {"id": "high", "total_cost": 65000},
                ],
                "selected_tier": "mid",
            }
        )
        db.add(state)
        db.commit()
        ok("Created completed project", project_token)

        # 2) Save project (email optional)
        resp = requests.post(
            f"{BASE_URL}/api/v1/projects/save",
            json={"email": "homeowner@example.com", "project_token": project_token},
            timeout=10,
        )
        assert resp.status_code == 200, f"save status {resp.status_code}: {resp.text}"
        ok("Save project", f"token={project_token}")

        # 3) Publish project
        resp = requests.post(
            f"{BASE_URL}/api/v1/projects/{project_token}/publish",
            json={
                "homeowner_name": "John Doe",
                "homeowner_email": "homeowner@example.com",
                "homeowner_phone": "(555) 123-4567",
            },
            timeout=10,
        )
        assert resp.status_code == 200, f"publish status {resp.status_code}: {resp.text}"
        ok("Publish project", "status=published")

        # 4) Initiate unlock
        resp = requests.post(
            f"{BASE_URL}/api/v1/unlocks/initiate",
            json={
                "project_id": str(project.id),
                "contractor_email": "contractor@example.com",
            },
            timeout=10,
        )
        assert resp.status_code == 200, f"initiate status {resp.status_code}: {resp.text}"
        data = resp.json()
        unlock_token = data["unlock_token"]
        ok("Initiate unlock", unlock_token)

        # 5) Simulate payment success (update DB directly)
        unlock = db.query(Unlock).filter(Unlock.unlock_token == unlock_token).first()
        unlock.payment_status = "completed"
        unlock.is_active = True
        unlock.unlocked_at = datetime.now(UTC)
        unlock.payment_id = unlock.payment_id or "mock_payment_id"
        project.status = "unlocked"
        db.commit()
        ok("Simulated payment success", f"unlock={unlock_token}")

        # 6) Save contractor details
        resp = requests.post(
            f"{BASE_URL}/api/v1/unlocks/{unlock_token}/details",
            json={
                "contractor_name": "Mike Smith",
                "contractor_phone": "(555) 987-6543",
                "contractor_company": "Mike's Renovations",
            },
            timeout=10,
        )
        assert resp.status_code == 200, f"details status {resp.status_code}: {resp.text}"
        ok("Save contractor details", "details saved")

        # 7) Get unlock details
        resp = requests.get(
            f"{BASE_URL}/api/v1/unlocks/{unlock_token}",
            timeout=10,
        )
        assert resp.status_code == 200, f"get unlock status {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["contractor_name"] == "Mike Smith"
        assert data["project"]["homeowner_email"] == "homeowner@example.com"
        ok("Get unlock details", "includes project + contractor")

        # Final status check
        db.refresh(project)
        db.refresh(unlock)
        assert project.status == "unlocked", "Project should be unlocked"
        assert unlock.contractor_details_saved is True, "Contractor details should be saved"
        ok("Final state", f"project={project.status}, unlock details saved")

        print("\n" + "="*60)
        print("✓ End-to-end flow passed")
        print("="*60 + "\n")
        return True

    except Exception as e:
        fail("E2E flow", str(e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("\n📋 Prerequisites:")
    print("   1. Backend running: python main.py")
    print("   2. PostgreSQL running: docker-compose up -d")
    print("   3. (Optional) Stripe & Resend keys in .env")
    print("\nPress Enter to continue...")
    try:
        input()
    except KeyboardInterrupt:
        sys.exit(0)

    success = e2e_flow()
    sys.exit(0 if success else 1)