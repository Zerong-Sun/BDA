"""One-use account invitations/recovery and revocable refresh families."""

import sqlalchemy as sa

from alembic import op

revision = "0075_account_access"
down_revision = "0074_research_decision_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_sessions", sa.Column("family_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE refresh_sessions SET family_id = id")
    op.alter_column("refresh_sessions", "family_id", nullable=False)
    op.create_index("ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"])
    op.add_column("refresh_sessions", sa.Column("realm", sa.String(32), nullable=False, server_default="bda"))
    op.create_table(
        "account_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(255), unique=True, nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("realm", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("member_role", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("credential_version", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("account_grants")
    op.drop_index("ix_refresh_sessions_family_id", table_name="refresh_sessions")
    op.drop_column("refresh_sessions", "family_id")
    op.drop_column("refresh_sessions", "realm")
