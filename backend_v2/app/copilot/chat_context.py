"""Bound chat prompt copies without changing persisted history or evidence identities."""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .citations import dedupe

HISTORY_MAX_BYTES = 16_000
RESEARCH_MAX_BYTES = 24_000
_PREVIEW_NOTE = (
    "Partial preview only, not full evidence. Reopen the named source with get_research_items "
    "using its kind and id before relying on omitted text. Do not infer missing results or review status."
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _prefix(text: str, byte_limit: int) -> str:
    result = text.encode("utf-8")[:max(0, byte_limit)].decode("utf-8", errors="ignore")
    # Never expose half a citation marker as though it were a valid reference.
    if result.rfind("[") > result.rfind("]"):
        result = result[:result.rfind("[")]
    return result


@dataclass(frozen=True, slots=True)
class ChatHistoryMessage:
    role: str
    content: str
    citations: list[dict[str, Any]]


def _field(item: Any, name: str, default: Any = None) -> Any:
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def select_chat_history(history: Sequence[Any], *, max_bytes: int = HISTORY_MAX_BYTES) -> list[ChatHistoryMessage]:
    """Newest contiguous message suffix, bounded by serialized role/content bytes.

    Citation arrays remain intact for original-index rebasing; they are metadata,
    not model messages. ``history_citations`` selects only actually referenced entries.
    Prior reasoning and tool-call continuations never enter this new turn.
    """
    if max_bytes < 512:
        raise ValueError("chat_history_budget_too_small")
    selected: list[ChatHistoryMessage] = []

    def size(rows: list[ChatHistoryMessage]) -> int:
        return len(_json([{"role": row.role, "content": row.content} for row in rows]).encode("utf-8"))

    for item in reversed(history):
        role, content = _field(item, "role"), _field(item, "content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
            continue
        citations = _field(item, "citations") or []
        row = ChatHistoryMessage(role, content, list(citations))
        if size([row, *selected]) <= max_bytes:
            selected.insert(0, row)
            continue
        if selected:
            break
        note = "\n[History preview truncated; omitted text is not available in this turn. Reopen the original message.]"
        low, high = 0, len(content.encode("utf-8"))
        while low < high:
            middle = (low + high + 1) // 2
            candidate = ChatHistoryMessage(role, _prefix(content, middle) + note, list(citations))
            if size([candidate]) <= max_bytes:
                low = middle
            else:
                high = middle - 1
        selected.append(ChatHistoryMessage(role, _prefix(content, low) + note, list(citations)))
        break
    return selected


def history_citations(history: Sequence[ChatHistoryMessage]) -> list[dict[str, Any]]:
    """Use the same original deduped indices as rebase_history_markers."""
    result: list[dict[str, Any]] = []
    for item in history:
        if item.role != "assistant":
            continue
        original = dedupe(item.citations)
        for marker in re.finditer(r"\[cite:(\d+)\]", item.content):
            index = int(marker[1]) - 1
            if 0 <= index < len(original):
                result.append(original[index])
    return dedupe(result)


def _bounded(value: Any, limit: int) -> Any:
    encoded = _json(value)
    size = len(encoded.encode("utf-8"))
    if size <= limit:
        return value
    return {"preview": _prefix(encoded, limit), "truncated": True, "original_utf8_bytes": size}


def compact_research_context(context: str, *, max_bytes: int = RESEARCH_MAX_BYTES) -> str:
    """Preserve item order/identity and original catalogue numbering; bound only prompt data.

    Every truncated value is explicit and carries a reopen instruction at the
    envelope level. If identities alone exceed the cap, fail before a paid call
    rather than dropping sources or silently relabeling their citation numbers.
    """
    if max_bytes < 512:
        raise ValueError("research_context_budget_too_small")
    if len(context.encode("utf-8")) <= max_bytes:
        return context
    try:
        payload = json.loads(context)
    except (TypeError, ValueError):
        payload = {"unparsed_context": context}
    if not isinstance(payload, dict):
        payload = {"unparsed_context": payload}

    def render(limit: int) -> str:
        result = {key: _bounded(value, min(4000, limit * 2))
                  for key, value in payload.items() if key != "retrieved_items"}
        items = []
        for item in payload.get("retrieved_items", []):
            if not isinstance(item, dict):
                raise ValueError("research_context_item_invalid")
            items.append({key: value if key in {"id", "kind", "label"} else _bounded(value, limit)
                          for key, value in item.items()})
        if "retrieved_items" in payload:
            result["retrieved_items"] = items
        result["context_compaction"] = {
            "truncated": True, "original_utf8_bytes": len(context.encode("utf-8")), "instruction": _PREVIEW_NOTE,
        }
        return _json(result)

    if len(render(0).encode("utf-8")) > max_bytes:
        raise ValueError("research_context_identity_budget_exceeded")
    low, high = 0, max_bytes
    while low < high:
        middle = (low + high + 1) // 2
        if len(render(middle).encode("utf-8")) <= max_bytes:
            low = middle
        else:
            high = middle - 1
    return render(low)
