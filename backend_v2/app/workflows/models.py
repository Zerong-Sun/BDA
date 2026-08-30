from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin
from ..core.statuses import WorkflowNodeStatus, WorkflowRunStatus


class WorkflowRun(UUIDVersionMixin, Base):
    __tablename__ = "workflow_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[WorkflowRunStatus] = mapped_column(String(40), default="draft", index=True)
    graph: Mapped[dict] = mapped_column(JSON, default=lambda: {"nodes": [], "edges": []})
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # The run this one is meant to be compared against. Causal claims come from comparing
    # runs, so the comparison itself has to be recorded rather than described afterwards.
    derived_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Derived from the parameter diff at submission, never author-supplied: "baseline"
    # (no ancestor), "replicate" (identical parameters) or "variant" (something changed).
    arm_label: Mapped[str] = mapped_column(String(40), default="baseline")
    # {node_key: {parameter: {"from": ..., "to": ...}}} against the ancestor. Computed by
    # the platform, which is what makes "only one parameter changed" checkable.
    varied_parameters: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkflowNode(UUIDVersionMixin, Base):
    __tablename__ = "workflow_nodes"
    __table_args__ = (UniqueConstraint("workflow_run_id", "node_key", name="uq_workflow_node_key"),)

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    node_key: Mapped[str] = mapped_column(String(120))
    node_type: Mapped[str] = mapped_column(String(80))
    model_plugin: Mapped[str] = mapped_column(String(160))
    model_plugin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_plugins.id"), nullable=True)
    container_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    queue: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[WorkflowNodeStatus] = mapped_column(String(40), default="draft")
    # "dispatch" (default) or "manual". A manual stage is part of the route but is not run
    # by this platform - target intake, a hand-built hotspot map, a scientist reviewing
    # candidates. It needs no registry plugin and produces no job.
    execution_mode: Mapped[str] = mapped_column(String(20), default="dispatch")
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    # [{port, source: "artifact"|"upstream", artifact_id?, from_node?, from_port?}]
    # Resolved into the job input manifest at submit (artifact) or at schedule time
    # (upstream), see compute/binding.py.
    input_bindings: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
