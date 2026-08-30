from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest
from backend_v2.app.copilot import actions
from backend_v2.app.core.problem import DomainError


@pytest.fixture
def action_environment(monkeypatch):
    project = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
    )
    user = SimpleNamespace(id=uuid.uuid4())
    audits: list[dict[str, Any]] = []
    monkeypatch.setattr(
        actions,
        "require_project",
        lambda session, project_id, actor: project,
    )
    monkeypatch.setattr(
        actions,
        "record_audit",
        lambda session, **kwargs: audits.append(kwargs),
    )
    return project, user, audits


def service(monkeypatch, action_environment, request_text: str):
    project, user, audits = action_environment
    gap_calls = []
    gap_service = SimpleNamespace(
        resolve_research_gaps=lambda target_id, **kwargs: (
            gap_calls.append((target_id, kwargs))
            or {
                "operation_id": str(uuid.uuid4()),
                "research_target_id": target_id,
                "status": "pending",
            }
        )
    )
    monkeypatch.setattr(
        actions,
        "ResearchActionService",
        lambda session, current_project, actor: gap_service,
    )
    instance = actions.CopilotActionService(
        # `scalar` answers the operation lookup a queued action does to name what
        # an agent run could wait on. Nothing was enqueued here, so None is the
        # honest answer and the returned payload is unchanged by it.
        cast(Any, SimpleNamespace(scalar=lambda *_args, **_kwargs: None)),
        cast(Any, project),
        cast(Any, user),
        request_text=request_text,
        source_message_id=uuid.uuid4(),
    )
    return instance, gap_calls, audits


def test_gap_repair_is_explicit_pending_and_audited(
    monkeypatch,
    action_environment,
) -> None:
    instance, gap_calls, audits = service(
        monkeypatch,
        action_environment,
        "请补齐这个 Research 靶点的 gaps。",
    )
    target_id = str(uuid.uuid4())
    result = instance.resolve_research_gaps(target_id)
    duplicate = instance.resolve_research_gaps(target_id)

    assert result == duplicate
    assert result["status"] == "pending"
    assert len(gap_calls) == 1
    assert audits[0]["action"] == "copilot.action.resolve_research_gaps"


def test_literature_search_is_explicit_pending_and_audited(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        "请检索并摄取 GPR65 proton sensing 文献。",
    )
    run_id = uuid.uuid4()
    monkeypatch.setattr(
        actions,
        "create_literature_search",
        lambda session, project, payload, user: SimpleNamespace(
            id=run_id,
            query=payload.query,
        ),
    )
    result = instance.start_literature_search(
        "GPR65 AND proton sensing",
        limit=3,
    )

    assert result == {
        "search_run_id": str(run_id),
        "status": "pending",
        "database": "europe_pmc",
        "query": "GPR65 AND proton sensing",
    }
    assert audits[0]["action"] == "copilot.action.start_literature_search"


def test_target_intelligence_is_exact_pending_and_audited(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        "请启动这个靶点的情报分析。",
    )
    run_id, target_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(
        actions,
        "create_intelligence_run",
        lambda session, project, payload, user: SimpleNamespace(
            id=run_id,
            target_id=payload.target_id,
        ),
    )
    result = instance.start_target_intelligence(
        str(target_id),
        query="binding sites",
    )

    assert result["intelligence_run_id"] == str(run_id)
    assert result["target_id"] == str(target_id)
    assert result["status"] == "pending"
    assert audits[0]["action"] == "copilot.action.start_target_intelligence"


def test_knowledge_output_is_a_pending_review_draft(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        "请保存以下内容为项目知识笔记。",
    )
    entry_id = uuid.uuid4()
    captured = {}

    def create(session, project, payload, user):
        captured["payload"] = payload
        return SimpleNamespace(id=entry_id, entry_type=payload.entry_type)

    monkeypatch.setattr(actions, "create_knowledge_entry", create)
    result = instance.create_knowledge_draft(
        "Copilot test note",
        "Unreviewed test content.",
        tags=["test"],
    )

    assert result["status"] == "pending_review"
    assert captured["payload"].entry_type == "copilot_draft"
    assert captured["payload"].source["review_status"] == "pending_review"
    assert audits[0]["action"] == "copilot.action.create_knowledge_draft"


def test_compute_output_remains_an_unconfirmed_draft(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        "请创建一个 LSF 计算任务草稿，不要提交。",
    )
    draft_id = uuid.uuid4()
    monkeypatch.setattr(
        actions,
        "create_compute_draft_service",
        lambda session, payload, user: SimpleNamespace(
            id=draft_id,
            backend=payload.backend,
        ),
    )
    result = instance.create_compute_draft(
        "Copilot LSF test",
        "lsf",
        {"queue": "normal"},
    )

    assert result == {
        "compute_draft_id": str(draft_id),
        "status": "draft",
        "backend": "lsf",
        "confirmation_required": True,
    }
    assert audits[0]["action"] == "copilot.action.create_compute_draft"


def test_write_action_is_rejected_without_explicit_user_request(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        "哪些 GPR65 文献可能相关？",
    )

    with pytest.raises(
        ValueError,
        match="copilot_action_requires_explicit_user_request",
    ):
        instance.start_literature_search("GPR65", limit=1)
    assert audits == []


def test_negated_literature_request_does_not_authorize_search(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        "只分析还缺哪些文献；不要启动检索、不要排队任务。",
    )

    assert instance.request_allows("start_literature_search") is False
    with pytest.raises(
        ValueError,
        match="copilot_action_requires_explicit_user_request",
    ):
        instance.start_literature_search("GPR65", limit=1)
    assert audits == []


def test_submit_request_does_not_authorize_a_new_compute_draft(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        "请确认并提交当前已有的 compute draft。不要创建新的草稿。",
    )

    assert instance.request_allows("create_compute_draft") is False
    with pytest.raises(
        ValueError,
        match="copilot_action_requires_explicit_user_request",
    ):
        instance.create_compute_draft("unexpected", "lsf", {})
    assert audits == []


@pytest.mark.parametrize(
    "request_text",
    [
        "哪些论文应该检索？",
        "请告诉我如何检索 GPR65 文献。",
        "Which papers should I search?",
        "Please explain how to search the literature.",
        "This research paper discusses proton sensing.",
    ],
)
def test_advice_question_does_not_authorize_literature_search(
    monkeypatch,
    action_environment,
    request_text,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        request_text,
    )

    assert instance.request_allows("start_literature_search") is False
    assert audits == []


def test_direct_request_after_advice_marker_authorizes_search(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, _ = service(
        monkeypatch,
        action_environment,
        "哪些论文最相关？请帮我检索 GPR65 文献。",
    )

    assert instance.request_allows("start_literature_search") is True


def test_project_scope_rejection_is_failure_audited(
    monkeypatch,
    action_environment,
) -> None:
    instance, _, audits = service(
        monkeypatch,
        action_environment,
        "请启动这个靶点的情报分析。",
    )
    monkeypatch.setattr(
        actions,
        "create_intelligence_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            DomainError(
                "target_not_found",
                "Target was not found in this project",
                status_code=404,
            )
        ),
    )

    with pytest.raises(DomainError, match="not found"):
        instance.start_target_intelligence(str(uuid.uuid4()))

    assert audits[0]["action"] == "copilot.action.start_target_intelligence"
    assert audits[0]["result"] == "failure"
    assert audits[0]["payload"]["error_code"] == "target_not_found"
