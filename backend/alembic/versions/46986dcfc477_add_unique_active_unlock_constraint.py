"""add_unique_active_unlock_constraint

Revision ID: 46986dcfc477
Revises: 5a1e0b55ed63
Create Date: 2025-12-22 14:57:23.835117

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '46986dcfc477'
down_revision = '5a1e0b55ed63'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add partial unique index: only one active unlock per project
    # This ensures is_active=TRUE is unique per project_id
    op.create_index(
        'idx_one_active_unlock_per_project',
        'unlocks',
        ['project_id'],
        unique=True,
        postgresql_where=sa.text('is_active = TRUE')
    )


def downgrade() -> None:
    # Remove the partial unique index
    op.drop_index(
        'idx_one_active_unlock_per_project',
        table_name='unlocks'
    )

