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
from types import SimpleNamespace
from typing import Any

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute import diagnosis
from backend_v2.app.compute.models import Job, JobEvent, JobSubmission
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine, select
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
        "phase_reached": "running",
        "reached_running": True,
        "runtime_seconds": 900.0,
        "previous_attempts": [],
        "retry_of": None,
        "recent_events": [],
    }
    base.update(overrides)
    return base


def _event(event_type: str, at: datetime) -> Any:
    """`_timeline` reads only `event_type` and `created_at`, so this is enough.

    Using the real model would need a session and a job row for a function that
    touches neither.
    """
    return SimpleNamespace(event_type=event_type, created_at=at)


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


def test_an_immediate_exit_is_measured_from_the_event_log() -> None:
    """Not from a JobAttempt row, which never carries an outcome.

    The first version of this rule read `attempt.status` and `attempt.finished_at`.
    The platform writes one attempt row per job at dispatch and never updates it,
    so both are permanently "dispatching" and NULL and the rule could not fire on
    any real job. These bundles carry what the event log actually records.
    """
    quick = _bundle(runtime_seconds=3.0)
    slow = _bundle(runtime_seconds=4000.0)
    succeeded_fast = _bundle(status="succeeded", runtime_seconds=2.0)

    assert "immediate_exit" in _ids(quick)
    assert "immediate_exit" not in _ids(slow)
    assert "immediate_exit" not in _ids(succeeded_fast)


def test_a_job_still_running_has_no_runtime_and_no_immediate_exit() -> None:
    """A missing terminal event means "not finished", not "finished at zero"."""
    assert "immediate_exit" not in _ids(_bundle(runtime_seconds=None))


def test_never_started_is_distinct_from_dying_quickly() -> None:
    """Two failures with disjoint causes, so they must not collapse into one.

    A job that ran for three seconds got as far as the container; one that never
    ran did not, and its command is not where to look.
    """
    never = _bundle(phase_reached="dispatching", reached_running=False, runtime_seconds=None)
    ran_briefly = _bundle(phase_reached="running", reached_running=True, runtime_seconds=3.0)

    assert "never_started" in _ids(never)
    assert "immediate_exit" not in _ids(never)
    assert "never_started" not in _ids(ran_briefly)
    assert "immediate_exit" in _ids(ran_briefly)


def test_never_started_stays_silent_on_a_job_that_did_not_fail() -> None:
    assert "never_started" not in _ids(_bundle(status="running", reached_running=False))


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


def test_identical_repeated_failures_are_read_from_the_retry_chain() -> None:
    """A retry is a new Job row, not another attempt on this one.

    `service.retry` copies the spec onto a fresh row and records the predecessor
    in the `job.pending` event payload, so the history lives in a linked list of
    jobs. The first version compared `JobAttempt.error` strings - a column
    nothing writes - and so could never fire.
    """
    same = _bundle(
        error_message="boom",
        previous_attempts=[{"job_id": "j1", "attempt_number": 1, "status": "failed", "error_message": "boom"}],
    )
    different = _bundle(
        error_message="other",
        previous_attempts=[{"job_id": "j1", "attempt_number": 1, "status": "failed", "error_message": "boom"}],
    )

    assert "repeated_identical_failure" in _ids(same)
    assert "repeated_identical_failure" not in _ids(different)
    assert "repeated_identical_failure" not in _ids(_bundle())


def test_a_predecessor_error_is_matched_by_the_pattern_rules() -> None:
    """A retry that failed differently is the interesting case.

    Matching only this job's message would miss that the first attempt was
    killed for memory and the second for something else.
    """
    evidence = _bundle(
        error_message="the sampler produced no poses",
        previous_attempts=[
            {"job_id": "j1", "attempt_number": 1, "status": "failed", "error_message": "TERM_MEMLIMIT"}
        ],
    )

    assert "out_of_memory" in _ids(evidence)


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


def _failed_job(
    session: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    with_retry_predecessor: bool = False,
) -> Job:
    """A job shaped the way the platform actually writes one.

    That is the point of this fixture. The rules must fire on the rows
    `compute/service.py` and `compute/tasks.py` produce - a status event per
    transition, and a retry as a *separate* job linked by the `job.pending`
    payload - not on a `JobAttempt` carrying an outcome, which nothing writes.
    """
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

    spec = {
        "queue": "2v100-32-e5",
        "command": "run.sh",
        "plugin_snapshot": {"key": "demo", "version": "1", "resources": {"cpus": 4}},
        "input_manifest": {"inputs": [{"port": "sequence"}], "pending_inputs": ["structure"]},
    }

    predecessor = None
    if with_retry_predecessor:
        predecessor = Job(
            submission_id=submission.id,
            workflow_run_id=run.id,
            workflow_node_id=node.id,
            project_id=project_id,
            status="failed",
            compute_backend="lsf",
            model_plugin="demo",
            attempt_number=1,
            error_code="job_failed",
            error_message="TERM_MEMLIMIT: job killed",
            runtime_spec=spec,
        )
        session.add(predecessor)
        session.flush()

    job = Job(
        submission_id=submission.id,
        workflow_run_id=run.id,
        workflow_node_id=node.id,
        project_id=project_id,
        status="failed",
        compute_backend="lsf",
        model_plugin="demo",
        attempt_number=2 if predecessor else 1,
        error_code="job_failed",
        error_message="TERM_MEMLIMIT: job killed",
        runtime_spec=spec,
    )
    session.add(job)
    session.flush()

    base = datetime.now(UTC) - timedelta(minutes=5)
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="job.pending",
            payload={"retry_of": str(predecessor.id)} if predecessor else {},
            created_at=base,
        )
    )
    for offset, event_type in (
        (2, "job.dispatching"),
        (5, "job.queued"),
        (30, "job.running"),
        (34, "job.failed"),
    ):
        session.add(
            JobEvent(job_id=job.id, event_type=event_type, created_at=base + timedelta(seconds=offset))
        )
    session.flush()
    return job


def test_diagnose_reads_the_recorded_evidence_and_applies_every_matching_rule(session: Session) -> None:
    """The rules fire on rows the platform actually writes.

    Every field read here is one `compute/service.py` or `compute/tasks.py`
    produces on an ordinary failed job: the status events, the runtime spec, and
    the job's own error.
    """
    project_id, user_id = _project(session)
    job = _failed_job(session, project_id, user_id)

    result = diagnosis.diagnose(session, project_id, job.id)

    ids = {finding["id"] for finding in result["findings"]}
    assert {"pending_inputs_unresolved", "out_of_memory", "gpu_forced_by_queue", "immediate_exit"} <= ids
    assert result["evidence"]["queue"] == "2v100-32-e5"
    assert result["evidence"]["runtime_seconds"] == pytest.approx(4.0, abs=0.5)
    assert result["evidence"]["phase_reached"] == "running"
    assert result["evidence"]["recent_events"][-1]["event_type"] == "job.failed"


def test_the_retry_chain_is_followed_through_the_pending_event(session: Session) -> None:
    """The predecessor is reachable only through the event payload.

    Nothing on the job row points backwards, so a diagnosis that did not read
    `job.pending` would report a first attempt where there had been two.
    """
    project_id, user_id = _project(session)
    job = _failed_job(session, project_id, user_id, with_retry_predecessor=True)

    result = diagnosis.diagnose(session, project_id, job.id)

    evidence = result["evidence"]
    assert evidence["attempt_number"] == 2
    assert evidence["retry_of"] is not None
    assert [item["attempt_number"] for item in evidence["previous_attempts"]] == [1]
    assert "repeated_identical_failure" in {finding["id"] for finding in result["findings"]}


def test_the_retry_chain_stops_at_a_project_boundary(session: Session) -> None:
    """A payload naming another project's job must not pull it into the bundle."""
    project_id, user_id = _project(session)
    other_project_id, other_user_id = _project(session)
    foreign = _failed_job(session, other_project_id, other_user_id)
    job = _failed_job(session, project_id, user_id)
    pending = session.scalars(
        select(JobEvent).where(JobEvent.job_id == job.id, JobEvent.event_type == "job.pending")
    ).one()
    pending.payload = {"retry_of": str(foreign.id)}
    session.flush()

    evidence = diagnosis.collect_evidence(session, project_id, job.id)

    assert evidence["previous_attempts"] == []


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


def test_the_timeline_starts_at_acceptance_not_at_row_creation() -> None:
    """Queue wait is the scheduler's time, not the stage's.

    Counting it would hide every fast failure behind a long PEND, which is the
    opposite of what the immediate-exit rule is for.
    """
    base = datetime(2026, 9, 13, 1, 0, 0, tzinfo=UTC)
    events = [
        _event("job.pending", base),
        _event("job.dispatching", base + timedelta(seconds=5)),
        _event("job.queued", base + timedelta(seconds=10)),
        _event("job.running", base + timedelta(hours=2)),
        _event("job.failed", base + timedelta(hours=2, seconds=4)),
    ]

    timeline = diagnosis._timeline(events)

    assert timeline["runtime_seconds"] == 4.0
    assert timeline["phase_reached"] == "running"
    assert timeline["reached_running"] is True


def test_a_job_with_no_terminal_event_has_no_runtime() -> None:
    base = datetime(2026, 9, 13, 1, 0, 0, tzinfo=UTC)

    timeline = diagnosis._timeline([_event("job.running", base)])

    assert timeline["runtime_seconds"] is None


def test_a_job_that_never_ran_reports_how_far_it_got() -> None:
    base = datetime(2026, 9, 13, 1, 0, 0, tzinfo=UTC)
    events = [_event("job.pending", base), _event("job.dispatching", base), _event("job.failed", base)]

    timeline = diagnosis._timeline(events)

    assert timeline["phase_reached"] == "dispatching"
    assert timeline["reached_running"] is False
    assert timeline["runtime_seconds"] is None


def test_a_naive_timestamp_is_read_as_utc_not_as_local_time() -> None:
    """SQLite hands back naive datetimes for timezone-aware columns.

    Subtracting a naive from an aware one raises; treating one as local time
    would shift every runtime by the host's offset.
    """
    naive = datetime(2026, 9, 13, 1, 0, 0)  # noqa: DTZ001 - the case under test
    events = [_event("job.running", naive), _event("job.failed", naive + timedelta(seconds=3))]

    assert diagnosis._timeline(events)["runtime_seconds"] == 3.0


def test_non_status_events_do_not_move_the_phase() -> None:
    """`job.input_adapter` and `job.parse_warning` are notes, not transitions."""
    base = datetime(2026, 9, 13, 1, 0, 0, tzinfo=UTC)
    events = [_event("job.pending", base), _event("job.input_adapter", base), _event("job.parse_warning", base)]

    assert diagnosis._timeline(events)["phase_reached"] == "pending"


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
