"""Point the AlphaFold 3 plugin at the parser that reads its confidences.

The output port glob has harvested ``*summary_confidences.json`` since
``0028_superfold_af3_real_runs``, and `model_plugins.output_parser` for that
row has been NULL the whole time - so every AF3 run stored its ipTM and pTM as
an artifact nobody could query, while `candidate_metrics` already had the
vocabulary for them.

Only rows that name no parser are touched. A deployment that has since pointed
AF3 at something of its own keeps it: this migration is filling a hole, not
asserting ownership of the column.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0068_alphafold3_parser"
down_revision: str | None = "0067_target_hotspot_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARSER = "alphafold3"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE model_plugins SET output_parser = :parser "
            "WHERE output_parser IS NULL "
            "AND (plugin_key ILIKE 'alphafold%3%' OR name ILIKE 'alphafold%3%')"
        ).bindparams(parser=PARSER)
    )


def downgrade() -> None:
    # Clears only what this migration could have set, so a hand-configured
    # value that happens to match is not collateral damage of a rollback.
    op.execute(
        sa.text("UPDATE model_plugins SET output_parser = NULL WHERE output_parser = :parser").bindparams(
            parser=PARSER
        )
    )
