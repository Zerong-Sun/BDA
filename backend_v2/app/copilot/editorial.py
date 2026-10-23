"""Reviewed static examples for the public synthetic PD1 package.

These are authored product examples, never records of model or tool execution.
Only a trusted import into a package-owned project may install them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..identity.models import User
from ..projects.models import Project
from .models import CopilotConversation, CopilotMessage

EXAMPLES = (
    ("What has this PD-1/PD-L1 demo established?",
     "This package demonstrates how to read evidence and follow project records. It contains three fictional candidates and synthetic metrics and coordinates. It has not established binding, affinity, activity or candidate quality.\n\nStart with the project question and its public references. Then inspect a candidate's source and a workflow's inputs. A successful demo step shows the software path works; a scientific conclusion requires appropriate real evidence."),
    ("Which references should I read first?",
     "Read the structural sources first to understand the molecular partners and chain numbering, then read the functional studies for the specific biological question. The library preserves the original source links and reading scope.\n\nA bibliographic record is a reading lead. An abstract supports only what it reports. A full-text excerpt still needs its location, experimental conditions and limits. If figures, tables or supplementary methods are missing, record the gap rather than treating the paper as fully reviewed."),
    ("Can the candidate with the best score move straight to validation?",
     "Use the score to decide what to inspect next. The scores here are synthetic and cannot rank real binders.\n\nFor a real project, first confirm the candidate sequence, construct, source files and comparison protocol. Keep model confidence and geometry separate from measured affinity and function. Freeze the project's criteria before comparing outcomes, and retain failed and inconclusive records alongside successful ones."),
    ("How do I start my own project and close the learning loop?",
     "Create a project with a concrete question, add its sources and inputs, and save a workflow draft. Review model parameters, resource requests and screening rules before submission. You can prepare the draft while missing inputs are still being resolved.\n\nAfter execution, check output integrity, evaluate the saved gates and record the decision with its supporting results. Manual review gates wait for a decision; missing measurements and failed calculations remain distinct. Save what was learned together with its conditions and limits.\n\nA BDA login does not connect your cluster account. Real LSF execution needs a separately assigned connection and an approved runtime; this static example runs no tools or jobs."),
)


def install_pd1_examples(session: Session, project: Project, user: User) -> None:
    key = "pd1-editorial-example-v1"
    conversation_id = uuid.uuid5(project.id, key)
    if session.get(CopilotConversation, conversation_id) is not None:
        return  # Preserve edits and every earlier model/user record.
    conversation = CopilotConversation(id=conversation_id, project_id=project.id, created_by=user.id,
                                        title="PD-1/PD-L1 · Authored demo walkthrough")
    session.add(conversation)
    session.flush()
    now = datetime.now(UTC)
    for index, (question, answer) in enumerate(EXAMPLES):
        for offset, (role, content) in enumerate((("user", question), ("assistant", answer))):
            session.add(CopilotMessage(id=uuid.uuid5(conversation_id, f"{index}:{role}"), conversation_id=conversation_id,
                                      role=role, content=content, bot=None, status="completed", tool_calls=[], citations=[],
                                      context={"editorial_demo": {"key": key, "static": True, "synthetic": True, "author_type": "ai_editor",
                                                                   "provenance": "Authored example for pd1-demo-v1; no model call, tool use or scientific validation."}},
                                      created_at=now + timedelta(microseconds=index * 2 + offset)))
    record_audit(session, action="copilot.demo.install", entity_type="copilot_conversation", entity_id=conversation_id,
                 project_id=project.id, organization_id=project.organization_id, actor_id=user.id,
                 payload={"key": key, "static_demo": True, "synthetic": True})
