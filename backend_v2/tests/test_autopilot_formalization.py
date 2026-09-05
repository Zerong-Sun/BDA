from __future__ import annotations

import uuid

pytest_plugins = ["backend_v2.tests.test_v2_domains"]


def _draft(client, project_id: str) -> tuple[dict, str]:
    response = client.post(
        "/api/v2/autopilot-drafts",
        json={
            "project_id": project_id,
            "structured_brief": {
                "objective": "Design a synthetic demonstration binder",
                "stages": ["research", "compute", "review"],
            },
        },
    )
    assert response.status_code == 201
    return response.json(), response.headers["etag"]


def test_supervised_campaign_budget_reservation_and_idempotent_cancel(domain_client) -> None:
    client, ids = domain_client
    draft, draft_etag = _draft(client, str(ids["project"]))

    missing_budget = client.post(
        f"/api/v2/autopilot-drafts/{draft['id']}/confirm",
        headers={"If-Match": draft_etag},
        json={"name": "No implicit budget", "autonomy": "supervised"},
    )
    assert missing_budget.status_code == 422

    confirmed = client.post(
        f"/api/v2/autopilot-drafts/{draft['id']}/confirm",
        headers={"If-Match": draft_etag},
        json={
            "name": "Explicit budget",
            "autonomy": "supervised",
            "budget": {"gpu_seconds_limit": 3600, "money_micros_limit": 2_000_000},
        },
    )
    assert confirmed.status_code == 201
    campaign = confirmed.json()
    assert campaign["frozen_prompt"].startswith("Autopilot protocol")

    start_payload = {"idempotency_key": "stage-compute-0001", "gpu_seconds": 1800, "money_micros": 500_000}
    first = client.post(f"/api/v2/autopilot-campaigns/{campaign['id']}/start", json=start_payload)
    second = client.post(f"/api/v2/autopilot-campaigns/{campaign['id']}/start", json=start_payload)
    assert first.status_code == second.status_code == 202
    assert first.json()["operation_id"] == second.json()["operation_id"]

    over = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/start",
        json={"idempotency_key": "stage-compute-0002", "gpu_seconds": 1801, "money_micros": 0},
    )
    assert over.status_code == 409
    assert over.json()["error_code"] == "campaign_budget_exceeded"

    cancelled = client.post(f"/api/v2/autopilot-campaigns/{campaign['id']}/cancel")
    cancelled_again = client.post(f"/api/v2/autopilot-campaigns/{campaign['id']}/cancel")
    assert cancelled.status_code == cancelled_again.status_code == 202
    assert cancelled.json()["operation_id"] == cancelled_again.json()["operation_id"]


def test_plan_only_campaign_has_no_default_budget_and_cannot_start(domain_client) -> None:
    client, ids = domain_client
    draft, draft_etag = _draft(client, str(ids["project"]))
    confirmed = client.post(
        f"/api/v2/autopilot-drafts/{draft['id']}/confirm",
        headers={"If-Match": draft_etag},
        json={"name": "Plan only", "autonomy": "plan_only"},
    )
    assert confirmed.status_code == 201
    started = client.post(
        f"/api/v2/autopilot-campaigns/{confirmed.json()['id']}/start",
        json={"idempotency_key": "plan-only-start", "gpu_seconds": 0, "money_micros": 0},
    )
    assert started.status_code == 409
    assert started.json()["error_code"] == "plan_only_compute_forbidden"


def _confirmed_campaign(client, project_id: str, name: str = "Adapter campaign") -> dict:
    draft, etag = _draft(client, project_id)
    confirmed = client.post(
        f"/api/v2/autopilot-drafts/{draft['id']}/confirm",
        headers={"If-Match": etag},
        json={
            "name": name,
            "autonomy": "supervised",
            "budget": {"gpu_seconds_limit": 3600, "money_micros_limit": 2_000_000},
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    return confirmed.json()


def test_a_compute_stage_lands_on_the_main_trunk_not_an_autopilot_copy(domain_client) -> None:
    """The stage points at a real `workflow_runs` row, reachable from the Workflow page.

    This is the whole of M2: before the adapter existed, an automatic campaign produced
    nothing a person could open. A private mirror would have been easier and is exactly
    what invariant I1 forbids - a candidate rejected by hand has to be the same row the
    next automatic stage reads.
    """
    from backend_v2.app.autopilot.adapters import ensure_stage_resource
    from backend_v2.app.autopilot.models import AutopilotCampaign, AutopilotStage
    from backend_v2.app.workflows.models import WorkflowRun
    from sqlalchemy import select

    client, ids = domain_client
    campaign_json = _confirmed_campaign(client, str(ids["project"]))
    with ids["session_factory"]() as session:
        campaign = session.get(AutopilotCampaign, uuid.UUID(campaign_json["id"]))
        stage = session.scalar(
            select(AutopilotStage).where(
                AutopilotStage.campaign_id == campaign.id, AutopilotStage.stage_key == "compute"
            )
        )

        resource = ensure_stage_resource(session, campaign, stage)
        session.commit()

        assert resource is not None
        assert resource[0] == "workflow_run"
        assert stage.resource_type == "workflow_run"
        assert stage.resource_id == resource[1]

        run = session.get(WorkflowRun, resource[1])
        assert run is not None
        # Same project as the campaign, and visible to every ordinary workflow read.
        assert run.project_id == campaign.project_id
        # No route in the frozen spec, so nothing was submitted on a guess.
        assert run.status == "draft"


def test_the_adapter_is_idempotent_under_redelivery(domain_client) -> None:
    """Celery redelivers. A second run would be real cluster time spent on a duplicate."""
    from backend_v2.app.autopilot.adapters import ensure_stage_resource
    from backend_v2.app.autopilot.models import AutopilotCampaign, AutopilotStage
    from backend_v2.app.workflows.models import WorkflowRun
    from sqlalchemy import func, select

    client, ids = domain_client
    campaign_json = _confirmed_campaign(client, str(ids["project"]), name="Redelivered")
    with ids["session_factory"]() as session:
        campaign = session.get(AutopilotCampaign, uuid.UUID(campaign_json["id"]))
        stage = session.scalar(
            select(AutopilotStage).where(
                AutopilotStage.campaign_id == campaign.id, AutopilotStage.stage_key == "compute"
            )
        )

        first = ensure_stage_resource(session, campaign, stage)
        session.commit()
        second = ensure_stage_resource(session, campaign, stage)
        session.commit()

        assert first == second
        runs = session.scalar(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.project_id == campaign.project_id)
        )
        assert runs == 1


def test_a_stage_with_no_adapter_stays_a_human_step(domain_client) -> None:
    """`review` has no trunk object. Saying so beats inventing one."""
    from backend_v2.app.autopilot.adapters import ensure_stage_resource
    from backend_v2.app.autopilot.models import AutopilotCampaign, AutopilotStage
    from sqlalchemy import select

    client, ids = domain_client
    campaign_json = _confirmed_campaign(client, str(ids["project"]), name="Human step")
    with ids["session_factory"]() as session:
        campaign = session.get(AutopilotCampaign, uuid.UUID(campaign_json["id"]))
        stage = session.scalar(
            select(AutopilotStage).where(
                AutopilotStage.campaign_id == campaign.id, AutopilotStage.stage_key == "review"
            )
        )

        assert ensure_stage_resource(session, campaign, stage) is None
        assert stage.resource_type is None
        assert stage.resource_id is None


def test_takeover_moves_authority_and_says_who(domain_client) -> None:
    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Taken over")

    stale = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/takeover",
        headers={"If-Match": 'W/"99"'},
    )
    assert stale.status_code == 412

    taken = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/takeover",
        headers={"If-Match": f'W/"{campaign["version"]}"'},
    )
    assert taken.status_code == 200, taken.text
    body = taken.json()
    assert body["status"] == "manual_takeover"
    assert body["taken_over_at"] is not None
    assert body["taken_over_by"] is not None


def test_takeover_requires_if_match(domain_client) -> None:
    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="No header")
    assert client.post(f"/api/v2/autopilot-campaigns/{campaign['id']}/takeover").status_code == 428


def test_taking_over_twice_does_not_record_two_handovers(domain_client) -> None:
    """A double-clicked button must not produce two entries naming two owners."""
    from backend_v2.app.autopilot.models import AutopilotLedgerEntry
    from sqlalchemy import func, select

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Double click")
    first = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/takeover",
        headers={"If-Match": f'W/"{campaign["version"]}"'},
    )
    assert first.status_code == 200
    again = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/takeover",
        headers={"If-Match": f'W/"{first.json()["version"]}"'},
    )
    assert again.status_code == 200
    from datetime import datetime

    def instant(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)

    assert instant(again.json()["taken_over_at"]) == instant(first.json()["taken_over_at"])

    with ids["session_factory"]() as session:
        handovers = session.scalar(
            select(func.count())
            .select_from(AutopilotLedgerEntry)
            .where(
                AutopilotLedgerEntry.campaign_id == uuid.UUID(campaign["id"]),
                AutopilotLedgerEntry.event_type == "campaign.takeover",
            )
        )
    assert handovers == 1


def test_a_cancelled_campaign_cannot_be_taken_over(domain_client) -> None:
    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Cancelled first")
    assert client.post(f"/api/v2/autopilot-campaigns/{campaign['id']}/cancel").status_code == 202
    refreshed = client.get(f"/api/v2/autopilot-campaigns/{campaign['id']}").json()
    refused = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/takeover",
        headers={"If-Match": f'W/"{refreshed["version"]}"'},
    )
    assert refused.status_code == 409
    assert refused.json()["error_code"] == "autopilot_campaign_cancelled"


def test_the_worker_stops_advancing_a_taken_over_campaign(domain_client, monkeypatch) -> None:
    """The race takeover exists to prevent: worker moves a stage while a person edits."""
    from contextlib import contextmanager

    from backend_v2.app.autopilot import tasks as autopilot_tasks

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Worker stands down")
    client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/takeover",
        headers={"If-Match": f'W/"{campaign["version"]}"'},
    )

    factory = ids["session_factory"]

    @contextmanager
    def fixture_scope():
        with factory() as session:
            yield session
            session.commit()

    # The task builds its own session from settings; point it at the fixture engine so the
    # guard is exercised for real rather than asserted by reading the source.
    monkeypatch.setattr(autopilot_tasks, "session_scope", fixture_scope)
    result = autopilot_tasks.execute_campaign.apply(args=[campaign["id"]]).get()
    assert result["status"] == "manual_takeover"


def _fixture_scope(ids):
    from contextlib import contextmanager

    factory = ids["session_factory"]

    @contextmanager
    def scope():
        with factory() as session:
            yield session
            session.commit()

    return scope


def _reservation(ids, campaign_id: str):
    from backend_v2.app.autopilot.models import BudgetReservation
    from sqlalchemy import select

    with ids["session_factory"]() as session:
        return session.scalar(
            select(BudgetReservation).where(BudgetReservation.campaign_id == uuid.UUID(campaign_id))
        )


def test_settling_moves_a_reservation_from_reserved_to_committed(domain_client, monkeypatch) -> None:
    """Until a reservation settles, the campaign's remaining budget is an estimate."""
    from backend_v2.app.autopilot import tasks as autopilot_tasks
    from backend_v2.app.autopilot.models import CampaignBudget
    from sqlalchemy import select

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Settled")
    client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/start",
        json={"idempotency_key": "settle-0001", "gpu_seconds": 1800, "money_micros": 100},
    )
    reservation = _reservation(ids, campaign["id"])
    assert reservation is not None

    monkeypatch.setattr(autopilot_tasks, "session_scope", _fixture_scope(ids))
    result = autopilot_tasks.settle_reservation.apply(
        args=[campaign["id"], str(reservation.id), 1200]
    ).get()

    assert result["status"] == "committed"
    assert result["committed_gpu_seconds"] == 1200
    with ids["session_factory"]() as session:
        budget = session.scalar(
            select(CampaignBudget).where(CampaignBudget.campaign_id == uuid.UUID(campaign["id"]))
        )
        # The 1800 held is released and the 1200 actually used is charged, so the
        # difference becomes headroom again rather than staying blocked forever.
        assert budget.gpu_seconds_reserved == 0
        assert budget.gpu_seconds_committed == 1200


def test_settling_twice_does_not_charge_twice(domain_client, monkeypatch) -> None:
    """Celery redelivers; a double charge would then have the hard limit refuse real work."""
    from backend_v2.app.autopilot import tasks as autopilot_tasks
    from backend_v2.app.autopilot.models import CampaignBudget
    from sqlalchemy import select

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Redelivered settle")
    client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/start",
        json={"idempotency_key": "settle-0002", "gpu_seconds": 900, "money_micros": 100},
    )
    reservation = _reservation(ids, campaign["id"])
    monkeypatch.setattr(autopilot_tasks, "session_scope", _fixture_scope(ids))

    autopilot_tasks.settle_reservation.apply(args=[campaign["id"], str(reservation.id), 600]).get()
    again = autopilot_tasks.settle_reservation.apply(
        args=[campaign["id"], str(reservation.id), 600]
    ).get()

    assert again.get("idempotent") is True
    with ids["session_factory"]() as session:
        budget = session.scalar(
            select(CampaignBudget).where(CampaignBudget.campaign_id == uuid.UUID(campaign["id"]))
        )
        assert budget.gpu_seconds_committed == 600


def test_an_overrun_is_clamped_and_recorded_rather_than_silently_charged(
    domain_client, monkeypatch
) -> None:
    """Spending more than was reserved is a real event; it belongs on the ledger."""
    from backend_v2.app.autopilot import tasks as autopilot_tasks
    from backend_v2.app.autopilot.models import AutopilotLedgerEntry, CampaignBudget
    from sqlalchemy import select

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Overrun")
    client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/start",
        json={"idempotency_key": "settle-0003", "gpu_seconds": 600, "money_micros": 100},
    )
    reservation = _reservation(ids, campaign["id"])
    monkeypatch.setattr(autopilot_tasks, "session_scope", _fixture_scope(ids))

    result = autopilot_tasks.settle_reservation.apply(
        args=[campaign["id"], str(reservation.id), 1000]
    ).get()

    assert result["committed_gpu_seconds"] == 600
    assert result["unbilled_overrun_gpu_seconds"] == 400
    with ids["session_factory"]() as session:
        budget = session.scalar(
            select(CampaignBudget).where(CampaignBudget.campaign_id == uuid.UUID(campaign["id"]))
        )
        # Charged at the reservation, never above it: the hard-limit CHECK constraints
        # stay satisfiable, and the 400 is on the ledger instead of in a stack trace.
        assert budget.gpu_seconds_committed == 600
        entry = session.scalar(
            select(AutopilotLedgerEntry).where(
                AutopilotLedgerEntry.campaign_id == uuid.UUID(campaign["id"]),
                AutopilotLedgerEntry.event_type == "reservation.settled",
            )
        )
        assert entry.payload["unbilled_overrun_gpu_seconds"] == 400


def test_a_released_reservation_is_not_settled_afterwards(domain_client, monkeypatch) -> None:
    """Cancellation already released it; settling would re-charge a campaign nobody ran."""
    from backend_v2.app.autopilot import tasks as autopilot_tasks
    from backend_v2.app.autopilot.models import CampaignBudget
    from sqlalchemy import select

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Cancelled then settled")
    client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/start",
        json={"idempotency_key": "settle-0004", "gpu_seconds": 600, "money_micros": 100},
    )
    reservation = _reservation(ids, campaign["id"])
    monkeypatch.setattr(autopilot_tasks, "session_scope", _fixture_scope(ids))
    client.post(f"/api/v2/autopilot-campaigns/{campaign['id']}/cancel")
    autopilot_tasks.reconcile_cancel.apply(args=[campaign["id"]]).get()

    result = autopilot_tasks.settle_reservation.apply(
        args=[campaign["id"], str(reservation.id), 600]
    ).get()

    assert result["status"] == "released"
    with ids["session_factory"]() as session:
        budget = session.scalar(
            select(CampaignBudget).where(CampaignBudget.campaign_id == uuid.UUID(campaign["id"]))
        )
        assert budget.gpu_seconds_committed == 0


def test_a_recovering_worker_reuses_the_run_it_already_made(domain_client, monkeypatch) -> None:
    """Adapter failure recovery: the second dispatch must not create a second run.

    The stage's pointer is deliberately cleared first, so the test exercises the adapter's
    own lookup rather than the short-circuit on `stage.resource_id` - which is the case
    that actually happens when a worker dies between creating the run and committing.
    """
    from backend_v2.app.autopilot import tasks as autopilot_tasks
    from backend_v2.app.autopilot.adapters import ensure_stage_resource
    from backend_v2.app.autopilot.models import AutopilotCampaign, AutopilotStage
    from backend_v2.app.workflows.models import WorkflowRun
    from sqlalchemy import func, select

    client, ids = domain_client
    campaign_json = _confirmed_campaign(client, str(ids["project"]), name="Crashed worker")
    monkeypatch.setattr(autopilot_tasks, "session_scope", _fixture_scope(ids))

    with ids["session_factory"]() as session:
        campaign = session.get(AutopilotCampaign, uuid.UUID(campaign_json["id"]))
        stage = session.scalar(
            select(AutopilotStage).where(
                AutopilotStage.campaign_id == campaign.id, AutopilotStage.stage_key == "compute"
            )
        )
        first = ensure_stage_resource(session, campaign, stage)
        session.commit()

        stage.resource_type = None
        stage.resource_id = None
        session.commit()

        second = ensure_stage_resource(session, campaign, stage)
        session.commit()

        assert second == first
        runs = session.scalar(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.project_id == campaign.project_id)
        )
        assert runs == 1


def test_a_campaign_cannot_be_taken_over_from_another_project(domain_client) -> None:
    """Project membership is the only security boundary; takeover is not an exception."""
    from backend_v2.app.identity.models import User
    from backend_v2.app.projects.models import Project

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Fenced")

    with ids["session_factory"]() as session:
        outsider = User(username="outsider", display_name="Outsider", role="member", enabled=True)
        other_project = Project(
            organization_id=ids["organization"],
            owner_id=ids["user"],
            name="Someone else's project",
            project_type="protein_design",
        )
        session.add_all([outsider, other_project])
        session.commit()
        outsider_id = outsider.id

    from backend_v2.app.identity.deps import current_user
    from backend_v2.app.main import app

    def as_outsider() -> User:
        with ids["session_factory"]() as session:
            return session.get(User, outsider_id)

    previous = app.dependency_overrides[current_user]
    app.dependency_overrides[current_user] = as_outsider
    try:
        refused = client.post(
            f"/api/v2/autopilot-campaigns/{campaign['id']}/takeover",
            headers={"If-Match": f'W/"{campaign["version"]}"'},
        )
        assert refused.status_code in (403, 404)
    finally:
        app.dependency_overrides[current_user] = previous
