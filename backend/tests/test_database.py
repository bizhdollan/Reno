"""
Test script to verify database setup and basic operations.

Run this after setting up the database to ensure everything works.
"""
from datetime import datetime, UTC

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db.database import SessionLocal, engine
from src.db.models import Project, Unlock, ConversationState, LLMCost
from src.utils.token_generator import generate_token

def test_database():
    """Test all database operations"""
    print("=" * 60)
    print("DATABASE TEST SUITE")
    print("=" * 60)
    
    # Create session
    db = SessionLocal()
    
    try:
        # Test 1: Create project
        print("\n[1/8] Testing project creation...")
        project = Project(
            token=generate_token("PRJ"),
            status="draft",
            project_type="kitchen",
            zip_code="10001",
            homeowner_email="test@example.com",
            homeowner_name="John Doe",
            total_price=45000.00,
            brief_scope="Full kitchen renovation with modern appliances"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        print(f"   ✅ Created project: {project.token} (ID: {project.id})")
        
        # Test 2: Query project
        print("\n[2/8] Testing project query...")
        found_project = db.query(Project).filter(Project.token == project.token).first()
        if found_project:
            print(f"   ✅ Found project by token: {found_project.token}")
        else:
            print("   ❌ Failed to find project")
            return
        
        # Test 3: Update project
        print("\n[3/8] Testing project update...")
        project.status = "completed"
        project.homeowner_phone = "(555) 123-4567"
        db.commit()
        print(f"   ✅ Updated project status: {project.status}")
        
        # Test 4: Create unlock
        print("\n[4/8] Testing unlock creation...")
        unlock = Unlock(
            project_id=project.id,
            unlock_token=generate_token("UNL"),
            contractor_email="contractor@example.com",
            payment_status="pending",
            amount=199.00
        )
        db.add(unlock)
        db.commit()
        db.refresh(unlock)
        print(f"   ✅ Created unlock: {unlock.unlock_token}")
        
        # Test 5: Update unlock (simulate payment)
        print("\n[5/8] Testing unlock payment update...")
        unlock.payment_status = "completed"
        unlock.is_active = True
        unlock.unlocked_at = datetime.now(UTC)
        unlock.contractor_name = "Mike Smith"
        unlock.contractor_phone = "(555) 987-6543"
        unlock.contractor_company = "Mike's Renovations"
        unlock.contractor_details_saved = True
        db.commit()
        print(f"   ✅ Updated unlock payment status: {unlock.payment_status}")
        
        # Test 6: Create conversation state
        print("\n[6/8] Testing conversation state...")
        state = ConversationState(
            project_id=project.id,
            state={
                "messages": [
                    {"role": "assistant", "content": "Hello!"},
                    {"role": "user", "content": "Hi!"}
                ],
                "current_stage": "project_basics",
                "project_title": "Kitchen Renovation",
                "zip_code": "10001"
            }
        )
        db.add(state)
        db.commit()
        print(f"   ✅ Created conversation state for project {project.id}")
        
        # Test 7: Create LLM cost record
        print("\n[7/8] Testing LLM cost tracking...")
        cost = LLMCost(
            project_id=project.id,
            model="gemini-2.5-flash",
            input_tokens=1200,
            output_tokens=850,
            cost=0.0042
        )
        db.add(cost)
        db.commit()
        print(f"   ✅ Created LLM cost record: {cost.model} (${cost.cost})")
        
        # Test 8: Marketplace query simulation
        print("\n[8/8] Testing marketplace query...")
        project.status = "published"
        db.commit()
        
        marketplace_projects = db.query(Project).filter(
            Project.status == "published",
            Project.deleted_at.is_(None)
        ).all()
        print(f"   ✅ Found {len(marketplace_projects)} published project(s)")
        
        # Test soft delete
        print("\n[EXTRA] Testing soft delete...")
        project.deleted_at = datetime.now(UTC)
        db.commit()
        
        active_projects = db.query(Project).filter(
            Project.deleted_at.is_(None)
        ).count()
        deleted_projects = db.query(Project).filter(
            Project.deleted_at.isnot(None)
        ).count()
        print(f"   ✅ Active projects: {active_projects}, Deleted: {deleted_projects}")
        
        # Summary
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print(f"\nTest Summary:")
        print(f"  - Project Token:  {project.token}")
        print(f"  - Unlock Token:   {unlock.unlock_token}")
        print(f"  - Project Status: {project.status}")
        print(f"  - Unlock Status:  {unlock.payment_status}")
        print(f"  - Database:       Connected ✅")
        print("\n✅ Database setup is working correctly!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nRolling back transaction...")
        db.rollback()
        return False
        
    finally:
        db.close()
    
    return True


if __name__ == "__main__":
    import sys
    
    try:
        success = test_database()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)

