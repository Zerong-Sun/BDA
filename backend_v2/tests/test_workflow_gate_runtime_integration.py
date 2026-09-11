"""Opt-in runtime checks using disposable containers and synthetic coordinates only."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("BDA_GATE_RUNTIME_IMAGE"), reason="Gate runtime image not configured")


def test_actual_dssp_helix_counts_scope_and_incomplete_atoms():
    import docker

    code = """
from Bio.PDB.PICIO import read_PIC_seq
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.PDB import PDBIO
from io import StringIO
import json
from backend_v2.app.workflows.structure_metrics import structure_metrics
from backend_v2.app.workflows.gate_schemas import StructurePolicy
results = {}
for kind, expected in (("none",0),("one",1),("two",2)):
    structure = read_PIC_seq(SeqRecord(Seq("A"*40),id="SYN:B"))
    for residue in structure.get_residues():
        extended = kind=="none" or (kind=="two" and 16 <= residue.id[1] <= 24)
        residue.internal_coord.set_angle("phi", -120 if extended else -60)
        residue.internal_coord.set_angle("psi", 130 if extended else -45)
    structure.internal_to_atom_coordinates()
    output = StringIO(); writer=PDBIO(); writer.set_structure(structure); writer.save(output)
    metrics = structure_metrics("synthetic.pdb", output.getvalue().encode(), StructurePolicy(chains=["B"]))
    assert metrics["helix_count"] == expected, (kind,metrics)
    assert metrics["dictionary_source_sha256"] and metrics["method_version"]
    results[kind] = metrics["helix_count"]
    if kind == "two":
        region = structure_metrics("synthetic.pdb", output.getvalue().encode(), StructurePolicy(chains=["B"],start=1,end=15))
        assert region["helix_count"] == 1
        # A different chain's structure cannot satisfy the design chain's policy.
        try:
            structure_metrics("synthetic.pdb", output.getvalue().encode(), StructurePolicy(chains=["A"]))
        except ValueError as error:
            assert "design_chain_missing" in str(error)
        else: raise AssertionError("Missing chain was accepted")
        next(structure.get_residues()).detach_child("O")
        output=StringIO();writer.save(output)
        try:
            structure_metrics("synthetic.pdb", output.getvalue().encode(), StructurePolicy(chains=["B"]))
        except ValueError as error:
            assert "backbone_atoms_missing" in str(error)
        else: raise AssertionError("Missing atoms were accepted")
print(json.dumps(results))
"""
    client = docker.from_env()
    container = client.containers.run(
        os.environ["BDA_GATE_RUNTIME_IMAGE"],
        ["python", "-c", code],
        detach=True,
        volumes={str(Path(__file__).resolve().parents[1]): {"bind": "/app/backend_v2", "mode": "ro"}},
        network_disabled=True,
        read_only=True,
        tmpfs={"/tmp": "rw,size=256m"},
        mem_limit="1g",
        nano_cpus=1000000000,
    )
    try:
        status = container.wait(timeout=180)
        logs = container.logs().decode()
        assert status["StatusCode"] == 0, logs
        assert json.loads(logs.splitlines()[-1]) == {"none": 0, "one": 1, "two": 2}
    finally:
        container.remove(force=True)


def test_actual_screening_sandbox_blocks_network_and_root_writes():
    from backend_v2.app.workflows.gate_runtime import _script_decisions

    script = """
import os, socket
from pathlib import Path
def screen(records):
    assert os.getuid() != 0
    try: Path("/escape").write_text("blocked")
    except OSError: pass
    else: raise AssertionError("root is writable")
    try: socket.create_connection(("1.1.1.1",443), timeout=0.3)
    except OSError: pass
    else: raise AssertionError("network is reachable")
    return [{"id":r["id"],"passed":r["metrics"]["score"]>=80,"reason":"synthetic threshold"} for r in records]
"""
    decisions = _script_decisions(
        script, [{"id": "keep", "metrics": {"score": 90}}, {"id": "drop", "metrics": {"score": 30}}]
    )
    assert [d["id"] for d in decisions if d["passed"]] == ["keep"]
    with pytest.raises(ValueError, match="gate_script_failed"):
        _script_decisions("raise RuntimeError('synthetic failure')", [{"id": "test"}])
