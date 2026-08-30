"""Lineage between runs, and how findings resolve.

Both exist because a real project needed them and the platform had nowhere to put the
information - see docs/RESEARCH_RECORD_STRUCTURE.md. The cases below are the ones that
project actually produced: a single-variable control, an independent replicate at identical
settings, and a conclusion that was later overturned.
"""

from __future__ import annotations

from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.workflows.lineage import (
    ARM_BASELINE,
    ARM_REPLICATE,
    ARM_VARIANT,
    arm_label_for,
    describe,
    diff_parameters,
    varied_parameter_names,
)

# The two arms that produced this project's central result: identical but for percent_x.
PX90 = {"proteinhunter": {"ligand_ccd": "TCI", "percent_x": 90, "num_designs": 5, "alanine_bias": True}}
PX50 = {"proteinhunter": {"ligand_ccd": "TCI", "percent_x": 50, "num_designs": 5, "alanine_bias": True}}


def test_a_single_variable_control_reports_exactly_one_difference() -> None:
    """The claim the whole percent_x conclusion rests on, now checkable."""
    differences = diff_parameters(PX90, PX50)
    assert differences == {"proteinhunter": {"percent_x": {"from": 90, "to": 50}}}
    assert varied_parameter_names(differences) == ["percent_x"]
    assert describe(differences) == "percent_x"


def test_an_identical_rerun_is_a_replicate_not_a_variant() -> None:
    """Reproducibility runs differ by nothing; the label has to follow the diff."""
    differences = diff_parameters(PX50, dict(PX50))
    assert differences == {}
    assert arm_label_for(object(), differences) == ARM_REPLICATE


def test_a_run_without_an_ancestor_is_a_baseline() -> None:
    assert arm_label_for(None, {}) == ARM_BASELINE
    # Even if something differs, with nothing to compare against it is still the baseline.
    assert arm_label_for(None, {"n": {"x": {"from": 1, "to": 2}}}) == ARM_BASELINE


def test_any_difference_makes_it_a_variant() -> None:
    assert arm_label_for(object(), diff_parameters(PX90, PX50)) == ARM_VARIANT


def test_multiple_changes_are_all_reported_so_a_control_cannot_be_overstated() -> None:
    """The point is to catch a run described as single-variable that is not."""
    sloppy = {"proteinhunter": {**PX50["proteinhunter"], "num_designs": 100, "temperature": 0.5}}
    differences = diff_parameters(PX90, sloppy)
    assert set(differences["proteinhunter"]) == {"percent_x", "num_designs", "temperature"}
    assert describe(differences) == "3 parameters across 1 node(s)"


def test_added_and_removed_nodes_count_as_differences() -> None:
    """Adding a validation step changes the experiment as much as retuning one."""
    with_extra = {**PX50, "alphafold": {"ligand": "TCI"}}
    assert diff_parameters(PX50, with_extra)["alphafold"] == {"node": {"from": None, "to": "added"}}
    assert diff_parameters(with_extra, PX50)["alphafold"] == {"node": {"from": "present", "to": None}}


def test_a_parameter_that_changed_type_is_a_difference() -> None:
    """"50" and 50 reach a CLI differently; treating them as equal would hide a change."""
    assert diff_parameters(
        {"n": {"percent_x": 50}}, {"n": {"percent_x": "50"}}
    ) == {"n": {"percent_x": {"from": 50, "to": "50"}}}


def test_describe_reads_plainly_when_nothing_changed() -> None:
    assert describe({}) == "no parameter differences"


def test_finding_outcomes_include_refuted_as_a_first_class_value() -> None:
    """The project's most valuable conclusion was a refutation; it needs a home."""
    from backend_v2.app.research.schemas import FindingCreate

    finding = FindingCreate(
        title="Designs show no selectivity for Delta9-THC",
        content="Median delta against the strongest control is -0.04 across ten candidates.",
        outcome="refuted",
        provenance={"job_ids": ["4083526"], "candidate_ids": ["thc_b0_c4"]},
    )
    assert finding.outcome == "refuted"
    assert finding.provenance["job_ids"] == ["4083526"]

    # Unspecified is the default so that rows predating the column do not claim an outcome.
    assert FindingCreate(title="t", content="c").outcome == "unspecified"


def test_finding_outcome_rejects_values_outside_the_vocabulary() -> None:
    import pytest
    from backend_v2.app.research.schemas import FindingCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FindingCreate(title="t", content="c", outcome="probably")


def _target(**fields):
    """A stand-in with just the attributes the readiness rules read."""
    from types import SimpleNamespace

    base = dict(
        target_kind="protein", uniprot_accession=None, sequence=None, chemical_identity={},
        identity_status="unconfirmed", structure_status="missing", structure_artifact_id=None,
    )
    return SimpleNamespace(**{**base, **fields})


def test_a_small_molecule_target_is_identified_by_its_chemistry() -> None:
    """A ligand has no accession and no sequence; demanding them blocks it forever."""
    from backend_v2.app.targets.identity import is_identified

    thc = _target(target_kind="small_molecule", chemical_identity={"ccd": "TCI"})
    assert is_identified(thc)
    # Any one resolver is enough.
    assert is_identified(_target(target_kind="small_molecule",
                                 chemical_identity={"inchikey": "CYQFCXCEBYINGO-IAGOWNOFSA-N"}))
    assert is_identified(_target(target_kind="small_molecule", chemical_identity={"smiles": "CCO"}))
    # Named but unresolved is not identified.
    assert not is_identified(_target(target_kind="small_molecule", chemical_identity={}))
    assert not is_identified(_target(target_kind="small_molecule", chemical_identity={"ccd": "  "}))


def test_a_protein_target_still_needs_an_accession_or_sequence() -> None:
    from backend_v2.app.targets.identity import is_identified

    assert not is_identified(_target())
    assert is_identified(_target(uniprot_accession="P07148"))
    assert is_identified(_target(sequence="MKTVRQ"))


def test_a_ligand_target_reaches_the_workflow_without_an_uploaded_structure() -> None:
    """The whole point: its coordinates come from the component library at run time."""
    from backend_v2.app.targets.identity import readiness_blockers

    thc = _target(target_kind="small_molecule", chemical_identity={"ccd": "TCI"},
                  identity_status="confirmed")
    assert readiness_blockers(thc) == []


def test_a_protein_target_without_a_structure_is_still_blocked() -> None:
    """Relaxing the ligand path must not relax the protein path."""
    from backend_v2.app.targets.identity import readiness_blockers

    protein = _target(uniprot_accession="P07148", identity_status="confirmed")
    assert readiness_blockers(protein) == ["target_structure_unavailable"]

    ready = _target(uniprot_accession="P07148", identity_status="confirmed",
                    structure_status="available", structure_artifact_id="artifact-1")
    assert readiness_blockers(ready) == []


def test_an_unidentified_ligand_target_is_blocked_on_identity_alone() -> None:
    from backend_v2.app.targets.identity import readiness_blockers

    blockers = readiness_blockers(_target(target_kind="small_molecule"))
    assert blockers == ["target_identity_unconfirmed"]
