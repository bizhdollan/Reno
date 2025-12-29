"""
Migration Script: Migrate existing data to new DB-backed architecture.

This script migrates data from the legacy conversation_state JSONB storage
to the new normalized tables (image_analysis, generation_history, etc.).

Usage:
    python scripts/migrate_to_new_architecture.py [--dry-run]

Options:
    --dry-run    Show what would be migrated without making changes
"""

import sys
import json
import argparse
from datetime import datetime
from uuid import uuid4, UUID
from typing import Optional

# Add project root to path
sys.path.insert(0, "/Users/chhabi/Desktop/Reno/backend")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.db.models import (
    Project,
    ConversationState,
    ImageAnalysis,
    ImageMetadata,
    GenerationHistory,
)
from src.db.database import DATABASE_URL


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Migrate to new architecture")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    return parser.parse_args()


def extract_critical_elements(extracted_data: dict) -> dict:
    """
    Extract critical elements from legacy extracted_data.

    Critical elements are structural features that must be preserved:
    - Windows (count, positions)
    - Doors (count, positions)
    - Structural elements
    """
    critical = {}

    # Look for window mentions in materials or fixtures
    materials = extracted_data.get("materials", [])
    fixtures = extracted_data.get("fixtures", [])
    measurements = extracted_data.get("measurements", {})

    # Count windows from fixtures or style description
    windows = [f for f in fixtures if "window" in f.get("name", "").lower()]
    if windows:
        critical["windows"] = {"count": len(windows), "detected_from": "fixtures"}

    # Count doors
    doors = [m for m in materials if "door" in m.get("name", "").lower()]
    if doors:
        critical["doors"] = {"count": len(doors), "detected_from": "materials"}

    # Add room dimensions if available
    if measurements:
        critical["room_dimensions"] = {
            "width_ft": measurements.get("room_width_ft"),
            "length_ft": measurements.get("room_length_ft"),
            "height_ft": measurements.get("room_height_ft"),
        }

    return critical


def migrate_project(
    session, project: Project, state: ConversationState, dry_run: bool = False
) -> dict:
    """
    Migrate a single project's data to new architecture.

    Returns migration stats.
    """
    stats = {
        "image_analyses_created": 0,
        "generation_history_created": 0,
        "skipped": False,
    }

    if not state or not state.state:
        stats["skipped"] = True
        return stats

    state_data = state.state

    # Extract image analyses from legacy state
    image_analyses = state_data.get("image_analyses", [])
    extracted_data = state_data.get("extracted_data", {})

    for img_data in image_analyses:
        img_url = img_data.get("url")
        analysis = img_data.get("analysis", {})

        if not img_url:
            continue

        # Check if already migrated
        existing = (
            session.query(ImageAnalysis)
            .filter_by(project_id=project.id, image_url=img_url)
            .first()
        )
        if existing:
            continue

        # Extract critical elements
        critical_elements = extract_critical_elements(analysis)

        # Detect room type
        style = analysis.get("style", {})
        room_type = style.get("overall_style", "unknown")

        if not dry_run:
            # Create ImageAnalysis record
            new_analysis = ImageAnalysis(
                id=uuid4(),
                project_id=project.id,
                image_url=img_url,
                room_type=room_type,
                extracted_features=analysis,
                critical_elements=critical_elements,
                confidence_score=0.8,  # Default confidence
            )
            session.add(new_analysis)
            stats["image_analyses_created"] += 1

    # Extract generation history from legacy state
    generated_history = state_data.get("generated_image_history", [])

    for gen_data in generated_history:
        gen_url = gen_data.get("url")
        description = gen_data.get("description", "")

        if not gen_url:
            continue

        # Check if already migrated
        existing = (
            session.query(GenerationHistory)
            .filter_by(project_id=project.id, result_image_url=gen_url)
            .first()
        )
        if existing:
            continue

        # Get the most recent image analysis for this project
        latest_analysis = (
            session.query(ImageAnalysis)
            .filter_by(project_id=project.id)
            .order_by(ImageAnalysis.created_at.desc())
            .first()
        )

        if not latest_analysis and not dry_run:
            # Skip if no analysis exists
            continue

        if not dry_run:
            # Create GenerationHistory record
            new_gen = GenerationHistory(
                id=uuid4(),
                project_id=project.id,
                image_analysis_id=latest_analysis.id if latest_analysis else None,
                generation_type="initial",
                prompt_data={
                    "vision": state_data.get("renovation_vision", {}),
                    "description": description,
                },
                critical_elements=critical_elements if latest_analysis else {},
                result_image_url=gen_url,
                user_feedback=gen_data.get("feedback"),
            )
            session.add(new_gen)
            stats["generation_history_created"] += 1

    return stats


def run_migration(dry_run: bool = False):
    """Run the full migration."""
    print(f"\n{'=' * 60}")
    print(f"Migration to New Architecture {'(DRY RUN)' if dry_run else ''}")
    print(f"{'=' * 60}\n")

    # Connect to database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get all projects with conversation state
        projects = session.query(Project).all()
        print(f"Found {len(projects)} projects to process\n")

        total_stats = {
            "projects_processed": 0,
            "projects_skipped": 0,
            "image_analyses_created": 0,
            "generation_history_created": 0,
        }

        for project in projects:
            print(f"Processing project: {project.id} ({project.project_type or 'Unknown type'})")

            # Get conversation state
            state = (
                session.query(ConversationState).filter_by(project_id=project.id).first()
            )

            if not state:
                print(f"  - No conversation state found, skipping")
                total_stats["projects_skipped"] += 1
                continue

            stats = migrate_project(session, project, state, dry_run)

            if stats["skipped"]:
                print(f"  - No data to migrate")
                total_stats["projects_skipped"] += 1
            else:
                print(f"  - Created {stats['image_analyses_created']} image analyses")
                print(f"  - Created {stats['generation_history_created']} generation history records")
                total_stats["projects_processed"] += 1
                total_stats["image_analyses_created"] += stats["image_analyses_created"]
                total_stats["generation_history_created"] += stats["generation_history_created"]

        # Commit changes if not dry run
        if not dry_run:
            session.commit()
            print("\n✓ Changes committed to database")
        else:
            session.rollback()
            print("\n(Dry run - no changes made)")

        # Print summary
        print(f"\n{'=' * 60}")
        print("Migration Summary")
        print(f"{'=' * 60}")
        print(f"Projects processed: {total_stats['projects_processed']}")
        print(f"Projects skipped: {total_stats['projects_skipped']}")
        print(f"Image analyses created: {total_stats['image_analyses_created']}")
        print(f"Generation history created: {total_stats['generation_history_created']}")

    except Exception as e:
        session.rollback()
        print(f"\n✗ Error during migration: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    args = parse_args()
    run_migration(dry_run=args.dry_run)
