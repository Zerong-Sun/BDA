from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..compute.schemas import ComputeDraftCreate
from ..compute.service import create_compute_draft as create_compute_draft_service
from ..core.problem import DomainError
from ..identity.models import User
from ..intelligence.schemas import IntelligenceCreate
from ..intelligence.service import create_run as create_intelligence_run
from ..knowledge.schemas import KnowledgeCreate
from ..knowledge.service import create_entry as create_knowledge_entry
from ..literature.schemas import LiteratureSearchCreate
from ..literature.service import create_search as create_literature_search
from ..projects.models import Project
from ..projects.service import require_project
from .research_actions import ResearchActionService

_ACTION_REQUEST_TERMS = {
    "resolve_research_gaps": {
        "domains": {"gap", "gaps", "缺口", "补齐", "修复"},
        "verbs": {
            "fix",
            "fill",
            "resolve",
            "repair",
            "修复",
            "补齐",
            "解决",
        },
    },
    "start_literature_search": {
        "domains": {
            "literature",
            "paper",
            "papers",
            "europe pmc",
            "文献",
            "论文",
            "检索",
            "搜索",
        },
        "verbs": {
            "run",
            "start",
            "queue",
            "ingest",
            "search",
            "运行",
            "启动",
            "排队",
            "摄取",
            "检索",
            "搜索",
        },
    },
    "start_target_intelligence": {
        "domains": {
            "target",
            "intelligence",
            "profile",
            "靶点",
            "情报",
            "档案",
        },
        "verbs": {
            "run",
            "start",
            "queue",
            "create",
            "运行",
            "启动",
            "排队",
            "创建",
        },
    },
    "create_knowledge_draft": {
        "domains": {"knowledge", "note", "notes", "知识", "笔记", "记录"},
        "verbs": {
            "create",
            "save",
            "add",
            "write",
            "创建",
            "保存",
            "添加",
            "写入",
            "记录",
            "起草",
        },
    },
    "create_compute_draft": {
        "domains": {
            "compute",
            "job",
            "task",
            "lsf",
            "docker",
            "计算",
            "作业",
            "任务",
            "草稿",
        },
        "verbs": {
            "create",
            "prepare",
            "创建",
            "起草",
            "准备",
        },
    },
}

_NEGATION_SUFFIXES = (
    "do not",
    "don't",
    "dont",
    "must not",
    "never",
    "no need to",
    "without",
    "不要",
    "不需",
    "无需",
    "不必",
    "禁止",
    "请勿",
    "别",
)

_ADVISORY_MARKERS = (
    "how to",
    "how should",
    "should i",
    "can i",
    "could i",
    "which",
    "what",
    "如何",
    "怎么",
    "怎样",
    "哪些",
    "什么",
    "是否",
    "能否",
    "该不该",
    "应不应该",
)

_DIRECT_REQUEST_MARKERS = (
    "please",
    "can you",
    "could you",
    "i want you to",
    "请",
    "帮我",
    "立即",
    "马上",
)

_CLAUSE_SEPARATORS = (";", "；", "。", ".", "!", "！", "?", "？", ",", "，")


def _term_occurrences(text: str, term: str) -> list[int]:
    escaped = re.escape(term)
    if term.isascii() and term[0].isalnum() and term[-1].isalnum():
        escaped = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return [match.start() for match in re.finditer(escaped, text)]


def _contains_term(text: str, term: str) -> bool:
    return bool(_term_occurrences(text, term))


def _last_term_position(text: str, terms: tuple[str, ...]) -> int:
    return max(
        (
            position
            for term in terms
            for position in _term_occurrences(text, term)
        ),
        default=-1,
    )



def _awaitable(session: Session, result: dict[str, Any], resource_id: uuid.UUID) -> dict[str, Any]:
    """Name the operation a queued action can be waited on by.

    A run suspends on `resource_id`, so every queued action has to hand one back
    or an agent can start the work and then do nothing but report "queued". The
    operation row was flushed by `enqueue_operation` inside this transaction, so
    it is found here rather than plumbed back out through each domain service's
    return type.
    """
    from ..platform.models import Operation

    operation_id = session.scalar(
        select(Operation.id)
        .where(Operation.resource_id == resource_id)
        .order_by(Operation.created_at.desc())
        .limit(1)
    )
    if operation_id is None:
        return result
    return {**result, "operation_id": str(operation_id), "resource_id": str(operation_id)}


class CopilotActionService:
    """Permission-checked and request-bound Copilot mutations."""

    def __init__(
        self,
        session: Session,
        project: Project,
        user: User,
        *,
        request_text: str,
        source_message_id: uuid.UUID,
    ):
        self.session = session
        self.project = require_project(session, project.id, user)
        self.user = user
        self.request_text = request_text
        self.source_message_id = source_message_id
        self._completed: dict[str, dict[str, Any]] = {}
        self._research = ResearchActionService(session, self.project, user)

    def resolve_research_gaps(
        self,
        research_target_id: str,
        *,
        resolve_references: bool = True,
        resolve_structure: bool = True,
    ) -> dict[str, Any]:
        self._require_explicit("resolve_research_gaps")
        payload = {
            "research_target_id": research_target_id,
            "resolve_references": resolve_references,
            "resolve_structure": resolve_structure,
        }


        def execute() -> dict[str, Any]:
            accepted = self._research.resolve_research_gaps(
                research_target_id,
                resolve_references=resolve_references,
                resolve_structure=resolve_structure,
            )
            # Already carries operation_id; `resource_id` is the key the agent
            # loop reads, and one spelling for all three queue tools is what
            # keeps the loop from needing to know which tool it called.
            return {**accepted, "resource_id": accepted["operation_id"]}

        return self._once("resolve_research_gaps", payload, execute)

    def start_literature_search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> dict[str, Any]:
        self._require_explicit("start_literature_search")
        payload = LiteratureSearchCreate(
            query=query,
            sources=["europe_pmc"],
            limit=limit,
            fetch_full_text=True,
            extract_claims=True,
        )

        def execute() -> dict[str, Any]:
            row = create_literature_search(
                self.session,
                self.project,
                payload,
                self.user,
            )
            return _awaitable(
                self.session,
                {
                    "search_run_id": str(row.id),
                    "status": "pending",
                    "database": "europe_pmc",
                    "query": row.query,
                },
                row.id,
            )

        return self._once(
            "start_literature_search",
            payload.model_dump(mode="json"),
            execute,
        )

    def start_target_intelligence(
        self,
        target_id: str,
        *,
        query: str = "",
    ) -> dict[str, Any]:
        self._require_explicit("start_target_intelligence")
        try:
            parsed_target_id = uuid.UUID(target_id)
        except ValueError as exc:
            raise ValueError("invalid_target_id") from exc
        payload = IntelligenceCreate(
            target_id=parsed_target_id,
            query={
                "prompt": query.strip(),
                "source": "copilot",
                "source_message_id": str(self.source_message_id),
            },
        )

        def execute() -> dict[str, Any]:
            row = create_intelligence_run(
                self.session,
                self.project,
                payload,
                self.user,
            )
            return _awaitable(
                self.session,
                {
                    "intelligence_run_id": str(row.id),
                    "target_id": str(row.target_id),
                    "status": "pending",
                },
                row.id,
            )

        return self._once(
            "start_target_intelligence",
            payload.model_dump(mode="json"),
            execute,
        )

    def create_knowledge_draft(
        self,
        title: str,
        content: str,
        *,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        self._require_explicit("create_knowledge_draft")
        payload = KnowledgeCreate(
            title=title,
            content=content,
            entry_type="copilot_draft",
            source={
                "type": "copilot",
                "review_status": "pending_review",
                "source_message_id": str(self.source_message_id),
            },
            tags=list(tags or [])[:30],
        )

        def execute() -> dict[str, Any]:
            row = create_knowledge_entry(
                self.session,
                self.project,
                payload,
                self.user,
            )
            return {
                "knowledge_entry_id": str(row.id),
                "status": "pending_review",
                "entry_type": row.entry_type,
            }

        return self._once(
            "create_knowledge_draft",
            payload.model_dump(mode="json"),
            execute,
        )

    def create_compute_draft(
        self,
        name: str,
        backend: str,
        specification: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_explicit("create_compute_draft")
        payload = ComputeDraftCreate(
            project_id=self.project.id,
            name=name,
            backend=backend,
            specification=specification,
        )

        def execute() -> dict[str, Any]:
            row = create_compute_draft_service(self.session, payload, self.user)
            return {
                "compute_draft_id": str(row.id),
                "status": "draft",
                "backend": row.backend,
                "confirmation_required": True,
            }

        return self._once(
            "create_compute_draft",
            payload.model_dump(mode="json"),
            execute,
        )

    def request_allows(self, action_name: str) -> bool:
        terms = _ACTION_REQUEST_TERMS[action_name]
        normalized = self.request_text.lower()
        if not any(_contains_term(normalized, term) for term in terms["domains"]):
            return False
        for verb in terms["verbs"]:
            for index in _term_occurrences(normalized, verb):
                clause_start = max(
                    normalized.rfind(separator, 0, index)
                    for separator in _CLAUSE_SEPARATORS
                )
                clause_prefix = normalized[clause_start + 1 : index].rstrip()
                advisory = _last_term_position(
                    clause_prefix,
                    _ADVISORY_MARKERS,
                )
                direct_request = _last_term_position(
                    clause_prefix,
                    _DIRECT_REQUEST_MARKERS,
                )
                if (
                    not any(
                        _contains_term(clause_prefix, negation)
                        for negation in _NEGATION_SUFFIXES
                    )
                    and (advisory < 0 or direct_request > advisory)
                ):
                    return True
        return False

    def _require_explicit(self, action_name: str) -> None:
        if not self.request_allows(action_name):
            raise ValueError("copilot_action_requires_explicit_user_request")

    def _once(
        self,
        name: str,
        payload: dict[str, Any],
        execute: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        key = f"{name}:{hashlib.sha256(canonical.encode()).hexdigest()}"
        if key in self._completed:
            return self._completed[key]
        try:
            result = execute()
        except DomainError as exc:
            record_audit(
                self.session,
                action=f"copilot.action.{name}",
                entity_type="copilot_message",
                entity_id=self.source_message_id,
                project_id=self.project.id,
                organization_id=self.project.organization_id,
                actor_id=self.user.id,
                result="failure",
                payload={
                    "arguments_sha256": key.rsplit(":", 1)[-1],
                    "error_code": exc.error_code,
                },
            )
            raise
        self._completed[key] = result
        record_audit(
            self.session,
            action=f"copilot.action.{name}",
            entity_type="copilot_message",
            entity_id=self.source_message_id,
            project_id=self.project.id,
            organization_id=self.project.organization_id,
            actor_id=self.user.id,
            payload={
                "arguments_sha256": key.rsplit(":", 1)[-1],
                "result": result,
            },
        )
        return result
