"""Druggability evidence: the misreadings a report is most prone to.

Fixtures are the shapes the sources actually returned for PD-1 (PDCD1) during
design - UniProt's cross-reference list, Open Targets' tractability rows and
clinical candidates - trimmed. The tests are about the ways a druggability
report goes wrong while looking right: an identifier resolved by name, a
modality missing from the output read as negative, an empty safety list read
as safe, an unretrieved phase read as zero, and a score where evidence belongs.
"""

from __future__ import annotations

from backend_v2.app.intelligence import druggability

UNIPROT_Q15116 = {
    "uniProtKBCrossReferences": [
        {"database": "Ensembl", "id": "ENST00000334409.10"},
        {"database": "OpenTargets", "id": "ENSG00000188389"},
    ]
}

OPEN_TARGETS_PDCD1 = {
    "target": {
        "approvedSymbol": "PDCD1",
        "tractability": [
            {"modality": "SM", "label": "Structure with Ligand", "value": True},
            {"modality": "SM", "label": "Approved Drug", "value": False},
            {"modality": "AB", "label": "Approved Drug", "value": True},
            {"modality": "AB", "label": "UniProt loc high conf", "value": True},
            {"modality": "PR", "label": "Literature", "value": True},
            {"modality": "OC", "label": "Advanced Clinical", "value": True},
        ],
        "safetyLiabilities": [],
        "drugAndClinicalCandidates": {
            "count": 26,
            "rows": [
                {"maxClinicalStage": "PHASE_3", "drug": {"id": "CHEMBL1", "name": "CAMRELIZUMAB"}},
                {"maxClinicalStage": "APPROVAL", "drug": {"id": "CHEMBL2", "name": "DOSTARLIMAB"}},
                {"maxClinicalStage": "APPROVAL", "drug": {"id": "CHEMBL3", "name": "SINTILIMAB"}},
                {"maxClinicalStage": "SOMETHING_NEW", "drug": {"id": "CHEMBL4", "name": "NOVELMAB"}},
            ],
        },
    }
}


def test_the_target_id_comes_from_uniprots_own_cross_reference() -> None:
    assert druggability.ensembl_from_uniprot(UNIPROT_Q15116) == "ENSG00000188389"


def test_no_cross_reference_means_no_id_rather_than_a_guess() -> None:
    """A transcript id is not a target id, and a name search is not a mapping."""
    only_transcript = {"uniProtKBCrossReferences": [{"database": "Ensembl", "id": "ENST00000334409.10"}]}

    assert druggability.ensembl_from_uniprot(only_transcript) is None


def test_tractability_keeps_the_evidence_behind_each_modality() -> None:
    rows = druggability.tractability(OPEN_TARGETS_PDCD1["target"]["tractability"])
    by_code = {row["modality"]: row for row in rows}

    assert by_code["AB"]["supported"] is True
    assert by_code["AB"]["evidence"] == ["Approved Drug", "UniProt loc high conf"]
    # SM is supported by a liganded structure, not by an approved drug.
    assert by_code["SM"]["evidence"] == ["Structure with Ligand"]


def test_a_modality_never_assessed_is_distinguished_from_one_assessed_negative() -> None:
    rows = druggability.tractability([{"modality": "SM", "label": "Approved Drug", "value": False}])
    by_code = {row["modality"]: row for row in rows}

    assert by_code["SM"] == {
        "modality": "SM",
        "name": "small molecule",
        "assessed": True,
        "supported": False,
        "evidence": [],
    }
    assert by_code["AB"]["assessed"] is False


def test_candidates_are_ordered_furthest_first_and_unknown_stages_are_kept() -> None:
    result = druggability.clinical_candidates(OPEN_TARGETS_PDCD1["target"]["drugAndClinicalCandidates"])

    assert [item["name"] for item in result["furthest"]] == [
        "DOSTARLIMAB",
        "SINTILIMAB",
        "CAMRELIZUMAB",
        "NOVELMAB",
    ]
    assert result["approved"] == 2
    assert result["reported_count"] == 26
    novel = next(item for item in result["furthest"] if item["name"] == "NOVELMAB")
    assert novel["stage_ranked"] is False


def test_an_empty_safety_list_is_never_presented_as_safe() -> None:
    result = druggability.safety_liabilities([])

    assert result["recorded"] == 0
    assert "not evidence that the target is safe" in result["interpretation"]


def test_a_phase_that_was_not_retrieved_is_none_not_zero() -> None:
    result = druggability.trial_activity(
        {"ALL": 4405, "PHASE1": 1335, "PHASE2": 2587, "PHASE3": 432, "PHASE4": None},
        query="PD-1",
    )

    assert result["by_phase"]["PHASE4"] is None
    assert "PHASE4" in result["phases_unavailable"]
    assert result["late_stage"] == 432


def test_a_report_without_a_mapping_names_the_gap_instead_of_reporting_zeros() -> None:
    report = druggability.assessment(
        target={"name": "Unmapped"}, ensembl_id=None, open_targets=None, trials=None
    )

    assert report["tractability"] is None
    assert report["clinical_candidates"] is None
    assert any("no Open Targets cross-reference" in gap for gap in report["gaps"])
    assert any("ClinicalTrials.gov activity was not retrieved" in gap for gap in report["gaps"])


def test_the_report_carries_no_score_and_always_carries_its_limits() -> None:
    report = druggability.assessment(
        target={"name": "PD-1", "uniprot_accession": "Q15116"},
        ensembl_id="ENSG00000188389",
        open_targets=OPEN_TARGETS_PDCD1,
        trials=druggability.trial_activity({"ALL": 10, "PHASE3": 2}, query="PD-1"),
    )

    flattened = str(report).lower()
    assert "probability" not in {key.lower() for key in report}
    assert "score" not in {key.lower() for key in report}
    assert "no druggability probability is given" in flattened
    assert "market size" in flattened


# --- Retrieval, with every failure named for what failed ----------------------


class _Result:
    def __init__(self, data, tool):
        self.data = data
        self.audit = {"tool": tool, "status": "completed"}


class _FakeTools:
    def __init__(self, *, uniprot=UNIPROT_Q15116, uniprot_fails=False, failing_phase=None):
        self.uniprot = uniprot
        self.uniprot_fails = uniprot_fails
        self.failing_phase = failing_phase
        self.open_targets_calls = 0

    def get_uniprot(self, accession):
        if self.uniprot_fails:
            raise RuntimeError("uniprot.entry_failed")
        return _Result(self.uniprot, "uniprot.entry")

    def get_open_targets_druggability(self, ensembl_id):
        self.open_targets_calls += 1
        return _Result({"data": OPEN_TARGETS_PDCD1}, "open_targets.druggability")

    def count_clinical_trials(self, term, *, phase=None):
        if phase is not None and phase == self.failing_phase:
            raise RuntimeError("clinical_trials.count_failed")
        return _Result({"totalCount": 100 if phase is None else 5}, "clinical_trials.count")


def _gather(tools):
    from backend_v2.app.intelligence.tasks import gather_druggability

    return gather_druggability(tools, {"name": "PD-1", "uniprot_accession": "Q15116"}, "PD-1")


def test_a_full_retrieval_records_every_call_and_reports_no_gaps() -> None:
    report = _gather(_FakeTools())

    assert report["ensembl_id"] == "ENSG00000188389"
    assert report["gaps"] == []
    assert set(report["retrieval"]) == {"uniprot_mapping", "open_targets", "clinical_trials"}
    assert report["trial_activity"]["total_matching"] == 100


def test_an_unreachable_uniprot_is_not_reported_as_a_missing_mapping() -> None:
    """Opposite conclusions: one sends a reader to fix a mapping that is not missing."""
    tools = _FakeTools(uniprot_fails=True)

    report = _gather(tools)

    assert tools.open_targets_calls == 0
    assert any("could not be retrieved" in gap for gap in report["gaps"])
    assert not any("no Open Targets cross-reference" in gap for gap in report["gaps"])


def test_a_uniprot_entry_without_the_cross_reference_says_so_and_queries_nothing_by_name() -> None:
    tools = _FakeTools(uniprot={"uniProtKBCrossReferences": []})

    report = _gather(tools)

    assert tools.open_targets_calls == 0
    assert any("no Open Targets cross-reference" in gap for gap in report["gaps"])


def test_one_failed_trial_count_is_none_and_named_not_zero() -> None:
    report = _gather(_FakeTools(failing_phase="PHASE3"))

    assert report["trial_activity"]["by_phase"]["PHASE3"] is None
    assert report["trial_activity"]["by_phase"]["PHASE2"] == 5
    assert any("PHASE3" in gap for gap in report["gaps"])
