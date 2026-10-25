"""Offline admission ledger tests; optional PostgreSQL uses an isolated schema."""
from __future__ import annotations

import hashlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import call_guard
from backend_v2.app.copilot.models import CopilotCallBudget, CopilotCallReservation
from backend_v2.app.core.problem import DomainError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

TABLES = [CopilotCallBudget.__table__, CopilotCallReservation.__table__]


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'ledger.db'}")
    for table in TABLES:
        table.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(call_guard, "_session", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def configured():
    return SimpleNamespace(id=uuid.uuid4(), model="offline-model", endpoint="https://provider.invalid/v1",
                           config={"bda_pricing": {
                               "model": "offline-model", "endpoint": "https://provider.invalid/v1",
                               "checked_at": datetime.now(UTC).isoformat(),
                               "input_cny_per_million": "0.1", "output_cny_per_million": "0.2"}})


def body(index=0, **extra):
    return {"model": "offline-model", "messages": [{"role": "user", "content": f"Offline request {index}"}], **extra}


def _hash(scope):
    return hashlib.sha256(scope.encode()).hexdigest()


def test_six_actual_reservations_share_a_durable_scope_and_seventh_is_denied(ledger, configured):
    with call_guard.call_scope("one-task", max_calls=100):
        receipts = [call_guard.reserve_call(configured, body(i)) for i in range(6)]
        with pytest.raises(DomainError) as caught:
            call_guard.reserve_call(configured, body(6))
    assert caught.value.error_code == "llm_call_limit"
    assert len(set(receipts)) == 6
    with ledger() as session:
        budget = session.get(CopilotCallBudget, _hash("one-task"))
        assert budget.calls == budget.max_calls == 6
        assert session.scalar(select(func.count()).select_from(CopilotCallReservation)) == 6


def test_one_yuan_ceiling_is_cny_and_rejected_attempt_is_not_counted(ledger, configured):
    configured.config["bda_pricing"].update(input_cny_per_million="60", output_cny_per_million="60")
    with call_guard.call_scope("cost-cap"):
        receipt = call_guard.reserve_call(configured, body(1))
        with pytest.raises(DomainError) as caught:
            call_guard.reserve_call(configured, body(2))
    assert caught.value.error_code == "llm_budget_exhausted"
    with ledger() as session:
        budget = session.get(CopilotCallBudget, receipt[0])
        assert budget.calls == 1
        assert 500_000 < budget.reserved_cny_micros <= 1_000_000
        assert budget.reserved_cny_micros == session.get(CopilotCallReservation, receipt).reserved_cny_micros


def test_missing_scope_or_prices_never_creates_a_reservation(ledger, configured):
    with pytest.raises(DomainError) as caught:
        call_guard.reserve_call(configured, body())
    assert caught.value.error_code == "llm_scope_required"
    configured.config = {}
    with call_guard.call_scope("unknown-price"), pytest.raises(DomainError) as caught:
        call_guard.reserve_call(configured, body())
    assert caught.value.error_code == "llm_pricing_required"
    with ledger() as session:
        assert session.scalar(select(func.count()).select_from(CopilotCallBudget)) == 0


@pytest.mark.parametrize("field,value", [
    ("input_cny_per_million", "NaN"), ("output_cny_per_million", "Infinity"),
    ("input_cny_per_million", "-1"), ("output_cny_per_million", "0"),
    ("input_cny_per_million", True), ("model", "different-model"),
    ("endpoint", "https://another.invalid/v1"), ("checked_at", "not-a-date"),
    ("checked_at", (datetime.now(UTC) - timedelta(days=31)).isoformat()),
    ("checked_at", (datetime.now(UTC) + timedelta(days=1)).isoformat()),
    ("checked_at", datetime.now().isoformat()),
])
def test_invalid_unverified_or_stale_prices_are_fail_closed(ledger, configured, field, value):
    configured.config["bda_pricing"][field] = value
    with call_guard.call_scope("invalid-price"), pytest.raises(DomainError) as caught:
        call_guard.reserve_call(configured, body())
    assert caught.value.error_code == "llm_pricing_required"


def test_duplicate_after_scope_reentry_is_denied_without_a_second_charge(ledger, configured):
    with call_guard.call_scope("duplicate"):
        receipt = call_guard.reserve_call(configured, body())
    with call_guard.call_scope("duplicate"), pytest.raises(DomainError) as caught:
        call_guard.reserve_call(configured, body())
    assert caught.value.error_code == "llm_duplicate_call"
    with ledger() as session:
        budget = session.get(CopilotCallBudget, receipt[0])
        assert budget.calls == 1
        assert budget.reserved_cny_micros == session.get(CopilotCallReservation, receipt).reserved_cny_micros


def test_reservation_survives_unrelated_outer_transaction_rollback(ledger, configured):
    business = create_engine("sqlite+pysqlite://")
    try:
        with business.begin() as connection:
            connection.execute(text("CREATE TABLE work (value INTEGER)"))
        with Session(business) as outer:
            outer.execute(text("INSERT INTO work VALUES (1)"))
            with call_guard.call_scope("outer-rollback"):
                receipt = call_guard.reserve_call(configured, body())
            outer.rollback()
            assert outer.scalar(text("SELECT count(*) FROM work")) == 0
        with ledger() as session:
            assert session.get(CopilotCallReservation, receipt) is not None
            assert session.get(CopilotCallBudget, receipt[0]).calls == 1
    finally:
        business.dispose()


def test_legacy_calls_without_ledger_consume_unknown_cost_allowance(ledger, configured):
    with call_guard.call_scope("legacy", initial_calls=1), pytest.raises(DomainError) as caught:
        call_guard.reserve_call(configured, body())
    assert caught.value.error_code == "llm_budget_exhausted"
    with ledger() as session:
        budget = session.get(CopilotCallBudget, _hash("legacy"))
        assert budget.calls == 1
        assert budget.reserved_cny_micros == 1_000_000
        assert session.scalar(select(func.count()).select_from(CopilotCallReservation)) == 0


def test_existing_ledger_does_not_double_charge_legacy_initial_count(ledger, configured):
    with call_guard.call_scope("tracked"):
        receipt = call_guard.reserve_call(configured, body(1))
    with call_guard.call_scope("tracked", initial_calls=100):
        call_guard.reserve_call(configured, body(2))
    with ledger() as session:
        budget = session.get(CopilotCallBudget, receipt[0])
        assert budget.calls == 2 and budget.reserved_cny_micros < 1_000_000


def test_nested_scope_uses_parent_identity_and_can_only_narrow(ledger, configured):
    with call_guard.call_scope("parent"):
        with call_guard.call_scope("child", max_calls=1):
            assert call_guard.current_scope_id() == "parent"
            call_guard.reserve_call(configured, body(1))
        assert call_guard.current_scope_id() == "parent"
        with call_guard.call_scope("other-child", max_calls=100), pytest.raises(DomainError) as caught:
            call_guard.reserve_call(configured, body(2))
        assert caught.value.error_code == "llm_call_limit"
    assert call_guard.current_scope_id() is None
    with ledger() as session:
        assert session.scalar(select(func.count()).select_from(CopilotCallBudget)) == 1


def test_nested_task_scope_carries_legacy_calls_past_an_empty_outer_header_scope(ledger, configured):
    with call_guard.call_scope("task-header", initial_calls=0):
        with call_guard.call_scope("nested-task", initial_calls=3), pytest.raises(DomainError) as caught:
            call_guard.reserve_call(configured, body())
        assert caught.value.error_code == "llm_budget_exhausted"
        with pytest.raises(DomainError) as caught:
            call_guard.reserve_call(configured, body(1))
        assert caught.value.error_code == "llm_budget_exhausted"
    with ledger() as session:
        budget = session.get(CopilotCallBudget, _hash("task-header"))
        assert budget.calls == 3 and budget.reserved_cny_micros == 1_000_000
        assert session.scalar(select(func.count()).select_from(CopilotCallBudget)) == 1


def test_nested_legacy_count_does_not_recharge_an_existing_durable_ledger(ledger, configured):
    with call_guard.call_scope("tracked-parent"):
        receipt = call_guard.reserve_call(configured, body(1))
        with call_guard.call_scope("nested", initial_calls=100):
            call_guard.reserve_call(configured, body(2))
    with ledger() as session:
        budget = session.get(CopilotCallBudget, receipt[0])
        assert budget.calls == 2 and budget.reserved_cny_micros < 1_000_000


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": True, "completion_tokens": -1},
                                  {"prompt_tokens": "20", "completion_tokens": 2_000_000_001}])
def test_unknown_invalid_usage_is_not_treated_as_free(ledger, configured, usage):
    with call_guard.call_scope("usage"):
        receipt = call_guard.reserve_call(configured, body())
    call_guard.record_usage(receipt, usage)
    with ledger() as session:
        row = session.get(CopilotCallReservation, receipt)
        assert row.input_tokens is None and row.output_tokens is None
        assert row.reserved_cny_micros > 0


def test_valid_usage_is_measured_but_does_not_refund_admission(ledger, configured):
    with call_guard.call_scope("usage"):
        receipt = call_guard.reserve_call(configured, body())
    with ledger() as session:
        reserved = session.get(CopilotCallReservation, receipt).reserved_cny_micros
    call_guard.record_usage(receipt, {"prompt_tokens": 101, "completion_tokens": 0, "total_tokens": 101})
    with ledger() as session:
        row = session.get(CopilotCallReservation, receipt)
        assert (row.input_tokens, row.output_tokens) == (101, 0)
        assert row.reserved_cny_micros == reserved
        assert session.get(CopilotCallBudget, receipt[0]).reserved_cny_micros == reserved


@pytest.mark.parametrize("extra,key", [({}, "max_tokens"), ({"max_tokens": 16384}, "max_tokens"),
                                      ({"max_completion_tokens": 16384, "max_tokens": 99999}, "max_completion_tokens")])
def test_effective_output_ceiling_is_reserved_and_sent(ledger, configured, extra, key):
    request = body(**extra)
    with call_guard.call_scope("output-cap"):
        call_guard.reserve_call(configured, request)
    assert request[key] == 4096
    if key == "max_completion_tokens":
        assert "max_tokens" not in request


@pytest.mark.parametrize("limit", [0, -1, True, "1000"])
def test_invalid_output_budget_is_rejected(ledger, configured, limit):
    with call_guard.call_scope("bad-output"), pytest.raises(DomainError) as caught:
        call_guard.reserve_call(configured, body(max_tokens=limit))
    assert caught.value.error_code == "copilot_output_limit_invalid"


def test_unbounded_multimodal_input_is_not_sent(ledger, configured):
    request = body()
    request["messages"][0]["content"] = [{"type": "image_url", "image_url": {"url": "https://private.invalid/image"}}]
    with call_guard.call_scope("image"), pytest.raises(DomainError) as caught:
        call_guard.reserve_call(configured, request)
    assert caught.value.error_code == "llm_unbounded_input"


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("duplicate", [False, True])
def test_postgres_siblings_serialize_without_stale_identity_map(monkeypatch, configured, existing, duplicate):
    url = os.getenv("BDA_GATE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated PostgreSQL schema test requires BDA_GATE_TEST_DATABASE_URL")
    schema = "call_guard_test_" + uuid.uuid4().hex
    admin = create_engine(url)
    engine = None
    scope_id = "parallel"
    barrier = Barrier(8)
    class SynchronizedSession(Session):
        def get(self, entity, ident, **kwargs):
            value = super().get(entity, ident, **kwargs)
            if entity is CopilotCallBudget and not self.info.get("barrier_passed"):
                self.info["barrier_passed"] = True
                # Deliberately hold the stale ORM instance while another
                # connection updates it: FOR UPDATE must populate existing.
                self.info["observed_budget"] = value
                barrier.wait(timeout=10)
            return value
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"}, pool_size=8, max_overflow=0)
        for table in TABLES:
            table.create(engine)
        factory = sessionmaker(engine, class_=SynchronizedSession, expire_on_commit=False)
        monkeypatch.setattr(call_guard, "_session", factory)
        if existing:
            with Session(engine) as session:
                session.add(CopilotCallBudget(scope_hash=_hash(scope_id), calls=0, reserved_cny_micros=0, max_calls=6))
                session.commit()
        def attempt(index):
            try:
                with call_guard.call_scope(scope_id):
                    call_guard.reserve_call(configured, body(0 if duplicate else index))
                return "accepted"
            except DomainError as exc:
                return exc.error_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        assert results.count("accepted") == (1 if duplicate else 6)
        assert results.count("llm_duplicate_call" if duplicate else "llm_call_limit") == (7 if duplicate else 2)
        with Session(engine) as session:
            budget = session.get(CopilotCallBudget, _hash(scope_id))
            assert budget.calls == (1 if duplicate else 6)
            assert budget.reserved_cny_micros == session.scalar(select(func.sum(CopilotCallReservation.reserved_cny_micros)))
    finally:
        if engine:
            engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
