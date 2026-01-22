"""Add multi-agent tool system columns to projects

Revision ID: 20250120_multi_agent
Revises: 445948cb44c0
Create Date: 2025-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20250120_multi_agent'
down_revision: Union[str, None] = '445948cb44c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add address fields
    op.add_column('projects', sa.Column('street_address', sa.String(255), nullable=True))
    op.add_column('projects', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('projects', sa.Column('state', sa.String(50), nullable=True))
    op.add_column('projects', sa.Column('latitude', sa.Numeric(10, 7), nullable=True))
    op.add_column('projects', sa.Column('longitude', sa.Numeric(10, 7), nullable=True))
    op.add_column('projects', sa.Column('is_nyc', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('projects', sa.Column('borough', sa.String(50), nullable=True))

    # Add NYC DOB fields
    op.add_column('projects', sa.Column('nyc_bbl', sa.String(20), nullable=True))
    op.add_column('projects', sa.Column('building_age', sa.Integer(), nullable=True))
    op.add_column('projects', sa.Column('zoning_district', sa.String(50), nullable=True))
    op.add_column('projects', sa.Column('landmark_status', sa.String(50), nullable=True))
    op.add_column('projects', sa.Column('open_violations_count', sa.Integer(), nullable=True))
    op.add_column('projects', sa.Column('dob_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Add session preferences fields
    op.add_column('projects', sa.Column('session_sticky_notes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('projects', sa.Column('pending_hitl_questions', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove session preferences fields
    op.drop_column('projects', 'pending_hitl_questions')
    op.drop_column('projects', 'session_sticky_notes')

    # Remove NYC DOB fields
    op.drop_column('projects', 'dob_data')
    op.drop_column('projects', 'open_violations_count')
    op.drop_column('projects', 'landmark_status')
    op.drop_column('projects', 'zoning_district')
    op.drop_column('projects', 'building_age')
    op.drop_column('projects', 'nyc_bbl')

    # Remove address fields
    op.drop_column('projects', 'borough')
    op.drop_column('projects', 'is_nyc')
    op.drop_column('projects', 'longitude')
    op.drop_column('projects', 'latitude')
    op.drop_column('projects', 'state')
    op.drop_column('projects', 'city')
    op.drop_column('projects', 'street_address')
