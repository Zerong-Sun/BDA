"""Real PostgreSQL regression tests for concurrent, opposite dual-assay decisions."""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import pytest
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.core.database import SessionFactory
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.learning import service
from backend_v2.app.learning.models import LearningModel, LearningStudy
from backend_v2.app.learning.schemas import (
    AssayCreate,
    DatasetCreate,
    LearningDecisionCreate,
    ModelReview,
    ObservationCreate,
    StudyCreate,
)
from backend_v2.app.projects.models import Project
from backend_v2.app.research.models import ResearchGoal
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration test disabled")


@pytest.fixture
def pair():
    with SessionFactory.begin() as session:
        user = User(
            username=f"release-{uuid.uuid4()}", display_name="Synthetic concurrency", role="admin", enabled=True
        )
        org = Organization(name="Synthetic release test")
        session.add_all([user, org])
        session.flush()
        project = Project(organization_id=org.id, owner_id=user.id, name="Synthetic", project_type="protein_design")
        session.add(project)
        session.flush()
        goal = ResearchGoal(project_id=project.id, title="Synthetic", detail="Test only", created_by=user.id)
        candidate = Candidate(
            project_id=project.id,
            candidate_key="synthetic-new",
            name="Synthetic new",
            properties={"sequence": "A" * 30 + "C" * 70},
        )
        artifact = Artifact(
            project_id=project.id,
            created_by=user.id,
            artifact_type="experiment_data",
            filename="synthetic.csv",
            content_type="text/csv",
            object_key=f"synthetic-{project.id}",
            checksum_sha256="a" * 64,
            size_bytes=10,
        )
        training_candidates = [
            Candidate(
                project_id=project.id,
                candidate_key=f"synthetic-{n}",
                name=f"Synthetic {n}",
                properties={"sequence": "A" * n + "C" * (100 - n)},
            )
            for n in (10, 25, 40, 55, 70, 85)
        ]
        session.add_all([goal, candidate, artifact, *training_candidates])
        session.flush()
        models, studies = [], []
        for index in range(2):
            assay = service.create_assay(
                session, project, user, AssayCreate(name=f"Assay {index}", method="Synthetic", unit="nM")
            )
            study = service.create_study(
                session,
                project,
                user,
                StudyCreate(
                    assay_id=assay.id,
                    research_goal_id=goal.id,
                    name=f"Study {index}",
                    direction="maximize",
                    batch_budget_cents=100,
                ),
            )
            results = [
                service.create_observation(
                    session,
                    project,
                    user,
                    ObservationCreate(
                        assay_id=assay.id,
                        candidate_id=item.id,
                        source_artifact_id=artifact.id,
                        batch_key="synthetic",
                        replicate_key="bio1",
                        replicate_type="biological",
                        status="measured",
                        value=float(item.properties["sequence"].count("A")),
                        unit="nM",
                        qc_accepted=True,
                        note="Synthetic concurrency fixture",
                    ),
                )
                for item in training_candidates
            ]
            dataset = service.freeze_dataset(
                session, project, user, DatasetCreate(study_id=study.id, result_ids=[r.id for r in results])
            )
            model = service.train_model(session, project, user, dataset.id)
            service.review_model(
                session, project, user, model.id, ModelReview(action="promote", rationale="Synthetic"), model.version
            )
            models.append(model.id)
            studies.append(study.id)
        ids = (user.id, org.id, project.id, candidate.id, studies, models)
    try:
        yield ids
    finally:
        with SessionFactory.begin() as session:
            session.execute(delete(AuditLog).where(AuditLog.project_id == ids[2]))
            session.execute(delete(Project).where(Project.id == ids[2]))
            session.execute(delete(Organization).where(Organization.id == ids[1]))
            session.execute(delete(User).where(User.id == ids[0]))


def propose(pair, primary=0, started=None, barrier=None):
    user_id, _, project_id, candidate_id, studies, models = pair
    with SessionFactory.begin() as session:
        user, project = session.get(User, user_id), session.get(Project, project_id)
        if barrier:
            barrier.wait()
        if started:
            started.set()
        decision = service.create_decision(
            session,
            project,
            user,
            LearningDecisionCreate(
                study_id=studies[primary],
                model_id=models[primary],
                secondary_model_id=models[1 - primary],
                candidates=[{"candidate_id": candidate_id, "cost_cents": 50}],
            ),
        )
        return decision.id


def test_secondary_model_retirement_serializes_with_proposal(pair):
    started = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        with SessionFactory.begin() as session:
            project = session.get(Project, pair[2])
            service.require_record(session, LearningStudy, project, pair[4][1], lock=True)
            model = service.require_record(session, LearningModel, project, pair[5][1], lock=True)
            model.status = "retired"
            model.version += 1
            session.flush()
            future = executor.submit(propose, pair, 0, started)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.3)
        with pytest.raises(DomainError) as failure:
            future.result(timeout=10)
        assert failure.value.error_code == "learning_secondary_model"


def test_opposite_dual_assay_requests_do_not_deadlock(pair):
    barrier = threading.Barrier(2, timeout=10)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(propose, pair, primary, None, barrier) for primary in (0, 1)]
        assert len({future.result(timeout=10) for future in futures}) == 2
