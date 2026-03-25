"""Add saved_results table for permanent job storage

Revision ID: add_saved_results
Revises: add_ai_tables
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_saved_results'
down_revision = 'add_ai_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'saved_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('save_id', sa.String(8), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('result_path', sa.Text(), nullable=False),
        sa.Column('original_path', sa.Text(), nullable=True),
        sa.Column('bounds', postgresql.JSON(), nullable=True),
        sa.Column('colormap', sa.String(50), nullable=False, server_default='viridis'),
        sa.Column('vmin', sa.Float(), nullable=True),
        sa.Column('vmax', sa.Float(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_query', sa.Text(), nullable=True),
        sa.Column('job_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('save_id'),
    )
    op.create_index('ix_saved_results_save_id', 'saved_results', ['save_id'])
    op.create_index('ix_saved_results_created', 'saved_results', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_saved_results_created', table_name='saved_results')
    op.drop_index('ix_saved_results_save_id', table_name='saved_results')
    op.drop_table('saved_results')
