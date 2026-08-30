from __future__ import annotations

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
