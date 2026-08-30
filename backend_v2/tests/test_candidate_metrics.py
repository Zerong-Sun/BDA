"""Model-produced numbers must survive collection and be queryable.

The fixtures are verbatim superfold output from a real GPR37 binder fold on qm,
including the bare ``NaN`` it writes for monomer folds.
"""

from __future__ import annotations

import os
import uuid

import pytest
from backend_v2.app.candidates.models import Candidate, CandidateMetric
from backend_v2.app.candidates.repository import CandidateRepository
from backend_v2.app.compute.parsers import ParseContext, ParsedMetric, get_parser
from backend_v2.app.compute.tasks import _record_metrics
from backend_v2.app.core.database import SessionFactory
from backend_v2.app.identity.models import Organization
from backend_v2.app.identity.service import bootstrap_admin
from backend_v2.app.projects.models import Project, ProjectMember
from sqlalchemy import select

METHOD = "alphafold2_superfold"

# Verbatim, including the unquoted NaN that makes this invalid strict JSON.
RESULT_JSON = """{
  "mean_plddt": 96.0792007446289,
  "recycles": 5,
  "tol": 0.022974567487835884,
  "model": "4",
  "type": "monomer_ptm",
  "seed": "0",
  "mean_pae_interaction": NaN,
  "mean_pae_intra_chain_A": 2.274610757827759,
  "mean_pae_intra_chain": 2.274610757827759,
  "mean_pae": 2.335745096206665,
  "pTMscore": 0.8502889275550842,
  "elapsed_time": 112.75930571556091
}"""


def _outputs(*names: str) -> tuple[list[dict], dict[str, bytes]]:
    outputs, payloads = [], {}
    for name in names:
        key = f"k/{name}"
        outputs.append({"object_key": key, "filename": name, "artifact_type": "compute_output", "port": None})
        if name.endswith(".json"):
            payloads[key] = RESULT_JSON.encode()
    return outputs, payloads


def _parse(outputs: list[dict], payloads: dict[str, bytes]):
    ctx = ParseContext(
        job_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        attempt_number=1,
        outputs=outputs,
        parameters={},
        read_bytes=lambda key: payloads[key],
    )
    return get_parser(METHOD)(ctx)


def test_confidence_numbers_become_metrics_with_their_provenance() -> None:
    outputs, payloads = _outputs(
        "d1_model_4_ptm_seed_0_prediction_results.json",
        "d1_model_4_ptm_seed_0_unrelaxed.pdb",
    )
    parsed = _parse(outputs, payloads)

    assert [c.candidate_key for c in parsed.candidates] == ["d1"]
    candidate = parsed.candidates[0]
    by_key = {m.key: m for m in candidate.metrics}
    assert round(by_key["plddt"].value, 2) == 96.08
    assert round(by_key["ptm"].value, 3) == 0.850
    assert by_key["pae"].unit == "angstrom"
    # Every metric records which tool and which model produced it, and that a predicted
    # confidence is not evidence.
    assert by_key["plddt"].method == METHOD
    assert by_key["plddt"].model_variant == "model_4_ptm_seed_0"
    assert by_key["plddt"].evidence_kind == "predicted"
    assert by_key["plddt"].context["recycles"] == 5
    # The prediction is linked to the structure it describes.
    assert candidate.structure_output_index == 1


def test_a_nan_metric_is_dropped_rather_than_stored() -> None:
    """superfold writes NaN for interface PAE on every monomer fold.

    Storing it would make the column unqueryable and imply an interface score exists.
    """
    outputs, payloads = _outputs("d1_model_4_ptm_seed_0_prediction_results.json")
    parsed = _parse(outputs, payloads)
    assert "pae_interaction" not in {m.key for m in parsed.candidates[0].metrics}
    assert parsed.warnings == []


def test_each_model_is_kept_separately_and_ranking_uses_the_worst() -> None:
    """Disagreement between AlphaFold2 models is information, not noise."""
    outputs, payloads = _outputs(
        "d1_model_1_ptm_seed_0_prediction_results.json",
        "d1_model_4_ptm_seed_0_prediction_results.json",
    )
    # Make model_1 pessimistic so the two disagree.
    payloads["k/d1_model_1_ptm_seed_0_prediction_results.json"] = RESULT_JSON.replace(
        "96.0792007446289", "54.5"
    ).encode()
    parsed = _parse(outputs, payloads)

    candidate = parsed.candidates[0]
    plddt = sorted(m.value for m in candidate.metrics if m.key == "plddt")
    assert [round(v, 1) for v in plddt] == [54.5, 96.1]
    assert {m.model_variant for m in candidate.metrics} == {"model_1_ptm_seed_0", "model_4_ptm_seed_0"}
    # A design only one model likes is not worth carrying forward.
    assert round(candidate.score, 1) == 54.5
    assert round(candidate.scores["plddt"], 1) == 96.1


def test_unreadable_and_unrecognised_files_warn_instead_of_failing() -> None:
    outputs, payloads = _outputs("not_a_superfold_name_prediction_results.json")
    payloads["k/not_a_superfold_name_prediction_results.json"] = b"{"
    parsed = _parse(outputs, payloads)
    assert parsed.candidates == []
    assert any("unrecognised" in w for w in parsed.warnings)


def test_no_predictions_degrades_to_a_warning() -> None:
    parsed = _parse(*_outputs("some_structure.pdb"))
    assert parsed.candidates == []
    assert parsed.warnings and "nothing scored" in parsed.warnings[0]


def test_parsed_metric_defaults_to_predicted() -> None:
    """A number is a prediction unless a parser says otherwise."""
    assert ParsedMetric(key="plddt", value=90.0, method=METHOD).evidence_kind == "predicted"


# --- database-backed behaviour -------------------------------------------------------

dbtest = pytest.mark.skipif(
    os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration test disabled"
)


def _project(session):
    user = bootstrap_admin(session, username="metrics-admin", password="StrongPass123")
    organization = session.scalar(select(Organization).where(Organization.legacy_id == "bootstrap-default"))
    project = Project(
        organization_id=organization.id, owner_id=user.id, name="Metrics", project_type="discovery"
    )
    session.add(project)
    session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    return project


@dbtest
def test_a_second_method_scores_a_candidate_another_method_created() -> None:
    """AlphaFold2 folding a ProteinMPNN design used to lose its numbers entirely."""
    session = SessionFactory()
    transaction = session.begin()
    try:
        project = _project(session)
        candidate = Candidate(
            project_id=project.id, candidate_key="design_7", name="design_7", scores={"mpnn_score": 1.09}
        )
        session.add(candidate)
        session.flush()

        _record_metrics(
            session,
            candidate,
            [ParsedMetric(key="plddt", value=96.1, method=METHOD, model_variant="model_4_ptm_seed_0")],
            job_id=None,
        )
        session.flush()

        rows = CandidateRepository(session).metrics_for(candidate.id)
        assert [(r.metric_key, r.value, r.method) for r in rows] == [("plddt", 96.1, METHOD)]
    finally:
        transaction.rollback()
        session.close()


@dbtest
def test_recollecting_updates_a_metric_instead_of_duplicating_it() -> None:
    session = SessionFactory()
    transaction = session.begin()
    try:
        project = _project(session)
        candidate = Candidate(project_id=project.id, candidate_key="design_8", name="design_8")
        session.add(candidate)
        session.flush()

        for value in (90.0, 93.5):
            _record_metrics(
                session,
                candidate,
                [ParsedMetric(key="plddt", value=value, method=METHOD, model_variant="model_4_ptm_seed_0")],
                job_id=None,
            )
            session.flush()

        rows = session.scalars(
            select(CandidateMetric).where(CandidateMetric.candidate_id == candidate.id)
        ).all()
        assert len(rows) == 1 and rows[0].value == 93.5
    finally:
        transaction.rollback()
        session.close()


@dbtest
def test_candidates_can_be_filtered_by_a_metric_range() -> None:
    """The query this table exists for."""
    session = SessionFactory()
    transaction = session.begin()
    try:
        project = _project(session)
        for key, plddt in (("good", 96.1), ("weak", 54.6)):
            candidate = Candidate(project_id=project.id, candidate_key=key, name=key)
            session.add(candidate)
            session.flush()
            _record_metrics(
                session,
                candidate,
                [
                    ParsedMetric(key="plddt", value=plddt, method=METHOD, model_variant="model_1"),
                    ParsedMetric(key="plddt", value=plddt, method=METHOD, model_variant="model_4"),
                ],
                job_id=None,
            )
        session.flush()

        repo = CandidateRepository(session)
        hits = repo.list_project(project.id, None, 50, metric_key="plddt", metric_min=90.0)
        # Scored by two models, but returned once.
        assert [c.candidate_key for c in hits] == ["good"]
        assert repo.list_project(project.id, None, 50, metric_key="plddt", metric_max=60.0)[0].candidate_key == "weak"
        assert repo.list_project(project.id, None, 50, metric_key="ptm", metric_min=0.5) == []
    finally:
        transaction.rollback()
        session.close()
