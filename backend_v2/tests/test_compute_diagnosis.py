"""Each diagnosis rule, fired and — more importantly — kept silent.

A rule that fires on everything is worse than no rule: it attaches a confident
cause to every failure, and the first time it is wrong someone changes the wrong
thing. So every rule below is asserted twice, once against the evidence it
claims to read and once against a bundle that does not contain it.

The bundles are literals rather than database rows, which is what makes the
second assertion possible: a rule's silence can only be proved against evidence
you fully control.
"""

from __future__ import annotations

import hashlib
import itertools
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute import diagnosis
from backend_v2.app.compute.models import Job, JobAttempt, JobEvent, JobSubmission
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _bundle(**overrides: Any) -> dict[str, Any]:
    """A job that failed with nothing recognisable about it.

    Every rule must stay silent on this, which is the baseline the "fires only
    on its own evidence" assertions are written against.
    """
    base: dict[str, Any] = {
        "job_id": str(uuid.uuid4()),
        "status": "failed",
        "compute_backend": "lsf",
        "model_plugin": "demo",
        "attempt_number": 1,
        "external_id": "1234",
        "error_code": None,
        "error_message": "the model reported an unspecified problem",
        "queue": "normal",
        "image": "demo:1",
        "command": "run.sh",
        "plugin_snapshot": {"key": "demo", "version": "1", "resources": {}, "runtime_mode": "container"},
        "resolved_input_count": 2,
        "pending_inputs": [],
        "attempts": [{"attempt_number": 1, "status": "failed", "error": "unspecified", "duration_seconds": 900.0}],
        "recent_events": [],
    }
    base.update(overrides)
    return base


def _ids(evidence: dict[str, Any]) -> set[str]:
    return {finding["id"] for finding in diagnosis.findings_for(evidence)["findings"]}


# --- The baseline ------------------------------------------------------------


def test_unrecognised_evidence_yields_no_findings_and_says_so() -> None:
    result = diagnosis.findings_for(_bundle())

    assert result["findings"] == []
    assert "none of the known failure patterns" in result["summary"]


def test_every_rule_is_silent_on_the_baseline() -> None:
    """Stated as its own test because it is the property that keeps the rest honest."""
    for rule in diagnosis.RULES:
        assert rule.check(_bundle()) is None, rule.id


def test_rule_ids_are_unique() -> None:
    ids = [rule.id for rule in diagnosis.RULES]
    assert len(ids) == len(set(ids))


def test_every_finding_names_its_evidence_and_a_remedy() -> None:
    """A finding without either is an assertion, not a diagnosis."""
    evidence = _bundle(
        pending_inputs=["ligand"],
        command=None,
        external_id=None,
        status="failed",
        queue="2v100-32-e5",
        plugin_snapshot={"key": "d", "version": "1", "resources": {"cpus": 8}, "runtime_mode": "container"},
        error_message="TERM_MEMLIMIT: job killed after reaching LSF memory usage limit",
        attempts=[
            {"attempt_number": 1, "status": "failed", "error": "same", "duration_seconds": 3.0},
            {"attempt_number": 2, "status": "failed", "error": "same", "duration_seconds": 3.0},
        ],
    )

    findings = diagnosis.findings_for(evidence)["findings"]

    assert findings
    for finding in findings:
        assert finding["evidence"], finding["id"]
        assert finding["remedy"].strip(), finding["id"]
        assert finding["confidence"] in {"confirmed", "possible"}


# --- One test per rule: fires, and does not fire ----------------------------


def test_unresolved_input_ports_are_confirmed() -> None:
    assert "pending_inputs_unresolved" in _ids(_bundle(pending_inputs=["structure", "ligand"]))
    assert "pending_inputs_unresolved" not in _ids(_bundle(pending_inputs=[]))


def test_a_missing_command_is_confirmed() -> None:
    assert "no_command_declared" in _ids(_bundle(command=None))
    assert "no_command_declared" in _ids(_bundle(command=""))
    assert "no_command_declared" not in _ids(_bundle(command="python run.py"))


def test_a_gpu_forcing_queue_is_reported_for_a_no_gpu_plugin_only() -> None:
    """The lesson this rule exists for: `#BSUB` carrying no `-gpu` is not proof.

    The queue merges its own requirement in, so a stage that declares no GPU
    still holds one exclusively. A plugin that *did* ask for a GPU on the same
    queue is doing what it said, and must not be reported.
    """
    no_gpu = _bundle(queue="2v100-32-e5")
    with_gpu = _bundle(
        queue="2v100-32-e5",
        plugin_snapshot={"key": "d", "version": "1", "resources": {"gpu": True}, "runtime_mode": "container"},
    )

    assert "gpu_forced_by_queue" in _ids(no_gpu)
    assert "gpu_forced_by_queue" not in _ids(with_gpu)
    assert "gpu_forced_by_queue" not in _ids(_bundle(queue="normal"))


def test_an_unsupported_cpu_declaration_is_possible_not_confirmed() -> None:
    """It is a claim about utilisation, which the job record cannot settle."""
    evidence = _bundle(
        plugin_snapshot={"key": "d", "version": "1", "resources": {"cpus": 8}, "runtime_mode": "container"}
    )

    finding = next(
        item for item in diagnosis.findings_for(evidence)["findings"]
        if item["id"] == "cpu_declaration_unsupported"
    )
    assert finding["confidence"] == "possible"

    with_evidence = _bundle(
        plugin_snapshot={
            "key": "d",
            "version": "1",
            "resources": {"cpus": 8, "cpus_evidence": "jackhmmer --cpu 8 measured at 7.6 cores"},
            "runtime_mode": "container",
        }
    )
    assert "cpu_declaration_unsupported" not in _ids(with_evidence)
    assert "cpu_declaration_unsupported" not in _ids(_bundle())


def test_an_immediate_exit_points_at_the_declaration_not_the_science() -> None:
    quick = _bundle(
        attempts=[{"attempt_number": 1, "status": "failed", "error": "", "duration_seconds": 3.0}]
    )
    slow = _bundle(
        attempts=[{"attempt_number": 1, "status": "failed", "error": "", "duration_seconds": 4000.0}]
    )
    succeeded_fast = _bundle(
        attempts=[{"attempt_number": 1, "status": "succeeded", "error": None, "duration_seconds": 2.0}]
    )

    assert "immediate_exit" in _ids(quick)
    assert "immediate_exit" not in _ids(slow)
    assert "immediate_exit" not in _ids(succeeded_fast)


def test_an_attempt_still_running_does_not_look_like_an_immediate_exit() -> None:
    """A null finished_at means "not finished", not "finished at zero seconds"."""
    running = _bundle(
        attempts=[{"attempt_number": 1, "status": "failed", "error": "", "duration_seconds": None}]
    )

    assert "immediate_exit" not in _ids(running)


@pytest.mark.parametrize(
    ("rule_id", "message"),
    [
        ("out_of_memory", "TERM_MEMLIMIT: job killed after reaching LSF memory usage limit"),
        ("out_of_memory", "torch.cuda.OutOfMemoryError: CUDA out of memory"),
        ("walltime_exceeded", "TERM_RUNLIMIT: job killed after reaching LSF run time limit"),
        ("image_unavailable", "Error response from daemon: manifest unknown"),
        ("input_file_missing", "FileNotFoundError: /staging/inputs/target.fasta"),
        ("checksum_mismatch", "sha256sum: WARNING: 1 computed checksum did NOT match"),
        ("permission_denied", "cp: cannot create regular file: Permission denied"),
    ],
)
def test_pattern_rules_fire_on_their_own_error_text(rule_id: str, message: str) -> None:
    assert rule_id in _ids(_bundle(error_message=message))


@pytest.mark.parametrize(
    "rule_id",
    [
        "out_of_memory",
        "walltime_exceeded",
        "image_unavailable",
        "input_file_missing",
        "checksum_mismatch",
        "permission_denied",
    ],
)
def test_pattern_rules_stay_silent_on_an_unrelated_error(rule_id: str) -> None:
    assert rule_id not in _ids(_bundle(error_message="the sampler produced no poses"))


def test_an_attempt_error_is_read_as_well_as_the_job_error() -> None:
    """A retry that failed differently is the interesting case.

    Matching only `error_message` would miss a first attempt that ran out of
    memory and a second that failed for another reason.
    """
    evidence = _bundle(
        error_message="job failed",
        attempts=[
            {"attempt_number": 1, "status": "failed", "error": "TERM_MEMLIMIT", "duration_seconds": 500.0},
            {"attempt_number": 2, "status": "failed", "error": "job failed", "duration_seconds": 500.0},
        ],
    )

    assert "out_of_memory" in _ids(evidence)


def test_identical_repeated_failures_are_confirmed_and_differing_ones_are_not() -> None:
    same = _bundle(
        attempts=[
            {"attempt_number": 1, "status": "failed", "error": "boom", "duration_seconds": 500.0},
            {"attempt_number": 2, "status": "failed", "error": "boom", "duration_seconds": 500.0},
        ]
    )
    different = _bundle(
        attempts=[
            {"attempt_number": 1, "status": "failed", "error": "boom", "duration_seconds": 500.0},
            {"attempt_number": 2, "status": "failed", "error": "other", "duration_seconds": 500.0},
        ]
    )

    assert "repeated_identical_failure" in _ids(same)
    assert "repeated_identical_failure" not in _ids(different)
    assert "repeated_identical_failure" not in _ids(_bundle())


def test_a_job_with_no_external_id_is_flagged_only_when_it_ended_badly() -> None:
    assert "never_reached_backend" in _ids(_bundle(external_id=None, status="failed"))
    assert "never_reached_backend" not in _ids(_bundle(external_id=None, status="running"))
    assert "never_reached_backend" not in _ids(_bundle(external_id="9", status="failed"))


def test_summary_counts_confirmed_and_possible_separately() -> None:
    evidence = _bundle(
        pending_inputs=["ligand"],  # confirmed
        plugin_snapshot={"key": "d", "version": "1", "resources": {"cpus": 4}, "runtime_mode": "container"},
    )

    summary = diagnosis.findings_for(evidence)["summary"]

    assert "1 confirmed" in summary
    assert "1 possible" in summary


# --- Database-backed: scope, and what actually reaches the rules -------------


@pytest.fixture
def session() -> Iterator[Session]:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


_counter = itertools.count()


def _project(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    n = next(_counter)
    user = User(username=f"ops-{n}", display_name="Ops", role="editor", enabled=True)
    organization = Organization(name=f"Ops Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        name=f"ops-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project.id, user.id


def _failed_job(session: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> Job:
    from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun

    run = WorkflowRun(project_id=project_id, name="wf", created_by=user_id, status="failed")
    session.add(run)
    session.flush()
    node = WorkflowNode(
        workflow_run_id=run.id,
        node_key="fold",
        node_type="model",
        model_plugin="demo",
    )
    session.add(node)
    session.flush()
    submission = JobSubmission(
        workflow_run_id=run.id, project_id=project_id, created_by=user_id, compute_backend="lsf"
    )
    session.add(submission)
    session.flush()
    job = Job(
        submission_id=submission.id,
        workflow_run_id=run.id,
        workflow_node_id=node.id,
        project_id=project_id,
        status="failed",
        compute_backend="lsf",
        model_plugin="demo",
        error_code="job_failed",
        error_message="TERM_MEMLIMIT: job killed",
        runtime_spec={
            "queue": "2v100-32-e5",
            "command": "run.sh",
            "plugin_snapshot": {"key": "demo", "version": "1", "resources": {"cpus": 4}},
            "input_manifest": {"inputs": [{"port": "sequence"}], "pending_inputs": ["structure"]},
        },
    )
    session.add(job)
    session.flush()
    started = datetime.now(UTC) - timedelta(seconds=5)
    session.add(
        JobAttempt(
            job_id=job.id,
            attempt_number=1,
            status="failed",
            error="TERM_MEMLIMIT: job killed",
            started_at=started,
            finished_at=started + timedelta(seconds=4),
        )
    )
    session.add(JobEvent(job_id=job.id, event_type="job.failed", payload={}))
    session.flush()
    return job


def test_diagnose_reads_the_recorded_evidence_and_applies_every_matching_rule(session: Session) -> None:
    project_id, user_id = _project(session)
    job = _failed_job(session, project_id, user_id)

    result = diagnosis.diagnose(session, project_id, job.id)

    ids = {finding["id"] for finding in result["findings"]}
    assert {"pending_inputs_unresolved", "out_of_memory", "gpu_forced_by_queue", "immediate_exit"} <= ids
    assert result["evidence"]["queue"] == "2v100-32-e5"
    assert result["evidence"]["attempts"][0]["duration_seconds"] == pytest.approx(4.0, abs=0.5)
    assert result["evidence"]["recent_events"][0]["event_type"] == "job.failed"


def test_a_job_from_another_project_is_not_found(session: Session) -> None:
    project_id, user_id = _project(session)
    other_project_id, _ = _project(session)
    job = _failed_job(session, project_id, user_id)

    with pytest.raises(DomainError) as error:
        diagnosis.diagnose(session, other_project_id, job.id)

    assert error.value.status_code == 404


def test_an_unknown_job_id_is_not_found(session: Session) -> None:
    project_id, _ = _project(session)

    with pytest.raises(DomainError) as error:
        diagnosis.diagnose(session, project_id, uuid.uuid4())

    assert error.value.status_code == 404


def test_evidence_carries_no_credentials_or_object_keys(session: Session) -> None:
    """The bundle reaches a language model, so it must not carry anything secret.

    `runtime_spec` holds presigned manifest keys among other things; the bundle
    names only the fields the rules read.
    """
    project_id, user_id = _project(session)
    job = _failed_job(session, project_id, user_id)
    job.runtime_spec = {
        **job.runtime_spec,
        "input_manifest_key": "jobs/x/attempt-1/input-manifest.json",
        "secret_token": hashlib.sha256(b"nope").hexdigest(),
    }
    session.flush()

    evidence = diagnosis.collect_evidence(session, project_id, job.id)

    serialised = repr(evidence)
    assert "secret_token" not in serialised
    assert "input_manifest_key" not in serialised


def test_an_unfinished_attempt_has_no_duration_rather_than_a_zero_one() -> None:
    """Zero would make every running attempt look like an immediate exit."""
    started = datetime.now(UTC)

    assert diagnosis._duration(started, None) is None
    assert diagnosis._duration(None, started) is None
    assert diagnosis._duration(started, started + timedelta(seconds=7)) == 7.0


def test_a_naive_timestamp_is_read_as_utc_not_as_local_time() -> None:
    """SQLite hands back naive datetimes for timezone-aware columns.

    Subtracting a naive from an aware one raises; treating one as local time
    would shift every duration by the host's offset.
    """
    naive = datetime(2026, 9, 13, 1, 0, 0)  # noqa: DTZ001 - the case under test

    assert diagnosis._duration(naive, naive.replace(tzinfo=UTC) + timedelta(seconds=3)) == 3.0


# --- Through the tool registry ----------------------------------------------


def test_diagnose_runs_through_the_registry_and_needs_its_capability(session: Session) -> None:
    from backend_v2.app.copilot import tools as _copilot_tools  # noqa: F401
    from backend_v2.app.copilot.registry import REGISTRY, ToolContext

    project_id, user_id = _project(session)
    job = _failed_job(session, project_id, user_id)
    ctx = ToolContext(project_id=project_id, session=session)

    result = REGISTRY.execute(
        "diagnose_compute_failure", ctx, {"job_id": str(job.id)}, granted={"failure-diagnosis"}
    )
    assert result["findings"]

    with pytest.raises(DomainError) as refused:
        REGISTRY.execute(
            "diagnose_compute_failure", ctx, {"job_id": str(job.id)}, granted={"project-read"}
        )
    assert refused.value.status_code == 403

    # A project-less turn must not reach a job at all.
    with pytest.raises(ValueError, match="project_context_required"):
        REGISTRY.execute(
            "diagnose_compute_failure",
            ToolContext(session=session),
            {"job_id": str(job.id)},
            granted={"failure-diagnosis"},
        )
