"""Clean stale Research copy and invalidate unconfirmed legacy drafts.

Revision ID: 0013_research_draft_repair
Revises: 0012_remove_research_boilerplate
"""

from __future__ import annotations

from alembic import op

revision = "0013_research_draft_repair"
down_revision = "0012_remove_research_boilerplate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE projects
        SET summary = btrim(replace(summary, '研究阶段先分析，不执行集群任务。', '')),
            version = version + 1,
            updated_at = now()
        WHERE summary LIKE '%研究阶段先分析，不执行集群任务。%'
        """
    )
    op.execute(
        """
        DELETE FROM literature_documents
        WHERE source = 'copilot_research_v2'
          AND metadata ->> 'source' = 'europe_pmc'
          AND (
            lower(title) LIKE 'abstracts of %'
            OR lower(title) LIKE '%annual meeting%'
            OR lower(title) LIKE '%congress of %'
            OR lower(title) LIKE '%poster presentations%'
            OR lower(title) LIKE '%conference abstracts%'
          )
        """
    )
    op.execute(
        """
        UPDATE research_generations
        SET validation = (
              coalesce(validation::jsonb, '{}'::jsonb)
              || '{"valid": false, "regenerate_required": true}'::jsonb
            )::json,
            error = 'regenerate_required_after_relevance_fix',
            version = version + 1,
            updated_at = now()
        WHERE status = 'ready'
          AND imported_project_id IS NULL
        """
    )


def downgrade() -> None:
    # Removed filler and rejected references are intentionally not restored.
    pass
