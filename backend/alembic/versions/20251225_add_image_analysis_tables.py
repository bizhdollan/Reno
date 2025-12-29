"""add_image_analysis_and_metadata_tables

Revision ID: 20251225_analysis
Revises: 46986dcfc477
Create Date: 2025-12-25

This migration adds:
- image_analysis: Store extracted features and critical elements per image
- image_metadata: Store perspective and consistency metadata
- generation_history: Track all generated images with metadata
- budget_context: Store detected budget sentiment (NO prices)
- correction_history: Track user corrections with undo capability
- perspective_changes: Track which regions changed in which perspective
- Enhanced llm_costs: Add api_call_id, operation_type, cost_usd columns
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251225_analysis'
down_revision = '46986dcfc477'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # 1. CREATE image_analysis TABLE
    # =========================================================================
    op.create_table(
        'image_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=False),
        sa.Column('room_type', sa.Text(), nullable=True),
        sa.Column('extracted_features', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('critical_elements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_image_analysis_project', 'image_analysis', ['project_id'])
    op.create_index('idx_image_analysis_url', 'image_analysis', ['image_url'])

    # =========================================================================
    # 2. CREATE image_metadata TABLE
    # =========================================================================
    op.create_table(
        'image_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('image_analysis.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=False),
        sa.Column('perspective_type', sa.Text(), nullable=True),
        sa.Column('perspective_confidence', sa.Float(), nullable=True),
        sa.Column('room_consistency_hash', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "perspective_type IN ('front', 'side', 'top_down', 'close_up') OR perspective_type IS NULL",
            name='check_perspective_type'
        ),
    )
    op.create_index('idx_image_metadata_project', 'image_metadata', ['project_id'])
    op.create_index('idx_image_metadata_analysis', 'image_metadata', ['image_analysis_id'])

    # =========================================================================
    # 3. CREATE generation_history TABLE
    # =========================================================================
    op.create_table(
        'generation_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_image_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('generation_type', sa.Text(), nullable=False),
        sa.Column('prompt_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('critical_elements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('perspective_constraint', sa.Text(), nullable=True),
        sa.Column('result_image_url', sa.Text(), nullable=True),
        sa.Column('user_feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "generation_type IN ('initial', 'additive', 'restart')",
            name='check_generation_type'
        ),
    )
    op.create_index('idx_generation_history_project', 'generation_history', ['project_id'])
    op.create_index('idx_generation_history_source', 'generation_history', ['source_image_id'])

    # =========================================================================
    # 4. CREATE budget_context TABLE
    # =========================================================================
    op.create_table(
        'budget_context',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('budget_sentiment', sa.Text(), nullable=False),
        sa.Column('detected_from_message', sa.Text(), nullable=True),
        sa.Column('suggested_materials', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "budget_sentiment IN ('low', 'medium', 'high')",
            name='check_budget_sentiment'
        ),
    )
    op.create_index('idx_budget_context_project', 'budget_context', ['project_id'])

    # =========================================================================
    # 5. CREATE correction_history TABLE
    # =========================================================================
    op.create_table(
        'correction_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('correction_type', sa.Text(), nullable=False),
        sa.Column('field_changed', sa.Text(), nullable=False),
        sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('user_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "correction_type IN ('extraction', 'vision', 'feedback')",
            name='check_correction_type'
        ),
    )
    op.create_index('idx_correction_history_project', 'correction_history', ['project_id'])
    op.create_index('idx_correction_history_timestamp', 'correction_history', [sa.text('created_at DESC')])

    # =========================================================================
    # 6. CREATE perspective_changes TABLE
    # =========================================================================
    op.create_table(
        'perspective_changes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_metadata_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('image_metadata.id', ondelete='CASCADE'), nullable=True),
        sa.Column('generation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('generation_history.id', ondelete='CASCADE'), nullable=True),
        sa.Column('change_category', sa.Text(), nullable=False),
        sa.Column('change_description', sa.Text(), nullable=True),
        sa.Column('applied_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_perspective_changes_project', 'perspective_changes', ['project_id'])
    op.create_index('idx_perspective_changes_generation', 'perspective_changes', ['generation_id'])

    # =========================================================================
    # 7. ENHANCE llm_costs TABLE
    # =========================================================================
    op.add_column('llm_costs', sa.Column('api_call_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('llm_costs', sa.Column('operation_type', sa.Text(), nullable=True))
    op.add_column('llm_costs', sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True))
    op.create_index('idx_llm_costs_api_call', 'llm_costs', ['api_call_id'], unique=True)
    op.create_index('idx_llm_costs_operation', 'llm_costs', ['operation_type'])


def downgrade() -> None:
    # Remove llm_costs enhancements
    op.drop_index('idx_llm_costs_operation', table_name='llm_costs')
    op.drop_index('idx_llm_costs_api_call', table_name='llm_costs')
    op.drop_column('llm_costs', 'cost_usd')
    op.drop_column('llm_costs', 'operation_type')
    op.drop_column('llm_costs', 'api_call_id')

    # Drop new tables in reverse order (respecting foreign keys)
    op.drop_index('idx_perspective_changes_generation', table_name='perspective_changes')
    op.drop_index('idx_perspective_changes_project', table_name='perspective_changes')
    op.drop_table('perspective_changes')

    op.drop_index('idx_correction_history_timestamp', table_name='correction_history')
    op.drop_index('idx_correction_history_project', table_name='correction_history')
    op.drop_table('correction_history')

    op.drop_index('idx_budget_context_project', table_name='budget_context')
    op.drop_table('budget_context')

    op.drop_index('idx_generation_history_source', table_name='generation_history')
    op.drop_index('idx_generation_history_project', table_name='generation_history')
    op.drop_table('generation_history')

    op.drop_index('idx_image_metadata_analysis', table_name='image_metadata')
    op.drop_index('idx_image_metadata_project', table_name='image_metadata')
    op.drop_table('image_metadata')

    op.drop_index('idx_image_analysis_url', table_name='image_analysis')
    op.drop_index('idx_image_analysis_project', table_name='image_analysis')
    op.drop_table('image_analysis')
