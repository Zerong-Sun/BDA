"""Status vocabularies shared by the ORM, the services and the API contract.

These live in one module because the alternative - a bare ``status: str`` on every
response schema - is exactly how the frontend came to gate its workflow editor on
``'completed'``, a value this backend has never produced. A ``Literal`` reaches the
OpenAPI document as an enum, so the generated client rejects the drift at compile
time instead of silently evaluating a branch that can never be true.

Adding a value here is a contract change: regenerate ``openapi.json`` and the
frontend SDK, and make sure the frontend handles it.
"""

from __future__ import annotations

from typing import Literal, get_args

# A run is 'queued' from submission until a job actually starts, 'running' while any
# job is in flight, and then terminal. 'draft' is the only editable state.
WorkflowRunStatus = Literal["draft", "queued", "running", "succeeded", "failed", "cancelled"]

# A node mirrors the status of its newest job attempt, so the vocabularies match except
# for two states that are not compute states: 'draft' (never submitted) and
# 'requires_review' (finished, but waiting on a human decision).
WorkflowNodeStatus = Literal[
    "draft",
    "pending",
    "dispatching",
    "queued",
    "running",
    "collecting",
    "succeeded",
    "failed",
    "cancelled",
    "requires_review",
]

JobStatus = Literal[
    "pending",
    "dispatching",
    "queued",
    "running",
    "collecting",
    "succeeded",
    "failed",
    "cancelled",
]

JobSubmissionStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]

# draft -> confirmed (user accepted the plan) -> submitted (a job was created for it).
ComputeDraftStatus = Literal["draft", "confirmed", "submitted"]

WORKFLOW_RUN_STATUSES = frozenset(get_args(WorkflowRunStatus))
WORKFLOW_NODE_STATUSES = frozenset(get_args(WorkflowNodeStatus))
JOB_STATUSES = frozenset(get_args(JobStatus))
JOB_SUBMISSION_STATUSES = frozenset(get_args(JobSubmissionStatus))
COMPUTE_DRAFT_STATUSES = frozenset(get_args(ComputeDraftStatus))

# Terminal job states. Kept here so the state machine and the vocabulary cannot drift
# apart; ``compute.service`` re-exports it under its historical name.
TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
