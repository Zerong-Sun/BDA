"""Expose collected AF3 protein alignments as a typed workflow output."""
import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0070_af3_msa_port"
down_revision: str | None = '0069_patent_search_jurisdictions'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen declaration: migrations must not change when application code changes.
PORT = {
    'name': 'protein_msa', 'kind': 'msa', 'artifact_type': 'sequence_alignment',
    'filename_glob': '*_msa.a3m',
    'description': 'Protein paired/unpaired A3M extracted from collected AF3 data JSON, with source and chain provenance.',
}


def _update(upgrade: bool) -> None:
    bind = op.get_bind()
    for row in bind.execute(sa.text("SELECT id, output_ports FROM model_plugins WHERE output_parser = 'alphafold3'")):
        ports = json.loads(row.output_ports) if isinstance(row.output_ports, str) else row.output_ports or []
        if upgrade:
            if any(port.get('name') == PORT['name'] for port in ports):
                continue
            changed = [*ports, PORT]
        else:
            changed = [port for port in ports if port != PORT]
            if changed == ports:
                continue
        bind.execute(sa.text('UPDATE model_plugins SET output_ports = CAST(:ports AS json), version = version + 1, updated_at = now() WHERE id = :id'), {'id': row.id, 'ports': json.dumps(changed)})


def upgrade() -> None:
    _update(True)


def downgrade() -> None:
    _update(False)
