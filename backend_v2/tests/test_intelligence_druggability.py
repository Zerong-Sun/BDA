"""Druggability evidence: the misreadings a report is most prone to.

Fixtures are the shapes the sources actually returned for PD-1 (PDCD1) during
design - UniProt's cross-reference list, Open Targets' tractability rows and
clinical candidates - trimmed. The tests are about the ways a druggability
report goes wrong while looking right: an identifier resolved by name, a
modality missing from the output read as negative, an empty safety list read
as safe, an unretrieved phase read as zero, and a score where evidence belongs.
"""

from __future__ import annotations

import pytest
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
    # The test's own name is the rule: an unretrieved phase is not zero. This
    # asserted 432 - the phase 3 count alone - which reports "432 late-stage
    # trials" for a target whose phase 4 count simply failed to load.
    assert result["late_stage"] is None


def test_late_stage_is_the_sum_once_both_late_phases_are_known() -> None:
    result = druggability.trial_activity(
        {"ALL": 4405, "PHASE1": 1335, "PHASE2": 2587, "PHASE3": 432, "PHASE4": 87},
        query="PD-1",
    )

    assert result["late_stage"] == 519
    assert result["phases_unavailable"] == ["EARLY_PHASE1"]


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
        # Two registrations per page, 50 pages: the announced 100 registrations.
        return _Result(
            {"studies": [_study("INDUSTRY", "Merck"), _study("OTHER", "Fudan")], "nextPageToken": str(self.sponsor_pages) if self.sponsor_pages < 50 else None},
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


def test_the_sponsor_scan_stops_at_its_cap_and_reports_itself_as_partial(monkeypatch) -> None:
    from backend_v2.app.intelligence import druggability as kernel

    monkeypatch.setattr(kernel, "MAX_SPONSOR_PAGES", 2)
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


# --- Edges the audit found untested -----------------------------------------


def test_rows_that_are_not_mappings_are_skipped_rather_than_crashing() -> None:
    """Every source here is external JSON; a string where an object belongs is its problem, not a traceback."""
    assert druggability.ensembl_from_uniprot({"uniProtKBCrossReferences": ["nonsense", 7]}) is None
    rows = druggability.tractability(["nonsense", {"modality": "", "value": True}, {"modality": "SM", "value": True, "label": "X"}])
    assert [row["modality"] for row in rows if row["supported"]] == ["SM"]
    assert druggability.safety_liabilities(["nonsense"])["recorded"] == 0
    assert druggability.sponsor_mix(["nonsense"], total_matching=0)["studies_aggregated"] == 0


def test_a_mapped_target_open_targets_does_not_know_is_a_named_gap() -> None:
    report = druggability.assessment(
        target={"name": "Mapped but absent"},
        ensembl_id="ENSG00000999999",
        open_targets={"target": None},
        trials=None,
    )

    assert any("Open Targets returned no record" in gap for gap in report["gaps"])
    assert report["tractability"] is None


def test_a_target_that_is_not_a_mapping_is_refused_before_a_report_exists() -> None:
    with pytest.raises(druggability.DruggabilityInputError):
        druggability.assessment(target="PD-1", ensembl_id=None, open_targets=None, trials=None)  # type: ignore[arg-type]


def test_a_project_with_nothing_saved_is_told_it_can_cite_nothing() -> None:
    """The report names public evidence; this says what the project itself can cite."""
    signal = druggability.literature_signal({"papers": 0, "patents": 0})
    report = druggability.assessment(
        target={"name": "PD-1"}, ensembl_id=None, open_targets=None, trials=None, literature=signal
    )

    assert "Run a literature or patent search first" in signal["interpretation"]
    assert any("saved no papers or patents" in gap for gap in report["gaps"])


def test_saved_documents_are_counted_without_claiming_they_were_read() -> None:
    signal = druggability.literature_signal(
        {"papers": 12, "patents": 30},
        recent=[{"document_id": "doc-1", "title": "PD-1 blockade", "source": "europe_pmc"}],
    )

    assert (signal["saved_papers"], signal["saved_patents"]) == (12, 30)
    assert signal["recent"][0]["document_id"] == "doc-1"
    assert "Saved is not read" in signal["interpretation"]


def test_sponsors_cover_more_than_5000_registrations_without_counting_page_overlap():
    class Pages(_FakeTools):
        def count_clinical_trials(self, term, *, phase=None, start_year=None):
            return _Result({"totalCount": 6001 if phase is None and start_year is None else 5}, "count")

        def list_clinical_trial_sponsors(self, term, *, page_token=None):
            start = int(page_token or 0)
            rows = []
            for n in range(max(0, start - 1), min(start + 1000, 6001)):
                row = _study("INDUSTRY", "Example")
                row["protocolSection"]["identificationModule"] = {"nctId": f"NCT{n:08d}"}
                rows.append(row)
            return _Result({"studies": rows, "nextPageToken": str(start + 1000) if start + 1000 < 6001 else None}, "sponsors")
    result = _gather(Pages())["market_landscape"]["sponsor_mix"]
    assert result["studies_aggregated"] == 6001
    assert result["duplicate_registrations_skipped"] == 6
    assert result["pages_read"] == 7
    assert result["complete"] is True


def test_repeated_sponsor_cursor_stops_and_never_reports_complete():
    class Repeated(_FakeTools):
        def list_clinical_trial_sponsors(self, term, *, page_token=None):
            return _Result({"studies": [_study("OTHER", "Example")], "nextPageToken": "same"}, "sponsors")
    report = _gather(Repeated())
    assert report["market_landscape"]["sponsor_mix"]["pages_read"] == 2
    assert report["market_landscape"]["sponsor_mix"]["complete"] is False
    assert any("repeated a page token" in gap for gap in report["gaps"])
