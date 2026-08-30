from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects import tasks as projects_tasks
from backend_v2.app.projects.models import ProjectPromptDraft
from backend_v2.app.projects.schemas import ProjectPromptDraftCreate
from backend_v2.app.projects.service import create_project_prompt_draft, require_project_prompt_draft
from backend_v2.app.registry.models import LLMProvider
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def draft_database(monkeypatch) -> Generator[tuple[sessionmaker, dict[str, uuid.UUID]]]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    @contextmanager
    def scope():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    monkeypatch.setattr(projects_tasks, "session_scope", scope)

    with factory() as session:
        owner = User(username="draft-owner", display_name="Draft Owner", role="researcher", enabled=True)
        other = User(username="draft-other", display_name="Draft Other", role="researcher", enabled=True)
        organization = Organization(name="Draft Org")
        session.add_all([owner, other, organization])
        session.flush()
        session.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role="owner"))
        session.commit()
        ids = {"owner": owner.id, "other": other.id, "organization": organization.id}
    yield factory, ids
    drop_all(engine, Base.metadata)
    engine.dispose()


def test_require_project_prompt_draft_rejects_other_users(draft_database) -> None:
    factory, ids = draft_database
    with factory() as session:
        owner = session.get(User, ids["owner"])
        accepted = create_project_prompt_draft(
            session,
            ProjectPromptDraftCreate(
                organization_id=ids["organization"],
                name="Draft project",
                project_type="protein_design",
                summary="Bind the target with high specificity.",
            ),
            owner,
        )
        session.commit()
        draft_id = accepted.draft_id

    with factory() as session:
        owner = session.get(User, ids["owner"])
        draft = require_project_prompt_draft(session, draft_id, owner)
        assert draft.status == "pending"

    with factory() as session:
        other = session.get(User, ids["other"])
        with pytest.raises(DomainError) as excinfo:
            require_project_prompt_draft(session, draft_id, other)
        assert excinfo.value.status_code == 403

    with factory() as session:
        owner = session.get(User, ids["owner"])
        with pytest.raises(DomainError) as excinfo:
            require_project_prompt_draft(session, uuid.uuid4(), owner)
        assert excinfo.value.status_code == 404


def test_project_prompt_generate_task_succeeds_with_configured_provider(draft_database, monkeypatch) -> None:
    factory, ids = draft_database
    with factory() as session:
        provider = LLMProvider(
            name="Test provider",
            provider_type="openai",
            endpoint="https://llm.test",
            model="test-model",
            credential_ref="env:TEST_LLM_KEY",
            enabled=True,
        )
        session.add(provider)
        session.flush()
        draft = ProjectPromptDraft(
            organization_id=ids["organization"],
            created_by=ids["owner"],
            status="pending",
            request={
                "name": "Draft project",
                "project_type": "protein_design",
                "summary": "Bind the target with high specificity.",
            },
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id

    monkeypatch.setattr("backend_v2.app.copilot.provider.complete", lambda provider, messages: "Generated design prompt.")

    result = projects_tasks.project_prompt_generate.run(str(draft_id))
    assert result["status"] == "ready"

    with factory() as session:
        draft = session.get(ProjectPromptDraft, draft_id)
        assert draft.status == "ready"
        assert draft.prompt == "Generated design prompt."
        assert draft.error is None


def test_project_prompt_generate_task_honors_requested_provider(draft_database, monkeypatch) -> None:
    factory, ids = draft_database
    with factory() as session:
        requested = LLMProvider(
            name="Requested provider",
            provider_type="openai",
            endpoint="https://llm.test",
            model="requested-model",
            credential_ref="env:TEST_LLM_KEY",
            enabled=True,
        )
        other = LLMProvider(
            name="Other provider",
            provider_type="openai",
            endpoint="https://llm.test",
            model="other-model",
            credential_ref="env:TEST_LLM_KEY",
            enabled=True,
        )
        session.add_all([requested, other])
        session.flush()
        draft = ProjectPromptDraft(
            organization_id=ids["organization"],
            created_by=ids["owner"],
            status="pending",
            request={
                "name": "Draft project",
                "project_type": "protein_design",
                "summary": "",
                "llm_provider_id": str(requested.id),
            },
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id
        requested_id = requested.id

    seen_providers = []
    monkeypatch.setattr(
        "backend_v2.app.copilot.provider.complete",
        lambda provider, messages: seen_providers.append(provider.id) or "Generated design prompt.",
    )

    result = projects_tasks.project_prompt_generate.run(str(draft_id))
    assert result["status"] == "ready"
    assert seen_providers == [requested_id]


def test_project_prompt_generate_task_records_llm_failure(draft_database, monkeypatch) -> None:
    factory, ids = draft_database
    with factory() as session:
        provider = LLMProvider(
            name="Failing provider",
            provider_type="openai",
            endpoint="https://llm.test",
            model="test-model",
            credential_ref="env:TEST_LLM_KEY",
            enabled=True,
        )
        session.add(provider)
        session.flush()
        draft = ProjectPromptDraft(
            organization_id=ids["organization"],
            created_by=ids["owner"],
            status="pending",
            request={"name": "Draft project", "project_type": "protein_design", "summary": ""},
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id

    def _raise(provider, messages):
        raise ValueError("llm_response_empty")

    monkeypatch.setattr("backend_v2.app.copilot.provider.complete", _raise)

    result = projects_tasks.project_prompt_generate.run(str(draft_id))
    assert result["status"] == "failed"

    with factory() as session:
        draft = session.get(ProjectPromptDraft, draft_id)
        assert draft.status == "failed"
        assert draft.error == "llm_response_empty"


def test_project_prompt_generate_task_handles_missing_draft(draft_database) -> None:
    result = projects_tasks.project_prompt_generate.run(str(uuid.uuid4()))
    assert result["status"] == "missing"


def test_project_prompt_generate_task_fails_without_configured_provider(draft_database) -> None:
    factory, ids = draft_database
    with factory() as session:
        draft = ProjectPromptDraft(
            organization_id=ids["organization"],
            created_by=ids["owner"],
            status="pending",
            request={"name": "Draft project", "project_type": "protein_design", "summary": ""},
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id

    result = projects_tasks.project_prompt_generate.run(str(draft_id))
    assert result["status"] == "failed"

    with factory() as session:
        draft = session.get(ProjectPromptDraft, draft_id)
        assert draft.status == "failed"
        assert draft.error == "no_llm_provider_configured"
