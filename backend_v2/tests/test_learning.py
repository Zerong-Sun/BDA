"""Learning contracts and an HTTP round trip using synthetic measurements only."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.identity.deps import current_user
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.learning import engine as learning
from backend_v2.app.learning.models import LearningDataset, LearningModel
from backend_v2.app.main import app
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.research.models import ResearchGoal
from backend_v2.app.timeline.models import ProjectTimelineEntry
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _sequence(n: int) -> str:
    return "A" * n + "C" * (100 - n)


@pytest.fixture
def client() -> Generator:
    db = enforce_foreign_keys(
        create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    Base.metadata.create_all(db)
    factory = sessionmaker(db, expire_on_commit=False)
    with factory() as s:
        user = User(username="learning", display_name="Learning", role="admin", enabled=True)
        org = Organization(name="Learning")
        s.add_all([user, org])
        s.flush()
        s.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
        project = Project(organization_id=org.id, owner_id=user.id, name="Learning", project_type="protein_design")
        other = Project(organization_id=org.id, owner_id=user.id, name="Other", project_type="protein_design")
        s.add_all([project, other])
        s.flush()
        s.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        goal = ResearchGoal(project_id=project.id, title="Synthetic assay", detail="Test only", created_by=user.id)
        artifact = Artifact(
            project_id=project.id,
            created_by=user.id,
            artifact_type="experiment_data",
            filename="synthetic.csv",
            content_type="text/csv",
            object_key="synthetic.csv",
            size_bytes=123,
            checksum_sha256="a" * 64,
        )
        candidates = [
            Candidate(project_id=project.id, name=f"C{n}", candidate_key=f"c{n}", properties={"sequence": _sequence(n)})
            for n in (10, 25, 40, 55, 70, 85, 35, 65, 95)
        ]
        foreign = Candidate(
            project_id=other.id, name="Foreign", candidate_key="foreign", properties={"sequence": "AAAA"}
        )
        s.add_all([goal, artifact, foreign, *candidates])
        s.flush()
        ids = {
            "user": user.id,
            "project": project.id,
            "other": other.id,
            "goal": goal.id,
            "artifact": artifact.id,
            "candidates": [c.id for c in candidates],
            "foreign": foreign.id,
        }
        s.commit()

    def session_override() -> Generator[Session]:
        with factory() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    def user_override() -> User:
        with factory() as s:
            return s.get(User, ids["user"])

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[current_user] = user_override
    try:
        yield TestClient(app), ids, factory
    finally:
        app.dependency_overrides.clear()
        drop_all(db, Base.metadata)


def _post(ctx, path, body, *, version=None, status=201):
    api, ids, _ = ctx
    headers = {"If-Match": f'W/"{version}"'} if version else {}
    response = api.post(f"/api/v2/projects/{ids['project']}/learning/{path}", json=body, headers=headers)
    assert response.status_code == status, response.text
    return response.json()


def _setup(ctx):
    _, ids, _ = ctx
    assay = _post(
        ctx, "assays", {"name": "Test assay", "method": "Synthetic fixture", "unit": "nM", "conditions": {"pH": "7"}}
    )
    study = _post(
        ctx,
        "studies",
        {
            "assay_id": assay["id"],
            "research_goal_id": str(ids["goal"]),
            "name": "Test loop",
            "direction": "maximize",
            "batch_budget_cents": 250,
            "max_batch_size": 2,
        },
    )
    return assay, study


def _observation(ids, assay, index=0, **extra):
    return {
        "assay_id": assay["id"],
        "candidate_id": str(ids["candidates"][index]),
        "source_artifact_id": str(ids["artifact"]),
        "batch_key": "test-batch",
        "replicate_key": "bio-1",
        "replicate_type": "biological",
        "status": "measured",
        "value": 10 + index * 15,
        "unit": "nM",
        "qc_accepted": True,
        "note": "Synthetic fixture",
        **extra,
    }


def _trained(ctx):
    assay, study = _setup(ctx)
    results = [_post(ctx, "observations", _observation(ctx[1], assay, i)) for i in range(6)]
    dataset = _post(ctx, "datasets", {"study_id": study["id"], "result_ids": [r["id"] for r in results]})
    model = _post(ctx, "models", {"dataset_id": dataset["id"]})
    assert model["evaluation"]["eligible_for_promotion"]
    return assay, study, results, dataset, model


def _proposal(ctx, study, model):
    return _post(
        ctx,
        "decisions",
        {
            "study_id": study["id"],
            "model_id": model["id"],
            "exploration_fraction": 0.5,
            "candidates": [{"candidate_id": str(c), "cost_cents": 100} for c in ctx[1]["candidates"]],
        },
    )


def test_full_round_trip_and_reproducible_evidence(client):
    api, ids, factory = client
    _, study, _, dataset, model = _trained(client)
    shadow = _proposal(client, study, model)
    assert shadow["proposal"]["status"] == "shadow"
    _post(client, f"decisions/{shadow['id']}/review", {"approve": True, "rationale": "Review"}, version=1, status=409)
    promoted = _post(
        client,
        f"models/{model['id']}/review",
        {"action": "promote", "rationale": "Retrospective baseline passed"},
        version=1,
        status=200,
    )
    assert promoted["version"] == 2
    decision = _proposal(client, study, promoted)
    proposal = decision["proposal"]
    assert len(proposal["selected"]) == 2 and proposal["estimated_cost_cents"] <= 250
    assert not proposal["execution_authorized"] and not proposal["budget_reserved"]
    reviewed = _post(
        client,
        f"decisions/{decision['id']}/review",
        {"approve": True, "rationale": "Next batch reviewed"},
        version=1,
        status=200,
    )
    assert reviewed["review_status"] == "approved" and reviewed["timeline_entry_id"]
    exported = api.get(f"/api/v2/projects/{ids['project']}/learning/decisions/{decision['id']}/export")
    assert exported.status_code == 200
    package = exported.json()
    assert learning.digest(package["content"]) == package["checksum"]
    assert learning.digest(package["content"]["dataset"]["manifest"]) == dataset["digest"]
    with factory() as s:
        assert s.get(ProjectTimelineEntry, uuid.UUID(reviewed["timeline_entry_id"])).body == "Next batch reviewed"
    # Retry-safe freezing and training do not create new versions of identical evidence.
    assert _post(client, "models", {"dataset_id": dataset["id"]})["id"] == model["id"]


@pytest.mark.parametrize(
    "patch",
    [
        {"status": "failed", "value": 0},
        {"status": "missing", "value": 1},
        {"status": "measured", "value": None},
        {"status": "below_limit", "value": None},
        {"qc_accepted": "true"},
        {"unknown": True},
        {"unit": "uM"},
    ],
)
def test_invalid_measurements_are_rejected(client, patch):
    assay, _ = _setup(client)
    _post(client, "observations", _observation(client[1], assay, **patch), status=422)


def test_failed_censored_and_qc_results_are_preserved_and_excluded(client):
    assay, study = _setup(client)
    measurements = [
        _post(client, "observations", _observation(client[1], assay, status="failed", value=None)),
        _post(client, "observations", _observation(client[1], assay, status="below_limit", value=0.01)),
        _post(client, "observations", _observation(client[1], assay, qc_accepted=False)),
    ]
    payload = {"study_id": study["id"], "result_ids": [r["id"] for r in measurements]}
    dataset = _post(client, "datasets", payload)
    assert not dataset["manifest"]["included"] and len(dataset["manifest"]["excluded"]) == 3
    assert dataset["manifest"]["sources"][0]["metadata"]["learning"]["status"] in {"failed", "below_limit", "measured"}
    assert _post(client, "datasets", payload)["id"] == dataset["id"]
    _post(client, "models", {"dataset_id": dataset["id"]}, status=422)


def test_scope_pagination_and_read_only_user(client):
    api, ids, factory = client
    assay, study = _setup(client)
    _post(client, "assays", {"name": "Other", "method": "Other", "unit": "nM"})
    base = f"/api/v2/projects/{ids['project']}/learning"
    one = api.get(base + "/assays?limit=1").json()
    two = api.get(base + "/assays", params={"limit": 1, "cursor": one["next_cursor"]}).json()
    assert one["items"][0]["id"] != two["items"][0]["id"] and two["next_cursor"] is None
    assert api.get(base + "/assays?cursor=broken").status_code == 422
    assert api.get(f"/api/v2/projects/{ids['other']}/learning/assays/{assay['id']}").status_code == 404
    _post(client, "observations", _observation(ids, assay, candidate_id=str(ids["foreign"])), status=404)
    with factory() as s:
        user = s.get(User, ids["user"])
        user.role = "viewer"
        member = s.scalar(select(OrganizationMember).where(OrganizationMember.user_id == ids["user"]))
        member.role = "viewer"
        project_member = s.scalar(select(ProjectMember).where(ProjectMember.user_id == ids["user"]))
        project_member.role = "viewer"
        s.commit()
    _post(client, "assays", {"name": "Forbidden", "method": "m", "unit": "nM"}, status=403)


@pytest.mark.parametrize("changed", ["candidate", "goal", "retired"])
def test_stale_proposals_cannot_be_approved(client, changed):
    _, study, _, _, model = _trained(client)
    model = _post(
        client, f"models/{model['id']}/review", {"action": "promote", "rationale": "Pass"}, version=1, status=200
    )
    decision = _proposal(client, study, model)
    with client[2]() as s:
        if changed == "candidate":
            candidate = s.get(Candidate, uuid.UUID(decision["proposal"]["selected"][0]["candidate_id"]))
            candidate.properties = {"sequence": "AAAA"}
        elif changed == "goal":
            goal = s.get(ResearchGoal, client[1]["goal"])
            goal.version += 1
        else:
            current = s.get(LearningModel, uuid.UUID(model["id"]))
            current.status = "retired"
        s.commit()
    _post(client, f"decisions/{decision['id']}/review", {"approve": True, "rationale": "Review"}, version=1, status=409)


def test_review_requires_matching_version_and_is_final(client):
    api, ids, _ = client
    _, study, _, _, model = _trained(client)
    path = f"models/{model['id']}/review"
    _post(client, path, {"action": "promote", "rationale": "Review"}, status=428)
    _post(client, path, {"action": "promote", "rationale": "Review"}, version=9, status=412)
    decision = _proposal(client, study, model)
    _post(
        client,
        f"decisions/{decision['id']}/review",
        {"approve": False, "rationale": "Insufficient evidence"},
        version=1,
        status=200,
    )
    _post(client, f"decisions/{decision['id']}/review", {"approve": False, "rationale": "Again"}, version=1, status=412)
    _post(client, f"decisions/{decision['id']}/review", {"approve": False, "rationale": "Again"}, version=2, status=409)


def test_mutated_metadata_and_frozen_manifest_are_detected(client):
    _, study, results, dataset, _ = _trained(client)
    with client[2]() as s:
        result = s.get(ExperimentResult, uuid.UUID(results[0]["id"]))
        result.value = 99
        frozen = s.get(LearningDataset, uuid.UUID(dataset["id"]))
        frozen.manifest = {**frozen.manifest, "changed": True}
        s.commit()
    _post(client, "datasets", {"study_id": study["id"], "result_ids": [results[0]["id"]]}, status=422)
    _post(client, "models", {"dataset_id": dataset["id"]}, status=409)


def _rows():
    return [
        {**learning.features(_sequence(n)), "value": n, "batch_key": "b", "replicate_key": "bio"}
        for n in (10, 25, 40, 55, 70, 85)
    ]


def test_grouped_validation_is_invariant_to_technical_duplicate_rows():
    rows = _rows()
    parameters, evaluation = learning.train(rows)
    duplicate, duplicate_eval = learning.train([*rows, *[rows[0]] * 30])
    assert parameters == duplicate
    assert evaluation["rmse"] == duplicate_eval["rmse"]
    assert duplicate_eval["groups"] == 6


def test_baseline_does_not_promote_uninformative_data():
    _, evaluation = learning.train([{**r, "value": 1.0} for r in _rows()])
    assert not evaluation["eligible_for_promotion"]


@pytest.mark.parametrize("sequence", ["", "AXZ", "A" * 10001])
def test_feature_contract(sequence):
    with pytest.raises(ValueError):
        learning.features(sequence)


def test_budget_stop_and_ood_are_explicit():
    parameters, _ = learning.train(_rows())
    pool = [{**learning.features("W" * 100), "candidate_id": "new", "cost_cents": 100}]
    stopped = learning.propose(
        parameters, pool, direction="maximize", budget=50, batch_size=2, exploration_fraction=0.5
    )
    assert stopped["action"] == "stop_no_feasible_candidate" and stopped["estimated_cost_cents"] == 0
    assert stopped["considered"][0]["out_of_domain"]
    selected = learning.propose(
        parameters, pool, direction="minimize", budget=100, batch_size=1, exploration_fraction=1
    )
    assert selected["selected"][0]["selection_reason"] == "exploration"
