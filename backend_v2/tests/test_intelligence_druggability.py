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

    def count_clinical_trials(self, term, *, phase=None, start_year=None):
        if phase is not None and phase == self.failing_phase:
            raise RuntimeError("clinical_trials.count_failed")
        if start_year is not None:
            return _Result({"totalCount": 10}, "clinical_trials.count")
        return _Result({"totalCount": 100 if phase is None else 5}, "clinical_trials.count")

    def list_clinical_trial_sponsors(self, term, *, page_token=None):
        self.sponsor_pages = getattr(self, "sponsor_pages", 0) + 1
        # Always offers another page, so the cap is what stops the loop.
        return _Result(
            {"studies": [_study("INDUSTRY", "Merck"), _study("OTHER", "Fudan")], "nextPageToken": "next"},
            "clinical_trials.sponsors",
        )


def _gather(tools, **kwargs):
    from backend_v2.app.intelligence.tasks import gather_druggability

    kwargs.setdefault("patent_priority_years", {"2015": 3})
    kwargs.setdefault("current_year", 2026)
    return gather_druggability(tools, {"name": "PD-1", "uniprot_accession": "Q15116"}, "PD-1", **kwargs)


def test_a_full_retrieval_records_every_call_and_reports_no_gaps() -> None:
    report = _gather(_FakeTools())

    assert report["ensembl_id"] == "ENSG00000188389"
    assert report["gaps"] == []
    assert set(report["retrieval"]) == {
        "uniprot_mapping",
        "open_targets",
        "clinical_trials",
        "clinical_trials_trend",
        "clinical_trials_sponsors",
    }
    assert report["trial_activity"]["total_matching"] == 100


def test_the_sponsor_scan_stops_at_its_cap_and_reports_itself_as_partial() -> None:
    from backend_v2.app.intelligence import druggability as kernel

    tools = _FakeTools()

    report = _gather(tools)

    sponsors = report["market_landscape"]["sponsor_mix"]
    assert tools.sponsor_pages == kernel.MAX_SPONSOR_PAGES
    assert sponsors["studies_aggregated"] == 2 * kernel.MAX_SPONSOR_PAGES
    assert sponsors["complete"] is False
    assert report["market_landscape"]["trial_registrations"]["partial_year"] == "2026"
    assert len(report["market_landscape"]["trial_registrations"]["by_start_year"]) == kernel.TREND_YEARS


def test_without_saved_patents_the_filing_trend_is_named_as_missing() -> None:
    report = _gather(_FakeTools(), patent_priority_years=None)

    assert report["market_landscape"]["patent_priority_years"] is None
    assert any("No patents are saved" in gap for gap in report["gaps"])


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


# --- Market prospects, as counts with their limits ----------------------------


def _study(sponsor_class, name):
    return {"protocolSection": {"sponsorCollaboratorsModule": {"leadSponsor": {"class": sponsor_class, "name": name}}}}


def test_the_sponsor_mix_counts_classes_and_names_industry_leaders() -> None:
    studies = [_study("INDUSTRY", "Merck"), _study("INDUSTRY", "Merck"), _study("OTHER", "Fudan University")]

    mix = druggability.sponsor_mix(studies, total_matching=3)

    assert mix["by_class"] == {"INDUSTRY": 2, "OTHER": 1}
    assert mix["industry_share"] == round(2 / 3, 3)
    assert mix["top_industry_sponsors"] == [{"sponsor": "Merck", "registrations": 2}]
    assert mix["complete"] is True


def test_a_sponsor_mix_from_part_of_the_registrations_says_it_is_partial() -> None:
    """A first page is not a random sample; the mix must not read as the whole field."""
    mix = druggability.sponsor_mix([_study("OTHER", "A")], total_matching=4405)

    assert mix["complete"] is False
    assert mix["studies_aggregated"] == 1


def test_an_unretrieved_year_is_listed_not_drawn_as_a_dip() -> None:
    trend = druggability.registration_trend({2024: 400, 2025: None, 2026: 120}, current_year=2026)

    assert trend["by_start_year"] == {"2024": 400, "2025": None, "2026": 120}
    assert trend["years_unavailable"] == ["2025"]
    assert trend["partial_year"] == "2026"


def test_the_market_landscape_carries_no_market_size_and_says_why() -> None:
    landscape = druggability.market_landscape(
        candidates={"approved": 9, "by_stage": {"APPROVAL": 9}},
        trend=None,
        sponsors=None,
        patent_priority_years={"2015": 3},
    )

    assert landscape["approved_on_target"] == 9
    assert not {"market_size", "revenue", "price", "share"} & set(landscape)
    assert "not a market forecast" in " ".join(landscape["limits"])
