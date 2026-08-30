"""Declarative plugin I/O ports, node input bindings, and provenance backfills.

Adds the schema that lets a job actually receive input files and lets a downstream
node consume an upstream node's outputs. Also repairs two provenance defects found
in live data: model plugin validation results written into the wrong column, and
experiment results whose ``candidate_ref`` was never resolved to ``candidate_id``.

Revision ID: 0016_compute_dataflow_ports
Revises: 0015_reference_token_cleanup
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_compute_dataflow_ports"
down_revision: str | None = "0015_reference_token_cleanup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _column_names(table):
        op.add_column(table, column)


def _drop_column(table: str, column: str) -> None:
    if column in _column_names(table):
        op.drop_column(table, column)


# Port definitions for the plugins that are currently enabled. Compatibility is keyed
# on ``kind`` (semantic) and ``accepts`` (artifact_type); ``content_types`` is advisory
# only because real uploads carry browser-sniffed types such as application/vnd.palm
# for .pdb files.
STRUCTURE_ACCEPTS = [
    "backbone_set",
    "target_structure",
    "candidate_structure",
    "predicted_structure",
    "structure",
]
STRUCTURE_CONTENT_TYPES = ["chemical/x-pdb", "chemical/x-mmcif"]

PLUGIN_PORTS: dict[str, dict[str, list[dict]]] = {
    "RFdiffusion": {
        "input_ports": [
            {
                "name": "input_structure",
                "kind": "protein_structure",
                "accepts": STRUCTURE_ACCEPTS,
                "content_types": STRUCTURE_CONTENT_TYPES,
                "required": False,
                "multiple": False,
                "description": "Motif or scaffold structure. Omit for unconditional generation.",
            }
        ],
        "output_ports": [
            {
                "name": "backbones",
                "kind": "protein_structure",
                "artifact_type": "backbone_set",
                "filename_glob": "*.pdb",
                "description": "Generated backbone structures.",
            }
        ],
    },
    "ProteinMPNN": {
        "input_ports": [
            {
                "name": "backbone",
                "kind": "protein_structure",
                "accepts": STRUCTURE_ACCEPTS,
                "content_types": STRUCTURE_CONTENT_TYPES,
                "required": True,
                "multiple": True,
                "description": "Backbone structures to design sequences for.",
            }
        ],
        "output_ports": [
            {
                "name": "sequences",
                "kind": "protein_sequence",
                "artifact_type": "sequence_set",
                "filename_glob": "*.fa*",
                "description": "Designed sequences in FASTA, score in the header comment.",
            }
        ],
    },
    "AlphaFold2": {
        "input_ports": [
            {
                "name": "sequences",
                "kind": "protein_sequence",
                "accepts": ["sequence_set", "sequence"],
                "content_types": ["text/x-fasta", "text/plain"],
                "required": True,
                "multiple": False,
                "description": "Sequences to fold.",
            },
            {
                "name": "msa",
                "kind": "msa",
                "accepts": ["msa", "alignment"],
                "content_types": ["text/plain"],
                "required": False,
                "multiple": False,
                "description": "Precomputed MSA. Generated internally when omitted.",
            },
        ],
        "output_ports": [
            {
                "name": "structures",
                "kind": "protein_structure",
                "artifact_type": "predicted_structure",
                "filename_glob": "*.pdb",
                "description": "Predicted structures, pLDDT in the B-factor column.",
            },
            {
                "name": "metrics",
                "kind": "tabular",
                "artifact_type": "confidence_record",
                "filename_glob": "*.json",
                "description": "Per-model confidence metrics.",
            },
        ],
    },
    "Rosetta": {
        "input_ports": [
            {
                "name": "structure",
                "kind": "protein_structure",
                "accepts": STRUCTURE_ACCEPTS,
                "content_types": STRUCTURE_CONTENT_TYPES,
                "required": True,
                "multiple": True,
                "description": "Structures to score or relax.",
            }
        ],
        "output_ports": [
            {
                "name": "scores",
                "kind": "tabular",
                "artifact_type": "score_table",
                "filename_glob": "score*.sc",
                "description": "Rosetta score table.",
            },
            {
                "name": "structures",
                "kind": "protein_structure",
                "artifact_type": "candidate_structure",
                "filename_glob": "*.pdb",
                "description": "Relaxed or repacked structures.",
            },
        ],
    },
}


def upgrade() -> None:
    _add_column(
        "model_plugins", sa.Column("input_ports", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json"))
    )
    _add_column(
        "model_plugins", sa.Column("output_ports", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json"))
    )
    _add_column(
        "model_plugins", sa.Column("resources", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json"))
    )
    _add_column(
        "model_plugins", sa.Column("runtime_mode", sa.String(20), nullable=False, server_default="container")
    )
    _add_column("model_plugins", sa.Column("output_parser", sa.String(80), nullable=True))
    _add_column(
        "workflow_nodes", sa.Column("input_bindings", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json"))
    )

    bind = op.get_bind()

    # 1. Move any validation result out of parameter_schema into its own columns.
    #    registry_model_plugin_validate used to write x-bda-validation into the user's
    #    schema while validation_status/validation_errors stayed 'unknown'/[].
    bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET validation_status = CASE
                    WHEN (parameter_schema::jsonb -> 'x-bda-validation' ->> 'valid') = 'true' THEN 'valid'
                    ELSE 'invalid'
                END,
                validation_errors = coalesce(
                    parameter_schema::jsonb -> 'x-bda-validation' -> 'errors', '[]'::jsonb
                )::json,
                validated_at = now(),
                parameter_schema = (parameter_schema::jsonb - 'x-bda-validation')::json,
                version = version + 1,
                updated_at = now()
            WHERE parameter_schema::jsonb ? 'x-bda-validation'
            """
        )
    )

    # 2. Seed ports for the plugins that are enabled today. Disabled plugins are left
    #    empty on purpose - guessing their contract would be worse than leaving it to
    #    whoever enables them.
    for plugin_key, ports in PLUGIN_PORTS.items():
        bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET input_ports = CAST(:input_ports AS json),
                    output_ports = CAST(:output_ports AS json),
                    version = version + 1,
                    updated_at = now()
                WHERE plugin_key = :plugin_key
                  AND enabled = true
                  AND coalesce(json_array_length(input_ports), 0) = 0
                  AND coalesce(json_array_length(output_ports), 0) = 0
                """
            ),
            {
                "plugin_key": plugin_key,
                "input_ports": json.dumps(ports["input_ports"]),
                "output_ports": json.dumps(ports["output_ports"]),
            },
        )

    # 3. Resolve experiment_results.candidate_ref -> candidate_id. candidates carries
    #    UNIQUE (project_id, candidate_key), so a match is unambiguous by construction.
    result = bind.execute(
        sa.text(
            """
            UPDATE experiment_results AS er
            SET candidate_id = c.id,
                version = er.version + 1,
                updated_at = now()
            FROM candidates AS c
            WHERE er.candidate_id IS NULL
              AND er.candidate_ref IS NOT NULL
              AND c.project_id = er.project_id
              AND c.candidate_key = er.candidate_ref
            """
        )
    )
    print(f"0016: linked {result.rowcount} experiment result(s) to candidates")


def downgrade() -> None:
    # Backfilled candidate links and relocated validation results are intentionally
    # retained - they are repairs, not new state, and dropping them would reintroduce
    # the defect.
    _drop_column("workflow_nodes", "input_bindings")
    for column in ("output_parser", "runtime_mode", "resources", "output_ports", "input_ports"):
        _drop_column("model_plugins", column)
