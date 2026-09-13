"""Who carries each stage of a campaign, and what that does and does not grant.

`gates.py` answers whether a step may act without a person; this answers whose
job it is when it does. A campaign is the platform's own name for running the
research phases in order, and until this mapping existed it was the one place
those phases ran with none of the roster's charters applying.

The tests worth keeping longest are the ones about what the mapping is *not*:
it grants nothing, it is frozen at confirmation rather than looked up later, and
a stage whose operator has nothing enabled produces no run instead of an
operator that looks broken.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.autopilot import adapters, gates, operators
from backend_v2.app.autopilot.models import AutopilotCampaign, AutopilotDraft, AutopilotStage
from backend_v2.app.copilot import bots
from backend_v2.app.copilot.capabilities import normalize_capabilities, tools_for_capabilities
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotConfig
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()

#: A person's own words, written into the draft and confirmed. The run an
#: automatic stage opens is authorised by this and by nothing the platform wrote.
BRIEF = "Find published PD-1 binder affinity data and save what you find"


# --- The declaration ---------------------------------------------------------


class TestTheMapping:
    def test_every_staffed_stage_names_a_real_operator(self) -> None:
        for stage_key, bot_id in operators.STAGE_OPERATORS.items():
            assert bots.get(bot_id) is not None, (stage_key, bot_id)

    def test_a_stage_is_carried_by_a_producer(self) -> None:
        """A reviewer or a director carrying a step would be doing the work its
        own stance forbids - `bots._validate_roster`'s rule, restated where a
        second mapping could break it."""
        for stage_key, bot_id in operators.STAGE_OPERATORS.items():
            assert bots.require(bot_id).stance == "produce", (stage_key, bot_id)

    def test_an_unstaffed_stage_says_why_rather_than_reading_as_a_gap(self) -> None:
        assert "review" in operators.UNSTAFFED
        assert operators.operator_for("review") is None
        assert "person's judgement" in operators.explain("review")

    def test_an_unclassified_stage_is_distinguishable_from_a_deliberate_one(self) -> None:
        """The same distinction `gates.UNKNOWN_TIER` draws for risk."""
        assert operators.operator_for("frobnicate") is None
        assert "not a classified stage" in operators.explain("frobnicate")
        assert "not a classified stage" not in operators.explain("review")

    def test_no_stage_is_both_staffed_and_declared_unstaffed(self) -> None:
        assert not (set(operators.STAGE_OPERATORS) & set(operators.UNSTAFFED))

    def test_every_held_stage_is_unstaffed(self) -> None:
        """A step a person has to release has no default operator.

        Naming one would be the platform deciding who carries a risk it has just
        said a human must accept.
        """
        for stage_key in operators.STAGE_OPERATORS:
            assert gates.is_held(stage_key) is False, stage_key

    def test_the_compute_stage_is_carried_by_the_operator_that_drafts(self) -> None:
        """`planner`, not `runner`, and the tier says why.

        `compute` is `reversible_draft` because its adapter creates a workflow
        run that stays a draft. `runner` becomes accountable when a person
        confirms it, which the campaign does not do.
        """
        assert operators.operator_for("compute") == "planner"
        assert gates.tier_for("compute") == "reversible_draft"

    def test_lookup_is_case_and_whitespace_insensitive(self) -> None:
        assert operators.operator_for("  Research ") == "librarian"

    def test_a_stage_naming_a_non_producer_fails_the_import_guard(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(operators, "STAGE_OPERATORS", {"research": "auditor"})

        with pytest.raises(ValueError, match="carried by a producer"):
            operators._validate()

    def test_a_stage_naming_an_unknown_operator_fails_the_import_guard(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(operators, "STAGE_OPERATORS", {"research": "ghost"})

        with pytest.raises(ValueError, match="unknown operator"):
            operators._validate()


# --- The adapter -------------------------------------------------------------


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


def _campaign(session: Session, *, enabled_skills: list[str] | None = None):
    n = next(_counter)
    user = User(username=f"ap-{n}", display_name="A", role="researcher", enabled=True)
    organization = Organization(name=f"AP Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"ap-{n}", project_type="protein_design"
    )
    session.add(project)
    session.flush()
    session.add(
        CopilotConfig(project_id=project.id, enabled_skills=enabled_skills or ["research"])
    )
    draft = AutopilotDraft(
        project_id=project.id,
        created_by=user.id,
        prompt=BRIEF,
        structured_brief={"text": BRIEF},
        normalized_spec={"stages": [{"key": "research"}]},
    )
    session.add(draft)
    session.flush()
    campaign = AutopilotCampaign(
        project_id=project.id,
        draft_id=draft.id,
        name="PD-1 campaign",
        autonomy="supervised",
        created_by=user.id,
        frozen_prompt=BRIEF,
        frozen_spec={"brief": {"text": BRIEF}, "stages": [{"key": "research"}]},
    )
    session.add(campaign)
    session.flush()
    return campaign, project, user


def _stage(session: Session, campaign, *, stage_key: str = "research", operator=...):
    stage = AutopilotStage(
        campaign_id=campaign.id,
        stage_key=stage_key,
        position=0,
        risk_tier=gates.tier_for(stage_key),
        operator=operators.operator_for(stage_key) if operator is ... else operator,
    )
    session.add(stage)
    session.flush()
    return stage


class TestTheStageOpensARun:
    def test_a_research_stage_opens_a_run_owned_by_its_operator(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign)

        resource = adapters.ensure_stage_resource(session, campaign, stage)

        assert resource is not None
        kind, run_id = resource
        assert kind == "copilot_agent_run"
        run = session.get(CopilotAgentRun, run_id)
        assert run is not None and run.bot == "librarian"
        assert (stage.resource_type, stage.resource_id) == ("copilot_agent_run", run.id)

    def test_the_run_is_authorised_by_the_persons_brief(self, session: Session) -> None:
        """The sharpest rule here, and the same one delegation obeys.

        `agent_loop.authorising_text` reads the run's goal, and the write-intent
        gate reads that. A goal this module composed would be the platform
        writing the user's half of the conversation - so the brief is reproduced
        and the stage key is a label on it, nothing more.
        """
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign)

        _, run_id = adapters.ensure_stage_resource(session, campaign, stage)  # type: ignore[misc]

        run = session.get(CopilotAgentRun, run_id)
        assert run is not None
        assert BRIEF in run.goal
        assert run.goal.startswith("[research] ")

    def test_the_runs_tools_are_the_operator_intersected_with_the_project(
        self, session: Session
    ) -> None:
        """A stage grants nothing the project has not enabled."""
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign)

        _, run_id = adapters.ensure_stage_resource(session, campaign, stage)  # type: ignore[misc]

        run = session.get(CopilotAgentRun, run_id)
        assert run is not None
        assert set(run.allowed_tools) == tools_for_capabilities(
            bots.capabilities_for_bot("librarian", normalize_capabilities(["research"]))
        )

    def test_the_run_is_dispatched_rather_than_left_for_a_sweep(self, session: Session) -> None:
        """Nothing looks at a `running` run no worker was told about - the
        deadlock delegation had."""
        from backend_v2.app.compute.models import OutboxEvent

        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign)

        _, run_id = adapters.ensure_stage_resource(session, campaign, stage)  # type: ignore[misc]

        dispatched = [
            str(row.payload.get("run_id"))
            for row in session.scalars(
                select(OutboxEvent).where(OutboxEvent.topic == "copilot.agent_step")
            )
        ]
        assert dispatched == [str(run_id)]

    def test_a_redelivered_stage_reuses_its_run(self, session: Session) -> None:
        """Celery redelivers, and a second operator working the same step would
        be two operators disagreeing with nothing reporting it."""
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign)

        first = adapters.ensure_stage_resource(session, campaign, stage)
        second = adapters.ensure_stage_resource(session, campaign, stage)

        assert first == second
        assert (
            len(list(session.scalars(select(CopilotAgentRun).where(CopilotAgentRun.bot == "librarian"))))
            == 1
        )

    def test_an_unstaffed_stage_opens_no_run(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign, stage_key="review")

        assert adapters.ensure_stage_resource(session, campaign, stage) is None

    def test_a_stage_confirmed_before_the_column_existed_opens_no_run(
        self, session: Session
    ) -> None:
        """NULL is a real state, not a reason to fall back to today's mapping.

        Staffing it now would run a campaign a person approved as unstaffed.
        """
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign, operator=None)

        assert adapters.ensure_stage_resource(session, campaign, stage) is None

    def test_a_stage_naming_a_retired_operator_opens_no_run(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign, operator="ghost")

        assert adapters.ensure_stage_resource(session, campaign, stage) is None

    def test_an_operator_with_nothing_enabled_opens_no_run(self, session: Session) -> None:
        """Rather than a run with no tools, which reads as a failed operator."""
        campaign, _, _ = _campaign(session, enabled_skills=["structure"])
        stage = _stage(session, campaign)

        assert adapters.ensure_stage_resource(session, campaign, stage) is None


class TestWhatTheStageReports:
    def test_a_staffed_stage_explains_who_carries_it(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign)

        assert stage.operator == "librarian"
        assert "librarian" in (stage.operator_reason or "")

    def test_the_reason_comes_from_the_stored_operator_not_the_current_mapping(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A campaign confirmed under an older staffing keeps reading as the
        campaign that was approved."""
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign)
        monkeypatch.setattr(operators, "STAGE_OPERATORS", {"research": "scout"})

        assert "librarian" in (stage.operator_reason or "")

    def test_a_retired_operator_is_named_rather_than_hidden(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign, operator="ghost")

        assert "no longer has" in (stage.operator_reason or "")

    def test_an_unstaffed_stage_explains_itself_too(self, session: Session) -> None:
        campaign, _, _ = _campaign(session)
        stage = _stage(session, campaign, stage_key="review")

        assert "person's judgement" in (stage.operator_reason or "")
