"""`projects.service.sync_package_project`: the project fields a research package may own."""

from __future__ import annotations

import uuid

import pytest
from backend_v2.app.projects.models import Project
from backend_v2.app.projects.service import flag_adopted_user_project, sync_package_project


def _project() -> Project:
    return Project(id=uuid.uuid4(), name="old", localized_content={"note": "kept"}, version=1)


def test_package_fields_are_applied_with_one_version_bump() -> None:
    project = _project()

    assert sync_package_project(project, name="new", source_package_id="pkg-1") is True
    assert (project.name, project.source_package_id, project.version) == ("new", "pkg-1", 2)
    assert sync_package_project(project, name="new") is False
    assert project.version == 2


def test_a_package_cannot_set_ownership_or_access_fields() -> None:
    project = _project()
    with pytest.raises(ValueError, match="organization_id, owner_id"):
        sync_package_project(project, organization_id=uuid.uuid4(), owner_id=uuid.uuid4())
    assert project.version == 1


def test_adoption_keeps_existing_localized_content() -> None:
    project = _project()
    flag_adopted_user_project(project)
    assert project.localized_content == {"note": "kept", "adopted_user_project": True}
    assert project.version == 2
