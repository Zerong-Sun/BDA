"""Bound room previews and carry explicit final-delivery constraints between stages."""
from __future__ import annotations

import re
from typing import Any

# Only explicit final-report character limits, not per-member limits, source
# statistics or token/word budgets. Ambiguous prose remains a model instruction.
_CHARACTERS = re.compile(
    r"(?:最终(?:中文)?(?:汇报|报告|答复|交付|回答)|(?:全部|所有)(?:可见)?(?:文字|内容|文本))"
    r"[^。；;\n]{0,35}?(?:不超过|最多|上限为?|≤)\s*(\d{1,6})\s*(?:个)?字(?:符)?"
    r"|(?:final (?:report|answer|delivery)|all visible (?:text|content))"
    r"[^.;\n]{0,35}?(?:at most|no more than|under|maximum of)\s*(\d{1,6})\s*characters",
    re.IGNORECASE,
)


def delivery_constraints(run: Any, turns: list) -> dict:
    requests = [getattr(run, "goal", "") or "", *(turn.content for turn in turns if turn.role == "user")]
    limit = None
    for request in requests:
        if re.search(r"(?:取消|不再设定)字数限制|最终(?:汇报|报告|答复|交付|回答)不限字数", request):
            limit = None
            continue
        matches = [match for match in _CHARACTERS.finditer(request)
                   if not re.search(r"(?:不要求|无需|不必|不再要求)\s*$", request[:match.start()])]
        if matches:
            limit = int(next(value for value in matches[-1].groups() if value)) or None
    return {"max_visible_characters": limit, "counting": "summary + section titles and values + missing + next_action"}


def visible_characters(delivery: dict) -> int:
    parts = [delivery.get("summary", ""), delivery.get("next_action", "")]
    for name, value in (delivery.get("sections") or {}).items():
        parts.extend((name, value))
    parts.extend(delivery.get("missing") or [])
    return sum(len(value) for value in parts if isinstance(value, str))


def room_preview(result: Any) -> Any:
    """Keep identities/states; omit nested UI payloads and mark text previews.

    This also handles historical oversized receipts in prompt construction.
    Stored receipts and the user's full room remain unchanged.
    """
    if not isinstance(result, dict) or not {"active_tasks", "recent_activity"}.issubset(result):
        return result

    def fields(value: dict) -> dict:
        output: dict[str, Any] = {}
        omitted = list(value.get("omitted_fields", [])) if isinstance(value.get("omitted_fields"), list) else []
        for key, item in value.items():
            if key == "omitted_fields":
                continue
            if isinstance(item, (dict, list)):
                omitted.append(key)
            elif isinstance(item, str) and len(item) > 1200:
                output[key] = item[:1200]
                output[f"{key}_truncated"] = True
            else:
                output[key] = item
        if omitted:
            output["omitted_fields"] = omitted
        return output

    active = result.get("active_tasks", [])
    activity = result.get("recent_activity", [])
    if not isinstance(active, list) or not isinstance(activity, list):
        return result
    events = []
    for entry in activity[:30]:
        if not isinstance(entry, dict):
            continue
        item = fields({key: value for key, value in entry.items()
                       if key not in {"message", "handoff", "task", "decision", "discussion"}})
        for key in ("message", "handoff", "task", "decision", "discussion"):
            if isinstance(entry.get(key), dict):
                item[key] = fields(entry[key])
        events.append(item)
    return {"active_tasks": [fields(item) for item in active[:30] if isinstance(item, dict)],
            "recent_activity": events, "preview_only": True,
            "active_tasks_truncated": result.get("active_tasks_truncated") is True or len(active) > 30,
            "recent_activity_truncated": result.get("recent_activity_truncated") is True or len(activity) > 30,
            "detail_instruction": "Read the identified run/source for evidence; previews and omitted fields do not establish absence or scientific validity."}


def prompt_records(records: list[dict]) -> list[dict]:
    return [{**record, "result": room_preview(record["result"])}
            if record["tool"] == "read_team_progress" else record for record in records]
