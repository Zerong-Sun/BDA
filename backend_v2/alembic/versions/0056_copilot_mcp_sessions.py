"""Let an external MCP client reach the copilot tool registry, on a named grant.

Revision ID: 0056_copilot_mcp_sessions
Revises: 0055_autopilot_worker_rls

The copilot tool registry already carries everything an external agent needs -
schema, capability, execution mode, audit - and `REGISTRY.execute` is the only
way a tool runs. What it does not carry is who is asking. A chat turn answers
that with a bearer token and the user's own message; an MCP client has neither.

One row here is one answer to both questions at once. `issued_by` is the person
whose RLS context the calls run under, and `agent_run_id` names the run whose
`goal` is that person's own words - the same substitution `agent_loop` already
makes when it passes `request_text=run.goal` into the action service. A row with
no run is a read-only grant, which is why the column is nullable rather than
defaulted to something.

The token is stored as a SHA-256 hash, the way `refresh_sessions.token_hash` is.
The raw value is returned once and is not recoverable afterwards.

RLS: the table is project-scoped, so it takes the same fence `0048_project_rls`
put on every other project table, worker branch included. Without it a session
row would be readable across projects while the rows it grants access to are not,
which is the wrong way round for the one table that describes an authorization.

The downgrade drops the table. Outstanding grants disappear with it, which is the
correct direction for a credential: a downgrade that left usable tokens behind
for a dispatch path that no longer exists would be worse than losing them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0056_copilot_mcp_sessions"
down_revision: str | None = "0055_autopilot_worker_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "copilot_mcp_sessions"

#: Verbatim from `0048_project_rls._project_expression`, so this table is fenced
#: by the same rule as every other project table rather than a similar one.
FENCE = f"""
    current_setting('bda.is_global_admin', true) = 'true'
    OR {TABLE}.project_id::text = current_setting('bda.worker_project_id', true)
    OR EXISTS (
        SELECT 1
        FROM projects p
        JOIN organization_members om ON om.organization_id = p.organization_id
        WHERE p.id = {TABLE}.project_id
          AND om.user_id::text = current_setting('bda.user_id', true)
    )
"""


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=True),
        sa.Column("issued_by", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("granted_capabilities", sa.JSON(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("length(label) > 0", name="ck_copilot_mcp_session_label"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["copilot_agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"]),
    )
    op.create_index(f"ix_{TABLE}_project_id", TABLE, ["project_id"])
    op.create_index(f"ix_{TABLE}_agent_run_id", TABLE, ["agent_run_id"])
    op.create_index(f"ix_{TABLE}_issued_by", TABLE, ["issued_by"])
    op.create_index(f"ix_{TABLE}_project", TABLE, ["project_id", "created_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {TABLE}_project_fence ON {TABLE} "
            f"USING ({FENCE}) WITH CHECK ({FENCE})"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"DROP POLICY IF EXISTS {TABLE}_project_fence ON {TABLE}")
        op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY")
    op.drop_index(f"ix_{TABLE}_project", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_issued_by", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_agent_run_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_project_id", table_name=TABLE)
    op.drop_table(TABLE)
