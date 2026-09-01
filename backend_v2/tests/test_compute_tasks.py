from __future__ import annotations

import hashlib
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact, ArtifactUpload
from backend_v2.app.campaigns import tasks as campaigns_tasks
from backend_v2.app.campaigns.models import Campaign, CampaignRound
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.compute import tasks
from backend_v2.app.compute.adapters import AdapterStatus
from backend_v2.app.compute.models import ComputeDraft, Job, JobSubmission, OutboxEvent
from backend_v2.app.copilot import tasks as copilot_tasks
from backend_v2.app.copilot.models import CopilotConversation, CopilotMessage
from backend_v2.app.core import celery_app as celery_app_module
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.delivery import tasks as delivery_tasks
from backend_v2.app.delivery.models import DeliveryPackage
from backend_v2.app.experiments import tasks as experiments_tasks
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.intelligence import tasks as intelligence_tasks
from backend_v2.app.intelligence.models import IntelligenceRun
from backend_v2.app.knowledge.models import KnowledgeEntry
from backend_v2.app.ligands import tasks as ligands_tasks
from backend_v2.app.ligands.models import LigandImport
from backend_v2.app.literature import tasks as literature_tasks
from backend_v2.app.literature.models import (
    LiteratureChunk,
    LiteratureClaim,
    LiteratureDocument,
    LiteratureEvidence,
    LiteratureRetrievalTrace,
    LiteratureSearchRun,
    LiteratureSubscription,
)
from backend_v2.app.projects.models import Project
from backend_v2.app.registry import tasks as registry_tasks
from backend_v2.app.registry.models import ComputeNode, ModelPlugin, RegistryServer
from backend_v2.app.research import tasks as research_tasks
from backend_v2.app.research.generation import import_research_generation
from backend_v2.app.research.models import ResearchBrief, ResearchFinding, ResearchGeneration
from backend_v2.app.research.workspace import build_research_workspace
from backend_v2.app.targets import tasks as targets_tasks
from backend_v2.app.targets.models import Target, TargetStructureRevision
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class FakeStorage:
    objects: dict[str, bytes] = {}
    removed: list[str] = []

    def put_json(self, key: str, payload: dict) -> None:
        self.objects[key] = b"json"

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def inspect_and_hash(self, key: str) -> tuple[int, str]:
        data = self.objects[key]
        return len(data), hashlib.sha256(data).hexdigest()

    def read_bytes(self, key: str, *, max_bytes: int) -> bytes:
        return self.objects[key][:max_bytes]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def remove(self, key: str) -> None:
        self.objects.pop(key, None)
        self.removed.append(key)

    def copy(self, source_key: str, target_key: str) -> None:
        self.objects[target_key] = self.objects[source_key]

    def list_objects(self):
        old = datetime.now(UTC) - timedelta(hours=2)
        return [SimpleNamespace(object_name=key, last_modified=old) for key in list(self.objects)]


# core.celery_app owns the task_failure handler, and it binds session_scope itself.
TASK_MODULES = (
    tasks,
    celery_app_module,
    campaigns_tasks,
    copilot_tasks,
    delivery_tasks,
    experiments_tasks,
    intelligence_tasks,
    ligands_tasks,
    literature_tasks,
    registry_tasks,
    research_tasks,
    targets_tasks,
)


class FakeAdapter:
    live_status = AdapterStatus("running")
    outputs: list[dict] = []

    def ensure_submitted(self, runtime) -> str:
        return f"external-{runtime.id}"

    def status(self, runtime, external_id: str) -> AdapterStatus:
        return self.live_status

    def cancel(self, external_id: str) -> bool:
        return True

    def collect(self, runtime, external_id: str) -> list[dict]:
        return self.outputs


def test_scientific_review_is_required_for_long_answers_with_only_project_metadata() -> None:
    assert copilot_tasks._needs_scientific_review({"project"}, "x" * 800)
    assert not copilot_tasks._needs_scientific_review({"project", "reference"}, "x" * 800)
    assert not copilot_tasks._needs_scientific_review({"project"}, "x" * 799)


@pytest.fixture
def task_database(monkeypatch) -> Generator[tuple[sessionmaker, dict[str, uuid.UUID]]]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    @contextmanager
    def scope():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    # Each domain's tasks module binds these names itself, so every module that owns a
    # task under test has to be redirected - patching only compute would leave the moved
    # tasks talking to the real database and object store.
    for module in TASK_MODULES:
        for name, replacement in (
            ("SessionFactory", factory),
            ("session_scope", scope),
            ("ObjectStorage", FakeStorage),
            ("adapter_for", lambda backend: FakeAdapter()),
        ):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, replacement)
    FakeStorage.objects = {}
    FakeStorage.removed = []
    FakeAdapter.live_status = AdapterStatus("running")
    FakeAdapter.outputs = []
    with factory() as session:
        user = User(username="tasks", display_name="Tasks", role="admin", enabled=True)
        org = Organization(name="Task org")
        session.add_all([user, org])
        session.flush()
        project = Project(organization_id=org.id, owner_id=user.id, name="Task project", project_type="design")
        session.add(project)
        session.flush()
        target = Target(project_id=project.id, name="Target", structure_status="missing")
        workflow = WorkflowRun(
            project_id=project.id, name="Task workflow", status="queued", graph={}, created_by=user.id
        )
        session.add_all([target, workflow])
        session.flush()
        node = WorkflowNode(
            workflow_run_id=workflow.id,
            node_key="node",
            node_type="model",
            model_plugin="demo",
            status="draft",
            parameters={},
        )
        submission = JobSubmission(
            workflow_run_id=workflow.id,
            project_id=project.id,
            created_by=user.id,
            status="pending",
            compute_backend="demo",
        )
        session.add_all([node, submission])
        session.flush()
        job = Job(
            submission_id=submission.id,
            workflow_run_id=workflow.id,
            workflow_node_id=node.id,
            project_id=project.id,
            compute_backend="demo",
            model_plugin="demo",
            timeout_at=datetime.now(UTC) + timedelta(hours=1),
            runtime_spec={
                "input_manifest": {"schema_version": "1", "inputs": []},
                "input_manifest_key": f"jobs/{uuid.uuid4()}/input.json",
                "output_manifest_key": f"jobs/{uuid.uuid4()}/output.json",
            },
        )
        session.add(job)
        session.commit()
        ids = {
            "user": user.id,
            "project": project.id,
            "target": target.id,
            "workflow": workflow.id,
            "submission": submission.id,
            "job": job.id,
        }
    yield factory, ids
    drop_all(engine, Base.metadata)
    engine.dispose()


def test_unknown_topic_backs_off_and_dead_letters_instead_of_blocking_the_queue(
    task_database, monkeypatch
) -> None:
    """A worker that predates a topic must not starve every event behind it.

    The unknown-topic branch used to set neither published_at nor available_at, so the
    row was re-selected every tick forever; batch_size of them stopped all delivery. This
    is what a rolling deploy or a rollback produces.
    """
    factory, ids = task_database
    with factory() as session:
        session.add(OutboxEvent(topic="topic.from.a.newer.release", aggregate_id=ids["job"], payload={}))
        session.add(OutboxEvent(topic="job.dispatch", aggregate_id=ids["job"], payload={"job_id": str(ids["job"])}))
        session.commit()

    sent: list[str] = []
    monkeypatch.setattr(tasks.celery_app, "send_task", lambda name, **kwargs: sent.append(name))

    # The known event is delivered even though the unknown one sorts ahead of nothing in
    # particular; the point is that the unknown one yields its slot afterwards.
    assert tasks.publish_outbox.run()["published"] == 1
    assert sent == ["bda_v2.dispatch_job"]

    with factory() as session:
        stuck = session.scalar(
            select(OutboxEvent).where(OutboxEvent.topic == "topic.from.a.newer.release")
        )
        assert stuck is not None
        assert stuck.attempts == 1
        assert stuck.last_error == "unknown_topic:topic.from.a.newer.release"
        assert tasks._as_utc(stuck.available_at) > datetime.now(UTC), "must not be immediately re-selectable"
        assert stuck.dead_lettered_at is None
        stuck_id = stuck.id

    for _ in range(tasks.MAX_OUTBOX_ATTEMPTS):
        with factory() as session:
            event = session.get(OutboxEvent, stuck_id)
            assert event is not None
            if event.dead_lettered_at is not None:
                break
            event.available_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
        tasks.publish_outbox.run()

    with factory() as session:
        event = session.get(OutboxEvent, stuck_id)
        assert event is not None
        assert event.dead_lettered_at is not None
        assert event.attempts == tasks.MAX_OUTBOX_ATTEMPTS

    # Dead events leave the backlog so the gauge keeps describing live work, and show up
    # under their own gauge so they stay alertable.
    result = tasks.publish_outbox.run()
    assert result["backlog"] == 0
    assert result["dead_lettered"] == 1


def test_send_failures_also_stop_at_the_attempt_ceiling(task_database, monkeypatch) -> None:
    factory, ids = task_database
    with factory() as session:
        session.add(OutboxEvent(topic="job.dispatch", aggregate_id=ids["job"], payload={"job_id": str(ids["job"])}))
        session.commit()

    def explode(name, **kwargs):
        raise RuntimeError("broker unreachable")

    monkeypatch.setattr(tasks.celery_app, "send_task", explode)

    for _ in range(tasks.MAX_OUTBOX_ATTEMPTS):
        with factory() as session:
            event = session.scalar(select(OutboxEvent))
            assert event is not None
            if event.dead_lettered_at is not None:
                break
            event.available_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
        tasks.publish_outbox.run()

    with factory() as session:
        event = session.scalar(select(OutboxEvent))
        assert event is not None
        assert event.dead_lettered_at is not None
        assert "broker unreachable" in (event.last_error or "")


def test_outbox_dispatch_poll_collect_cancel(task_database, monkeypatch) -> None:
    factory, ids = task_database
    assert tasks._runtime(factory().get(Job, ids["job"])).id == ids["job"]
    with factory() as session:
        session.add(OutboxEvent(topic="job.dispatch", aggregate_id=ids["job"], payload={"job_id": str(ids["job"])}))
        session.commit()
    sent: list[str] = []
    monkeypatch.setattr(tasks.celery_app, "send_task", lambda name, **kwargs: sent.append(name))
    assert tasks.publish_outbox.run()["published"] == 1
    assert sent == ["bda_v2.dispatch_job"]

    dispatched = tasks.dispatch_job.run(str(ids["job"]))
    assert dispatched["status"] == "queued"
    with factory() as session:
        job = session.get(Job, ids["job"])
        assert job.external_id and job.status == "queued"
        job.next_poll_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert tasks.poll_due_jobs.run()["queued"] == 1
    assert tasks.poll_job.run(str(ids["job"]))["status"] == "running"
    FakeAdapter.live_status = AdapterStatus("succeeded")
    assert tasks.poll_job.run(str(ids["job"]))["status"] == "collecting"

    output_key = f"jobs/{ids['job']}/attempt-1/outputs/result.txt"
    FakeStorage.objects[output_key] = b"result"
    FakeAdapter.outputs = [
        {
            "object_key": output_key,
            "size_bytes": 6,
            "checksum_sha256": hashlib.sha256(b"result").hexdigest(),
            "artifact_type": "compute_output",
            "filename": "result.txt",
            "content_type": "text/plain",
            "metadata": {},
        }
    ]
    assert tasks.collect_job.run(str(ids["job"]))["status"] == "succeeded"
    assert tasks.cancel_job.run(str(ids["job"]))["status"] == "ignored"


def test_outbox_dispatch_carries_project_rls_header(task_database, monkeypatch) -> None:
    factory, ids = task_database
    with factory() as session:
        session.add(
            OutboxEvent(
                topic="job.dispatch",
                aggregate_id=ids["job"],
                payload={"job_id": str(ids["job"]), "project_id": str(ids["project"])},
            )
        )
        session.commit()

    sent: list[dict] = []
    monkeypatch.setattr(
        tasks.celery_app,
        "send_task",
        lambda _name, **kwargs: sent.append(kwargs),
    )

    assert tasks.publish_outbox.run()["published"] == 1
    assert sent[0]["headers"] == {"bda_project_id": str(ids["project"])}


def test_outbox_recovers_legacy_job_project_context(task_database, monkeypatch) -> None:
    factory, ids = task_database
    with factory() as session:
        session.add(
            OutboxEvent(
                topic="job.dispatch",
                aggregate_id=ids["job"],
                payload={"job_id": str(ids["job"])},
            )
        )
        session.commit()

    sent: list[dict] = []
    monkeypatch.setattr(tasks.celery_app, "send_task", lambda _name, **kwargs: sent.append(kwargs))

    assert tasks.publish_outbox.run()["published"] == 1
    assert sent[0]["headers"] == {"bda_project_id": str(ids["project"])}


def test_project_outbox_fails_closed_without_project_context(task_database, monkeypatch) -> None:
    factory, _ids = task_database
    missing_id = uuid.uuid4()
    with factory() as session:
        session.add(OutboxEvent(topic="job.dispatch", aggregate_id=missing_id, payload={}))
        session.commit()

    sent: list[dict] = []
    monkeypatch.setattr(tasks.celery_app, "send_task", lambda _name, **kwargs: sent.append(kwargs))
    result = tasks.publish_outbox.run()

    assert result["published"] == 0
    assert sent == []
    with factory() as session:
        event = session.scalar(select(OutboxEvent).where(OutboxEvent.aggregate_id == missing_id))
        assert event is not None
        assert event.last_error == "missing_project_context"


def test_cross_project_beat_tasks_are_isolated_on_scheduler_queue() -> None:
    schedule = celery_app_module.celery_app.conf.beat_schedule
    for item in schedule.values():
        assert item["options"]["queue"] == "scheduler"


def test_celery_hooks_bind_and_reset_project_context(monkeypatch) -> None:
    marker: ContextVar[str | None] = ContextVar("test_worker_project", default=None)
    bound: list[object | None] = []

    def bind(project_id):
        bound.append(project_id)
        return marker.set(str(project_id) if project_id else None)

    def reset(token):
        marker.reset(token)

    monkeypatch.setattr("backend_v2.app.core.database.bind_worker_project_context", bind)
    monkeypatch.setattr("backend_v2.app.core.database.reset_worker_project_context", reset)
    task_id = str(uuid.uuid4())
    sender = SimpleNamespace(
        request=SimpleNamespace(headers={"bda_project_id": "project-from-message"})
    )

    celery_app_module._bind_operation_project(sender=sender, task_id=task_id)
    assert bound == ["project-from-message"]
    assert marker.get() == "project-from-message"

    celery_app_module._reset_operation_project(task_id=task_id)
    assert marker.get() is None


def test_poll_failure_timeout_and_cancellation(task_database) -> None:
    factory, ids = task_database
    with factory() as session:
        job = session.get(Job, ids["job"])
        job.status = "queued"
        job.external_id = "external"
        job.next_poll_at = datetime.now(UTC)
        job.timeout_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert tasks.poll_job.run(str(ids["job"]))["status"] == "failed"
    with factory() as session:
        job = session.get(Job, ids["job"])
        job.status = "running"
        job.timeout_at = datetime.now(UTC) + timedelta(hours=1)
        session.commit()
    FakeAdapter.live_status = AdapterStatus("failed", "remote error")
    assert tasks.poll_job.run(str(ids["job"]))["status"] == "failed"
    with factory() as session:
        job = session.get(Job, ids["job"])
        job.status = "running"
        session.commit()
    assert tasks.cancel_job.run(str(ids["job"]))["status"] == "cancelled"


def test_poll_keeps_polling_when_the_backend_cannot_answer(task_database) -> None:
    """An 'unknown' status must not resolve the job.

    A scheduler that has forgotten a job it can no longer describe is not evidence of
    failure, so the job stays pollable and only its own deadline may end the wait.
    """
    factory, ids = task_database
    with factory() as session:
        job = session.get(Job, ids["job"])
        job.status = "running"
        job.external_id = "4039777"
        job.next_poll_at = datetime.now(UTC)
        job.timeout_at = datetime.now(UTC) + timedelta(hours=1)
        session.commit()
    FakeAdapter.live_status = AdapterStatus("unknown", "lsf_job_gone_without_remote_dir:4039777")
    assert tasks.poll_job.run(str(ids["job"]))["status"] == "running"
    with factory() as session:
        job = session.get(Job, ids["job"])
        assert job.status == "running" and job.error_code is None
        assert tasks._as_utc(job.next_poll_at) > datetime.now(UTC)


def test_domain_background_tasks(task_database, monkeypatch) -> None:
    factory, ids = task_database
    with factory() as session:
        package = DeliveryPackage(
            project_id=ids["project"], created_by=ids["user"], name="Delivery", selection={"all": True}
        )
        document = LiteratureDocument(project_id=ids["project"], title="Paper", source="doi", status="pending")
        run = IntelligenceRun(
            project_id=ids["project"],
            target_id=ids["target"],
            query={"topic": "binding"},
            created_by=ids["user"],
        )
        conversation = CopilotConversation(project_id=ids["project"], created_by=ids["user"])
        subscription = LiteratureSubscription(
            project_id=ids["project"],
            query="binding protein",
            cadence="weekly",
            created_by=ids["user"],
        )
        session.add_all([package, document, run, conversation, subscription])
        session.flush()
        message = CopilotMessage(conversation_id=conversation.id, role="user", content="help", status="pending")
        ligand = LigandImport(
            project_id=ids["project"],
            created_by=ids["user"],
            ligand_id="thc",
            source="pubchem",
        )
        draft = ComputeDraft(
            project_id=ids["project"],
            created_by=ids["user"],
            name="Draft",
            backend="demo",
            specification={"command": "true"},
            status="confirmed",
        )
        session.add_all([message, ligand, draft])
        session.commit()
        domain_ids = [package.id, document.id, run.id, message.id, ligand.id, draft.id, subscription.id]

    assert delivery_tasks.build_delivery_package.run(str(domain_ids[0]))["status"] == "available"
    assert delivery_tasks.build_delivery_package.run(str(domain_ids[0]))["status"] == "ignored"
    assert literature_tasks.literature_ingest.run(str(domain_ids[1]))["status"] == "available"
    monkeypatch.setattr(literature_tasks.literature_search, "run", lambda run_id: {"status": "completed", "result_count": 0})
    assert literature_tasks.subscription_run.run(str(domain_ids[6]))["status"] == "completed"
    assert intelligence_tasks.intelligence_run.run(str(domain_ids[2]))["status"] == "succeeded"
    assert intelligence_tasks.intelligence_export.run(str(domain_ids[2]))["status"] == "available"
    assert intelligence_tasks.intelligence_export.run(str(domain_ids[2]))["status"] == "available"
    assert copilot_tasks.copilot_respond.run(str(domain_ids[3]))["status"] == "completed"
    response = SimpleNamespace(
        content=b"ligand",
        headers={"content-type": "chemical/x-mdl-sdfile"},
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: response)
    assert ligands_tasks.ligand_import.run(str(domain_ids[4]))["status"] == "available"
    assert ligands_tasks.ligand_import.run(str(domain_ids[4]))["status"] == "ignored"
    draft_result = tasks.compute_draft_confirm.run(str(domain_ids[5]))
    assert draft_result["status"] == "accepted" and draft_result["job_id"]
    assert tasks.compute_draft_confirm.run(str(domain_ids[5]))["job_id"] == draft_result["job_id"]


def test_literature_search_preserves_search_full_text_and_evidence_trace(task_database, monkeypatch) -> None:
    factory, ids = task_database
    with factory() as session:
        run = LiteratureSearchRun(
            project_id=ids["project"],
            query='"flavor protein" AND aroma',
            sources=["europe_pmc"],
            requested_limit=3,
            fetch_full_text=True,
            extract_claims=True,
            created_by=ids["user"],
        )
        session.add(run)
        packaged_document = LiteratureDocument(
            project_id=ids["project"],
            title="Traceable flavor paper",
            source="research_package",
            external_id="R014",
            status="pending_review",
            metadata_json={
                "ref_id": "R014",
                "pmid": "123",
                "pmcid": "PMC123",
                "doi": "10.1000/trace",
            },
        )
        session.add(packaged_document)
        session.commit()
        run_id, packaged_document_id = run.id, packaged_document.id

    search_audit = {
        "tool": "europe_pmc.search",
        "query": {"url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search", "params": {}},
        "queried_at": datetime.now(UTC).isoformat(),
        "response_checksum_sha256": "a" * 64,
        "http_status": 200,
        "content_type": "application/json",
        "byte_count": 100,
        "attempts": 1,
        "status": "completed",
    }
    crossref_audit = {
        **search_audit,
        "tool": "crossref.work",
        "response_checksum_sha256": "b" * 64,
    }
    full_text_audit = {
        **search_audit,
        "tool": "europe_pmc.full_text_xml",
        "content_type": "application/xml",
        "response_checksum_sha256": "c" * 64,
    }
    xml = b"""<article><front><article-meta><title-group><article-title>Traceable flavor paper</article-title>
    </title-group><permissions><license><license-p>CC BY</license-p></license></permissions></article-meta></front>
    <body><sec><title>Results</title><p>The engineered enzyme reduced the measured aldehyde signal.</p>
    </sec></body></article>"""
    tools_closed = False

    class FakeEvidenceTools:
        def __init__(self, **_kwargs):
            self.audits = []

        def search_europe_pmc(self, query, page_size):
            self.audits.append(search_audit)
            return SimpleNamespace(
                audit=search_audit,
                data={"resultList": {"result": [{
                    "id": "123",
                    "source": "MED",
                    "pmid": "123",
                    "pmcid": "PMC123",
                    "doi": "10.1000/trace",
                    "title": "Traceable flavor paper",
                    "abstractText": "The abstract reports an enzyme result.",
                    "authorString": "A. Researcher",
                    "journalTitle": "Journal",
                    "pubYear": "2026",
                    "isOpenAccess": "Y",
                    "inEPMC": "Y",
                }]}},
            )

        def get_crossref(self, doi):
            self.audits.append(crossref_audit)
            return SimpleNamespace(audit=crossref_audit, data={"message": {"title": ["Traceable flavor paper"]}})

        def get_europe_pmc_full_text(self, pmcid):
            self.audits.append(full_text_audit)
            return SimpleNamespace(audit=full_text_audit, content=xml)

        def close(self):
            nonlocal tools_closed
            tools_closed = True

    monkeypatch.setattr(
        "backend_v2.app.research.evidence_tools.EvidenceToolService",
        FakeEvidenceTools,
    )
    result = literature_tasks.literature_search.run(str(run_id))
    assert result["status"] == "completed"
    assert tools_closed
    with factory() as session:
        run = session.get(LiteratureSearchRun, run_id)
        document = session.scalar(
            select(LiteratureDocument).where(LiteratureDocument.project_id == ids["project"])
        )
        assert run.status == "completed" and run.result_count == 1
        assert document is not None and document.status == "available"
        assert document.id == packaged_document_id
        assert document.external_id == "R014"
        assert document.metadata_json["ref_id"] == "R014"
        assert len(
            list(
                session.scalars(
                    select(LiteratureDocument).where(
                        LiteratureDocument.project_id == ids["project"]
                    )
                )
            )
        ) == 1
        provenance = document.metadata_json["content_provenance"]
        assert provenance["content_kind"] == "open_access_full_text"
        assert len(provenance["content_checksum_sha256"]) == 64
        assert provenance["retrieval_trace_id"]
        assert session.scalar(
            select(LiteratureChunk).where(LiteratureChunk.document_id == document.id)
        ).content.startswith("Results:")
        claim = session.scalar(select(LiteratureClaim).where(LiteratureClaim.document_id == document.id))
        evidence = session.scalar(select(LiteratureEvidence).where(LiteratureEvidence.claim_id == claim.id))
        assert evidence.source_ref["content_checksum_sha256"] == provenance["content_checksum_sha256"]
        stages = set(
            session.scalars(
                select(LiteratureRetrievalTrace.stage).where(
                    LiteratureRetrievalTrace.search_run_id == run_id
                )
            )
        )
        assert {"search", "search_hit", "metadata_verification", "full_text"} <= stages


def test_research_target_accession_resolves_exact_supported_alias(
    task_database,
    monkeypatch,
) -> None:
    factory, ids = task_database
    with factory() as session:
        candidate = Candidate(
            project_id=ids["project"],
            candidate_key="R03",
            name="PD-L2",
            candidate_kind="research_target",
            properties={},
        )
        session.add(candidate)
        session.commit()
        candidate_id = candidate.id

    class UniProtResponse:
        url = (
            "https://rest.uniprot.org/uniprotkb/search?"
            "query=gene_exact%3APDCD1LG2"
        )

        def json(self):
            return {"results": [{"primaryAccession": "Q9BQ51"}]}

        def raise_for_status(self):
            return None

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: UniProtResponse())
    with tasks.session_scope() as session:
        candidate = session.get(Candidate, candidate_id)
        assert research_tasks._research_target_accession(session, candidate) == "Q9BQ51"
    with factory() as session:
        properties = session.get(Candidate, candidate_id).properties
        assert properties["gene"] == "PDCD1LG2"
        assert properties["uniprot_accession"] == "Q9BQ51"
        assert properties["identity_resolution"]["status"] == "verified_uniprot_rest"


def test_research_gap_resolution_imports_structure_and_reference_content(
    task_database,
    monkeypatch,
) -> None:
    factory, ids = task_database
    with factory() as session:
        candidate = Candidate(
            project_id=ids["project"],
            candidate_key="C10",
            name="GPR65/TDAG8",
            candidate_kind="research_target",
            properties={"gene": "GPR65", "reference_ids": ["R014"]},
        )
        identifiers = KnowledgeEntry(
            project_id=ids["project"],
            title="Identifiers",
            content="",
            entry_type="dataset",
            source={
                "entry_key": "identifiers",
                "data": [{
                    "gene": "GPR65",
                    "uniprot_accession": "Q8IYL9",
                }],
            },
            created_by=ids["user"],
        )
        document = LiteratureDocument(
            project_id=ids["project"],
            title="GPR65 paper",
            source="research_package",
            external_id="R014",
            status="pending_review",
            metadata_json={
                "ref_id": "R014",
                "pmid": "39661058",
                "pmcid": "PMC11665855",
                "doi": "10.1073/pnas.2410653121",
            },
        )
        session.add_all([candidate, identifiers, document])
        session.commit()
        candidate_id, document_id = candidate.id, document.id

    pdb = b"ATOM      1  CA  GLY A   1      0.000   0.000   0.000\n"

    class AlphaFoldResponse:
        def __init__(self, *, payload=None, content=b""):
            self._payload = payload
            self.content = content

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    def alphafold_get(url, **_kwargs):
        if "/api/prediction/" in url:
            return AlphaFoldResponse(payload=[{
                "uniprotAccession": "Q8IYL9",
                "isComplex": False,
                "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-Q8IYL9-F1-model_v6.pdb",
                "entryId": "AF-Q8IYL9-F1",
                "modelEntityId": "AF-Q8IYL9-F1",
                "latestVersion": 6,
                "globalMetricValue": 82.62,
            }])
        return AlphaFoldResponse(content=pdb)

    def fake_literature_search(run_id):
        with tasks.session_scope() as session:
            run = session.get(LiteratureSearchRun, uuid.UUID(run_id))
            saved = session.get(LiteratureDocument, document_id)
            saved.metadata_json = {
                **saved.metadata_json,
                "content_provenance": {
                    "content_kind": "open_access_full_text",
                    "retrieval_trace_id": str(uuid.uuid4()),
                },
            }
            saved.status = "available"
            session.add(LiteratureChunk(document_id=saved.id, position=0, content="Full text"))
            run.status = "completed"
        return {"status": "completed", "result_count": 1}

    monkeypatch.setattr("httpx.get", alphafold_get)
    monkeypatch.setattr(literature_tasks.literature_search, "run", fake_literature_search)
    result = research_tasks.research_gaps_resolve.run(
        str(candidate_id),
        {"resolve_references": True, "resolve_structure": True},
    )
    assert result["status"] == "completed_with_remaining_scientific_gaps"
    assert result["resolved_count"] == 2
    with factory() as session:
        candidate = session.get(Candidate, candidate_id)
        artifact = session.get(Artifact, candidate.structure_artifact_id)
        assert artifact.lineage["source"] == "alphafold_db"
        assert artifact.lineage["uniprot_accession"] == "Q8IYL9"
        assert session.scalar(
            select(LiteratureChunk).where(LiteratureChunk.document_id == document_id)
        )
        resolution = candidate.properties["gap_resolution"]
        assert resolution["resolved_count"] == 2
        assert resolution["items"][-1]["status"] == "requires_experiment"


def test_gap_resolution_marks_ambiguous_structure_identity_for_review(
    task_database,
) -> None:
    factory, ids = task_database
    with factory() as session:
        candidate = Candidate(
            project_id=ids["project"],
            candidate_key="R-axis",
            name="IL-33–ST2 axis",
            candidate_kind="research_target",
            properties={},
        )
        session.add(candidate)
        session.commit()
        candidate_id = candidate.id

    result = research_tasks.research_gaps_resolve.run(
        str(candidate_id),
        {
            "resolve_references": False,
            "resolve_structure": True,
        },
    )

    assert result["status"] == "completed_with_remaining_scientific_gaps"
    assert result["failed_count"] == 0
    assert result["items"][0]["status"] == "requires_review"


def test_stale_gap_operation_does_not_overwrite_newer_status(
    task_database,
) -> None:
    factory, ids = task_database
    newest_operation_id = str(uuid.uuid4())
    stale_operation_id = str(uuid.uuid4())
    with factory() as session:
        candidate = Candidate(
            project_id=ids["project"],
            candidate_key="R-stale",
            name="Concurrent target",
            candidate_kind="research_target",
            properties={
                "gap_resolution": {
                    "operation_id": newest_operation_id,
                    "status": "pending",
                }
            },
        )
        session.add(candidate)
        session.commit()
        candidate_id = candidate.id

    result = research_tasks.research_gaps_resolve.run(
        str(candidate_id),
        {
            "operation_id": stale_operation_id,
            "resolve_references": False,
            "resolve_structure": False,
        },
    )

    assert result["operation_id"] == stale_operation_id
    with factory() as session:
        resolution = session.get(Candidate, candidate_id).properties["gap_resolution"]
        assert resolution == {
            "operation_id": newest_operation_id,
            "status": "pending",
        }


def test_copilot_task_failure_marks_pending_source_message_failed(
    task_database,
) -> None:
    factory, ids = task_database
    with factory() as session:
        conversation = CopilotConversation(
            project_id=ids["project"],
            created_by=ids["user"],
        )
        session.add(conversation)
        session.flush()
        message = CopilotMessage(
            conversation_id=conversation.id,
            role="user",
            content="provider failure",
            status="pending",
        )
        session.add(message)
        session.commit()
        message_id = message.id

    celery_app_module._operation_failed(
        sender=SimpleNamespace(name="bda_v2.copilot_respond"),
        task_id=str(uuid.uuid4()),
        exception=RuntimeError("provider unavailable"),
        args=(str(message_id),),
    )

    with factory() as session:
        message = session.get(CopilotMessage, message_id)
        assert message.status == "failed"
        assert "provider unavailable" in message.error


def test_reconciliation_and_purge(task_database) -> None:
    factory, ids = task_database
    expired_key, failed_key = "staging/expired", "staging/failed"
    active_key, missing_key, orphan_key = "staging/active", "objects/missing", "objects/orphan"
    FakeStorage.objects[expired_key] = b"expired"
    FakeStorage.objects[failed_key] = b"failed"
    FakeStorage.objects[active_key] = b"active"
    FakeStorage.objects[orphan_key] = b"orphan"
    with factory() as session:
        session.add_all(
            [
                ArtifactUpload(
                    project_id=ids["project"],
                    created_by=ids["user"],
                    filename="expired",
                    artifact_type="data",
                    content_type="text/plain",
                    object_key=expired_key,
                    expires_at=datetime.now(UTC) - timedelta(hours=1),
                ),
                ArtifactUpload(
                    project_id=ids["project"],
                    created_by=ids["user"],
                    filename="failed",
                    artifact_type="data",
                    content_type="text/plain",
                    object_key=failed_key,
                    status="failed",
                    expires_at=datetime.now(UTC) - timedelta(hours=1),
                ),
                ArtifactUpload(
                    project_id=ids["project"],
                    created_by=ids["user"],
                    filename="active",
                    artifact_type="data",
                    content_type="text/plain",
                    object_key=active_key,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                ),
            ]
        )
        session.add(
            Artifact(
                project_id=ids["project"],
                created_by=ids["user"],
                artifact_type="data",
                filename="missing",
                content_type="text/plain",
                object_key=missing_key,
                size_bytes=1,
                checksum_sha256="a" * 64,
            )
        )
        session.commit()
    result = tasks.reconcile_artifacts.run()
    assert result == {"expired_uploads": 1, "missing_objects": 1, "orphaned_objects": 2}
    assert active_key in FakeStorage.objects
    assert failed_key not in FakeStorage.objects

    with factory() as session:
        project = session.get(Project, ids["project"])
        project.deleted_at = datetime.now(UTC) - timedelta(days=31)
        session.commit()
    assert tasks.purge_deleted_projects.run()["purged_projects"] == 1


def test_experiment_parsers_and_import_task(task_database) -> None:
    factory, ids = task_database
    assert experiments_tasks._experiment_rows("results.json", "application/json", b'[{"experiment_type":"binding"}]')
    assert experiments_tasks._experiment_rows("results.csv", "text/csv", b"experiment_type,value\nbinding,1.5\n")
    with pytest.raises(ValueError, match="result_objects"):
        experiments_tasks._experiment_rows("results.json", "application/json", b'{"results":"invalid"}')
    with pytest.raises(ValueError, match="unsupported"):
        experiments_tasks._experiment_rows("results.txt", "text/plain", b"x")

    data = b"candidate_ref,experiment_type,pass_status,value,unit\nc-1,binding,pass,2.5,nM\n"
    key = "projects/results.csv"
    FakeStorage.objects[key] = data
    with factory() as session:
        artifact = Artifact(
            project_id=ids["project"],
            created_by=ids["user"],
            artifact_type="experiment_import",
            filename="results.csv",
            content_type="text/csv",
            object_key=key,
            size_bytes=len(data),
            checksum_sha256=hashlib.sha256(data).hexdigest(),
        )
        session.add(artifact)
        session.commit()
        artifact_id = artifact.id
    assert experiments_tasks.experiment_results_import.run(str(artifact_id))["imported"] == 1
    with factory() as session:
        imported = session.scalar(
            select(ExperimentResult).where(ExperimentResult.project_id == ids["project"])
        )
        assert imported is not None and imported.source_artifact_id == artifact_id
    assert experiments_tasks.experiment_results_import.run(str(artifact_id))["imported"] == 0
    assert experiments_tasks.experiment_results_import.run(str(uuid.uuid4()))["status"] == "missing"


def test_collect_failure_transitions_job_to_failed_after_retries(task_database, monkeypatch) -> None:
    factory, ids = task_database

    class FailingAdapter(FakeAdapter):
        def collect(self, runtime, external_id: str) -> list[dict]:
            raise RuntimeError("output manifest unavailable")

    with factory() as session:
        job = session.get(Job, ids["job"])
        assert job is not None
        job.status = "collecting"
        job.external_id = "failed-output"
        session.commit()
    monkeypatch.setattr(tasks, "adapter_for", lambda backend: FailingAdapter())
    monkeypatch.setattr(tasks.collect_job, "max_retries", 0)
    with pytest.raises(RuntimeError, match="output manifest unavailable"):
        tasks.collect_job.run(str(ids["job"]))
    with factory() as session:
        job = session.get(Job, ids["job"])
        assert job is not None
        assert job.status == "failed"
        assert job.error_code == "collect_failed"
        assert "output manifest unavailable" in (job.error_message or "")


def test_target_structure_import_and_prepare(task_database, monkeypatch) -> None:
    factory, ids = task_database
    body = (
        b"ATOM      1  CA  GLY A   1      0.000   0.000   0.000\n"
        b"HETATM    2  O   HOH A   2      0.000   0.000   0.000\n"
    )
    key = "projects/source.pdb"
    FakeStorage.objects[key] = body
    with factory() as session:
        artifact = Artifact(
            project_id=ids["project"],
            created_by=ids["user"],
            artifact_type="target_structure",
            filename="source.pdb",
            content_type="chemical/x-pdb",
            object_key=key,
            size_bytes=len(body),
            checksum_sha256=hashlib.sha256(body).hexdigest(),
        )
        session.add(artifact)
        session.flush()
        revision = TargetStructureRevision(
            target_id=ids["target"],
            source_artifact_id=artifact.id,
            options={"remove_waters": True, "selected_chains": ["A"]},
            created_by=ids["user"],
        )
        session.add(revision)
        session.commit()
        artifact_id, revision_id = artifact.id, revision.id
    imported = targets_tasks.target_structure_import.run(
        str(ids["target"]), {"source": "artifact", "artifact_id": str(artifact_id)}
    )
    assert imported["status"] == "available"
    response = SimpleNamespace(content=body, raise_for_status=lambda: None)
    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: response)
    secondary = targets_tasks.target_structure_import.run(
        str(ids["target"]),
        {
            "source": "pdb",
            "pdb_id": "1ABC",
            "attach_to_target": False,
            "metadata": {"role": "secondary evidence structure"},
        },
    )
    assert secondary["attached"] is False
    with factory() as session:
        target = session.get(Target, ids["target"])
        secondary_artifact = session.get(Artifact, uuid.UUID(secondary["artifact_id"]))
        assert target.structure_artifact_id == artifact_id
        assert secondary_artifact.lineage["pdb_id"] == "1ABC"
        assert secondary_artifact.lineage["role"] == "secondary evidence structure"
    prepared = targets_tasks.target_structure_prepare.run(str(revision_id))
    assert prepared["status"] == "available"
    assert targets_tasks.target_structure_prepare.run(str(revision_id))["status"] == "available"
    assert targets_tasks.target_structure_import.run(str(uuid.uuid4()), {"source": "artifact"})["status"] == "missing"


def test_campaign_literature_and_registry_workers(task_database) -> None:
    factory, ids = task_database
    with factory() as session:
        campaign = Campaign(project_id=ids["project"], name="Loop", created_by=ids["user"])
        session.add(campaign)
        session.flush()
        round_ = CampaignRound(campaign_id=campaign.id, round_number=1, workflow_run_id=ids["workflow"])
        document = LiteratureDocument(
            project_id=ids["project"],
            title="Evidence",
            source="manual",
            abstract="Binding proteins improve stability.\n\nBinding proteins improve selectivity.",
        )
        valid_plugin = ModelPlugin(
            plugin_key="valid",
            plugin_version="1",
            name="Valid",
            container_image="registry/model:1",
            command="run",
            parameter_schema={},
            output_schema={},
        )
        invalid_plugin = ModelPlugin(
            plugin_key="invalid",
            plugin_version="1",
            name="Invalid",
            container_image="untagged",
            command=" ",
            parameter_schema={},
            output_schema={},
        )
        server = RegistryServer(name="registry", server_type="oci", endpoint="https://registry.example")
        node = ComputeNode(name="lsf-node", backend="lsf", enabled=True)
        session.add_all([round_, document, valid_plugin, invalid_plugin, server, node])
        session.commit()
        object_ids = (round_.id, document.id, valid_plugin.id, invalid_plugin.id, server.id, node.id)

    assert campaigns_tasks.campaign_evaluate.run(str(object_ids[0]))["status"] == "review"
    assert campaigns_tasks.campaign_evaluate.run(str(uuid.uuid4()))["status"] == "missing"
    assert literature_tasks.literature_ingest.run(str(object_ids[1]))["status"] == "available"
    relation_result = literature_tasks.literature_relations_detect.run(str(ids["project"]))
    assert relation_result["status"] == "completed" and relation_result["created"] == 1
    assert registry_tasks.registry_model_plugin_validate.run(str(object_ids[2]))["status"] == "valid"
    assert registry_tasks.registry_model_plugin_validate.run(str(object_ids[3]))["status"] == "invalid"
    assert registry_tasks.registry_model_plugin_validate.run(str(uuid.uuid4()))["status"] == "missing"
    assert registry_tasks.registry_compute_node_health.run(str(object_ids[5]))["status"] == "configured"
    assert registry_tasks.registry_compute_node_health.run(str(uuid.uuid4()))["status"] == "missing"
    assert registry_tasks.registry_server_test.run(str(object_ids[4]))["status"] == "configured"
    assert registry_tasks.registry_server_test.run(str(uuid.uuid4()))["status"] == "missing"


def test_research_generation_v2_round_trip_preserves_workspace_categories(
    task_database,
    monkeypatch,
) -> None:
    factory, ids = task_database
    monkeypatch.setattr("backend_v2.app.research.generation.ObjectStorage", FakeStorage)
    structure_body = b"data_source_generated\n_entry.id TEST\n"
    structure_key = "projects/source/structure.cif"
    structure_checksum = hashlib.sha256(structure_body).hexdigest()
    FakeStorage.objects[structure_key] = structure_body
    with factory() as session:
        project = session.get(Project, ids["project"])
        project.primary_target_id = ids["target"]
        brief = ResearchBrief(
            project_id=project.id,
            title="Evidence review",
            content="Reviewed source evidence.",
            created_by=ids["user"],
        )
        session.add(brief)
        session.flush()
        session.add_all([
            ResearchFinding(
                project_id=project.id,
                brief_id=brief.id,
                finding_type="mechanism",
                title="Supported mechanism",
                content="A project-scoped finding.",
                evidence={"reference_ids": ["PMID:123"], "review_status": "accepted"},
                created_by=ids["user"],
            ),
            LiteratureDocument(
                project_id=project.id,
                title="Verified evidence",
                source="pubmed",
                external_id="123",
                status="available",
                metadata_json={
                    "ref_id": "PMID:123",
                    "pmid": "123",
                    "verification_status": "verified",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
                },
            ),
            Candidate(
                project_id=project.id,
                candidate_key="target-a",
                name="Target A",
                candidate_kind="research_target",
                rank=1,
                score=0.9,
                properties={"reference_ids": ["PMID:123"], "review_status": "accepted"},
            ),
            KnowledgeEntry(
                project_id=project.id,
                title="Search method",
                content="Controlled literature query.",
                entry_type="search_method",
                source={"entry_key": "search_method"},
                created_by=ids["user"],
            ),
            KnowledgeEntry(
                project_id=project.id,
                title="Identifiers",
                content="Identifier table.",
                entry_type="identifiers",
                source={"entry_key": "identifiers", "data": [{"id": "PMID:123"}]},
                created_by=ids["user"],
            ),
            Artifact(
                project_id=project.id,
                created_by=ids["user"],
                artifact_type="target_structure",
                filename="1ABC.cif",
                content_type="chemical/x-mmcif",
                object_key=structure_key,
                status="available",
                size_bytes=len(structure_body),
                checksum_sha256=structure_checksum,
                lineage={
                    "pdb_id": "1ABC",
                    "name": "Reference complex",
                    "reference_id": "PMID:123",
                },
            ),
        ])
        generation = ResearchGeneration(
            source_project_id=project.id,
            organization_id=project.organization_id,
            created_by=ids["user"],
            request={
                "topic": "Round-trip research",
                "candidate_count": 10,
                "language": "en",
                "use_external_evidence": False,
            },
        )
        session.add(generation)
        session.commit()
        generation_id = generation.id

    completed = research_tasks.research_generate.run(str(generation_id))
    assert completed["status"] == "ready"
    assert completed["counts"] == {
        "review_sections": 1,
        "references": 1,
        "graph_nodes": 0,
        "graph_edges": 0,
        "structures": 1,
        "research_targets": 1,
        "methods": 1,
        "datasets": 4,
    }

    with factory() as session:
        generation = session.get(ResearchGeneration, generation_id)
        user = session.get(User, ids["user"])
        imported = import_research_generation(session, generation, generation.checksum, user)
        imported_project = session.get(Project, imported.project_id)
        workspace = build_research_workspace(session, imported_project)
        assert generation.status == "imported"
        assert len(workspace.review_sections) == 1
        assert len(workspace.references) == 1
        assert len(workspace.structures) == 1
        assert workspace.structures[0].status == "available"
        copied_structure = session.scalar(
            select(Artifact).where(
                Artifact.project_id == imported.project_id,
                Artifact.artifact_type == "target_structure",
            )
        )
        assert copied_structure.checksum_sha256 == structure_checksum
        assert FakeStorage.objects[copied_structure.object_key] == structure_body
        assert len(workspace.research_targets) == 1
        assert len(workspace.methods) == 1
        assert len(workspace.datasets) == 4


def test_research_generation_blocks_confirmation_when_required_categories_are_empty(task_database) -> None:
    factory, ids = task_database
    with factory() as session:
        project = session.get(Project, ids["project"])
        generation = ResearchGeneration(
            source_project_id=project.id,
            organization_id=project.organization_id,
            created_by=ids["user"],
            request={
                "topic": "Empty evidence project",
                "candidate_count": 10,
                "language": "en",
                "use_external_evidence": False,
            },
        )
        session.add(generation)
        session.commit()
        generation_id = generation.id

    completed = research_tasks.research_generate.run(str(generation_id))
    assert completed["status"] == "ready"

    with factory() as session:
        generation = session.get(ResearchGeneration, generation_id)
        user = session.get(User, ids["user"])
        assert generation.validation["valid"] is False
        assert generation.validation["required_missing_categories"] == [
            "references",
            "research_targets",
            "review_sections",
        ]
        with pytest.raises(DomainError, match="missing required categories"):
            import_research_generation(session, generation, generation.checksum, user)


def test_a_topic_with_several_subscribers_reaches_all_of_them(task_database, monkeypatch) -> None:
    """`job.settled` is read by campaigns and by copilot agent runs, and neither
    is the other's business.

    The task ids must differ, or the second send would be treated as a redelivery
    of the first; they are derived from the event id so redelivery of the *event*
    still deduplicates per subscriber.
    """
    factory, ids = task_database
    with factory() as session:
        session.add(
            OutboxEvent(
                topic="job.settled",
                aggregate_id=ids["job"],
                payload={"job_id": str(ids["job"]), "status": "failed"},
            )
        )
        session.commit()

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tasks.celery_app,
        "send_task",
        lambda name, **kwargs: sent.append((name, kwargs["task_id"])),
    )

    assert tasks.publish_outbox.run()["published"] == 1
    assert [name for name, _ in sent] == [
        "bda_v2.campaign_advance",
        "bda_v2.copilot_agent_task_settled",
    ]
    assert len({task_id for _, task_id in sent}) == 2
