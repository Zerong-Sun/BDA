"""Add traceable scientific literature search and retrieval records.

Revision ID: 0011_literature_retrieval_trace
Revises: 0010_copilot_research_generation
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_literature_retrieval_trace"
down_revision = "0010_copilot_research_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "literature_search_runs",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column("fetch_full_text", sa.Boolean(), nullable=False),
        sa.Column("extract_claims", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legacy_id", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_id"),
    )
    op.create_index("ix_literature_search_runs_project_id", "literature_search_runs", ["project_id"])
    op.create_index("ix_literature_search_runs_created_by", "literature_search_runs", ["created_by"])
    op.create_index("ix_literature_search_runs_status", "literature_search_runs", ["status"])

    op.create_table(
        "literature_retrieval_traces",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("search_run_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("response_metadata", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("content_checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("byte_count", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legacy_id", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["search_run_id"], ["literature_search_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["literature_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_id"),
    )
    op.create_index("ix_literature_retrieval_traces_project_id", "literature_retrieval_traces", ["project_id"])
    op.create_index("ix_literature_retrieval_traces_search_run_id", "literature_retrieval_traces", ["search_run_id"])
    op.create_index("ix_literature_retrieval_traces_document_id", "literature_retrieval_traces", ["document_id"])
    op.create_index("ix_literature_retrieval_traces_stage", "literature_retrieval_traces", ["stage"])
    op.create_index("ix_literature_retrieval_traces_source", "literature_retrieval_traces", ["source"])
    op.create_index("ix_literature_retrieval_traces_status", "literature_retrieval_traces", ["status"])
    op.create_index(
        "ix_literature_retrieval_traces_response_checksum_sha256",
        "literature_retrieval_traces",
        ["response_checksum_sha256"],
    )
    op.create_index(
        "ix_literature_retrieval_traces_content_checksum_sha256",
        "literature_retrieval_traces",
        ["content_checksum_sha256"],
    )


def downgrade() -> None:
    op.drop_table("literature_retrieval_traces")
    op.drop_table("literature_search_runs")
