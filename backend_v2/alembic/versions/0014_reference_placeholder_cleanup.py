"""Remove or repair untraceable legacy reference placeholders.

Revision ID: 0014_reference_cleanup
Revises: 0013_research_draft_repair
"""

from __future__ import annotations

from alembic import op

revision = "0014_reference_cleanup"
down_revision = "0013_research_draft_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM research_findings AS finding
        USING projects AS project
        WHERE finding.project_id = project.id
          AND project.name = 'Enzyme_repair_0507'
          AND finding.finding_type = 'references_reading'
          AND finding.title IN (
            'Project enzyme identity placeholder (still required)',
            'UniProt and PDB attachment placeholder'
          )
        """
    )
    op.execute(
        """
        UPDATE research_findings AS finding
        SET evidence = jsonb_set(
                coalesce(finding.evidence::jsonb, '{}'::jsonb),
                '{sources}',
                '[
                  "https://www.nature.com/articles/nature18010",
                  "https://www.nature.com/articles/nature13404"
                ]'::jsonb
            )::json,
            version = finding.version + 1,
            updated_at = now()
        FROM projects AS project
        WHERE finding.project_id = project.id
          AND project.name = 'Nanocage_delivery_0518'
          AND finding.finding_type = 'references_reading'
          AND finding.title = 'RCSB nanomaterial and cage geometry precedents'
          AND finding.evidence::jsonb -> 'sources'
              = '["RCSB protein nanomaterial and cage design references"]'::jsonb
        """
    )


def downgrade() -> None:
    # Removed placeholders and repaired source links are intentionally retained.
    pass
