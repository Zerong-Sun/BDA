"""Rows other domains used to construct directly, now created by the owning service."""

from __future__ import annotations

import uuid
from unittest.mock import Mock

from backend_v2.app.audit.models import AuditLog
from backend_v2.app.audit.service import record_audit
from backend_v2.app.knowledge.models import KnowledgeEntry
from backend_v2.app.knowledge.service import save_content_addressed_entry
from backend_v2.app.platform.models import WorkerHeartbeat
from backend_v2.app.platform.operations import record_worker_heartbeat
from backend_v2.app.registry.models import LLMProvider
from backend_v2.app.registry.service import provider_request_variant, save_byok_provider


def test_byok_provider_is_created_once_then_repointed_without_losing_settings() -> None:
    session = Mock()
    created = save_byok_provider(
        session, None, name="Project p BYOK", endpoint="https://llm.example/v1", model="m1", credential_ref="file:/a"
    )
    session.add.assert_called_once_with(created)
    assert (created.provider_type, created.enabled, created.config) == ("openai_compatible", True, {})

    created.version = 1
    created.enabled = False
    same = save_byok_provider(session, created, name="Project p BYOK", endpoint="", model="", credential_ref="file:/b")

    assert same is created
    assert (same.endpoint, same.model, same.credential_ref, same.enabled, same.version) == (
        "https://llm.example/v1", "m1", "file:/b", True, 2
    )
    session.add.assert_called_once()


def test_request_variant_changes_only_config_and_is_never_added() -> None:
    saved = LLMProvider(id=uuid.uuid4(), name="p", model="m", provider_type="openai_compatible",
                        endpoint="https://llm.example/v1", credential_ref="env:KEY", config={"thinking": "on"})
    variant = provider_request_variant(saved, {"thinking": {"type": "disabled"}})

    assert variant is not saved
    assert (variant.id, variant.credential_ref, variant.config) == (saved.id, "env:KEY", {"thinking": {"type": "disabled"}})
    assert saved.config == {"thinking": "on"}


def test_content_addressed_entry_is_created_at_most_once_per_transaction() -> None:
    entry_id = uuid.uuid4()
    session = Mock()
    session.get.return_value = None
    session.new = set()
    fields = dict(project_id=uuid.uuid4(), created_by=uuid.uuid4(), title="t", entry_type="bot_record",
                  content="c", tags=[], source={})

    first = save_content_addressed_entry(session, entry_id=entry_id, **fields)
    session.new = {first}
    second = save_content_addressed_entry(session, entry_id=entry_id, **fields)

    assert isinstance(first, KnowledgeEntry) and second is first
    session.add.assert_called_once_with(first)

    stored = KnowledgeEntry(id=entry_id)
    session.get.return_value = stored
    assert save_content_addressed_entry(session, entry_id=entry_id, **fields) is stored


def test_worker_heartbeat_upserts_by_instance() -> None:
    session = Mock()
    session.get.return_value = None
    row = record_worker_heartbeat(
        session, "worker@a", service="celery-worker", queues=["poll"], build_revision="b1", schema_revision="s1"
    )
    assert isinstance(row, WorkerHeartbeat)
    session.add.assert_called_once_with(row)

    session.get.return_value = row
    again = record_worker_heartbeat(
        session, "worker@a", service="celery-worker", queues=["dispatch"], build_revision="b2", schema_revision="s1"
    )
    assert again is row and (row.queues, row.build_revision) == (["dispatch"], "b2")
    session.add.assert_called_once()


def test_record_audit_returns_the_row_it_adds() -> None:
    session = Mock()
    row = record_audit(session, action="a", entity_type="e", actor_id=None, payload={"k": 1})
    assert isinstance(row, AuditLog) and row.payload == {"k": 1}
    session.add.assert_called_once_with(row)
