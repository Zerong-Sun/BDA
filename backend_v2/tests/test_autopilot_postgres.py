"""The two Autopilot claims that only a real PostgreSQL can settle.

Everything else in the Autopilot suite runs on SQLite against one session, which is fine
for logic and useless for the two properties that are about the *database*:

* the budget hard limit under genuine concurrency - SQLite has no ``SELECT ... FOR
  UPDATE``, so a single-session test proves the arithmetic and nothing about the lock;
* row-level security - SQLite has no RLS at all, and the owner role bypasses it, so both
  the policy and the role have to be real.

`docs/DUAL_MODE_OPERATION_PLAN.md` listed both as not covered. They are covered here.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from backend_v2.app.autopilot.models import (
    AutopilotCampaign,
    AutopilotDraft,
    AutopilotLedgerEntry,
    BudgetReservation,
    CampaignBudget,
)
from backend_v2.app.autopilot.schemas import AutopilotStart
from backend_v2.app.autopilot.service import start_campaign
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

pytestmark = pytest.mark.skipif(
    os.getenv("BDA_V2_RUN_DB_TESTS") != "1",
    reason="PostgreSQL integration test disabled",
)

#: Two arms, each asking for more than half the limit, so at most one can win.
GPU_LIMIT = 1000
GPU_PER_ARM = 400
ARMS = 8


class _Fixture:
    """A campaign with a hard budget, and the ids needed to clean up after it."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.factory = sessionmaker(engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:8]
        with self.factory() as session:
            self.user = User(username=f"ap-{suffix}", display_name="Autopilot user", role="researcher")
            self.organization = Organization(name=f"Autopilot org {suffix}")
            session.add_all([self.user, self.organization])
            session.flush()
            session.add(
                OrganizationMember(
                    organization_id=self.organization.id, user_id=self.user.id, role="owner"
                )
            )
            self.project = Project(
                organization_id=self.organization.id,
                owner_id=self.user.id,
                name=f"Autopilot project {suffix}",
                project_type="protein_design",
            )
            session.add(self.project)
            session.flush()
            draft = AutopilotDraft(
                project_id=self.project.id,
                created_by=self.user.id,
                prompt="concurrency fixture",
                structured_brief={},
                normalized_spec={"stages": ["compute", "review"]},
            )
            session.add(draft)
            session.flush()
            self.campaign = AutopilotCampaign(
                project_id=self.project.id,
                draft_id=draft.id,
                created_by=self.user.id,
                name=f"Contended {suffix}",
                autonomy="supervised",
                status="confirmed",
                frozen_prompt="concurrency fixture",
                frozen_spec={"stages": ["compute", "review"]},
            )
            session.add(self.campaign)
            session.flush()
            session.add(
                CampaignBudget(campaign_id=self.campaign.id, gpu_seconds_limit=GPU_LIMIT)
            )
            session.commit()
            self.campaign_id = self.campaign.id
            self.project_id = self.project.id
            self.user_id = self.user.id
            self.organization_id = self.organization.id

    def cleanup(self) -> None:
        with self.factory() as session:
            session.execute(
                text("delete from autopilot_campaigns where project_id = :p"),
                {"p": str(self.project_id)},
            )
            session.execute(
                text("delete from autopilot_drafts where project_id = :p"), {"p": str(self.project_id)}
            )
            session.execute(text("delete from projects where id = :p"), {"p": str(self.project_id)})
            session.execute(
                text("delete from organization_members where user_id = :u"), {"u": str(self.user_id)}
            )
            session.execute(
                text("delete from organizations where id = :o"), {"o": str(self.organization_id)}
            )
            session.execute(text("delete from users where id = :u"), {"u": str(self.user_id)})
            session.commit()


@pytest.fixture
def fixture():
    engine = create_engine(get_settings().database_url)
    made = _Fixture(engine)
    try:
        yield made
    finally:
        made.cleanup()
        engine.dispose()


def test_concurrent_reservations_never_exceed_the_hard_limit(fixture) -> None:
    """Eight threads race for a budget that fits two of them.

    A single-session test cannot tell a working lock from a missing one - the arithmetic
    is identical either way - so this is the only place the hard limit is actually tested.
    Separate connections, real contention.

    Writing it turned up how the guard is really composed. Two mechanisms protect the
    limit and they fire in this order:

    1. `_reserve_budget` takes `SELECT ... FOR UPDATE` on the budget row, so the arithmetic
       is serialised and anything over the limit is refused with `campaign_budget_exceeded`;
    2. `start_campaign` then bumps `campaign.version`, and SQLAlchemy's version check lets
       exactly one concurrent transaction through - the rest raise `StaleDataError` and roll
       back, taking their reservation with them.

    So under same-campaign contention the version check, not the budget lock, is usually
    what refuses. Both are real refusals, and the assertion below is the property that
    matters either way: the limit is never exceeded, and no reservation row survives a
    transaction that rolled back.
    """

    def reserve(index: int) -> str:
        with fixture.factory() as session:
            campaign = session.get(AutopilotCampaign, fixture.campaign_id)
            user = session.get(User, fixture.user_id)
            try:
                start_campaign(
                    session,
                    campaign,
                    AutopilotStart(
                        idempotency_key=f"race-{index:04d}",
                        gpu_seconds=GPU_PER_ARM,
                        money_micros=0,
                    ),
                    user,
                )
                session.commit()
                return "reserved"
            except DomainError as error:
                session.rollback()
                return error.error_code
            except StaleDataError:
                # Another transaction bumped the campaign version first.
                session.rollback()
                return "stale"
            except DBAPIError:
                # A serialization failure is a refusal too: the row was taken by another
                # transaction. Counting it as success is what would hide a real bug.
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=ARMS) as pool:
        outcomes = list(pool.map(reserve, range(ARMS)))

    reserved = outcomes.count("reserved")
    # At least one thread must get through - a test where everything fails proves nothing.
    assert reserved >= 1, outcomes
    # 1000 / 400 = 2 whole arms, and nothing may push past that.
    assert reserved <= GPU_LIMIT // GPU_PER_ARM, outcomes
    assert set(outcomes) - {"reserved"} <= {
        "campaign_budget_exceeded",
        "stale",
        "conflict",
    }, outcomes

    with fixture.factory() as session:
        budget = session.scalar(
            select(CampaignBudget).where(CampaignBudget.campaign_id == fixture.campaign_id)
        )
        assert budget.gpu_seconds_reserved == reserved * GPU_PER_ARM
        assert budget.gpu_seconds_reserved + budget.gpu_seconds_committed <= GPU_LIMIT
        rows = session.scalar(
            select(func.count())
            .select_from(BudgetReservation)
            .where(BudgetReservation.campaign_id == fixture.campaign_id)
        )
        # Every refusal rolled back cleanly; no orphan reservation rows behind them.
        assert rows == reserved


def test_the_same_idempotency_key_under_contention_yields_one_reservation(fixture) -> None:
    """A retried request is not a second request, however many threads send it at once."""

    def reserve(_: int) -> str:
        with fixture.factory() as session:
            campaign = session.get(AutopilotCampaign, fixture.campaign_id)
            user = session.get(User, fixture.user_id)
            try:
                start_campaign(
                    session,
                    campaign,
                    AutopilotStart(idempotency_key="retried-once", gpu_seconds=100, money_micros=0),
                    user,
                )
                session.commit()
                return "ok"
            except (DomainError, DBAPIError):
                session.rollback()
                return "refused"

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(reserve, range(6)))

    with fixture.factory() as session:
        rows = session.scalar(
            select(func.count())
            .select_from(BudgetReservation)
            .where(BudgetReservation.campaign_id == fixture.campaign_id)
        )
        budget = session.scalar(
            select(CampaignBudget).where(CampaignBudget.campaign_id == fixture.campaign_id)
        )
        assert rows == 1
        assert budget.gpu_seconds_reserved == 100


def test_a_worker_confined_to_one_project_cannot_see_another_projects_campaign(fixture) -> None:
    """The confinement `AUTOPILOT_CAMPAIGNS.md` §5 states, checked against the database.

    `0049` fenced these tables when it created them, but only through `bda.user_id`;
    `0051` later added the `bda.worker_project_id` branch to every other project table and
    did not reach these. The failure that leaves is the reverse of a leak: a worker
    confined to its *own* project could not see the campaign it was sent to execute, which
    only started to matter when the stage adapter made a worker read one. `0055` adds the
    missing branch, and both halves are asserted below - pinned elsewhere sees nothing,
    pinned to its own project sees exactly its own campaign.
    """
    role = f"bda_test_ap_{uuid.uuid4().hex}"
    engine = fixture.engine
    with Session(engine, expire_on_commit=False) as owner:
        elsewhere = Project(
            organization_id=fixture.organization_id,
            owner_id=fixture.user_id,
            name=f"Elsewhere {uuid.uuid4().hex[:6]}",
            project_type="protein_design",
        )
        owner.add(elsewhere)
        owner.commit()
        elsewhere_id = elsewhere.id

    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOBYPASSRLS'))
            connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            connection.execute(
                text(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON autopilot_campaigns, '
                    'autopilot_drafts, autopilot_ledger_entries, autopilot_stages, '
                    'autopilot_campaign_budgets, autopilot_budget_reservations, '
                    f'projects, organization_members TO "{role}"'
                )
            )

        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text(f'SET LOCAL ROLE "{role}"'))

            # A worker pinned to an unrelated project sees no campaigns at all.
            connection.execute(
                text("select set_config('bda.worker_project_id', :p, true)"),
                {"p": str(elsewhere_id)},
            )
            assert list(connection.scalars(select(AutopilotCampaign.id))) == []

            # Pinned to its own project, it sees exactly its own campaign.
            connection.execute(
                text("select set_config('bda.worker_project_id', :p, true)"),
                {"p": str(fixture.project_id)},
            )
            assert set(connection.scalars(select(AutopilotCampaign.id))) == {fixture.campaign_id}

            # Children are fenced through the parent campaign, not by a copied project id.
            assert list(connection.scalars(select(CampaignBudget.campaign_id))) == [
                fixture.campaign_id
            ]

            # And it cannot write a ledger entry against a campaign it cannot see.
            connection.execute(
                text("select set_config('bda.worker_project_id', :p, true)"),
                {"p": str(elsewhere_id)},
            )
            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(
                        AutopilotLedgerEntry.__table__.insert().values(
                            campaign_id=fixture.campaign_id,
                            event_type="campaign.forged",
                            payload={},
                        )
                    )
            transaction.rollback()
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP OWNED BY "{role}"'))
            connection.execute(text(f'DROP ROLE "{role}"'))
            connection.execute(text("delete from projects where id = :p"), {"p": str(elsewhere_id)})
