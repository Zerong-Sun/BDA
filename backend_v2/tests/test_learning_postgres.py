"""PostgreSQL serialization for competing model promotions (isolated test DB)."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from backend_v2.app.core.database import SessionFactory
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.learning import engine, service
from backend_v2.app.learning.models import LearningAssay, LearningDataset, LearningModel, LearningStudy
from backend_v2.app.learning.schemas import ModelReview
from backend_v2.app.projects.models import Project
from backend_v2.app.research.models import ResearchGoal
from sqlalchemy import select

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration test disabled")


def test_competing_promotions_leave_one_current_model() -> None:
    token = uuid.uuid4().hex
    with SessionFactory.begin() as session:
        user = User(username=f"learning-{token}", display_name="Concurrency test", role="admin", enabled=True)
        org = Organization(name=f"learning-{token}")
        session.add_all([user, org])
        session.flush()
        project = Project(
            organization_id=org.id, owner_id=user.id, name="Synthetic learning", project_type="protein_design"
        )
        session.add(project)
        session.flush()
        goal = ResearchGoal(project_id=project.id, title="Synthetic goal", detail="Test only", created_by=user.id)
        assay = LearningAssay(
            project_id=project.id, name="Synthetic", method="Synthetic", unit="nM", conditions={}, created_by=user.id
        )
        session.add_all([goal, assay])
        session.flush()
        study = LearningStudy(
            project_id=project.id,
            assay_id=assay.id,
            research_goal_id=goal.id,
            name="Test study",
            goal_snapshot={},
            direction="maximize",
            currency="USD",
            batch_budget_cents=100,
            max_batch_size=1,
            created_by=user.id,
        )
        session.add(study)
        session.flush()
        dataset = LearningDataset(
            project_id=project.id, study_id=study.id, digest=engine.digest({}), manifest={}, created_by=user.id
        )
        session.add(dataset)
        session.flush()
        models = [
            LearningModel(
                project_id=project.id,
                study_id=study.id,
                dataset_id=dataset.id,
                algorithm="synthetic-concurrency-fixture",
                parameters={},
                evaluation={"model_digest": engine.digest({}), "eligible_for_promotion": True},
                created_by=user.id,
            )
            for _ in range(2)
        ]
        session.add_all(models)
        session.flush()
        user_id, org_id, project_id, study_id = user.id, org.id, project.id, study.id
        model_ids = [m.id for m in models]
    barrier = threading.Barrier(2, timeout=10)

    def promote(model_id):
        with SessionFactory.begin() as session:
            user = session.get(User, user_id)
            project = session.get(Project, project_id)
            barrier.wait()
            service.review_model(
                session,
                project,
                user,
                model_id,
                ModelReview(action="promote", rationale="Synthetic concurrent test"),
                1,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(promote, model_ids))
        with SessionFactory() as session:
            statuses = list(session.scalars(select(LearningModel.status).where(LearningModel.study_id == study_id)))
            assert sorted(statuses) == ["promoted", "retired"]
    finally:
        # Remove only rows owned by this test, after threads have released locks.
        with SessionFactory.begin() as session:
            from backend_v2.app.audit.models import AuditLog
            from sqlalchemy import delete

            session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
            session.execute(delete(Project).where(Project.id == project_id))
            session.execute(delete(Organization).where(Organization.id == org_id))
            session.execute(delete(User).where(User.id == user_id))
