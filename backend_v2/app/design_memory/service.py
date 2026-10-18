from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.problem import DomainError
from ..projects.models import Project
from ..workflows.models import WorkflowRun
from ..workflows.repository import WorkflowRepository
from .models import DesignLesson, DesignReview
from .schemas import FeedbackCreate, LessonCreate, ReviewCreate

# Questions, not scientific conclusions. Domain-specific evidence lives in project lessons.
CHECKLIST = [
    {
        "key": "identity",
        "title": "对象与输入身份",
        "title_en": "Identity and inputs",
        "prompt": "版本、序列/结构/材料、预处理及状态是否明确？",
        "prompt_en": "Are versions, inputs, preprocessing and states unambiguous?",
    },
    {
        "key": "objective",
        "title": "目标与方向",
        "title_en": "Objective and direction",
        "prompt": "优化哪个指标、哪个状态？方向、单位和符号是否已校准？",
        "prompt_en": "Which metric and state are optimized? Are direction, units and signs calibrated?",
    },
    {
        "key": "mechanism",
        "title": "机制与适用条件",
        "title_en": "Mechanism and applicability",
        "prompt": "已有证据适用于什么条件？哪些仍是假说或存在反证？",
        "prompt_en": "Under which conditions does evidence apply? What remains uncertain or contradicted?",
    },
    {
        "key": "controls",
        "title": "变量与对照",
        "title_en": "Factors and controls",
        "prompt": "改变哪些因素？如何设置匹配对照并区分组合效应？",
        "prompt_en": "Which factors change? How will matched controls distinguish combined effects?",
    },
    {
        "key": "feasibility",
        "title": "可实现性与方法边界",
        "title_en": "Feasibility and method limits",
        "prompt": "计算/实验方法、制造与测量是否可用？已知失效条件是什么？",
        "prompt_en": "Are computation, experiments, production and measurement feasible? What invalidates the method?",
    },
    {
        "key": "readout",
        "title": "判定与结果回流",
        "title_en": "Decisions and feedback",
        "prompt": "如何区分支持、反证、不确定和方法无效？结果将改变什么？",
        "prompt_en": "How will support, refutation, uncertainty and invalid methods be distinguished? What changes next?",
    },
]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def fingerprint(session: Session, workflow: WorkflowRun) -> str:
    # Read executable rows, not merely the canvas cache. Presentation/layout changes do not invalidate review.
    nodes = WorkflowRepository(session).nodes(workflow.id)
    return digest(
        {
            "ancestor": workflow.derived_from_id,
            "backend": workflow.graph.get("compute_backend"),
            "nodes": sorted(
                [
                    {
                        k: getattr(n, k)
                        for k in (
                            "node_key",
                            "node_type",
                            "execution_mode",
                            "model_plugin",
                            "model_plugin_id",
                            "container_image",
                            "command",
                            "queue",
                            "parameters",
                            "configuration",
                            "input_bindings",
                        )
                    }
                    for n in nodes
                ],
                key=lambda n: n["node_key"],
            ),
            "edges": workflow.graph.get("edges", []),
        }
    )


def lessons(session: Session, project_id: uuid.UUID) -> list[DesignLesson]:
    return list(
        session.scalars(
            select(DesignLesson)
            .where(DesignLesson.project_id == project_id)
            .order_by(DesignLesson.created_at, DesignLesson.id)
        )
    )


def active_lessons(rows: list[DesignLesson]) -> list[DesignLesson]:
    replaced = {r.supersedes_id for r in rows if r.supersedes_id}
    return [r for r in rows if r.id not in replaced]


def serialize(row) -> dict:
    return {
        "id": str(row.id),
        "created_at": row.created_at.isoformat(),
        "created_by": str(row.created_by),
        "project_id": str(row.project_id),
        "payload": row.payload,
        **(
            {
                "review_id": str(row.review_id) if row.review_id else None,
                "item_key": row.item_key,
                "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
            }
            if isinstance(row, DesignLesson)
            else {
                "workflow_run_id": str(row.workflow_run_id),
                "fingerprint": row.fingerprint,
                "memory_digest": row.memory_digest,
            }
        ),
    }


def latest_review(session: Session, workflow: WorkflowRun):
    return session.scalar(
        select(DesignReview)
        .where(DesignReview.workflow_run_id == workflow.id)
        .order_by(DesignReview.created_at.desc(), DesignReview.id.desc())
        .limit(1)
    )


def memory_digest(rows: list[DesignLesson]) -> str:
    return digest([serialize(row) for row in active_lessons(rows)])


def review_state(session: Session, workflow: WorkflowRun) -> dict:
    rows = lessons(session, workflow.project_id)
    review = latest_review(session, workflow)
    current = fingerprint(session, workflow)
    memory = memory_digest(rows)
    nodes = WorkflowRepository(session).nodes(workflow.id)
    valid = bool(review and review.fingerprint == current and review.memory_digest == memory)
    # Feedback adds new lessons; it must not retroactively invalidate an executed review.
    state = "ready" if valid else "stale" if review else "missing"
    if workflow.status != "draft" and review:
        state = "frozen"
    pending = []
    if review:
        done = {row.item_key for row in active_lessons(rows) if row.review_id == review.id}
        pending = [
            item["key"]
            for item in review.payload["items"]
            if item["disposition"] != "not_applicable" and item["key"] not in done
        ]
    return {
        "manual_only": bool(nodes) and all(n.execution_mode == "manual" for n in nodes),
        "manual_execution": bool(workflow.graph.get("design_learning_manual_execution")),
        "manual_execution_complete": bool(workflow.graph.get("design_learning_manual_execution"))
        and workflow.status in ("succeeded", "failed", "cancelled"),
        "required": bool(workflow.graph.get("design_learning_required")),
        "state": state,
        "fingerprint": current,
        "memory_digest": memory,
        "checklist": CHECKLIST,
        "lessons": [serialize(r) for r in active_lessons(rows)],
        "review": serialize(review) if review else None,
        "pending_feedback": pending,
        "feedback": [serialize(r) for r in rows if review and r.review_id == review.id],
    }


def blockers(session: Session, workflow: WorkflowRun) -> list[dict]:
    if not workflow.graph.get("design_learning_required"):
        return []
    # Submission already holds the workflow lock. Serialize evidence additions with
    # the checked snapshot until the submission transaction completes.
    session.scalar(select(Project).where(Project.id == workflow.project_id).with_for_update(read=True))
    state = review_state(session, workflow)
    issues = []
    if state["state"] not in ("ready", "frozen"):
        issues.append(
            {
                "code": "design_learning_review_required",
                "message": "Complete the design learning review; inputs or prior evidence may have changed.",
            }
        )
    if workflow.derived_from_id:
        parent = session.get(WorkflowRun, workflow.derived_from_id)
        if parent and parent.status != "draft" and parent.graph.get("design_learning_required"):
            parent_state = review_state(session, parent)
            if not parent_state["review"] or parent_state["pending_feedback"]:
                issues.append(
                    {
                        "code": "design_learning_feedback_required",
                        "message": "Record the parent design's learning outcomes before submitting its next iteration.",
                    }
                )
    return issues


def audit(session, project, user, action, row):
    record_audit(
        session,
        action=action,
        entity_type=row.__tablename__,
        entity_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )


def save_review(session, project, workflow, user, payload: ReviewCreate, expected_version: int):
    session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.id == workflow.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    session.scalar(select(Project).where(Project.id == project.id).with_for_update())
    if workflow.status != "draft":
        raise DomainError("design_review_frozen", "Submitted design reviews are immutable", status_code=409)
    if workflow.version != expected_version:
        raise DomainError("version_conflict", "Workflow changed; reload before reviewing", status_code=412)
    rows = lessons(session, project.id)
    if payload.fingerprint != fingerprint(session, workflow) or payload.memory_digest != memory_digest(rows):
        raise DomainError(
            "design_review_stale", "Design or prior evidence changed; reload the checklist", status_code=409
        )
    required = {item["key"] for item in CHECKLIST} | {f"lesson:{r.id}" for r in active_lessons(rows)}
    keys = [i.key for i in payload.items]
    if (
        len(keys) != len(set(keys))
        or not required.issubset(keys)
        or any(k not in required and not k.startswith("question:") for k in keys)
    ):
        raise DomainError(
            "design_checklist_incomplete",
            "Review every checklist question and current lesson exactly once; new questions use question: keys",
            status_code=422,
        )
    row = DesignReview(
        project_id=project.id,
        workflow_run_id=workflow.id,
        created_by=user.id,
        fingerprint=payload.fingerprint,
        memory_digest=payload.memory_digest,
        payload={**payload.model_dump(mode="json"), "lesson_snapshots": [serialize(r) for r in active_lessons(rows)]},
    )
    session.add(row)
    workflow.graph = {**workflow.graph, "design_learning_required": True}
    workflow.version += 1  # serializes concurrent reviews against the workflow version
    session.flush()
    audit(session, project, user, "design.review.create", row)
    return row


def save_lesson(session, project, user, payload: LessonCreate, *, review=None, item_key=None, origin=None):
    session.scalar(select(Project).where(Project.id == project.id).with_for_update())
    if payload.supersedes_id:
        previous = session.get(DesignLesson, payload.supersedes_id)
        if not previous or previous.project_id != project.id:
            raise DomainError("design_lesson_not_found", "Prior lesson was not found in this project", status_code=404)
        if session.scalar(select(DesignLesson.id).where(DesignLesson.supersedes_id == previous.id)):
            raise DomainError("design_lesson_superseded", "Revise the latest lesson instead", status_code=409)
    row = DesignLesson(
        project_id=project.id,
        created_by=user.id,
        review_id=review.id if review else None,
        item_key=item_key,
        supersedes_id=payload.supersedes_id,
        payload={
            **payload.model_dump(mode="json", exclude={"supersedes_id", "review_id", "item_key"}),
            **({"origin": origin} if origin else {}),
        },
    )
    session.add(row)
    session.flush()
    audit(session, project, user, "design.feedback.create" if review else "design.lesson.create", row)
    return row


def save_feedback(session, project, workflow, user, payload: FeedbackCreate):
    # Serialize feedback with manual completion and review changes.
    session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.id == workflow.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if workflow.status == "draft":
        raise DomainError(
            "design_not_executed",
            "Submit the reviewed design before recording its results; prior evidence belongs in the lesson library",
            status_code=409,
        )
    review = session.get(DesignReview, payload.review_id)
    if not review or review.workflow_run_id != workflow.id or review.project_id != project.id:
        raise DomainError("design_review_not_found", "Review was not found for this design", status_code=404)
    if review.id != latest_review(session, workflow).id:
        raise DomainError(
            "design_review_superseded", "Link results to the final review of the executed design", status_code=409
        )
    item = next((i for i in review.payload["items"] if i["key"] == payload.item_key), None)
    if not item or item["disposition"] == "not_applicable":
        raise DomainError(
            "design_feedback_item_invalid",
            "Feedback must address an applicable question in the frozen review",
            status_code=422,
        )
    if payload.supersedes_id:
        previous = session.get(DesignLesson, payload.supersedes_id)
        if not previous or previous.review_id != review.id or previous.item_key != payload.item_key:
            raise DomainError(
                "design_feedback_revision_mismatch",
                "A feedback revision must address the same reviewed question",
                status_code=422,
            )
    # A later observation corrects the record by appending; it never rewrites the hypothesis.
    return save_lesson(session, project, user, payload, review=review, item_key=payload.item_key)


def manual_execution(session, project, workflow, user, phase: str, expected_version: int):
    session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.id == workflow.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if workflow.version != expected_version:
        raise DomainError("version_conflict", "Workflow changed; reload before continuing", status_code=412)
    # Lesson revisions use this same project lock; read a consistent feedback set.
    session.scalar(select(Project).where(Project.id == project.id).with_for_update())
    state = review_state(session, workflow)
    if not state["manual_only"]:
        raise DomainError(
            "manual_execution_only", "This action is only for entirely manual or external routes", status_code=409
        )
    if phase == "start":
        if workflow.status != "draft" or state["state"] != "ready" or blockers(session, workflow):
            raise DomainError(
                "design_review_required",
                "Complete the current design review and parent feedback first",
                status_code=409,
            )
        workflow.status = "running"
        workflow.graph = {**workflow.graph, "design_learning_manual_execution": True}
    else:
        if workflow.status != "running" or not state["manual_execution"] or state["pending_feedback"]:
            raise DomainError(
                "design_feedback_required",
                "Record all applicable learning outcomes before completing the manual record",
                status_code=409,
            )
        superseded = {row["supersedes_id"] for row in state["feedback"] if row["supersedes_id"]}
        outcomes = {row["payload"]["outcome"] for row in state["feedback"] if row["id"] not in superseded}
        workflow.status = (
            "cancelled"
            if "execution_blocked" in outcomes
            else "failed"
            if "method_invalid" in outcomes
            else "succeeded"
        )
    workflow.version += 1
    session.flush()
    audit(session, project, user, "design.manual_execution." + phase, workflow)
    return {"workflow_run_id": str(workflow.id), "status": workflow.status, "workflow_version": workflow.version}
