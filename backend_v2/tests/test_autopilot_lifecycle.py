"""A stage that ends, and a campaign that moves on - or refuses to.

A stage went `pending` -> `ready` and stopped there for ever. Nothing wrote
`succeeded`, so the page reported "ready" after the work was done and the
campaign had no way to know a step was over. The missing half was not the
advancing; it was the knowing.

The tests worth keeping longest are the refusals. Advancing a campaign is the
one thing in this module that acts without a person, so what stops it matters
more than what moves it: a cancelled campaign, a taken-over campaign, and a held
stage each stop the chain, and each for a different reason.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.autopilot import adapters, gates, operators
from backend_v2.app.autopilot.models import (
    AutopilotCampaign,
    AutopilotDraft,
    AutopilotLedgerEntry,
    AutopilotStage,
)
from backend_v2.app.autopilot.service import advance_campaign, next_stage, settle_stage
from backend_v2.app.compute.models import OutboxEvent
from backend_v2.app.copilot import agent_runs
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotConfig
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()

BRIEF = "Find published PD-1 binder affinity data and save what you find"


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


def _campaign(session: Session, *, stage_keys: list[str] | None = None):
    n = next(_counter)
    user = User(username=f"life-{n}", display_name="L", role="researcher", enabled=True)
    organization = Organization(name=f"Life Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"life-{n}", project_type="protein_design"
    )
    session.add(project)
    session.flush()
    session.add(CopilotConfig(project_id=project.id, enabled_skills=["research"]))
    draft = AutopilotDraft(
        project_id=project.id,
        created_by=user.id,
        prompt=BRIEF,
        structured_brief={"text": BRIEF},
        normalized_spec={},
    )
    session.add(draft)
    session.flush()
    campaign = AutopilotCampaign(
        project_id=project.id,
        draft_id=draft.id,
        name="PD-1 campaign",
        autonomy="supervised",
        created_by=user.id,
        status="running",
        frozen_prompt=BRIEF,
        frozen_spec={"brief": {"text": BRIEF}},
    )
    session.add(campaign)
    session.flush()
    for position, key in enumerate(stage_keys or ["research", "plan"]):
        session.add(
            AutopilotStage(
                campaign_id=campaign.id,
                stage_key=key,
                position=position,
                risk_tier=gates.tier_for(key),
                operator=operators.operator_for(key),
            )
        )
    session.flush()
    return campaign, project, user


def _stages(session: Session, campaign) -> list[AutopilotStage]:
    return list(
        session.scalars(
            select(AutopilotStage)
            .where(AutopilotStage.campaign_id == campaign.id)
            .order_by(AutopilotStage.position)
        )
    )


# --- Settling -----------------------------------------------------------------


class TestSettleStage:
    def test_a_stage_records_how_it_ended(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        stage = _stages(session, campaign)[0]

        settle_stage(session, campaign, stage, status="succeeded")

        assert stage.status == "succeeded"

    def test_settling_is_written_to_the_ledger_with_its_operator(self, session: Session) -> None:
        """Who carried the step is part of how it ended."""
        campaign, _, _ = _campaign(session)
        stage = _stages(session, campaign)[0]

        settle_stage(session, campaign, stage, status="failed")

        entry = session.scalars(
            select(AutopilotLedgerEntry).where(AutopilotLedgerEntry.event_type == "stage.settled")
        ).one()
        assert entry.payload["status"] == "failed"
        assert entry.payload["operator"] == "librarian"
        # Signed by the worker principal, not by the person who confirmed the
        # campaign: attributing an automatic settlement to them answers "who
        # caused this" wrongly.
        assert entry.service_principal_id is not None
        assert entry.writer_user_id is None

    def test_a_settled_stage_is_not_re_settled(self, session: Session) -> None:
        """A second write would be a second answer to how the step ended."""
        campaign, _, _ = _campaign(session)
        stage = _stages(session, campaign)[0]

        settle_stage(session, campaign, stage, status="succeeded")
        settle_stage(session, campaign, stage, status="failed")

        assert stage.status == "succeeded"
        assert (
            len(
                list(
                    session.scalars(
                        select(AutopilotLedgerEntry).where(
                            AutopilotLedgerEntry.event_type == "stage.settled"
                        )
                    )
                )
            )
            == 1
        )

    def test_a_status_that_is_not_terminal_is_refused(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        stage = _stages(session, campaign)[0]

        with pytest.raises(DomainError, match="settles as one of"):
            settle_stage(session, campaign, stage, status="ready")


# --- Advancing ----------------------------------------------------------------


class TestAdvanceCampaign:
    def test_the_next_stage_is_activated(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        first, second = _stages(session, campaign)
        settle_stage(session, campaign, first, status="succeeded")

        reached, _ = advance_campaign(session, campaign)

        assert reached is not None and reached.id == second.id
        assert second.status == "ready"

    def test_a_finished_chain_advances_to_nothing(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        for stage in _stages(session, campaign):
            settle_stage(session, campaign, stage, status="succeeded")

        reached, resource = advance_campaign(session, campaign)

        assert reached is None and resource is None

    def test_a_cancelled_campaign_does_not_advance(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        settle_stage(session, campaign, _stages(session, campaign)[0], status="succeeded")
        campaign.status = "cancelled"

        assert advance_campaign(session, campaign) == (None, None)
        assert _stages(session, campaign)[1].status == "pending"

    def test_a_taken_over_campaign_does_not_advance(self, session: Session) -> None:
        """The exact race takeover exists to prevent: the worker moving a step on
        while somebody is correcting the products of the one before it."""
        campaign, _, _ = _campaign(session)
        settle_stage(session, campaign, _stages(session, campaign)[0], status="succeeded")
        campaign.status = "manual_takeover"

        assert advance_campaign(session, campaign) == (None, None)
        assert _stages(session, campaign)[1].status == "pending"

    def test_advancing_stops_at_a_held_stage_rather_than_stepping_over_it(
        self, session: Session
    ) -> None:
        """Arriving at the gate is advancing working, not failing."""
        campaign, _, _ = _campaign(session, stage_keys=["research", "submit", "report"])
        research, submit, report = _stages(session, campaign)
        settle_stage(session, campaign, research, status="succeeded")

        reached, resource = advance_campaign(session, campaign)

        assert reached is not None and reached.id == submit.id
        assert submit.status == "awaiting_release"
        assert submit.held is True
        assert resource is None
        assert report.status == "pending"

    def test_advancing_again_does_not_walk_past_the_gate(self, session: Session) -> None:
        """`next_stage` reads `awaiting_release` as unstarted for this reason: a
        query on `pending` alone would find the stage *behind* the hold."""
        campaign, _, _ = _campaign(session, stage_keys=["research", "submit", "report"])
        research, submit, report = _stages(session, campaign)
        settle_stage(session, campaign, research, status="succeeded")
        advance_campaign(session, campaign)

        reached, _ = advance_campaign(session, campaign)

        assert reached is not None and reached.id == submit.id
        assert report.status == "pending"

    def test_next_stage_skips_what_has_already_settled(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        first, second = _stages(session, campaign)
        settle_stage(session, campaign, first, status="failed")

        assert next_stage(session, campaign) is not None
        assert next_stage(session, campaign).id == second.id  # type: ignore[union-attr]


# --- The signal that connects them --------------------------------------------


class TestTheSettledEvent:
    def _stage_with_run(self, session: Session, campaign):
        stage = _stages(session, campaign)[0]
        resource = adapters.ensure_stage_resource(session, campaign, stage)
        assert resource is not None
        return stage, session.get(CopilotAgentRun, resource[1])

    def _settled_events(self, session: Session) -> list[OutboxEvent]:
        return list(
            session.scalars(
                select(OutboxEvent).where(OutboxEvent.topic == "copilot.agent_run.settled")
            )
        )

    def test_a_finished_run_announces_itself(self, session: Session) -> None:
        """Nothing outside the copilot could learn a run had ended. `settle_parent`
        wakes a parent run; no other domain had a signal at all."""
        campaign, _, _ = _campaign(session)
        _, run = self._stage_with_run(session, campaign)

        agent_runs.finish(session, run, status="succeeded")

        events = self._settled_events(session)
        assert [event.payload["status"] for event in events] == ["succeeded"]
        assert events[0].payload["run_id"] == str(run.id)

    def test_a_failed_run_announces_itself_too(self, session: Session) -> None:
        """Emitting on success alone is the mistake compute already made and
        recorded: the consumer left to discover failure by polling does not."""
        campaign, _, _ = _campaign(session)
        _, run = self._stage_with_run(session, campaign)

        agent_runs.finish(session, run, status="failed", error="boom")

        assert [event.payload["status"] for event in self._settled_events(session)] == ["failed"]

    def test_a_cancelled_run_announces_itself(self, session: Session) -> None:
        """Otherwise a stage whose operator was stopped waits on a run that will
        never report."""
        campaign, _, _ = _campaign(session)
        _, run = self._stage_with_run(session, campaign)

        agent_runs.cancel(session, run, reason="stopped")

        assert [event.payload["status"] for event in self._settled_events(session)] == ["cancelled"]

    def test_the_event_carries_the_project_for_the_worker_fence(self, session: Session) -> None:
        """The publisher defers an event with no project context, so a missing
        one would silently strand the whole chain."""
        campaign, project, _ = _campaign(session)
        _, run = self._stage_with_run(session, campaign)

        agent_runs.finish(session, run, status="succeeded")

        assert self._settled_events(session)[0].payload["project_id"] == str(project.id)


# --- Takeover stops the operator ----------------------------------------------


class TestTakeoverStopsTheOperator:
    def test_taking_over_cancels_the_stage_operator(self, session: Session) -> None:
        """Takeover leaves products alone by design - a compute job keeps GPU
        hours somebody already paid for. An agent run is the one product where
        that inverts: it is not a result sitting there, it is an operator still
        writing."""
        from backend_v2.app.autopilot.service import take_over_campaign

        campaign, _, user = _campaign(session)
        stage = _stages(session, campaign)[0]
        resource = adapters.ensure_stage_resource(session, campaign, stage)
        assert resource is not None
        session.flush()

        take_over_campaign(session, campaign, campaign.version, user)

        run = session.get(CopilotAgentRun, resource[1])
        assert run is not None and run.status == "cancelled"
        assert "taken over" in (run.error or "")

    def test_the_ledger_records_what_the_handover_stopped(self, session: Session) -> None:
        from backend_v2.app.autopilot.service import take_over_campaign

        campaign, _, user = _campaign(session)
        stage = _stages(session, campaign)[0]
        adapters.ensure_stage_resource(session, campaign, stage)
        session.flush()

        take_over_campaign(session, campaign, campaign.version, user)

        entry = session.scalars(
            select(AutopilotLedgerEntry).where(
                AutopilotLedgerEntry.event_type == "campaign.takeover"
            )
        ).one()
        assert entry.payload["operators_stopped"] == ["research"]

    def test_taking_over_a_campaign_with_no_operator_stops_nothing(
        self, session: Session
    ) -> None:
        from backend_v2.app.autopilot.service import take_over_campaign

        campaign, _, user = _campaign(session)

        take_over_campaign(session, campaign, campaign.version, user)

        entry = session.scalars(
            select(AutopilotLedgerEntry).where(
                AutopilotLedgerEntry.event_type == "campaign.takeover"
            )
        ).one()
        assert entry.payload["operators_stopped"] == []

    def test_taking_over_does_not_then_advance(self, session: Session) -> None:
        """Cancelling the operator emits `settled`, which is what advances a
        campaign. A takeover that advanced itself by stopping its own operator
        would be the race it exists to prevent, caused by the fix for it."""
        from backend_v2.app.autopilot.service import take_over_campaign

        campaign, _, user = _campaign(session)
        stage = _stages(session, campaign)[0]
        adapters.ensure_stage_resource(session, campaign, stage)
        session.flush()
        take_over_campaign(session, campaign, campaign.version, user)

        reached, _ = advance_campaign(session, campaign)

        assert reached is None
        assert _stages(session, campaign)[1].status == "pending"


# --- The worker that joins them -----------------------------------------------


class TestTheWorker:
    """`autopilot_stage_settled` is the join. Each half worked and nothing called
    the other, which is the shape this whole line of work keeps finding."""

    def _run_task(self, session: Session, run_id: uuid.UUID) -> dict:
        # `session_scope` opens its own session against the configured database;
        # this suite runs on an in-memory SQLite fixture, so the task body is
        # driven directly with the fixture's session. What is under test is the
        # join, not the transaction helper.
        import contextlib

        from backend_v2.app.autopilot import tasks

        @contextlib.contextmanager
        def _scope():
            yield session

        original = tasks.session_scope
        tasks.session_scope = _scope  # type: ignore[assignment]
        try:
            return tasks.stage_settled.run(str(run_id))
        finally:
            tasks.session_scope = original  # type: ignore[assignment]

    def test_a_finished_run_settles_its_stage_and_advances(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        first, second = _stages(session, campaign)
        resource = adapters.ensure_stage_resource(session, campaign, first)
        assert resource is not None
        run = session.get(CopilotAgentRun, resource[1])
        assert run is not None
        agent_runs.finish(session, run, status="succeeded")

        result = self._run_task(session, run.id)

        assert result["advanced"] is True
        assert first.status == "succeeded"
        assert second.status == "ready"

    def test_a_cancelled_run_settles_the_stage_as_cancelled_not_failed(
        self, session: Session
    ) -> None:
        """Somebody stopped it. Calling that a failure puts a fault in the record
        where a decision belongs."""
        campaign, _, _ = _campaign(session)
        first = _stages(session, campaign)[0]
        resource = adapters.ensure_stage_resource(session, campaign, first)
        assert resource is not None
        run = session.get(CopilotAgentRun, resource[1])
        assert run is not None
        agent_runs.cancel(session, run, reason="stopped")

        self._run_task(session, run.id)

        assert first.status == "cancelled"

    def test_a_run_that_is_not_a_stage_is_not_an_error(self, session: Session) -> None:
        """The topic fans out to whoever cares, and most runs are somebody typing
        in the drawer."""
        campaign, project, user = _campaign(session)
        loose = agent_runs.create_run(
            session,
            project_id=project.id,
            user_id=user.id,
            goal="just chatting",
            allowed_tools=["research_overview"],
        )

        assert self._run_task(session, loose.id)["status"] == "not_a_stage"

    def test_redelivery_settles_once_and_does_not_advance_twice(self, session: Session) -> None:
        """Celery redelivers, and advancing twice would activate the stage after
        next while the one in between had never run."""
        campaign, _, _ = _campaign(session, stage_keys=["research", "plan", "report"])
        first, second, third = _stages(session, campaign)
        resource = adapters.ensure_stage_resource(session, campaign, first)
        assert resource is not None
        run = session.get(CopilotAgentRun, resource[1])
        assert run is not None
        agent_runs.finish(session, run, status="succeeded")

        self._run_task(session, run.id)
        self._run_task(session, run.id)

        assert second.status == "ready"
        assert third.status == "pending"

    def test_the_advance_is_written_to_the_ledger(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        first = _stages(session, campaign)[0]
        resource = adapters.ensure_stage_resource(session, campaign, first)
        assert resource is not None
        run = session.get(CopilotAgentRun, resource[1])
        assert run is not None
        agent_runs.finish(session, run, status="succeeded")

        self._run_task(session, run.id)

        entry = session.scalars(
            select(AutopilotLedgerEntry).where(
                AutopilotLedgerEntry.event_type == "campaign.advanced"
            )
        ).one()
        assert entry.payload["stage_key"] == "plan"
        assert entry.payload["held"] is False

    def test_a_taken_over_campaign_settles_its_stage_but_does_not_move(
        self, session: Session
    ) -> None:
        campaign, _, _ = _campaign(session)
        first, second = _stages(session, campaign)
        resource = adapters.ensure_stage_resource(session, campaign, first)
        assert resource is not None
        run = session.get(CopilotAgentRun, resource[1])
        assert run is not None
        agent_runs.finish(session, run, status="succeeded")
        campaign.status = "manual_takeover"

        result = self._run_task(session, run.id)

        assert result["advanced"] is False
        assert first.status == "succeeded"
        assert second.status == "pending"


def test_a_campaign_with_a_stage_in_flight_does_not_start_another(session: Session) -> None:
    """One stage at a time, which `execute_campaign` has always assumed.

    Without this, a redelivered settlement advanced twice: the stage the first
    advance activated is `ready`, which `next_stage` does not count as unstarted,
    so the second found the stage *after* it and started that one while the one
    between had not run.
    """
    campaign, _, _ = _campaign(session, stage_keys=["research", "plan", "report"])
    first, second, third = _stages(session, campaign)
    settle_stage(session, campaign, first, status="succeeded")
    advance_campaign(session, campaign)
    assert second.status == "ready"

    reached, resource = advance_campaign(session, campaign)

    assert reached is None and resource is None
    assert third.status == "pending"


# --- A human step a human can finish -------------------------------------------


class TestCompleteStage:
    """The dead end that advancing made reachable.

    `review` has no automatic product by design, and `release` refuses anything
    that is not held - so a chain that reached one stopped there with no action
    available anywhere. The default campaign ends with `review`, so that was
    every default campaign.
    """

    def _complete(self, session: Session, campaign, stage, user, version=None):
        from backend_v2.app.autopilot.service import complete_stage

        return complete_stage(
            session, campaign, stage, stage.version if version is None else version, user
        )

    def test_a_person_finishes_a_human_step(self, session: Session) -> None:
        campaign, _, user = _campaign(session, stage_keys=["review", "report"])
        review, report = _stages(session, campaign)
        review.status = "ready"
        session.flush()

        self._complete(session, campaign, review, user)

        assert review.status == "succeeded"
        assert report.status == "ready"

    def test_the_person_signs_it_not_the_worker(self, session: Session) -> None:
        """A human step marked complete by a worker id reads as automatic work
        that never happened."""
        campaign, _, user = _campaign(session, stage_keys=["review", "report"])
        review = _stages(session, campaign)[0]
        review.status = "ready"
        session.flush()

        self._complete(session, campaign, review, user)

        entry = session.scalars(
            select(AutopilotLedgerEntry).where(AutopilotLedgerEntry.event_type == "stage.settled")
        ).one()
        assert entry.writer_user_id == user.id
        assert entry.service_principal_id is None
        assert entry.payload["by"] == "user"

    def test_a_stage_with_a_product_is_refused(self, session: Session) -> None:
        """Its product settles it. A second answer to "how did this end" would let
        somebody mark a step complete while its operator is still writing."""
        campaign, _, user = _campaign(session)
        stage = _stages(session, campaign)[0]
        adapters.ensure_stage_resource(session, campaign, stage)
        stage.status = "ready"
        session.flush()

        with pytest.raises(DomainError, match="which settles it"):
            self._complete(session, campaign, stage, user)

    def test_a_held_stage_is_released_not_completed(self, session: Session) -> None:
        """Two different questions. A release says *may this act*; completing says
        *is this done*."""
        campaign, _, user = _campaign(session, stage_keys=["submit"])
        stage = _stages(session, campaign)[0]
        stage.status = "awaiting_release"
        session.flush()

        with pytest.raises(DomainError, match="release it rather than completing it"):
            self._complete(session, campaign, stage, user)

    def test_a_stage_that_has_not_started_is_refused(self, session: Session) -> None:
        campaign, _, user = _campaign(session, stage_keys=["review"])
        stage = _stages(session, campaign)[0]

        with pytest.raises(DomainError, match="has not started"):
            self._complete(session, campaign, stage, user)

    def test_a_stale_version_is_refused(self, session: Session) -> None:
        campaign, _, user = _campaign(session, stage_keys=["review"])
        stage = _stages(session, campaign)[0]
        stage.status = "ready"
        session.flush()

        with pytest.raises(DomainError, match="Autopilot stage changed") as raised:
            self._complete(session, campaign, stage, user, version=stage.version + 5)

        assert raised.value.error_code == "version_conflict"
        assert raised.value.status_code == 412

    def test_completing_twice_is_idempotent(self, session: Session) -> None:
        campaign, _, user = _campaign(session, stage_keys=["review", "report"])
        review = _stages(session, campaign)[0]
        review.status = "ready"
        session.flush()

        self._complete(session, campaign, review, user)
        self._complete(session, campaign, review, user)

        assert (
            len(
                list(
                    session.scalars(
                        select(AutopilotLedgerEntry).where(
                            AutopilotLedgerEntry.event_type == "stage.settled"
                        )
                    )
                )
            )
            == 1
        )

    def test_a_cancelled_campaign_has_no_step_to_complete(self, session: Session) -> None:
        campaign, _, user = _campaign(session, stage_keys=["review"])
        stage = _stages(session, campaign)[0]
        stage.status = "ready"
        campaign.status = "cancelled"
        session.flush()

        with pytest.raises(DomainError, match="has no stage to complete"):
            self._complete(session, campaign, stage, user)


class TestCampaignFinishes:
    """A campaign stayed `running` after its last stage, because nothing ever
    reached the end. Now that the chain moves, "running" on a campaign with every
    stage settled is a status that means nothing and a page inviting someone to
    wait for a step that will not come."""

    def test_the_last_stage_finishes_the_campaign(self, session: Session) -> None:
        campaign, _, user = _campaign(session, stage_keys=["review"])
        stage = _stages(session, campaign)[0]
        stage.status = "ready"
        session.flush()
        from backend_v2.app.autopilot.service import complete_stage

        complete_stage(session, campaign, stage, stage.version, user)

        assert campaign.status == "succeeded"

    def test_a_chain_that_lost_a_step_did_not_succeed(self, session: Session) -> None:
        """The campaign's outcome is not the last stage's. Reporting otherwise
        would make the ledger the only place the failure survived."""
        from backend_v2.app.autopilot.service import complete_stage, settle_stage

        campaign, _, user = _campaign(session, stage_keys=["review", "report"])
        review, report = _stages(session, campaign)
        settle_stage(session, campaign, review, status="failed")
        report.status = "ready"
        session.flush()

        complete_stage(session, campaign, report, report.version, user)

        assert campaign.status == "failed"

    def test_a_campaign_with_work_left_is_not_finished(self, session: Session) -> None:
        from backend_v2.app.autopilot.service import finish_campaign

        campaign, _, _ = _campaign(session)

        finish_campaign(session, campaign)

        assert campaign.status == "running"

    def test_a_cancelled_campaign_is_not_overwritten(self, session: Session) -> None:
        from backend_v2.app.autopilot.service import finish_campaign

        campaign, _, _ = _campaign(session)
        for stage in _stages(session, campaign):
            stage.status = "cancelled"
        campaign.status = "cancelled"
        session.flush()

        finish_campaign(session, campaign)

        assert campaign.status == "cancelled"


def test_a_released_stage_is_then_completed_by_hand(session: Session) -> None:
    """The full path for a held human step, which is two different signatures.

    `submit` is held and has no operator, so a person releases it (*may this
    act*) and later marks it done (*is this done*). `complete_stage` refuses a
    held stage, and release is what clears the hold - so the order is forced and
    neither signature stands in for the other.
    """
    from backend_v2.app.autopilot.service import complete_stage, release_stage

    campaign, _, user = _campaign(session, stage_keys=["submit", "report"])
    submit, report = _stages(session, campaign)
    submit.status = "awaiting_release"
    session.flush()

    release_stage(session, campaign, submit, user, submit.version)
    assert submit.held is False
    assert submit.status == "ready"

    complete_stage(session, campaign, submit, submit.version, user)

    assert submit.status == "succeeded"
    assert report.status == "ready"


def test_completing_a_step_whose_successor_is_held_stops_at_the_gate(
    session: Session,
) -> None:
    """A person finishing one step does not thereby approve the next."""
    from backend_v2.app.autopilot.service import complete_stage

    campaign, _, user = _campaign(session, stage_keys=["review", "submit"])
    review, submit = _stages(session, campaign)
    review.status = "ready"
    session.flush()

    complete_stage(session, campaign, review, review.version, user)

    assert submit.status == "awaiting_release"
    assert submit.held is True
    entry = session.scalars(
        select(AutopilotLedgerEntry).where(AutopilotLedgerEntry.event_type == "campaign.advanced")
    ).one()
    assert entry.payload["held"] is True
    assert entry.writer_user_id == user.id


def test_a_workflow_draft_stage_is_finished_by_the_person_who_finished_it(
    session: Session,
) -> None:
    """The dead end one stage past `review`.

    `complete_stage` first refused every stage with a product. Only an agent run
    ends its own stage; a `workflow_run` is a *draft* the adapter hands to a
    person to open and finish, so nothing was ever going to settle it and the
    chain stopped at the first `compute` stage with no action available.
    """
    from backend_v2.app.autopilot.service import complete_stage

    campaign, _, user = _campaign(session, stage_keys=["compute", "report"])
    compute, report = _stages(session, campaign)
    compute.resource_type, compute.resource_id = "workflow_run", uuid.uuid4()
    compute.status = "ready"
    session.flush()

    complete_stage(session, campaign, compute, compute.version, user)

    assert compute.status == "succeeded"
    assert report.status == "ready"


def test_a_stage_carrying_an_agent_run_is_still_refused(session: Session) -> None:
    """The narrowing is to `SELF_SETTLING_RESOURCE_TYPES`, not a removal."""
    from backend_v2.app.autopilot.service import complete_stage

    campaign, _, user = _campaign(session)
    stage = _stages(session, campaign)[0]
    adapters.ensure_stage_resource(session, campaign, stage)
    stage.status = "ready"
    session.flush()

    with pytest.raises(DomainError, match="which settles it"):
        complete_stage(session, campaign, stage, stage.version, user)
