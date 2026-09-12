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
