"""Allow verified account audit inserts and pre-account-access refresh writers."""

import sqlalchemy as sa

from alembic import op

revision = "0076_account_audit_compat"
down_revision = "0075_account_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older API images omit family_id. Keep those inserts valid during the
    # pre-upgrade hook and image rollback; each old login gets its own family.
    op.alter_column("refresh_sessions", "family_id", server_default=sa.text("gen_random_uuid()"))
    # This adds INSERT permission only. The existing project fence still owns
    # SELECT, UPDATE and DELETE, including for these projectless account rows.
    op.execute("""
        CREATE POLICY audit_logs_verified_account_insert ON audit_logs FOR INSERT
        WITH CHECK (
            project_id IS NULL
            AND entity_type = 'user'
            AND actor_id = entity_id
            AND actor_id::text = current_setting('bda.account_audit_user_id', true)
            AND (
                (action IN ('account.password.change', 'account.password.reset') AND organization_id IS NULL)
                OR (action = 'account.register' AND EXISTS (
                    SELECT 1 FROM organization_members om
                    WHERE om.organization_id = audit_logs.organization_id
                      AND om.user_id = audit_logs.actor_id
                ))
            )
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_logs_verified_account_insert ON audit_logs")
    op.alter_column("refresh_sessions", "family_id", server_default=None)
