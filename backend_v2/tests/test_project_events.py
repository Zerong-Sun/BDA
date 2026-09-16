from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from backend_v2.app.copilot import project_events
from backend_v2.app.copilot.models import CopilotConversation, CopilotMessage
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import OrganizationMember, User
from backend_v2.app.projects.models import ProjectMember
from backend_v2.tests.test_room_decision_hotspot_api import client as client
from sqlalchemy import delete


def test_revisions_detect_old_message_edits_and_isolate_projects(client):
    _, ids = client
    with ids['factory']() as session:
        original = project_events.revision(session, ids['project'])
        other = project_events.revision(session, ids['other_project'])
        conversation = CopilotConversation(project_id=ids['project'], created_by=ids['user'], title='Example')
        session.add(conversation)
        session.flush()
        message = CopilotMessage(conversation_id=conversation.id, role='assistant', content='First')
        session.add(message)
        session.commit()
        inserted = project_events.revision(session, ids['project'])
        assert inserted != original
        message.content = 'Updated'
        session.commit()
        assert project_events.revision(session, ids['project']) != inserted
        assert project_events.revision(session, ids['other_project']) == other


def test_stream_rechecks_revoked_membership_and_disabled_account(client, monkeypatch):
    _, ids = client
    monkeypatch.setattr(project_events, 'SessionFactory', ids['factory'])
    with ids['factory']() as session:
        user = session.get(User, ids['user'])
        user.role = 'researcher'
        # Project owners retain rights, so detach ownership before revocation.
        from backend_v2.app.projects.models import Project
        owner = User(username='second-owner', display_name='Owner', role='researcher', enabled=True)
        session.add(owner)
        session.flush()
        session.get(Project, ids['project']).owner_id = owner.id
        session.commit()
    project_events.authorized_revision(ids['project'], ids['user'])
    with ids['factory']() as session:
        session.execute(delete(OrganizationMember).where(OrganizationMember.user_id == ids['user']))
        session.execute(delete(ProjectMember).where(ProjectMember.project_id == ids['project'], ProjectMember.user_id == ids['user']))
        session.commit()
    with pytest.raises(DomainError):
        project_events.authorized_revision(ids['project'], ids['user'])
    with ids['factory']() as session:
        user = session.get(User, ids['user'])
        user.role = 'admin'
        user.enabled = False
        session.commit()
    with pytest.raises(DomainError):
        project_events.authorized_revision(ids['project'], ids['user'])


def test_stream_emits_only_changes_and_heartbeats_then_stops_on_revocation(monkeypatch):
    project_id, user_id = uuid.uuid4(), uuid.uuid4()
    values = iter(['one', 'one', 'two', DomainError('forbidden', 'Revoked', status_code=403)])
    def read(*args):
        value = next(values)
        if isinstance(value, Exception):
            raise value
        return value
    async def sleep(_):
        pass
    monkeypatch.setattr(project_events, 'authorized_revision', read)
    monkeypatch.setattr(project_events.asyncio, 'sleep', sleep)
    async def collect():
        return [event async for event in project_events.stream(project_id, user_id)]
    events = asyncio.run(collect())
    assert [event['event'] for event in events] == ['project-change', 'heartbeat', 'project-change']
    assert json.loads(events[0]['data']) == {'project_id': str(project_id)}
