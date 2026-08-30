"""Remove non-citation legacy tokens from migrated finding sources.

Revision ID: 0015_reference_token_cleanup
Revises: 0014_reference_cleanup
"""

from __future__ import annotations

from alembic import op

revision = "0015_reference_token_cleanup"
down_revision = "0014_reference_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE research_findings AS finding
        SET evidence = jsonb_set(
                jsonb_set(
                    coalesce(finding.evidence::jsonb, '{}'::jsonb),
                    '{sources}',
                    (
                        coalesce(finding.evidence::jsonb -> 'sources', '[]'::jsonb)
                        - 'Project-specific substrate and enzyme identity still required'
                        - 'UniProt and PDB records should be attached once the enzyme is selected'
                    )
                ),
                '{source_metadata}',
                (
                    coalesce(finding.evidence::jsonb -> 'source_metadata', '{}'::jsonb)
                    - 'Project-specific substrate and enzyme identity still required'
                    - 'UniProt and PDB records should be attached once the enzyme is selected'
                )
            )::json,
            version = finding.version + 1,
            updated_at = now()
        FROM projects AS project
        WHERE finding.project_id = project.id
          AND project.name = 'Enzyme_repair_0507'
          AND (
              finding.evidence::jsonb -> 'sources'
                  ? 'Project-specific substrate and enzyme identity still required'
              OR finding.evidence::jsonb -> 'sources'
                  ? 'UniProt and PDB records should be attached once the enzyme is selected'
          )
        """
    )
    op.execute(
        """
        UPDATE research_findings AS finding
        SET evidence = jsonb_set(
                jsonb_set(
                    coalesce(finding.evidence::jsonb, '{}'::jsonb),
                    '{sources}',
                    (
                        coalesce(finding.evidence::jsonb -> 'sources', '[]'::jsonb)
                        - 'RCSB protein nanomaterial and cage design references'
                    )
                ),
                '{source_metadata}',
                (
                    coalesce(finding.evidence::jsonb -> 'source_metadata', '{}'::jsonb)
                    - 'RCSB protein nanomaterial and cage design references'
                )
            )::json,
            version = finding.version + 1,
            updated_at = now()
        FROM projects AS project
        WHERE finding.project_id = project.id
          AND project.name = 'Nanocage_delivery_0518'
          AND finding.evidence::jsonb -> 'sources'
              ? 'RCSB protein nanomaterial and cage design references'
        """
    )


def downgrade() -> None:
    # Removed non-citation tokens are intentionally retained as deleted.
    pass
