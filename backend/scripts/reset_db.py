"""
Utility script to clear application data from the database.

This keeps the schema (tables, migrations) intact and only deletes rows from:
- unlocks
- conversation_states
- llm_costs
- projects

Usage (from backend directory, with your virtualenv active):

    python scripts/reset_db.py
"""

from sqlalchemy import text

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db.database import SessionLocal


def reset_database() -> None:
  """Truncate core tables and restart identity sequences."""
  db = SessionLocal()
  try:
    # Order doesn't matter with CASCADE, but we list all app tables explicitly.
    db.execute(
      text(
        """
        TRUNCATE TABLE
          llm_costs,
          conversation_states,
          unlocks,
          projects
        RESTART IDENTITY CASCADE;
        """
      )
    )
    db.commit()
    print("✅ Database reset: projects, unlocks, conversation_states, llm_costs cleared.")
  except Exception as exc:
    db.rollback()
    print(f"⚠️ Failed to reset database: {exc}")
    raise
  finally:
    db.close()


if __name__ == "__main__":
  reset_database()


