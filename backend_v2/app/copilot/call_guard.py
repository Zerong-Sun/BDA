"""Fail-closed, durable limits for every paid completion, including repairs.

Reservations commit on a separate connection BEFORE the request. A timeout,
worker crash, or outer transaction rollback never restores spent allowance.
No cached response is replayed: duplicates stop rather than repeating tools.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..core.problem import DomainError
from ..registry.models import LLMProvider
from .models import CopilotCallBudget, CopilotCallReservation

MAX_CALLS = 6
MAX_CNY_MICROS = 1_000_000  # CNY 1, not USD; no exchange-rate approximation.
MAX_OUTPUT_TOKENS = 4096


@dataclass(frozen=True)
class Scope:
    id: str
    max_calls: int = MAX_CALLS
    initial_calls: int = 0


_scope: ContextVar[Scope | None] = ContextVar("paid_model_scope", default=None)


def current_scope_id() -> str | None:
    scope = _scope.get()
    return scope.id if scope else None


@contextmanager
def call_scope(scope_id: str, *, max_calls: int = MAX_CALLS, initial_calls: int = 0):
    # A tool, child bot or review can narrow a task, never mint a fresh budget.
    parent = _scope.get()
    if parent is not None:
        token = _scope.set(Scope(parent.id, max(0, min(parent.max_calls, max_calls)),
                                max(parent.initial_calls, initial_calls)))
        try:
            yield
        finally:
            _scope.reset(token)
        return
    if not scope_id:
        raise DomainError("llm_scope_required", "A durable task scope is required.", status_code=409)
    token = _scope.set(Scope(scope_id, max(0, min(MAX_CALLS, max_calls)), max(0, initial_calls)))
    try:
        yield
    finally:
        _scope.reset(token)


def _session():
    from ..core.database import SessionFactory
    return SessionFactory()


def _rates(provider: LLMProvider) -> tuple[Decimal, Decimal]:
    pricing = (provider.config or {}).get("bda_pricing", {})
    try:
        checked = datetime.fromisoformat(pricing["checked_at"].replace("Z", "+00:00"))
        now = datetime.now(UTC)
        if checked.tzinfo is None or not now - timedelta(days=30) <= checked <= now:
            raise ValueError("stale prices")
        endpoint = provider.endpoint
        if not endpoint or pricing["model"] != provider.model or pricing["endpoint"].rstrip("/") != endpoint.rstrip("/"):
            raise ValueError("different model or endpoint")
        rates = (Decimal(str(pricing["input_cny_per_million"])), Decimal(str(pricing["output_cny_per_million"])))
        if any(not rate.is_finite() or rate <= 0 for rate in rates):
            raise ValueError("invalid prices")
        return rates
    except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError):
        raise DomainError("llm_pricing_required", "Current model prices are not configured; no request was sent.", status_code=409) from None


def reserve_call(provider: LLMProvider, body: dict[str, Any]) -> tuple[str, str]:
    scope = _scope.get()
    if scope is None:
        raise DomainError("llm_scope_required", "A durable task scope is required; no request was sent.", status_code=409)
    input_rate, output_rate = _rates(provider)
    limit = body.get("max_completion_tokens", body.get("max_tokens", MAX_OUTPUT_TOKENS))
    if type(limit) is not int or limit < 1:
        raise DomainError("copilot_output_limit_invalid", "A positive output token limit is required.", status_code=409)
    limit = min(limit, MAX_OUTPUT_TOKENS)
    # Both aliases, if supplied, must agree with the reserved ceiling.
    if "max_completion_tokens" in body:
        body["max_completion_tokens"] = limit
    body["max_tokens"] = limit
    if "max_completion_tokens" in body:
        del body["max_tokens"]
    # Only text/tool requests have a byte-based conservative token bound. Remote
    # images/audio can expand after submission and require a separate estimator.
    if any(not isinstance(item.get("content"), (str, type(None))) for item in body.get("messages", [])):
        raise DomainError("llm_unbounded_input", "This input requires a bounded token estimate.", status_code=409)
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    # One UTF-8 byte per input token plus protocol overhead, peak uncached
    # prices, capped output (including thinking), and 25% safety margin.
    amount = int(((Decimal(len(encoded) + 4096) * input_rate + limit * output_rate) * Decimal("1.25")).to_integral_value(rounding=ROUND_CEILING))
    scope_hash = hashlib.sha256(scope.id.encode()).hexdigest()
    request_hash = hashlib.sha256(str(provider.id).encode() + (provider.endpoint or "").encode() + encoded).hexdigest()
    # Insert-if-absent independently; collision is expected for sibling workers.
    with _session() as session:
        if session.get(CopilotCallBudget, scope_hash) is None:
            session.add(CopilotCallBudget(scope_hash=scope_hash, calls=scope.initial_calls,
                                         reserved_cny_micros=MAX_CNY_MICROS if scope.initial_calls else 0,
                                         max_calls=scope.max_calls))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
        budget = session.scalar(select(CopilotCallBudget).where(CopilotCallBudget.scope_hash == scope_hash)
                                .with_for_update().execution_options(populate_existing=True))
        assert budget is not None
        if session.get(CopilotCallReservation, (scope_hash, request_hash)) is not None:
            raise DomainError("llm_duplicate_call", "This request was already attempted; automatic replay is blocked.", status_code=409)
        if budget.calls >= min(budget.max_calls, scope.max_calls, MAX_CALLS):
            raise DomainError("llm_call_limit", "The task call limit has been reached.", status_code=409)
        if budget.reserved_cny_micros + amount > MAX_CNY_MICROS:
            raise DomainError("llm_budget_exhausted", "The task allowance cannot cover another request.", status_code=409)
        budget.calls += 1
        budget.reserved_cny_micros += amount
        budget.max_calls = min(budget.max_calls, scope.max_calls)
        session.add(CopilotCallReservation(scope_hash=scope_hash, request_hash=request_hash, reserved_cny_micros=amount))
        session.commit()
    return scope_hash, request_hash


def record_usage(receipt: tuple[str, str], usage: Any) -> None:
    # Missing/invalid provider usage is unknown, never free. Reservations are
    # deliberately not refunded, including unsuccessful or truncated answers.
    if not isinstance(usage, dict):
        return
    with _session() as session:
        row = session.get(CopilotCallReservation, receipt)
        if row is None:
            raise DomainError("llm_reservation_missing", "The model call reservation is missing.", status_code=409)
        for field, key in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens")):
            value = usage.get(key)
            if type(value) is int and 0 <= value <= 2_000_000_000:
                setattr(row, field, value)
        session.commit()
