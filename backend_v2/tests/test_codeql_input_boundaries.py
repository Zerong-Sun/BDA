"""Regressions for CodeQL findings and reviewed false-positive boundaries."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend_v2.app.core.problem import DomainError
from backend_v2.app.research.copilot_import import _extract_json
from backend_v2.app.wetlab.kernels.bli import parse_fortebio_csv
from backend_v2.app.workflows.assistance import node_command, parse_script
from backend_v2.app.workflows.gate_schemas import ScriptImport

from scripts import check_public_data


@pytest.mark.parametrize("source", [
    {"title": "embedded ``` marker"},
    '{"title": "embedded ``` marker"}',
    '```JSON\n {"title": "embedded ``` marker"} \n```',
    '``` {"title": "embedded ``` marker"} ```',
])
def test_research_json_preserves_plain_and_fenced_objects(source):
    assert _extract_json(source) == {"title": "embedded ``` marker"}


@pytest.mark.parametrize("source", ['```json {} ``', '```python {} ```', '```json```', '[1]'])
def test_research_json_rejects_invalid_envelopes(source):
    with pytest.raises(DomainError, match="Copilot research JSON"):
        _extract_json(source)


def test_unterminated_fences_do_not_exhaust_request_worker_cpu():
    code = '''
from backend_v2.app.core.problem import DomainError
from backend_v2.app.research.copilot_import import _extract_json
for source in ['```json' + ' ' * 30000 + '!', '```' + '\\n ' * 15000 + '!']:
    try:
        _extract_json(source)
    except DomainError as error:
        assert error.status_code == 422
    else:
        raise AssertionError('malformed JSON accepted')
'''
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)


@pytest.mark.parametrize("source", ['/etc/passwd', '../secrets.csv', 'file:///tmp/input.csv', Path('input.csv')])
def test_instrument_content_cannot_select_a_local_file(source, monkeypatch):
    def unexpected_open(*_args, **_kwargs):
        pytest.fail("instrument input attempted filesystem access")
    monkeypatch.setattr('builtins.open', unexpected_open)
    with pytest.raises(ValueError, match="content must be bytes"):
        parse_fortebio_csv(source)


@pytest.mark.parametrize('separator', ['\n', '\r\n', '\u2028'])
def test_shell_assignment_inputs_remain_line_scoped_and_reviewable(separator):
    source = separator.join([' ' * 10000, 'A' * 10000, 'export count=5', 'label="a b"', 'empty=', 'COUNT =7'])
    imported = parse_script(ScriptImport(filename='node.sh', language='shell', source=source))
    assert imported['parameters'] == {'count': 5, 'label': 'a b', 'empty': ''}
    assert 'COUNT =7' in imported['commands']
    rendered = node_command(SimpleNamespace(configuration={'script': imported}, parameters={'count': 17}), None)
    assert 'export count=17' in rendered


def test_secret_gate_reports_location_without_logging_matched_content(tmp_path, monkeypatch, capsys):
    source = 'ghp_' + 'A' * 35
    (tmp_path / 'example.txt').write_text(source)
    monkeypatch.setattr(check_public_data, 'ROOT', tmp_path)
    monkeypatch.setattr(check_public_data, 'repository_files', lambda: {Path('example.txt')})
    monkeypatch.setattr(check_public_data, 'validate_package', lambda _errors: None)
    monkeypatch.setattr(check_public_data, 'validate_manifest', lambda _errors: None)
    assert check_public_data.main() == 1
    output = capsys.readouterr().out
    assert 'GitHub token in example.txt' in output
    assert source not in output
    # Error output remains plain diagnostic text, never a serialized input object.
    assert json.dumps(source) not in output
