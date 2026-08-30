"""durable copilot agent runs

Revision ID: 0043_durable_agent_runs
Revises: 0042_measured_metric_provenance
Create Date: 2026-08-24 01:25:01.442694
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0043_durable_agent_runs"
down_revision: str | None = "0042_measured_metric_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('copilot_agent_runs',
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('goal', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('parent_run_id', sa.Uuid(), nullable=True),
    sa.Column('allowed_tools', sa.JSON(), nullable=False),
    sa.Column('max_turns', sa.Integer(), nullable=False),
    sa.Column('turn_count', sa.Integer(), nullable=False),
    sa.Column('cost_usd_cents', sa.Integer(), nullable=False),
    sa.Column('max_cost_usd_cents', sa.Integer(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('legacy_id', sa.String(length=255), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['copilot_conversations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['parent_run_id'], ['copilot_agent_runs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('legacy_id')
    )
    op.create_index(op.f('ix_copilot_agent_runs_conversation_id'), 'copilot_agent_runs', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_copilot_agent_runs_created_by'), 'copilot_agent_runs', ['created_by'], unique=False)
    op.create_index(op.f('ix_copilot_agent_runs_parent_run_id'), 'copilot_agent_runs', ['parent_run_id'], unique=False)
    op.create_index('ix_copilot_agent_runs_project', 'copilot_agent_runs', ['project_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_copilot_agent_runs_project_id'), 'copilot_agent_runs', ['project_id'], unique=False)
    op.create_index('ix_copilot_agent_runs_status', 'copilot_agent_runs', ['status', 'updated_at'], unique=False)
    op.create_table('copilot_agent_tasks',
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('resource_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('tool_call_id', sa.String(length=120), nullable=False),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('legacy_id', sa.String(length=255), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['copilot_agent_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('legacy_id'),
    sa.UniqueConstraint('run_id', 'kind', 'resource_id', name='uq_agent_task_resource')
    )
    op.create_index(op.f('ix_copilot_agent_tasks_kind'), 'copilot_agent_tasks', ['kind'], unique=False)
    op.create_index(op.f('ix_copilot_agent_tasks_resource_id'), 'copilot_agent_tasks', ['resource_id'], unique=False)
    op.create_index(op.f('ix_copilot_agent_tasks_run_id'), 'copilot_agent_tasks', ['run_id'], unique=False)
    op.create_index('ix_copilot_agent_tasks_status', 'copilot_agent_tasks', ['status', 'updated_at'], unique=False)
    op.create_table('copilot_agent_turns',
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=24), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('tool_calls', sa.JSON(), nullable=False),
    sa.Column('tokens_in', sa.Integer(), nullable=False),
    sa.Column('tokens_out', sa.Integer(), nullable=False),
    sa.Column('cost_usd_cents', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('legacy_id', sa.String(length=255), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['copilot_agent_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('legacy_id'),
    sa.UniqueConstraint('run_id', 'sequence', name='uq_agent_turn_sequence')
    )
    op.create_index('ix_copilot_agent_turns_run', 'copilot_agent_turns', ['run_id', 'sequence'], unique=False)
    op.create_index(op.f('ix_copilot_agent_turns_run_id'), 'copilot_agent_turns', ['run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_copilot_agent_turns_run_id'), table_name='copilot_agent_turns')
    op.drop_index('ix_copilot_agent_turns_run', table_name='copilot_agent_turns')
    op.drop_table('copilot_agent_turns')
    op.drop_index('ix_copilot_agent_tasks_status', table_name='copilot_agent_tasks')
    op.drop_index(op.f('ix_copilot_agent_tasks_run_id'), table_name='copilot_agent_tasks')
    op.drop_index(op.f('ix_copilot_agent_tasks_resource_id'), table_name='copilot_agent_tasks')
    op.drop_index(op.f('ix_copilot_agent_tasks_kind'), table_name='copilot_agent_tasks')
    op.drop_table('copilot_agent_tasks')
    op.drop_index('ix_copilot_agent_runs_status', table_name='copilot_agent_runs')
    op.drop_index(op.f('ix_copilot_agent_runs_project_id'), table_name='copilot_agent_runs')
    op.drop_index('ix_copilot_agent_runs_project', table_name='copilot_agent_runs')
    op.drop_index(op.f('ix_copilot_agent_runs_parent_run_id'), table_name='copilot_agent_runs')
    op.drop_index(op.f('ix_copilot_agent_runs_created_by'), table_name='copilot_agent_runs')
    op.drop_index(op.f('ix_copilot_agent_runs_conversation_id'), table_name='copilot_agent_runs')
    op.drop_table('copilot_agent_runs')
