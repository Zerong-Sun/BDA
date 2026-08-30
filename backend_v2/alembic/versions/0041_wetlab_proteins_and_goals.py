"""Wet-lab protein library, and the research goal tree that links dry and wet work.

Revision ID: 0041_wetlab_proteins_and_goals
Revises: 0039_proteinhunter_drop_dead_seq
Create Date: 2026-08-23 15:16:00.715892
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0041_wetlab_proteins_and_goals"
down_revision: str | None = "0040_project_design_prompt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('research_goals',
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('legacy_id', sa.String(length=255), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['research_goals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('legacy_id')
    )
    op.create_index(op.f('ix_research_goals_created_by'), 'research_goals', ['created_by'], unique=False)
    op.create_index(op.f('ix_research_goals_parent_id'), 'research_goals', ['parent_id'], unique=False)
    op.create_index(op.f('ix_research_goals_project_id'), 'research_goals', ['project_id'], unique=False)
    op.create_index('ix_research_goals_project_parent', 'research_goals', ['project_id', 'parent_id', 'sort_order'], unique=False)
    op.create_index('ix_research_goals_project_status', 'research_goals', ['project_id', 'status'], unique=False)
    op.create_index(op.f('ix_research_goals_status'), 'research_goals', ['status'], unique=False)
    op.create_table('research_goal_links',
    sa.Column('goal_id', sa.Uuid(), nullable=False),
    sa.Column('resource_type', sa.String(length=40), nullable=False),
    sa.Column('resource_id', sa.Uuid(), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('legacy_id', sa.String(length=255), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['goal_id'], ['research_goals.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('goal_id', 'resource_type', 'resource_id', name='uq_goal_link_resource'),
    sa.UniqueConstraint('legacy_id')
    )
    op.create_index('ix_goal_links_resource', 'research_goal_links', ['resource_type', 'resource_id'], unique=False)
    op.create_index(op.f('ix_research_goal_links_created_by'), 'research_goal_links', ['created_by'], unique=False)
    op.create_index(op.f('ix_research_goal_links_goal_id'), 'research_goal_links', ['goal_id'], unique=False)
    op.create_index(op.f('ix_research_goal_links_resource_id'), 'research_goal_links', ['resource_id'], unique=False)
    op.create_index(op.f('ix_research_goal_links_resource_type'), 'research_goal_links', ['resource_type'], unique=False)
    op.create_table('proteins',
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('sequence', sa.Text(), nullable=False),
    sa.Column('sequence_sha256', sa.String(length=64), nullable=False),
    sa.Column('length', sa.Integer(), nullable=False),
    sa.Column('molecular_weight', sa.Float(), nullable=True),
    sa.Column('ext_coeff_reduced', sa.Float(), nullable=True),
    sa.Column('ext_coeff_oxidized', sa.Float(), nullable=True),
    sa.Column('candidate_id', sa.Uuid(), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('legacy_id', sa.String(length=255), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('legacy_id'),
    sa.UniqueConstraint('project_id', 'sequence_sha256', name='uq_protein_project_sequence')
    )
    op.create_index(op.f('ix_proteins_candidate_id'), 'proteins', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_proteins_created_by'), 'proteins', ['created_by'], unique=False)
    op.create_index(op.f('ix_proteins_project_id'), 'proteins', ['project_id'], unique=False)
    op.create_index('ix_proteins_project_name', 'proteins', ['project_id', 'name'], unique=False)
    op.create_index(op.f('ix_proteins_sequence_sha256'), 'proteins', ['sequence_sha256'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_proteins_sequence_sha256'), table_name='proteins')
    op.drop_index('ix_proteins_project_name', table_name='proteins')
    op.drop_index(op.f('ix_proteins_project_id'), table_name='proteins')
    op.drop_index(op.f('ix_proteins_created_by'), table_name='proteins')
    op.drop_index(op.f('ix_proteins_candidate_id'), table_name='proteins')
    op.drop_table('proteins')
    op.drop_index(op.f('ix_research_goal_links_resource_type'), table_name='research_goal_links')
    op.drop_index(op.f('ix_research_goal_links_resource_id'), table_name='research_goal_links')
    op.drop_index(op.f('ix_research_goal_links_goal_id'), table_name='research_goal_links')
    op.drop_index(op.f('ix_research_goal_links_created_by'), table_name='research_goal_links')
    op.drop_index('ix_goal_links_resource', table_name='research_goal_links')
    op.drop_table('research_goal_links')
    op.drop_index(op.f('ix_research_goals_status'), table_name='research_goals')
    op.drop_index('ix_research_goals_project_status', table_name='research_goals')
    op.drop_index('ix_research_goals_project_parent', table_name='research_goals')
    op.drop_index(op.f('ix_research_goals_project_id'), table_name='research_goals')
    op.drop_index(op.f('ix_research_goals_parent_id'), table_name='research_goals')
    op.drop_index(op.f('ix_research_goals_created_by'), table_name='research_goals')
    op.drop_table('research_goals')
