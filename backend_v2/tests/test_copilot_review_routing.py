from backend_v2.app.copilot.tasks import _traceable_literature_citations


def test_project_entities_do_not_trigger_grounded_literature_review() -> None:
    citations = [
        {
            "source_type": "project_database",
            "entity_id": "workflow-1",
        }
    ]

    assert _traceable_literature_citations(citations) == []


def test_only_checksum_and_trace_backed_excerpt_triggers_grounded_review() -> None:
    traceable = {
        "source_type": "scientific_literature",
        "document_id": "doc-1",
        "chunk_id": "chunk-1",
        "content_checksum_sha256": "a" * 64,
        "retrieval_trace_id": "trace-1",
    }
    discovery_metadata = {
        "source_type": "scientific_literature",
        "document_id": "doc-2",
        "chunk_id": None,
        "content_checksum_sha256": None,
        "retrieval_trace_id": "trace-2",
    }

    assert _traceable_literature_citations([discovery_metadata, traceable]) == [traceable]
