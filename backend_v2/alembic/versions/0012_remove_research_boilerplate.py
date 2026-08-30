"""Remove generic Research review filler imported from legacy projects.

Revision ID: 0012_remove_research_boilerplate
Revises: 0011_literature_retrieval_trace
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_remove_research_boilerplate"
down_revision = "0011_literature_retrieval_trace"
branch_labels = None
depends_on = None

BOILERPLATE = (
    "Treat the review as an operating contract: every downstream workflow choice should cite the "
    "application need, the target evidence, and the validation readout it is meant to improve.",
    "Validation should separate target engagement, mechanism, and developability. A candidate can bind "
    "but still fail if competition, specificity, stability, or matrix behavior contradicts the intended use.",
    "Use purification readouts as design feedback, not only manufacturing steps: expression yield, SEC "
    "profile, tag-cleavage behavior, and aggregation state should feed the next redesign round.",
    "Before design generation, freeze a target packet containing sequence boundaries, construct choices, "
    "modeled or experimental coordinates, protected functional residues, and residues allowed for interface sampling.",
    "Rank binding strategies by physical access and assayability first, then by model score; any design that "
    "cannot be purified, presented to the target, or counterscreened should remain a lower-confidence hypothesis.",
    "Keep at least two routes in the plan: one conservative route that preserves known structural constraints "
    "and one exploratory route that tests whether generative design adds useful diversity.",
)


def upgrade() -> None:
    findings = sa.table("research_findings", sa.column("content", sa.Text()))
    op.execute(findings.delete().where(findings.c.content.in_(BOILERPLATE)))


def downgrade() -> None:
    # Deleted template filler is intentionally not recreated.
    pass
