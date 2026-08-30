"""Register the IP-filter and interface-physics tools installed under our own account.

Three of route A's and route 3's gaps were "lightweight, install it ourselves" items. They
are now installed and verified to start on qm, so they get plugin rows:

* **Foldseek** - route A's IP fold-space gate. Pairwise TM-score comparisons against a
  small reference set cannot answer the freedom-to-operate question "does this design
  collide with *anything* in the PDB", which is a search, not
  a pairwise alignment. Only Foldseek does that in usable time.
* **US-align** - the pairwise half of the same gate, and a TM-align superset that handles
  multi-chain comparisons. Compiled from source; there is no conda package.
* **APBS + PDB2PQR** - route 3's local surface potential. Rosetta's electrostatics is an
  implicit-solvent score term and is *not* a Poisson-Boltzmann surface potential, so this
  one genuinely needed installing. They run as one plugin because PDB2PQR both protonates
  the structure and writes the APBS input file; splitting them would make a node whose only
  output is an input file for the next node.

ThermoMPNN is installed at ``/opt/bda/software/ThermoMPNN`` with its default
weights but is deliberately **not** registered: its ``analysis/SSM.py`` entry point reads
dataset paths from the authors' own cluster layout (``local.yaml`` points at
``/nas/longleaf/...``), so running it on arbitrary PDBs needs a wrapper rather than a
command template. It is also not blocking - the protocol only uses it to *propose*
substitutions, and Rosetta ``cartesian_ddg`` (present on qm, reachable through the Rosetta
plugin's ``application`` parameter) covers that at lower throughput.

The allergenicity screen stays unregistered for a different reason: MMseqs2 is installed,
but AllergenOnline and COMPARE require accepting their terms and registering, which is the
owner's action, not a migration's.

Revision ID: 0027_ip_and_physics_tools
Revises: 0026_rfd3_and_af3
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_ip_and_physics_tools"
down_revision: str | None = "0026_rfd3_and_af3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TOOLS_ENV = "/opt/bda/.conda/envs/bda-tools"
OUR_CONDA_PROFILE = "/opt/bda/miniconda3/etc/profile.d/conda.sh"
CONDA_SETUP = [f"source {OUR_CONDA_PROFILE}", f"conda activate {TOOLS_ENV}"]

# easy-search takes query structures, a target database, an output file and a scratch dir.
# The target database is staged as an input so the IP reference set is an artifact with
# provenance rather than a path baked into the plugin.
FOLDSEEK_COMMAND = """\
foldseek_target="$(find "$BDA_INPUT_DIR/reference_db" -maxdepth 1 -type f ! -name '*.dbtype' ! -name '*.index' 2>/dev/null | sort | head -1)"
if [ -z "$foldseek_target" ]; then echo "bda: no Foldseek reference database staged" >&2; exit 2; fi
foldseek easy-search \
  "$BDA_INPUT_DIR/structures" \
  "$foldseek_target" \
  "$BDA_OUTPUT_DIR/foldseek_hits.m8" \
  "$BDA_OUTPUT_DIR/tmp" \
  --format-output "${format_output:-query,target,fident,alntmscore,evalue,prob}" \
  -e "${evalue:-0.001}" \
  --alignment-type "${alignment_type:-2}" \
  --max-seqs "${max_seqs:-1000}"\
"""

# -dir1 takes a DIRECTORY plus a list of names *relative to it*. Passing an empty prefix
# with absolute paths in the list makes US-align read zero chains and then segfault - it
# does not error out, it dies, which a smoke run found and no amount of reading would have.
# The trailing slash on the directory matters: US-align concatenates prefix + name.
USALIGN_COMMAND = """\
usalign_dir="$BDA_INPUT_DIR/structures"
find "$usalign_dir" -maxdepth 1 \\( -name '*.pdb' -o -name '*.cif' \\) -printf '%f\\n' 2>/dev/null | sort > "$BDA_OUTPUT_DIR/query.list"
usalign_ref="$(find "$BDA_INPUT_DIR/reference" -maxdepth 1 -type f 2>/dev/null | sort | head -1)"
if [ ! -s "$BDA_OUTPUT_DIR/query.list" ] || [ -z "$usalign_ref" ]; then echo "bda: US-align needs structures and a reference" >&2; exit 2; fi
/opt/bda/software/USalign/USalign \
  -dir1 "$usalign_dir/" "$BDA_OUTPUT_DIR/query.list" \
  "$usalign_ref" \
  -TMscore "${tmscore_mode:-0}" \
  -outfmt "${outfmt:-2}" \
  > "$BDA_OUTPUT_DIR/usalign_tmscores.tsv"\
"""

# pdb2pqr protonates and writes the APBS input; apbs then solves. One plugin, because the
# .in file is an intermediate, not a deliverable.
#
# The input must be a FULL-ATOM structure. A smoke run against an RFdiffusion backbone
# failed with "Found gap in biomolecule structure": pdb2pqr rebuilds hydrogens, not missing
# heavy atoms. In the routes this node always sits after sequence design and prediction, so
# that is the contract - but the failure is opaque enough to be worth catching up front.
APBS_COMMAND = """\
apbs_pdb="$(find "$BDA_INPUT_DIR/structure" -name '*.pdb' 2>/dev/null | sort | head -1)"
if [ -z "$apbs_pdb" ]; then echo "bda: no structure staged for APBS" >&2; exit 2; fi
apbs_stem="$(basename "$apbs_pdb" .pdb)"
if ! grep -qE '^ATOM.{9}(CB|CG|CD|CZ|NZ|OG) ' "$apbs_pdb"; then
  echo "bda: $apbs_pdb looks backbone-only; APBS needs a full-atom structure" >&2
  exit 4
fi
pdb2pqr30 \
  --ff="${forcefield:-AMBER}" \
  --apbs-input "$BDA_OUTPUT_DIR/$apbs_stem.in" \
  ${with_ph:+--titration-state-method propka --with-ph "$with_ph"} \
  ${keep_chain:+--keep-chain} \
  "$apbs_pdb" "$BDA_OUTPUT_DIR/$apbs_stem.pqr"
cd "$BDA_OUTPUT_DIR" && apbs "$apbs_stem.in" > "$BDA_OUTPUT_DIR/apbs.log" 2>&1\
"""

FOLDSEEK = {
    "plugin_key": "Foldseek",
    "plugin_version": "conda-forge-2026-08",
    "name": "Foldseek (structure search)",
    "container_image": TOOLS_ENV,
    "command": FOLDSEEK_COMMAND,
    "runtime_mode": "conda",
    "runtime_setup": CONDA_SETUP,
    "resources": {"cpus": 8, "memory_gb": 16, "walltime_minutes": 240},
    "parameter_schema": {
        "fields": [
            {
                "key": "format_output",
                "label": "Output columns",
                "type": "string",
                "default": "query,target,fident,alntmscore,evalue,prob",
                "help": "alntmscore is the column the IP gate thresholds on (TM < 0.40).",
                "advanced": False,
            },
            {"key": "evalue", "label": "E-value", "type": "number", "default": 0.001, "advanced": False},
            {
                "key": "alignment_type",
                "label": "Alignment type",
                "type": "integer",
                "default": 2,
                "help": "2 = 3Di+AA Gotoh-Smith-Waterman, the default structural mode.",
                "advanced": True,
            },
            {"key": "max_seqs", "label": "Max hits per query", "type": "integer", "default": 1000, "advanced": True},
        ]
    },
    "input_ports": [
        {
            "name": "structures",
            "kind": "protein_structure",
            "accepts": ["backbone_set", "candidate_structure", "predicted_structure", "structure"],
            "content_types": [],
            "required": True,
            "multiple": True,
            "description": "Designs to screen for fold-space collisions.",
        },
        {
            "name": "reference_db",
            "kind": "opaque",
            "accepts": ["structure_database", "sequence_set", "structure"],
            "content_types": [],
            "required": True,
            "multiple": False,
            "description": "Foldseek target database, or a FASTA/structure set it can build from.",
        },
    ],
    "output_ports": [
        {
            "name": "hits",
            "kind": "tabular",
            "artifact_type": "score_table",
            "filename_glob": "foldseek_hits.m8",
            "description": "One row per hit; alntmscore drives the IP gate.",
        }
    ],
}

USALIGN = {
    "plugin_key": "US-align",
    "plugin_version": "20260527",
    "name": "US-align (TM-score)",
    "container_image": "/opt/bda/software/USalign",
    "command": USALIGN_COMMAND,
    # A single static binary: nothing to activate.
    "runtime_mode": "script",
    "runtime_setup": [],
    "resources": {"cpus": 1, "memory_gb": 4, "walltime_minutes": 120},
    "parameter_schema": {
        "fields": [
            {
                "key": "tmscore_mode",
                "label": "TM-score normalisation",
                "type": "integer",
                "default": 0,
                "help": "0 = normalise by both lengths and report both; see US-align docs.",
                "advanced": True,
            },
            {
                "key": "outfmt",
                "label": "Output format",
                "type": "integer",
                "default": 2,
                "help": "2 = one tab-separated line per comparison.",
                "advanced": True,
            },
        ]
    },
    "input_ports": [
        {
            "name": "structures",
            "kind": "protein_structure",
            "accepts": ["backbone_set", "candidate_structure", "predicted_structure", "structure"],
            "content_types": [],
            "required": True,
            "multiple": True,
            "description": "Designs to compare.",
        },
        {
            "name": "reference",
            "kind": "protein_structure",
            "accepts": ["target_structure", "structure"],
            "content_types": [],
            "required": True,
            "multiple": False,
            "description": "Reference protein structure to compare against.",
        },
    ],
    "output_ports": [
        {
            "name": "tmscores",
            "kind": "tabular",
            "artifact_type": "score_table",
            "filename_glob": "usalign_tmscores.tsv",
            "description": "Pairwise TM-scores, one line per design.",
        }
    ],
}

APBS = {
    "plugin_key": "APBS+PDB2PQR",
    "plugin_version": "conda-forge-2026-08",
    "name": "APBS + PDB2PQR (surface electrostatics)",
    "container_image": TOOLS_ENV,
    "command": APBS_COMMAND,
    "runtime_mode": "conda",
    "runtime_setup": CONDA_SETUP,
    "resources": {"cpus": 4, "memory_gb": 16, "walltime_minutes": 240},
    "parameter_schema": {
        "fields": [
            {
                "key": "forcefield",
                "label": "Force field",
                "type": "string",
                "default": "AMBER",
                "help": "AMBER, CHARMM, PARSE, TYL06, PEOEPB or SWANSON.",
                "advanced": False,
            },
            {
                "key": "with_ph",
                "label": "Titrate at pH",
                "type": "number",
                "default": None,
                "help": (
                    "Assign protonation with PROPKA at this pH. Set it for the beverage "
                    "formulation pH; leaving it empty uses standard states."
                ),
                "advanced": False,
            },
            {"key": "keep_chain", "label": "Keep chain IDs", "type": "boolean", "default": True, "advanced": True},
        ]
    },
    "input_ports": [
        {
            "name": "structure",
            "kind": "protein_structure",
            "accepts": ["complex_structure", "candidate_structure", "predicted_structure", "structure"],
            "content_types": [],
            "required": True,
            "multiple": False,
            "description": (
                "Full-atom complex or monomer. Backbone-only designs are rejected: pdb2pqr "
                "rebuilds hydrogens, not missing side-chain heavy atoms."
            ),
        }
    ],
    "output_ports": [
        {
            "name": "potential",
            "kind": "opaque",
            "artifact_type": "electrostatics_map",
            "filename_glob": "*.dx",
            "description": "Poisson-Boltzmann potential grid.",
        },
        {
            "name": "pqr",
            "kind": "protein_structure",
            "artifact_type": "prepared_structure",
            "filename_glob": "*.pqr",
            "description": "Protonated structure with charges and radii.",
        },
        {
            "name": "log",
            "kind": "opaque",
            "artifact_type": "run_log",
            "filename_glob": "apbs.log",
            "description": "APBS solver log, including the computed energies.",
        },
    ],
}

PLUGINS = [FOLDSEEK, USALIGN, APBS]


def upgrade() -> None:
    bind = op.get_bind()
    for plugin in PLUGINS:
        existing = bind.execute(
            sa.text("SELECT id FROM model_plugins WHERE plugin_key = :key"),
            {"key": plugin["plugin_key"]},
        ).fetchone()
        if existing is not None:
            print(f"0027: {plugin['plugin_key']} already registered")
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO model_plugins (
                    id, plugin_key, plugin_version, name, container_image, command,
                    parameter_schema, output_schema, input_ports, output_ports, resources,
                    runtime_mode, runtime_setup, enabled,
                    validation_status, validation_errors, version, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :plugin_key, :plugin_version, :name, :container_image, :command,
                    CAST(:parameter_schema AS json), '{}'::json,
                    CAST(:input_ports AS json), CAST(:output_ports AS json), CAST(:resources AS json),
                    :runtime_mode, CAST(:runtime_setup AS json), true,
                    'unknown', '[]'::json, 1, now(), now()
                )
                """
            ),
            {
                **{
                    key: plugin[key]
                    for key in ("plugin_key", "plugin_version", "name", "container_image", "command", "runtime_mode")
                },
                "parameter_schema": json.dumps(plugin["parameter_schema"]),
                "input_ports": json.dumps(plugin["input_ports"]),
                "output_ports": json.dumps(plugin["output_ports"]),
                "resources": json.dumps(plugin["resources"]),
                "runtime_setup": json.dumps(plugin["runtime_setup"]),
            },
        )
        print(f"0027: registered {plugin['plugin_key']}")


def downgrade() -> None:
    for plugin in PLUGINS:
        # workflow_nodes.model_plugin_id has no ON DELETE clause, so the delete
        # below is refused while any node still points at this plugin. The column
        # is nullable precisely so a node can name a plugin by key without one
        # being registered, which is the state a downgrade returns it to.
        op.execute(
            sa.text(
                "UPDATE workflow_nodes SET model_plugin_id = NULL WHERE model_plugin_id IN ("
                " SELECT id FROM model_plugins WHERE plugin_key = :key)"
            ).bindparams(key=plugin["plugin_key"])
        )
        op.execute(
            sa.text("DELETE FROM model_plugins WHERE plugin_key = :key").bindparams(key=plugin["plugin_key"])
        )
