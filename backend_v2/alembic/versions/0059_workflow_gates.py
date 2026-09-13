"""Join the original gate migration with the later public migration branch.

Both 0056 and 0059 were used by feature-branch deployments. Keep both IDs
resolvable and create the gate tables only once, in 0056. Databases already
stamped at 0059 contain those tables and treat 0056 as an applied ancestor.
"""

revision = "0059_workflow_gates"
down_revision = ("0058_autopilot_stage_gates", "0056_workflow_gates")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
