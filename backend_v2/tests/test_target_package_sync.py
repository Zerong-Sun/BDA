"""`targets.service.sync_package_target`: the only way a research package writes a target.

A package knows a target's name, accession and organism and nothing else, so a
re-import must leave everything a person added on top of that untouched.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.targets.service import sync_package_target
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session() -> Iterator[Session]:
    engine = enforce_foreign_keys(
        create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


def _project(session: Session) -> Project:
    user = User(username="pkg-sync", display_name="P", role="researcher", enabled=True)
    organization = Organization(name="Package Sync Org")
    session.add_all([user, organization])
    session.flush()
    project = Project(organization_id=organization.id, owner_id=user.id, name="pd1", project_type="research")
    session.add(project)
    session.flush()
    return project


def test_first_import_creates_the_primary_target(session: Session) -> None:
    project = _project(session)
    target = sync_package_target(session, project, name="PD-1", uniprot_accession="Q15116", organism="Homo sapiens")

    assert project.primary_target_id == target.id
    assert (target.name, target.uniprot_accession, target.organism) == ("PD-1", "Q15116", "Homo sapiens")
    assert target.identity_status == "confirmed"


def test_reimport_keeps_user_fields_and_version_when_nothing_changed(session: Session) -> None:
    project = _project(session)
    target = sync_package_target(session, project, name="PD-1", uniprot_accession="Q15116", organism="Homo sapiens")
    target.sequence = "MQIPQAPWPVVWAVLQLGWRPGWFLDSPDRPWNPPTFSPALLVVTEGDNATFTCSFSNTSESFVLNWYRMSPSNQTDKLAAFPEDRSQPGQDCRFRVTQLPNGRDFHMSVVRARRNDSGTYLCGAISLAPKAQIKESLRAELRVTERRAE"
    target.chemical_identity = {"note": "user supplied"}
    session.flush()
    target_version, project_version = target.version, project.version

    again = sync_package_target(session, project, name="PD-1", uniprot_accession="Q15116", organism="Homo sapiens")

    assert again.id == target.id
    assert again.sequence.startswith("MQIPQAPW")
    assert again.chemical_identity == {"note": "user supplied"}
    assert (again.version, project.version) == (target_version, project_version)


def test_a_changed_package_field_bumps_the_version_once(session: Session) -> None:
    project = _project(session)
    target = sync_package_target(session, project, name="PD-1", uniprot_accession=None, organism=None)
    assert target.identity_status == "unconfirmed"
    version = target.version

    sync_package_target(session, project, name="PD-1", uniprot_accession="Q15116", organism=None)

    assert target.version == version + 1
    assert target.identity_status == "confirmed"
