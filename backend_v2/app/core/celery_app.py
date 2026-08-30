"""The Celery application, its routing, and the operation-lifecycle signal handlers.

This lives in ``core`` rather than in a domain package because every domain registers
tasks against it. It previously sat in ``compute.tasks`` alongside roughly forty tasks
belonging to a dozen other domains, which made ``compute`` import every sibling package
and forced dozens of function-local imports to break the resulting cycles.

Task names, queue routing and the beat schedule are unchanged: they are the deployment
contract. Workers are still started with
``-A backend_v2.app.compute.tasks.celery_app``, which re-exports this app, and
``conf.imports`` below is what makes every domain's tasks register regardless of the
module a worker was pointed at. Adding a task module means adding it to that tuple.

The signal handlers use function-local imports on purpose: mirroring a task's outcome
onto an ``Operation`` row is a platform concern, and importing it at module scope would
make ``core`` depend on ``platform``. They run once per task, not in any hot path.
"""

from __future__ import annotations

import uuid

from celery import Celery  # type: ignore[import-untyped]
from celery.signals import task_failure, task_prerun, task_success  # type: ignore[import-untyped]

from .config import get_settings
from .database import session_scope

settings = get_settings()
celery_app = Celery("bda-v2", broker=settings.celery_broker_url, backend=settings.redis_url)

# Every module that registers a task. A worker imports these at startup, so no module
# here may be imported at the top of another for registration purposes.
TASK_MODULES = (
    "backend_v2.app.compute.tasks",
    "backend_v2.app.campaigns.tasks",
    "backend_v2.app.copilot.tasks",
    "backend_v2.app.delivery.tasks",
    "backend_v2.app.experiments.tasks",
    "backend_v2.app.intelligence.tasks",
    "backend_v2.app.ligands.tasks",
    "backend_v2.app.literature.tasks",
    "backend_v2.app.projects.tasks",
    "backend_v2.app.registry.tasks",
    "backend_v2.app.research.tasks",
    "backend_v2.app.targets.tasks",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    imports=TASK_MODULES,
    task_routes={
        "bda_v2.dispatch_job": {"queue": "dispatch"},
        "bda_v2.poll_job": {"queue": "poll"},
        "bda_v2.collect_job": {"queue": "collect"},
        "bda_v2.cancel_job": {"queue": "dispatch"},
        "bda_v2.copilot_respond": {"queue": "copilot"},
        "bda_v2.copilot_agent_step": {"queue": "copilot"},
        "bda_v2.copilot_agent_task_settled": {"queue": "copilot"},
        "bda_v2.copilot_agent_operation_settled": {"queue": "copilot"},
        "bda_v2.copilot_agent_sweep": {"queue": "maintenance"},
        "bda_v2.project_prompt_generate": {"queue": "copilot"},
        "bda_v2.research_generate": {"queue": "research"},
        "bda_v2.research_gaps_resolve": {"queue": "research"},
        "bda_v2.literature_ingest": {"queue": "research"},
        "bda_v2.literature_search": {"queue": "research"},
        "bda_v2.subscription_run": {"queue": "research"},
        "bda_v2.intelligence_run": {"queue": "research"},
        "bda_v2.intelligence_export": {"queue": "research"},
        "bda_v2.ligand_import": {"queue": "research"},
        "bda_v2.delivery_build": {"queue": "collect"},
        "bda_v2.compute_draft_confirm": {"queue": "dispatch"},
        "bda_v2.experiment_results_import": {"queue": "research"},
        "bda_v2.target_structure_import": {"queue": "research"},
        "bda_v2.target_structure_prepare": {"queue": "research"},
        "bda_v2.campaign_advance": {"queue": "research"},
        "bda_v2.campaign_evaluate": {"queue": "research"},
        "bda_v2.literature_relations_detect": {"queue": "research"},
        "bda_v2.registry_model_plugin_validate": {"queue": "maintenance"},
        "bda_v2.registry_compute_node_health": {"queue": "maintenance"},
        "bda_v2.registry_server_test": {"queue": "maintenance"},
        "bda_v2.*": {"queue": "maintenance"},
    },
    beat_schedule={
        "publish-outbox": {"task": "bda_v2.publish_outbox", "schedule": 2.0},
        "poll-due-jobs": {"task": "bda_v2.poll_due_jobs", "schedule": 5.0},
        "reconcile-artifacts": {"task": "bda_v2.reconcile_artifacts", "schedule": 300.0},
        "reap-stale-jobs": {"task": "bda_v2.reap_stale_jobs", "schedule": 120.0},
        # The backstop for agent runs, not their wake-up mechanism: compute emits
        # an event on every terminal job state, so this normally finds nothing.
        # It exists for the wake-ups no event can carry - a task settled by a
        # cancel, or an event lost between the publisher and the worker.
        "sweep-agent-runs": {"task": "bda_v2.copilot_agent_sweep", "schedule": 60.0},
        "purge-deleted-projects": {"task": "bda_v2.purge_deleted_projects", "schedule": 86400.0},
    },
)


@task_prerun.connect
def _operation_started(task_id=None, **_kwargs) -> None:
    from ..platform.models import Operation
    from ..platform.operations import mark_operation_running

    try:
        parsed = uuid.UUID(str(task_id))
    except (TypeError, ValueError):
        return
    with session_scope() as session:
        if session.get(Operation, parsed) is not None:
            mark_operation_running(session, parsed)


@task_success.connect
def _operation_succeeded(sender=None, result=None, **_kwargs) -> None:
    from ..platform.models import Operation
    from ..platform.operations import finish_operation

    task_id = getattr(getattr(sender, "request", None), "id", None)
    try:
        parsed = uuid.UUID(str(task_id))
    except (TypeError, ValueError):
        return
    with session_scope() as session:
        if session.get(Operation, parsed) is not None:
            finish_operation(session, parsed, result=result if isinstance(result, dict) else {"result": result})


@task_failure.connect
def _operation_failed(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    **_kwargs,
) -> None:
    from ..platform.models import Operation
    from ..platform.operations import finish_operation

    try:
        parsed = uuid.UUID(str(task_id))
    except (TypeError, ValueError):
        return
    with session_scope() as session:
        error = exception if isinstance(exception, Exception) else RuntimeError(str(exception))
        if session.get(Operation, parsed) is not None:
            finish_operation(session, parsed, error=error)
        if getattr(sender, "name", "") == "bda_v2.copilot_respond" and args:
            from ..copilot.models import CopilotMessage

            try:
                message_id = uuid.UUID(str(args[0]))
            except (TypeError, ValueError):
                return
            message = session.get(CopilotMessage, message_id)
            if message is not None and message.status == "pending":
                message.status = "failed"
                message.error = f"{error.__class__.__name__}: {str(error)[:1000]}"
                message.version += 1
