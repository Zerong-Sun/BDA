"""Structure reads remain reviewable in chat after the model response ends."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import research_agent
from backend_v2.app.structures import service as structures
from backend_v2.tests.test_structure_residues import _pdb
from backend_v2.tests.test_structure_service import _stored_structure
from backend_v2.tests.test_structure_service import session as session  # noqa: F401
from backend_v2.tests.test_structure_service import stored as stored  # noqa: F401


def _turn(monkeypatch, context, artifact_id):
    replies = iter([
        {"tool_calls": [{"id": "residue-read-1", "type": "function", "function": {
            "name": "list_structure_residues", "arguments": json.dumps({"artifact_id": str(artifact_id), "chain": "A", "residue_property": "positive"}),
        }}]},
        {"content": "The structure contains LYS A:52 and ARG A:52A; charge is a convention, and no validated hotspot is established."},
    ])
    monkeypatch.setattr(research_agent, "completion_message", lambda *args, **kwargs: next(replies))
    return research_agent.complete_research_turn(
        object(), [], context, initial_citations=[], initial_tool_calls=[],
        allowed_tools={"list_structure_residues"}, bot="planner",
    )


def test_actual_structure_read_survives_in_chat_tool_calls(session, stored, monkeypatch):
    project_id, artifact = _stored_structure(session, stored, text=_pdb())
    artifact.lineage = {"synthetic": True, "token": "do-not-copy"}
    answer = _turn(monkeypatch, SimpleNamespace(session=session, project_id=project_id), artifact.id)
    call = answer.tool_calls[0]
    assert call["tool_call_id"] == "residue-read-1"
    assert call["status"] == "completed"
    result = call["result"]
    assert result["artifact_id"] == str(artifact.id)
    assert result["checksum_sha256"] == artifact.checksum_sha256
    assert result["provenance"] == {"synthetic": True}
    assert result["residues"][1]["insertion_code"] == "A"
    assert result["viewer_selection"]["residues"][1]["insertion_code"] == "A"
    assert result["confidence"]["metric"] == "unknown"
    assert result["hotspot_status"] == "not_assessed_requires_independent_experimental_evidence"


def test_rendered_structure_selection_survives_in_chat_tool_calls(session, stored, monkeypatch):
    project_id, artifact = _stored_structure(session, stored, text=_pdb())
    monkeypatch.setattr(structures.ObjectStorage, "download_url", lambda self, key: "https://storage.test/synthetic.pdb", raising=False)
    selection = [{"chain": "A", "seq": 52, "insertion_code": "A"}]
    replies = iter([
        {"tool_calls": [{"id": "structure-view-1", "type": "function", "function": {
            "name": "render_structure_view", "arguments": json.dumps({"artifact_id": str(artifact.id), "residues": selection}),
        }}]},
        {"content": "Highlighted ARG A:52A."},
    ])
    monkeypatch.setattr(research_agent, "completion_message", lambda *args, **kwargs: next(replies))
    answer = research_agent.complete_research_turn(
        object(), [], SimpleNamespace(session=session, project_id=project_id),
        initial_citations=[], initial_tool_calls=[], allowed_tools={"render_structure_view"}, bot="planner",
    )
    call = answer.tool_calls[0]
    assert call["status"] == "completed"
    assert call["tool_call_id"] == "structure-view-1"
    assert call["result"]["artifact_id"] == str(artifact.id)
    assert call["result"]["checksum_sha256"] == artifact.checksum_sha256
    assert call["result"]["highlighted"] == selection
    assert call["result"]["scene_format"].startswith("molviewspec/")


def test_chat_oversized_result_is_explicitly_omitted_without_silent_partial_residue_list(monkeypatch):
    result = {
        "artifact_id": "source-artifact", "filename": "synthetic.pdb", "checksum_sha256": "f" * 64,
        "provenance": {"synthetic": True}, "residues": [{"detail": "测" * 45000}],
    }
    # Fewer than 128KiB characters, but more than 128KiB UTF-8 bytes.
    assert len(json.dumps(result, ensure_ascii=False)) < 131072
    monkeypatch.setattr(research_agent, "_execute", lambda *args, **kwargs: (result, []))
    answer = _turn(monkeypatch, SimpleNamespace(session=object()), "source-artifact")
    saved = answer.tool_calls[0]["result"]
    assert saved["result_omitted"] is True
    assert saved["artifact_id"] == result["artifact_id"]
    assert saved["checksum_sha256"] == result["checksum_sha256"]
    assert saved["provenance"] == result["provenance"]
    assert "residues" not in saved
    assert "reopen" in saved["reason"]


@pytest.mark.parametrize("size,omitted", [(131072, False), (131073, True)])
def test_saved_preview_limit_is_inclusive_bytes(size, omitted):
    # A JSON string's two quote bytes count towards the payload limit.
    result = "x" * (size - 2)
    saved = research_agent._logged_evidence(result)
    assert (isinstance(saved, dict) and saved.get("result_omitted") is True) is omitted


def test_oversized_comparison_retains_both_source_identities():
    sources = {side: {"artifact_id": side, "filename": f"{side}.pdb", "checksum_sha256": "f" * 64,
                      "provenance": {"synthetic": True}} for side in ("reference", "mobile")}
    saved = research_agent._logged_evidence({**sources, "residue_correspondence": ["x" * 131072]})
    assert saved["result_omitted"] is True
    assert saved["reference"] == sources["reference"]
    assert saved["mobile"] == sources["mobile"]
