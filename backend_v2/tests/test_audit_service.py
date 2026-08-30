import uuid
from types import SimpleNamespace
from typing import Any, cast

from backend_v2.app.audit.service import record_audit


def test_record_audit_persists_explicit_failure_result() -> None:
    rows = []
    session = SimpleNamespace(add=rows.append)

    record_audit(
        cast(Any, session),
        action="copilot.action.test",
        entity_type="copilot_message",
        entity_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        result="failure",
        payload={"error_code": "target_not_found"},
    )

    assert rows[0].result == "failure"
    assert rows[0].payload["error_code"] == "target_not_found"
