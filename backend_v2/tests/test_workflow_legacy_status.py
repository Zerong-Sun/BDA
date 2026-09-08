from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend_v2.app.workflows.schemas import WorkflowNodeResponse


@pytest.mark.parametrize(("stored", "response"), [("not_started", "draft"), ("completed", "succeeded"), ("skipped", "skipped")])
def test_legacy_node_status_is_normalized_only_for_the_response(stored, response):
    now = datetime.now(UTC)
    node = SimpleNamespace(
        id=uuid4(), workflow_run_id=uuid4(), node_key="synthetic", node_type="scoring",
        model_plugin="synthetic", model_plugin_id=None, container_image=None,
        command=None, queue=None, status=stored, parameters={}, error_message=None,
        version=1, created_at=now, updated_at=now,
    )
    assert WorkflowNodeResponse.model_validate(node).status == response
    assert node.status == stored
    node.status = "unknown-state"
    with pytest.raises(ValidationError):
        WorkflowNodeResponse.model_validate(node)
