"""Add project_title, county, country columns to projects

Revision ID: 20250121_location
Revises: 20250120_multi_agent
Create Date: 2025-01-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20250121_location'
down_revision: Union[str, None] = '20250120_multi_agent'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add project_title column
    op.add_column('projects', sa.Column('project_title', sa.String(255), nullable=True))

    # Add county and country columns for comprehensive location data
    op.add_column('projects', sa.Column('county', sa.String(100), nullable=True))
    op.add_column('projects', sa.Column('country', sa.String(50), server_default='US', nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'country')
    op.drop_column('projects', 'county')
    op.drop_column('projects', 'project_title')
