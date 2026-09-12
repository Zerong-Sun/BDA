"""Which stages a person has to release, decided by what the step does.

`autonomy` is a campaign-level dial with two positions, and that is the failure rather than
the control: a campaign that asks about every step trains the reviewer to approve without
reading, and one that asks about none is not supervised. These pin the replacement -
a per-stage tier, frozen at confirmation, that the worker cannot walk past.

The tier table is deliberately ahead of the capability. No stage submits work today, so
gating `compute` would stop something that spends nothing and teach people to click through
a hold before it guards anything. The declaration exists so that the day a stage submits,
one word changes here instead of someone having to notice the question arose.
"""

from __future__ import annotations

import uuid

import pytest
from backend_v2.app.autopilot import gates

pytest_plugins = ["backend_v2.tests.test_v2_domains"]


class TestTierTable:
    def test_an_unclassified_stage_is_held(self) -> None:
        """A stage nobody classified is a stage nobody thought about."""
        assert gates.tier_for("frobnicate") == gates.UNKNOWN_TIER
        assert gates.is_held("frobnicate") is True
        assert "nobody has decided the risk" in gates.explain("frobnicate")

    def test_bench_work_is_held_because_nothing_undoes_it(self) -> None:
        for key in ("wetlab", "bench", "express", "assay", "order"):
            assert gates.is_held(key) is True, key
        assert "nothing undoes it" in gates.explain("express")

    def test_work_that_spends_a_slot_is_held(self) -> None:
        assert gates.is_held("submit") is True
        assert "spent when it runs" in gates.explain("submit")

    def test_draft_producing_stages_are_not_held_today(self) -> None:
        # Recorded as a decision, not an oversight: every adapter that exists produces a
        # draft, and there is no path from an Autopilot stage to a submission.
        for key in ("research", "plan", "design", "compute", "collect", "review", "report"):
            assert gates.is_held(key) is False, key

    def test_lookup_is_case_and_whitespace_insensitive(self) -> None:
        assert gates.tier_for("  WetLab ") == "irreversible"

    def test_every_tier_in_the_table_is_a_known_tier(self) -> None:
        """A stage declared at a tier nothing defines would be silently ungated."""
        assert set(gates.STAGE_TIERS.values()) <= set(gates.TIERS)
        assert gates.UNKNOWN_TIER in gates.TIERS


class TestHeldIsDerived:
    """`held` is computed from the tier and the release, so the two cannot disagree."""

    def _stage(self, tier: str, released=None):
        from backend_v2.app.autopilot.models import AutopilotStage

        return AutopilotStage(stage_key="wetlab", position=0, risk_tier=tier, released_at=released)

    def test_a_held_tier_with_no_release_is_held(self) -> None:
        assert self._stage("irreversible").held is True

    def test_a_release_clears_the_hold(self) -> None:
        from datetime import UTC, datetime

        stage = self._stage("irreversible", released=datetime.now(UTC))
        assert stage.held is False
        assert stage.hold_reason is None

    def test_an_unknown_tier_reads_as_held(self) -> None:
        # A row whose classification this code does not recognise is not one to wave
        # through - the same deny-first reading `UNKNOWN_TIER` encodes.
        assert self._stage("tier-from-the-future").held is True


def test_confirmation_freezes_the_tier(domain_client) -> None:
    """Reclassifying a stage key later must not re-open a confirmed campaign."""
    from backend_v2.tests.test_autopilot_formalization import _confirmed_campaign

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Tiered campaign")
    tiers = {stage["stage_key"]: stage["risk_tier"] for stage in campaign["stages"]}
    assert tiers == {
        "research": "reversible_draft",
        "compute": "reversible_draft",
        "review": "reversible_draft",
    }
    assert all(stage["held"] is False for stage in campaign["stages"])


def test_an_unclassified_stage_arrives_held_and_can_be_released(domain_client) -> None:
    client, ids = domain_client
    draft = client.post(
        "/api/v2/autopilot-drafts",
        json={
            "project_id": str(ids["project"]),
            "structured_brief": {"objective": "Hold me", "stages": ["research", "express"]},
        },
    )
    assert draft.status_code == 201, draft.text
    confirmed = client.post(
        f"/api/v2/autopilot-drafts/{draft.json()['id']}/confirm",
        headers={"If-Match": draft.headers["etag"]},
        json={"name": "Held campaign", "autonomy": "supervised", "budget": {"gpu_seconds_limit": 60}},
    )
    assert confirmed.status_code == 201, confirmed.text
    campaign = confirmed.json()
    bench = next(stage for stage in campaign["stages"] if stage["stage_key"] == "express")
    assert bench["risk_tier"] == "irreversible"
    assert bench["held"] is True
    assert "nothing undoes it" in bench["hold_reason"]

    released = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/stages/{bench['id']}/release",
        headers={"If-Match": 'W/"1"'},
        json={},
    )
    assert released.status_code == 200, released.text
    assert released.json()["held"] is False
    assert released.json()["released_by"] is not None

    # Idempotent: a retry is not a second signature, and two release records would make
    # "who let this through" unanswerable.
    again = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/stages/{bench['id']}/release",
        headers={"If-Match": released.headers["etag"]},
        json={},
    )
    assert again.status_code == 200
    # Compared as instants: the second response is reloaded from SQLite, which hands back
    # a naive datetime for a timezone-aware column, so the serialisations differ by a "Z"
    # that Postgres would not drop. The point being pinned is that no second release
    # happened, not how the test database renders a timestamp.
    assert again.json()["released_at"].rstrip("Z") == released.json()["released_at"].rstrip("Z")


def test_releasing_a_stage_nobody_was_asked_to_approve_is_refused(domain_client) -> None:
    """A signature on an ungated stage makes the release log claim more review than happened."""
    from backend_v2.tests.test_autopilot_formalization import _confirmed_campaign

    client, ids = domain_client
    campaign = _confirmed_campaign(client, str(ids["project"]), name="Nothing to release")
    stage = campaign["stages"][0]
    refused = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/stages/{stage['id']}/release",
        headers={"If-Match": 'W/"1"'},
        json={},
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error_code"] == "autopilot_stage_not_held"


@pytest.mark.parametrize("stale", ['W/"99"'])
def test_a_stale_release_is_refused(domain_client, stale: str) -> None:
    client, ids = domain_client
    draft = client.post(
        "/api/v2/autopilot-drafts",
        json={
            "project_id": str(ids["project"]),
            "structured_brief": {"objective": "Stale", "stages": ["bench"]},
        },
    )
    confirmed = client.post(
        f"/api/v2/autopilot-drafts/{draft.json()['id']}/confirm",
        headers={"If-Match": draft.headers["etag"]},
        json={"name": "Stale release", "autonomy": "supervised", "budget": {"gpu_seconds_limit": 60}},
    )
    campaign = confirmed.json()
    stage = campaign["stages"][0]
    response = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/stages/{stage['id']}/release",
        headers={"If-Match": stale},
        json={},
    )
    assert response.status_code == 412


# --- The gate has to bind on both paths ---------------------------------------
#
# Two defects these pin, both found by reading the code after it shipped:
#
# 1. `execute_campaign` selected the first *pending* stage. A held stage sits in
#    `awaiting_release`, so a redelivery stepped over it and started the stage behind the
#    gate - the exact thing the gate exists to stop.
# 2. Releasing wrote the signature and nothing else, leaving the stage in
#    `awaiting_release` for ever. A gate with no other side is not an approval, it is a
#    dead end.


def _start(client, campaign_id: str, key: str) -> str:
    """Start a campaign and return the operation id the reservation is keyed on.

    The worker finds its reservation by `operation_id == self.request.id`, so a test that
    drives it has to run the task under that id - otherwise it fails before reaching the
    code under test.
    """
    started = client.post(
        f"/api/v2/autopilot-campaigns/{campaign_id}/start",
        json={"idempotency_key": key, "gpu_seconds": 60, "money_micros": 10},
    )
    assert started.status_code == 202, started.text
    return started.json()["operation_id"]


def _held_campaign(client, project_id: str, stages: list[str]) -> dict:
    draft = client.post(
        "/api/v2/autopilot-drafts",
        json={"project_id": project_id, "structured_brief": {"objective": "Gate", "stages": stages}},
    )
    assert draft.status_code == 201, draft.text
    confirmed = client.post(
        f"/api/v2/autopilot-drafts/{draft.json()['id']}/confirm",
        headers={"If-Match": draft.headers["etag"]},
        json={"name": f"Gate {stages}", "autonomy": "supervised", "budget": {"gpu_seconds_limit": 600}},
    )
    assert confirmed.status_code == 201, confirmed.text
    return confirmed.json()


def test_dispatch_does_not_step_over_a_held_stage(domain_client, monkeypatch) -> None:
    """The stage behind the gate must not start because the gate is in the way."""
    from backend_v2.app.autopilot import tasks as autopilot_tasks
    from backend_v2.tests.test_autopilot_formalization import _fixture_scope

    client, ids = domain_client
    # `express` is irreversible and therefore held; `compute` behind it is not.
    campaign = _held_campaign(client, str(ids["project"]), ["express", "compute"])
    monkeypatch.setattr(autopilot_tasks, "session_scope", _fixture_scope(ids))
    first_op = _start(client, campaign["id"], "gate-0001")
    first = autopilot_tasks.execute_campaign.apply(args=[campaign["id"]], task_id=first_op).get()
    assert first["status"] == "awaiting_release"

    # A second start under a different idempotency key is a second reservation and a
    # second dispatch - not a redelivery, so the ledger idempotency check does not
    # short-circuit it. This is the reachable path that used to walk past the gate.
    second_op = _start(client, campaign["id"], "gate-0001-again")
    autopilot_tasks.execute_campaign.apply(args=[campaign["id"]], task_id=second_op).get()

    after = client.get(f"/api/v2/autopilot-campaigns/{campaign['id']}").json()
    by_key = {stage["stage_key"]: stage for stage in after["stages"]}
    assert by_key["express"]["status"] == "awaiting_release"
    assert by_key["express"]["held"] is True
    # The stage behind the gate has not been touched.
    assert by_key["compute"]["status"] == "pending"
    assert by_key["compute"]["resource_id"] is None


def test_releasing_a_stage_actually_makes_it_act(domain_client, monkeypatch) -> None:
    """Recording the signature is not the point; letting the work proceed is."""
    from backend_v2.app.autopilot import tasks as autopilot_tasks
    from backend_v2.tests.test_autopilot_formalization import _fixture_scope

    client, ids = domain_client
    campaign = _held_campaign(client, str(ids["project"]), ["express"])
    monkeypatch.setattr(autopilot_tasks, "session_scope", _fixture_scope(ids))
    op = _start(client, campaign["id"], "gate-0002")
    autopilot_tasks.execute_campaign.apply(args=[campaign["id"]], task_id=op).get()

    stage = client.get(f"/api/v2/autopilot-campaigns/{campaign['id']}").json()["stages"][0]
    assert stage["status"] == "awaiting_release"

    released = client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/stages/{stage['id']}/release",
        headers={"If-Match": f'W/"{stage["version"]}"'},
        json={},
    )
    assert released.status_code == 200, released.text
    # It moved. Before this fix it stayed in `awaiting_release` for ever.
    assert released.json()["status"] == "ready"
    assert released.json()["held"] is False


def test_the_release_is_recorded_as_the_reason_the_work_started(domain_client, monkeypatch) -> None:
    """A resource created by a release is signed by the person, not the worker principal.

    "Who caused this run" is the question the ledger is read for, and a service principal
    on that row would answer it wrongly.
    """
    from backend_v2.app.autopilot import tasks as autopilot_tasks
    from backend_v2.app.autopilot.models import AutopilotLedgerEntry
    from backend_v2.tests.test_autopilot_formalization import _fixture_scope
    from sqlalchemy import select

    client, ids = domain_client
    campaign = _held_campaign(client, str(ids["project"]), ["wetlab"])
    monkeypatch.setattr(autopilot_tasks, "session_scope", _fixture_scope(ids))
    op = _start(client, campaign["id"], "gate-0003")
    autopilot_tasks.execute_campaign.apply(args=[campaign["id"]], task_id=op).get()
    stage = client.get(f"/api/v2/autopilot-campaigns/{campaign['id']}").json()["stages"][0]
    client.post(
        f"/api/v2/autopilot-campaigns/{campaign['id']}/stages/{stage['id']}/release",
        headers={"If-Match": f'W/"{stage["version"]}"'},
        json={},
    )

    with ids["session_factory"]() as session:
        rows = list(
            session.scalars(
                select(AutopilotLedgerEntry).where(
                    AutopilotLedgerEntry.campaign_id == uuid.UUID(campaign["id"]),
                    AutopilotLedgerEntry.event_type == "stage.released",
                )
            )
        )
    assert len(rows) == 1
    assert rows[0].writer_user_id is not None
    assert rows[0].service_principal_id is None
    assert "nothing undoes it" in rows[0].payload["reason"]
