"""Durable, source-attributed Markdown journals; no provider text is an execution receipt.

A content-addressed KnowledgeEntry is an immutable revision. The transaction hook
observes only source models, never knowledge, so recording cannot record itself.
Readers and tools only read; administrators can explicitly backfill old sources.
"""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from ..knowledge.models import KnowledgeEntry

KIND = "bot_work_record"
NAMESPACE = uuid.UUID("8b37d975-e31c-413d-8d13-3db272809141")


def _refs(value):
    """Extract declared workflow/evidence identifiers, never infer execution from prose."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"workflow_id", "workflow_run_id", "evidence_id", "claim_id", "artifact_id", "document_id"}:
                if isinstance(item, str):
                    found.add((key, item))
            elif key == "arguments" and isinstance(item, str):
                try:
                    found.update(_refs(json.loads(item)))
                except (ValueError, TypeError):
                    pass
            else:
                found.update(_refs(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_refs(item))
    return sorted(found)


def source_items(session, project_id, bot_id):
    from .models import CopilotAgentRun, CopilotAgentTurn, CopilotConversation, CopilotMessage
    from .project_context import _sanitize

    items = []
    messages = session.scalars(
        select(CopilotMessage)
        .join(CopilotConversation)
        .where(
            CopilotConversation.project_id == project_id,
            CopilotMessage.bot == bot_id,
            CopilotMessage.role == "assistant",
        )
        .order_by(CopilotMessage.created_at, CopilotMessage.id)
    )
    for message in messages:
        items.append(
            {
                "kind": "message",
                "id": str(message.id),
                "bot": message.bot,
                "conversation_id": str(message.conversation_id),
                "status": message.status,
                "created_at": message.created_at.isoformat(),
                "updated_at": message.updated_at.isoformat(),
                "source_version": message.version,
                "content": message.content or "",
                "error": message.error,
                "citations": _sanitize(message.citations or []),
                "references": _refs([message.context, message.tool_calls, message.citations]),
            }
        )
    runs = session.scalars(
        select(CopilotAgentRun)
        .where(
            CopilotAgentRun.project_id == project_id,
            CopilotAgentRun.bot == bot_id,
        )
        .order_by(CopilotAgentRun.created_at, CopilotAgentRun.id)
    )
    for run in runs:
        turns = list(
            session.scalars(
                select(CopilotAgentTurn).where(CopilotAgentTurn.run_id == run.id).order_by(CopilotAgentTurn.sequence)
            )
        )
        items.append(
            {
                "kind": "agent_run",
                "id": str(run.id),
                "bot": run.bot,
                "status": run.status,
                "created_at": run.created_at.isoformat(),
                "updated_at": run.updated_at.isoformat(),
                "source_version": run.version,
                "content": run.goal,
                "error": run.error,
                "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
                "outcome": _sanitize(run.outcome or {}),
                "references": _refs([run.task_contract, run.outcome, [t.tool_calls for t in turns]]),
                # Tool results/reasoning are not copied into the journal. The durable
                # transcript remains the authority and is addressed by these IDs.
                "turn_ids": [str(turn.id) for turn in turns],
            }
        )
    return sorted(items, key=lambda item: (item["created_at"], item["kind"], item["id"]))


def markdown(project_id, bot_id, items):
    lines = [
        f"# {bot_id} 工作记录",
        "",
        f"Project: {project_id}",
        f"Bot: {bot_id}",
        "",
        "记录来自平台持久消息和任务；消息中的结论仍是 Bot 陈述，任务成功不等同于科学验证通过。",
        "Workflow 引用仅说明记录涉及该工作流，不表示此 Bot 创建或完成了它。",
        "",
    ]
    if not items:
        lines += ["暂无以此 Bot 身份记录的工作。", ""]
    for item in items:
        lines += [
            f"## {item['kind']} · {item['id']}",
            "",
            f"Bot: {item['bot']} · Status: {item['status']} · Source version: {item['source_version']}",
            f"Created: {item['created_at']} · Updated: {item['updated_at']}",
            "",
            item["content"],
            "",
        ]
        for key in ("conversation_id", "parent_run_id", "error"):
            if item.get(key):
                lines += [f"{key}: {item[key]}", ""]
        for key in ("references", "citations", "turn_ids", "outcome"):
            if item.get(key):
                lines += [f"### {key}", "", "```json", json.dumps(item[key], ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)


def _record_lock_key(project_id, bot_id):
    # A stable namespace-qualified signed bigint: different operators never lock
    # a shared Project row, including while a provider holds its run transaction.
    value = hashlib.sha256(f"{NAMESPACE}:{project_id}:{bot_id}".encode()).digest()[:8]
    return int.from_bytes(value, byteorder="big", signed=True)


def _lock_record(session, project_id, bot_id):
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _record_lock_key(project_id, bot_id)})
    # SQLite serializes writers itself; no synthetic row lock is needed.


def refresh_record(session, project_id, bot_id, actor_id):
    from .bots import bot_ids

    if bot_id not in bot_ids():
        return None
    # Serialize only this operator's projections. Never lock Project: a worker
    # may keep its transaction open across provider calls, which would otherwise
    # block unrelated operators and ordinary project writes for minutes.
    _lock_record(session, project_id, bot_id)
    items = source_items(session, project_id, bot_id)
    content = markdown(project_id, bot_id, items)
    digest = hashlib.sha256(content.encode()).hexdigest()
    row_id = uuid.uuid5(NAMESPACE, f"{project_id}:{bot_id}:{digest}")
    existing = session.get(KnowledgeEntry, row_id)
    if existing is not None:
        return existing
    pending = next((row for row in session.new if isinstance(row, KnowledgeEntry) and row.id == row_id), None)
    if pending is not None:
        return pending
    row = KnowledgeEntry(
        id=row_id,
        project_id=project_id,
        created_by=actor_id,
        title=f"{bot_id} · 工作记录 · {digest[:12]}",
        entry_type=KIND,
        content=content,
        tags=["bot-record", bot_id],
        source={"format": "markdown", "bot_id": bot_id, "schema_version": 1, "sha256": digest, "items": items},
    )
    session.add(row)
    return row


def refresh_project_records(session, project_id, actor_id):
    from .bots import bot_ids

    return [refresh_record(session, project_id, bot_id, actor_id) for bot_id in sorted(bot_ids())]


def read_record(session, project_id, bot_id, query="", limit=100, offset=0):
    from .bots import require

    require(bot_id)
    latest = session.scalar(
        select(KnowledgeEntry)
        .where(
            KnowledgeEntry.project_id == project_id,
            KnowledgeEntry.entry_type == KIND,
            KnowledgeEntry.source["bot_id"].as_string() == bot_id,
        )
        .order_by(KnowledgeEntry.created_at.desc(), KnowledgeEntry.id.desc())
        .limit(1)
    )
    all_items = list((latest.source or {}).get("items", [])) if latest else []
    needle = query.strip().casefold()
    matching = [
        item for item in reversed(all_items) if not needle or needle in json.dumps(item, ensure_ascii=False).casefold()
    ]
    return {
        "project_id": str(project_id),
        "bot_id": bot_id,
        "record_id": str(latest.id) if latest else None,
        "sha256": (latest.source or {}).get("sha256") if latest else None,
        "updated_at": latest.created_at.isoformat() if latest else None,
        "total": len(all_items),
        "matched": len(matching),
        "offset": offset,
        "items": matching[offset : offset + limit],
        "markdown": latest.content if latest else markdown(project_id, bot_id, []),
    }


@event.listens_for(Session, "before_flush")
def _track_sources(session, flush_context, instances):
    from .models import CopilotAgentRun, CopilotAgentTurn, CopilotMessage

    changed = [
        row
        for row in session.new.union(session.dirty)
        if isinstance(row, (CopilotMessage, CopilotAgentRun, CopilotAgentTurn))
    ]
    if changed:
        session.info.setdefault("bot_record_sources", []).extend(changed)


@event.listens_for(Session, "after_flush_postexec")
def _record_sources(session, flush_context):
    from .models import CopilotAgentRun, CopilotAgentTurn, CopilotConversation, CopilotMessage

    owners = set()
    for row in session.info.pop("bot_record_sources", []):
        if isinstance(row, CopilotMessage) and row.role == "assistant" and row.bot:
            conversation = session.get(CopilotConversation, row.conversation_id)
            if conversation:
                owners.add((conversation.project_id, row.bot, conversation.created_by))
        elif isinstance(row, (CopilotAgentRun, CopilotAgentTurn)):
            run = row if isinstance(row, CopilotAgentRun) else session.get(CopilotAgentRun, row.run_id)
            if run and run.bot:
                owners.add((run.project_id, run.bot, run.created_by))
    for project_id, bot_id, actor in sorted(owners, key=str):
        refresh_record(session, project_id, bot_id, actor)


@event.listens_for(Session, "after_rollback")
def _clear_pending(session):
    session.info.pop("bot_record_sources", None)
