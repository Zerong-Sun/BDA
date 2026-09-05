"""Let a confined worker see the campaign it was sent to execute.

Revision ID: 0055_autopilot_worker_rls
Revises: 0054_autopilot_takeover

`0049_autopilot_formalization` fenced all six Autopilot tables when it created them, and
it did so correctly for the case that existed then: a request carrying `bda.user_id`,
matched through organization membership. `0051_worker_project_rls` later added a second
way to be inside the fence - `bda.worker_project_id`, set by
`core/database.worker_project_scope` so a worker is confined to the one project its
operation belongs to - and extended the project tables to honour it. The Autopilot
policies were not extended, because at the time no worker read them: `execute_campaign`
only moved a stage to `ready`.

The stage adapter changed that. A worker now reads the campaign, its stages and its
budget, and creates a workflow run against them. Under a restricted role with only
`bda.worker_project_id` set, every one of those reads returns nothing - the worker cannot
see the campaign it was handed. Not a leak; the opposite. The fence is one-sided, and the
side that is missing is the one the docs describe as mandatory
(`docs/AUTOPILOT_CAMPAIGNS.md` §5: the worker must run in the operation's project
context, never as an unbounded application account).

So this migration replaces the six policies with the same two expressions, each gaining
the worker branch that `0048._project_expression` already uses. Nothing is widened for
users: organization membership still decides, and a worker still sees exactly one
project's campaigns and nothing else.

The downgrade restores 0049's expressions verbatim rather than dropping the policies,
because dropping them would leave the tables unfenced - a downgrade that removes a
security boundary is not a downgrade.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0055_autopilot_worker_rls"
down_revision: str | None = "0054_autopilot_takeover"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIRECT_TABLES = ("autopilot_drafts", "autopilot_campaigns")
INDIRECT_TABLES = (
    "autopilot_campaign_budgets",
    "autopilot_budget_reservations",
    "autopilot_stages",
    "autopilot_ledger_entries",
)

#: 0049's expressions, kept verbatim so the downgrade restores exactly what was there.
DIRECT_WITHOUT_WORKER = """
    current_setting('bda.is_global_admin', true) = 'true'
    OR EXISTS (
        SELECT 1 FROM projects p
        JOIN organization_members om ON om.organization_id = p.organization_id
        WHERE p.id = {table}.project_id
          AND om.user_id::text = current_setting('bda.user_id', true)
    )
"""

INDIRECT_WITHOUT_WORKER = """
    current_setting('bda.is_global_admin', true) = 'true'
    OR EXISTS (
        SELECT 1 FROM autopilot_campaigns ac
        JOIN projects p ON p.id = ac.project_id
        JOIN organization_members om ON om.organization_id = p.organization_id
        WHERE ac.id = {table}.campaign_id
          AND om.user_id::text = current_setting('bda.user_id', true)
    )
"""

#: The same, plus the worker branch 0048 uses on every other project-scoped table.
DIRECT_WITH_WORKER = """
    current_setting('bda.is_global_admin', true) = 'true'
    OR {table}.project_id::text = current_setting('bda.worker_project_id', true)
    OR EXISTS (
        SELECT 1 FROM projects p
        JOIN organization_members om ON om.organization_id = p.organization_id
        WHERE p.id = {table}.project_id
          AND om.user_id::text = current_setting('bda.user_id', true)
    )
"""

INDIRECT_WITH_WORKER = """
    current_setting('bda.is_global_admin', true) = 'true'
    OR EXISTS (
        SELECT 1 FROM autopilot_campaigns ac
        WHERE ac.id = {table}.campaign_id
          AND (
            ac.project_id::text = current_setting('bda.worker_project_id', true)
            OR EXISTS (
                SELECT 1 FROM projects p
                JOIN organization_members om ON om.organization_id = p.organization_id
                WHERE p.id = ac.project_id
                  AND om.user_id::text = current_setting('bda.user_id', true)
            )
          )
    )
"""


def _replace(direct: str, indirect: str) -> None:
    for table in DIRECT_TABLES:
        expression = direct.format(table=table)
        op.execute(f"DROP POLICY IF EXISTS {table}_project_fence ON {table}")
        op.execute(
            f"CREATE POLICY {table}_project_fence ON {table} "
            f"USING ({expression}) WITH CHECK ({expression})"
        )
    for table in INDIRECT_TABLES:
        expression = indirect.format(table=table)
        op.execute(f"DROP POLICY IF EXISTS {table}_project_fence ON {table}")
        op.execute(
            f"CREATE POLICY {table}_project_fence ON {table} "
            f"USING ({expression}) WITH CHECK ({expression})"
        )


def upgrade() -> None:
    _replace(DIRECT_WITH_WORKER, INDIRECT_WITH_WORKER)


def downgrade() -> None:
    _replace(DIRECT_WITHOUT_WORKER, INDIRECT_WITHOUT_WORKER)
