"""Wire ProteinMPNN to the parser that reads its own FASTA.

`parsers/proteinmpnn.py` has existed and been unit-tested since the parser interface
landed, but no ProteinMPNN row ever named it, so collection fell through to
`manifest_metadata` and the designs arrived as untyped files.

Two things were missing as a result, both visible in the 2026-09-11 cluster run
(LSF 4267822):

* **No metrics.** Gate records came from `records_in_file`, which can list a FASTA's
  members but cannot read ProteinMPNN's per-design `score`, `global_score` and
  `seq_recovery` out of the headers. A manual gate worked; an automatic gate had no
  number to screen on, so conditions and ranking were unusable on the one plugin most
  likely to need them.
* **The input's own sequence was offered as a design.** ProteinMPNN writes the native
  sequence as the first FASTA record. `gate_runtime` skips that record only when the
  plugin declares this parser, so without it a reviewer saw five candidates for four
  designs, the extra one being the sequence they started from.

Setting the parser also makes collection create `candidates` rows with recorded metrics
rather than only artifacts, which is what the parser interface is for. It upserts on
`(project_id, candidate_key)`, so a re-run of the same design set updates in place.

Applied to every enabled ProteinMPNN row: same tool, same output format, same parser.
Only rows that name no parser are touched, so an explicit choice elsewhere is preserved.

Revision ID: 0063_proteinmpnn_parser
Revises: 0061_staged_port_paths
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0063_proteinmpnn_parser"
down_revision: str | None = "0061_staged_port_paths"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARSER = "proteinmpnn_fasta"
PLUGIN_KEYS = ("ProteinMPNN", "ProteinMPNN-authoring-6810138a")


def upgrade() -> None:
    bind = op.get_bind()
    for plugin_key in PLUGIN_KEYS:
        result = bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET output_parser = :parser, version = version + 1, updated_at = now()
                WHERE plugin_key = :key AND output_parser IS NULL
                """
            ),
            {"parser": PARSER, "key": plugin_key},
        )
        print(f"0062: {plugin_key}: {result.rowcount} row(s) now read {PARSER}")


def downgrade() -> None:
    bind = op.get_bind()
    for plugin_key in PLUGIN_KEYS:
        bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET output_parser = NULL, version = version + 1, updated_at = now()
                WHERE plugin_key = :key AND output_parser = :parser
                """
            ),
            {"parser": PARSER, "key": plugin_key},
        )
