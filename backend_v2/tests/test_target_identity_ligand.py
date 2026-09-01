"""A ligand-only project must be able to reach a runnable workflow.

A small-molecule design project may have no protein target, accession or uploaded target
coordinates because the model resolves the ligand from its component library at run
time. Two defects together made that workflow permanently read-only:

1. `upsert_target` never persisted `target_kind` / `chemical_identity`, so a
   small-molecule target was stored as a protein with no chemical identity;
2. with no accession and no sequence, `is_identified` was then False, so
   `identity_status` stayed "unconfirmed" and readiness reported a blocker.

The second-order effect is the nastier one: a target wrongly typed as protein is also
asked for a structure artifact it is never supposed to have.
"""

from __future__ import annotations

from types import SimpleNamespace

from backend_v2.app.targets.identity import (
    is_identified,
    readiness_blockers,
    requires_structure_artifact,
)


def _target(**kwargs) -> SimpleNamespace:
    base = dict(
        target_kind="protein",
        chemical_identity={},
        uniprot_accession=None,
        sequence=None,
        identity_status="unconfirmed",
        structure_status="missing",
        structure_artifact_id=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_a_ccd_identifies_a_small_molecule() -> None:
    assert is_identified(_target(target_kind="small_molecule", chemical_identity={"ccd": "TCI"}))


def test_any_single_chemical_identifier_is_enough() -> None:
    for key, value in (("ccd", "TCI"), ("inchikey", "CYQFCXCEBYINGO-IAGOWNOFSA-N"), ("smiles", "CCC")):
        assert is_identified(_target(target_kind="small_molecule", chemical_identity={key: value})), key


def test_blank_identifiers_do_not_count() -> None:
    assert not is_identified(_target(target_kind="small_molecule", chemical_identity={"ccd": "   "}))
    assert not is_identified(_target(target_kind="small_molecule", chemical_identity={}))


def test_a_small_molecule_is_never_asked_for_a_structure_artifact() -> None:
    """Demanding one asks for a file that does not exist and would never be read."""
    assert not requires_structure_artifact(_target(target_kind="small_molecule"))
    assert requires_structure_artifact(_target(target_kind="protein"))


def test_a_confirmed_ligand_target_has_no_readiness_blockers() -> None:
    ligand = _target(
        target_kind="small_molecule",
        chemical_identity={"ccd": "TCI"},
        identity_status="confirmed",
    )
    assert readiness_blockers(ligand) == []


def test_a_ligand_target_mistyped_as_protein_is_blocked_on_a_structure_it_cannot_have() -> None:
    """The exact second-order failure the upsert bug produced."""
    mistyped = _target(target_kind="protein", chemical_identity={"ccd": "TCI"}, identity_status="confirmed")
    assert "target_structure_unavailable" in readiness_blockers(mistyped)


def test_a_de_novo_protein_is_identified_by_its_sequence_alone() -> None:
    """A designed protein has no accession; the sequence is its identity."""
    assert is_identified(_target(sequence="MKTAYIAKQR"))


def test_upsert_persists_target_kind_and_chemical_identity() -> None:
    """The dropped-fields bug, at the level of the service that dropped them."""
    import inspect

    from backend_v2.app.targets import service

    source = inspect.getsource(service.upsert_target)
    assert "target.target_kind = payload.target_kind" in source
    assert "target.chemical_identity = payload.chemical_identity" in source
