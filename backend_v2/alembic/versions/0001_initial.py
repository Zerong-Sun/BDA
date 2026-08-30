"""Initial BDA v2 PostgreSQL schema.

Revision ID: 0001_initial
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def entity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(255), unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        *entity_columns(),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="researcher"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("oidc_issuer", sa.String(500)),
        sa.Column("oidc_subject", sa.String(255)),
        sa.UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_user_oidc_subject"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "organizations",
        *entity_columns(),
        sa.Column("name", sa.String(160), nullable=False, unique=True),
    )
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_table(
        "organization_members",
        sa.Column(
            "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
    )
    op.create_table(
        "oidc_login_states",
        sa.Column("state", sa.String(120), primary_key=True),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("code_verifier", sa.String(255), nullable=False),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "projects",
        *entity_columns(),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("project_type", sa.String(80), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_deleted_at", "projects", ["deleted_at"])
    op.create_table(
        "project_members",
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="researcher"),
    )
    op.create_table(
        "targets",
        *entity_columns(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sequence", sa.Text()),
        sa.Column("uniprot_accession", sa.String(32)),
        sa.Column("organism", sa.String(200)),
        sa.Column("identity_status", sa.String(40), nullable=False, server_default="unconfirmed"),
        sa.Column("structure_artifact_id", sa.Uuid()),
        sa.Column("structure_status", sa.String(40), nullable=False, server_default="missing"),
        sa.UniqueConstraint("project_id", name="uq_target_project"),
    )
    op.create_index("ix_targets_project_id", "targets", ["project_id"])
    op.create_table(
        "workflow_runs",
        *entity_columns(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_workflow_runs_project_id", "workflow_runs", ["project_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_table(
        "workflow_nodes",
        *entity_columns(),
        sa.Column("workflow_run_id", sa.Uuid(), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_key", sa.String(120), nullable=False),
        sa.Column("node_type", sa.String(80), nullable=False),
        sa.Column("model_plugin", sa.String(160), nullable=False),
        sa.Column("container_image", sa.String(500)),
        sa.Column("command", sa.Text()),
        sa.Column("queue", sa.String(120)),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.UniqueConstraint("workflow_run_id", "node_key", name="uq_workflow_node_key"),
    )
    op.create_index("ix_workflow_nodes_workflow_run_id", "workflow_nodes", ["workflow_run_id"])
    op.create_table(
        "job_submissions",
        *entity_columns(),
        sa.Column("workflow_run_id", sa.Uuid(), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("compute_backend", sa.String(32), nullable=False),
    )
    op.create_index("ix_job_submissions_workflow_run_id", "job_submissions", ["workflow_run_id"])
    op.create_index("ix_job_submissions_project_id", "job_submissions", ["project_id"])
    op.create_index("ix_job_submissions_created_by", "job_submissions", ["created_by"])
    op.create_index("ix_job_submissions_status", "job_submissions", ["status"])
    op.create_table(
        "jobs",
        *entity_columns(),
        sa.Column("submission_id", sa.Uuid(), sa.ForeignKey("job_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "workflow_node_id", sa.Uuid(), sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("compute_backend", sa.String(32), nullable=False),
        sa.Column("model_plugin", sa.String(160), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("external_id", sa.String(255)),
        sa.Column("next_poll_at", sa.DateTime(timezone=True)),
        sa.Column("timeout_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(120)),
        sa.Column("error_message", sa.Text()),
        sa.Column("runtime_spec", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "submission_id", "workflow_node_id", "attempt_number", name="uq_job_submission_node_attempt"
        ),
    )
    op.create_index("ix_jobs_submission_id", "jobs", ["submission_id"])
    op.create_index("ix_jobs_workflow_run_id", "jobs", ["workflow_run_id"])
    op.create_index("ix_jobs_workflow_node_id", "jobs", ["workflow_node_id"])
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_external_id", "jobs", ["external_id"])
    op.create_index("ix_jobs_next_poll_at", "jobs", ["next_poll_at"])
    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="created"),
        sa.Column("external_id", sa.String(255)),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("job_id", "attempt_number"),
    )
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])
    op.create_table(
        "job_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
    op.create_index("ix_job_events_created_at", "job_events", ["created_at"])
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("topic", sa.String(120), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_outbox_events_topic", "outbox_events", ["topic"])
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"])
    op.create_index("ix_outbox_events_published_at", "outbox_events", ["published_at"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(160), nullable=False),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("actor_id", "scope", "key"),
    )
    op.create_index("ix_idempotency_records_actor_id", "idempotency_records", ["actor_id"])
    op.create_table(
        "artifact_uploads",
        *entity_columns(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("artifact_type", sa.String(80), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("object_key", sa.String(800), nullable=False, unique=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="uploading"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.String(1000)),
    )
    op.create_index("ix_artifact_uploads_project_id", "artifact_uploads", ["project_id"])
    op.create_index("ix_artifact_uploads_created_by", "artifact_uploads", ["created_by"])
    op.create_index("ix_artifact_uploads_status", "artifact_uploads", ["status"])
    op.create_index("ix_artifact_uploads_expires_at", "artifact_uploads", ["expires_at"])
    op.create_table(
        "artifacts",
        *entity_columns(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("upload_id", sa.Uuid(), sa.ForeignKey("artifact_uploads.id"), unique=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("artifact_type", sa.String(80), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("object_key", sa.String(800), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="available"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("lineage", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
    op.create_index("ix_artifacts_created_by", "artifacts", ["created_by"])
    op.create_index("ix_artifacts_artifact_type", "artifacts", ["artifact_type"])
    op.create_index("ix_artifacts_object_key", "artifacts", ["object_key"])
    op.create_index("ix_artifacts_status", "artifacts", ["status"])
    op.create_index("ix_artifacts_checksum_sha256", "artifacts", ["checksum_sha256"])
    op.create_table(
        "experiment_results",
        *entity_columns(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_ref", sa.String(255)),
        sa.Column("experiment_type", sa.String(120), nullable=False),
        sa.Column("pass_status", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("value", sa.Float()),
        sa.Column("unit", sa.String(40)),
        sa.Column("conclusion", sa.Text()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_experiment_results_project_id", "experiment_results", ["project_id"])
    op.create_index("ix_experiment_results_candidate_ref", "experiment_results", ["candidate_ref"])
    op.create_index("ix_experiment_results_experiment_type", "experiment_results", ["experiment_type"])
    op.create_index("ix_experiment_results_pass_status", "experiment_results", ["pass_status"])
    op.create_index("ix_experiment_results_created_by", "experiment_results", ["created_by"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("organization_id", sa.Uuid()),
        sa.Column("project_id", sa.Uuid()),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("trace_id", sa.String(120), nullable=False),
        sa.Column("result", sa.String(32), nullable=False, server_default="success"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_project_id", "audit_logs", ["project_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    for table in (
        "audit_logs",
        "experiment_results",
        "artifacts",
        "artifact_uploads",
        "idempotency_records",
        "outbox_events",
        "job_events",
        "job_attempts",
        "jobs",
        "job_submissions",
        "workflow_nodes",
        "workflow_runs",
        "targets",
        "project_members",
        "projects",
        "oidc_login_states",
        "organization_members",
        "refresh_sessions",
        "organizations",
        "users",
    ):
        op.drop_table(table)
