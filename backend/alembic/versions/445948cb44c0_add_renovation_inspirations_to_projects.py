"""add renovation_inspirations to projects

Revision ID: 445948cb44c0
Revises: 20251225_analysis
Create Date: 2026-01-05 11:43:00.769067

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '445948cb44c0'
down_revision = '20251225_analysis'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add renovation_inspirations column to projects table
    op.add_column('projects', sa.Column('renovation_inspirations', JSONB, nullable=True))


def downgrade() -> None:
    # Remove renovation_inspirations column from projects table
    op.drop_column('projects', 'renovation_inspirations')

