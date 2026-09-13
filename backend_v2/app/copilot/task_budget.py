"""Conservative per-call reservations for providers with administrator-declared prices.

Unpriced calls must never appear as free. This is a platform estimate, not a
replacement for the provider's billing limit; retry and protocol overhead are reserved.
"""
from __future__ import annotations

import json
import math
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..registry.models import LLMProvider
from . import agent_runs
from .models import CopilotAgentRun
from .provider import LLM_MAX_ATTEMPTS


def reserve_model_call(session: Session, run: CopilotAgentRun, provider: LLMProvider, messages: list[dict], tools: list[dict] | None = None) -> None:
    root = agent_runs.budget_root(session, run)
    # Sibling subagents spend the same allowance; serialize before reserving.
    from sqlalchemy import select
    session.scalar(select(CopilotAgentRun).where(CopilotAgentRun.id == root.id).with_for_update())
    rates = (provider.config or {}).get("bda_pricing", {})
    try:
        input_rate = Decimal(str(rates["input_usd_per_million"]))
        output_rate = Decimal(str(rates["output_usd_per_million"]))
        if not input_rate.is_finite() or not output_rate.is_finite() or min(input_rate, output_rate) < 0:
            raise ValueError("invalid rates")
    except (KeyError, TypeError, ValueError, InvalidOperation):
        run.task_contract = {**(run.task_contract or {}), "cost_mode": "unavailable"}
        if root.max_cost_usd_cents is not None:
            raise DomainError("copilot_budget_pricing_required", "A cost ceiling requires administrator-configured bda_pricing. No model call was made.", status_code=409) from None
        return
    maximum = (provider.config or {}).get("max_completion_tokens", (provider.config or {}).get("max_tokens", 2048))
    if not isinstance(maximum, int) or maximum < 1:
        raise DomainError("copilot_output_limit_invalid", "Configure a positive model output token limit.", status_code=409)
    # UTF-8 byte length is deliberately conservative for text tokens; reserve
    # additional protocol overhead and every possible HTTP attempt.
    input_bound = len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False).encode()) + 4096
    reservation = math.ceil((input_bound * input_rate + maximum * output_rate) * LLM_MAX_ATTEMPTS / 10000)
    if root.max_cost_usd_cents is not None and agent_runs.tree_cost_usd_cents(session, root) + reservation > root.max_cost_usd_cents:
        raise DomainError("copilot_budget_insufficient", "The next model call exceeds the remaining estimated budget.", status_code=409)
    run.cost_usd_cents += reservation
    run.task_contract = {**(run.task_contract or {}), "cost_mode": "conservative_estimate"}
    run.version += 1
    session.flush()
