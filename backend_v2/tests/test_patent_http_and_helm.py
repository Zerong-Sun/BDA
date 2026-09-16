from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
import yaml
from backend_v2.app.compute.models import OutboxEvent
from backend_v2.app.identity.models import User
from backend_v2.app.literature import patent_service
from backend_v2.app.platform.models import Operation
from backend_v2.tests.test_literature_patent_service import _patent, _project
from backend_v2.tests.test_literature_patent_service import session as session
from backend_v2.tests.test_room_decision_hotspot_api import client as client
from sqlalchemy import func, select


def test_families_group_only_saved_publications_and_keep_unknown_separate(session):
    project = _project(session)
    for number, office in [('EP100A1', 'EP'), ('US200A1', 'US')]:
        row = _patent(session, project, number, country=office, kind='A1', stage='application')
        row.metadata_json = {**row.metadata_json, 'patent_legal_status': {'family_id': 'family-1'}}
    _patent(session, project, 'WO300A1', country='WO', kind='A1', stage='application')
    view = patent_service.project_landscape(session, project)
    group, = view['families']['groups']
    assert group['family_id'] == 'family-1'
    assert group['publications'] == 2
    assert group['jurisdictions'] == ['EP', 'US']
    assert len(group['members']) == 2
    assert view['families']['publications_without_family_id'] == 1
    assert view['complete'] is True


def test_bounded_landscape_discloses_incomplete_counts(session, monkeypatch):
    project = _project(session)
    for n in range(3):
        _patent(session, project, f'EP{n}A1', country='EP', kind='A1', stage='application')
    monkeypatch.setattr(patent_service, 'MAX_DOCUMENTS_READ', 2)
    view = patent_service.project_landscape(session, project)
    assert view['records_matched'] == view['documents_read'] == 2
    assert view['documents_truncated'] is True
    assert view['complete'] is False


def test_http_lookup_queues_once_and_does_not_call_ops(client, monkeypatch):
    http, ids = client
    monkeypatch.setattr(patent_service, 'credential_available', lambda _: True)
    with ids['factory']() as session:
        document = _patent(session, ids['project'], 'EP100A1', country='EP', kind='A1', stage='application')
        document_id = str(document.id)
        session.commit()
    path = f"/api/v2/projects/{ids['project']}/patents"
    response = http.post(path + '/legal-status-lookups', json={'document_ids': [document_id, document_id]})
    assert response.status_code == 202, response.text
    assert response.json()['documents'] == 1
    with ids['factory']() as session:
        operation = session.get(Operation, uuid.UUID(response.json()['operation_id']))
        assert operation.project_id == ids['project']
        event = session.get(OutboxEvent, operation.id)
        assert event.topic == patent_service.LEGAL_STATUS_TOPIC
    assert http.get(path + '/landscape').json()['records_matched'] == 1
    assert http.get(path + '/landscape?jurisdictions=DE').status_code == 422


def test_http_lookup_denies_other_project_documents_and_viewer_writes(client, monkeypatch):
    http, ids = client
    monkeypatch.setattr(patent_service, 'credential_available', lambda _: True)
    with ids['factory']() as session:
        row = _patent(session, ids['other_project'], 'EP200A1', country='EP', kind='A1', stage='application')
        document_id = str(row.id)
        session.commit()
    path = f"/api/v2/projects/{ids['project']}/patents"
    assert http.post(path + '/legal-status-lookups', json={'document_ids': [document_id]}).status_code == 404
    with ids['factory']() as session:
        session.get(User, ids['user']).role = 'viewer'
        session.commit()
    assert http.get(path + '/landscape').status_code == 200
    assert http.post(path + '/legal-status-lookups', json={'document_ids': [document_id]}).status_code == 403
    with ids['factory']() as session:
        assert session.scalar(select(func.count()).select_from(Operation)) == 0


@pytest.mark.skipif(shutil.which('helm') is None, reason='Helm is required')
def test_ops_secret_is_mounted_only_where_the_client_runs():
    chart = Path(__file__).resolve().parents[1] / 'helm'
    command = ['helm', 'template', 'audit', str(chart), '--set', 'config.computeBackend=docker']
    plain = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    assert 'epo-ops-credentials' not in plain
    rendered = subprocess.run(command + ['--set', 'epoOpsCredentials.secretName=ops-test'], check=True, capture_output=True, text=True).stdout
    objects = list(yaml.safe_load_all(rendered))
    config = next(x for x in objects if x and x['kind'] == 'ConfigMap')
    assert config['data']['BDA_V2_EPO_OPS_CREDENTIAL_REF'] == 'file:/var/run/secrets/bda/epo-ops/credentials'
    mounted = []
    for item in objects:
        if not item or item['kind'] != 'Deployment':
            continue
        pod = item['spec']['template']['spec']
        volume = next((v for v in pod.get('volumes', []) if v['name'] == 'epo-ops-credentials'), None)
        if volume:
            mounted.append(item['metadata']['name'])
            assert volume['secret']['defaultMode'] == 0o440
            assert volume['secret']['items'] == [{'key': 'credentials', 'path': 'credentials'}]
            mount = next(m for m in pod['containers'][0]['volumeMounts'] if m['name'] == 'epo-ops-credentials')
            assert mount['readOnly'] is True
    assert sorted(mounted) == ['audit-api', 'audit-copilot-worker', 'audit-research-worker']
    refused = subprocess.run(command + ['--set', 'epoOpsCredentials.secretName=ops-test', '--set', 'epoOpsCredentials.keyFile=../other'], capture_output=True)
    assert refused.returncode != 0


def test_claims_http_validates_query_and_queues_the_claims_topic(client, monkeypatch):
    http, ids = client
    monkeypatch.setattr(patent_service, 'credential_available', lambda _: True)
    with ids['factory']() as session:
        document = _patent(session, ids['project'], 'EP100A1', country='EP', kind='A1', stage='application')
        document_id = str(document.id)
        session.commit()
    path = f"/api/v2/projects/{ids['project']}/patents"
    assert http.get(path + '/claims', params={'query': '   '}).status_code == 422
    assert http.get(path + '/claims', params={'query': 'device'}).json() == {'items': [], 'next_cursor': None}
    response = http.post(path + '/claims-lookups', json={'document_ids': [document_id]})
    assert response.status_code == 202
    with ids['factory']() as session:
        event = session.get(OutboxEvent, uuid.UUID(response.json()['operation_id']))
        assert event.topic == patent_service.CLAIMS_TOPIC
        session.get(User, ids['user']).role = 'viewer'
        session.commit()
    assert http.post(path + '/claims-lookups', json={'document_ids': [document_id]}).status_code == 403
