"""Add AI session and process graph tables

Revision ID: add_ai_tables
Revises: 862aed8d0722
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_ai_tables'
down_revision = '9ad7e6b87a94'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ai_sessions table
    op.create_table(
        'ai_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('context', postgresql.JSON(), nullable=True, default={}),
        sa.Column('messages', postgresql.JSON(), nullable=True, default=[]),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_sessions_user_id', 'ai_sessions', ['user_id'])
    op.create_index('ix_ai_sessions_user_updated', 'ai_sessions', ['user_id', 'updated_at'])

    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create saved_process_graphs table
    op.create_table(
        'saved_process_graphs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('process_graph', postgresql.JSON(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=True, default=False),
        sa.Column('use_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_saved_process_graphs_user_id', 'saved_process_graphs', ['user_id'])
    op.create_index('ix_saved_process_graphs_user_name', 'saved_process_graphs', ['user_id', 'name'])
    op.create_index('ix_saved_process_graphs_public', 'saved_process_graphs', ['is_public'])

    # Create process_graph_tags junction table
    op.create_table(
        'process_graph_tags',
        sa.Column('process_graph_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['process_graph_id'], ['saved_process_graphs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('process_graph_id', 'tag_id')
    )

    # Create execution_history table
    op.create_table(
        'execution_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('process_graph', postgresql.JSON(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('result_path', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('cost_estimate', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['ai_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_history_user_id', 'execution_history', ['user_id'])
    op.create_index('ix_execution_history_user_created', 'execution_history', ['user_id', 'created_at'])
    op.create_index('ix_execution_history_status', 'execution_history', ['status'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_execution_history_status', table_name='execution_history')
    op.drop_index('ix_execution_history_user_created', table_name='execution_history')
    op.drop_index('ix_execution_history_user_id', table_name='execution_history')
    op.drop_table('execution_history')

    op.drop_table('process_graph_tags')

    op.drop_index('ix_saved_process_graphs_public', table_name='saved_process_graphs')
    op.drop_index('ix_saved_process_graphs_user_name', table_name='saved_process_graphs')
    op.drop_index('ix_saved_process_graphs_user_id', table_name='saved_process_graphs')
    op.drop_table('saved_process_graphs')

    op.drop_table('tags')

    op.drop_index('ix_ai_sessions_user_updated', table_name='ai_sessions')
    op.drop_index('ix_ai_sessions_user_id', table_name='ai_sessions')
    op.drop_table('ai_sessions')
