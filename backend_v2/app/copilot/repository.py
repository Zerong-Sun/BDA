from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..registry.models import LLMProvider
from .models import (
    CopilotAgentRun,
    CopilotAgentTurn,
    CopilotConfig,
    CopilotConversation,
    CopilotMessage,
)


class CopilotRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def conversation(self, conversation_id: uuid.UUID) -> CopilotConversation | None:
        return self.session.get(CopilotConversation, conversation_id)

    def list_conversations(
        self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[CopilotConversation]:
        query = select(CopilotConversation).where(CopilotConversation.project_id == project_id)
        if after:
            query = query.where(CopilotConversation.id > after)
        return list(self.session.scalars(query.order_by(CopilotConversation.id).limit(limit + 1)))

    def list_messages(self, conversation_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[CopilotMessage]:
        query = select(CopilotMessage).where(CopilotMessage.conversation_id == conversation_id)
        if after:
            query = query.where(CopilotMessage.id > after)
        return list(self.session.scalars(query.order_by(CopilotMessage.id).limit(limit + 1)))

    def all_messages(self, conversation_id: uuid.UUID) -> list[CopilotMessage]:
        return list(
            self.session.scalars(
                select(CopilotMessage)
                .where(CopilotMessage.conversation_id == conversation_id)
                .order_by(CopilotMessage.created_at)
            )
        )

    def list_agent_runs(
        self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[CopilotAgentRun]:
        query = select(CopilotAgentRun).where(CopilotAgentRun.project_id == project_id)
        if after:
            query = query.where(CopilotAgentRun.id > after)
        return list(self.session.scalars(query.order_by(CopilotAgentRun.id).limit(limit + 1)))

    def agent_run(self, run_id: uuid.UUID) -> CopilotAgentRun | None:
        return self.session.get(CopilotAgentRun, run_id)

    def agent_turns(
        self, run_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[CopilotAgentTurn]:
        """A transcript page, ordered by sequence.

        The cursor names a turn, but the page is ordered and cut by `sequence`:
        a transcript is only ever read in order, and the random row id says
        nothing about that order.
        """
        query = select(CopilotAgentTurn).where(CopilotAgentTurn.run_id == run_id)
        if after is not None:
            cursor_turn = self.session.get(CopilotAgentTurn, after)
            if cursor_turn is None or cursor_turn.run_id != run_id:
                return []
            query = query.where(CopilotAgentTurn.sequence > cursor_turn.sequence)
        return list(self.session.scalars(query.order_by(CopilotAgentTurn.sequence).limit(limit + 1)))

    def config(self, project_id: uuid.UUID) -> CopilotConfig | None:
        return self.session.scalar(select(CopilotConfig).where(CopilotConfig.project_id == project_id))

    def llm_provider(self, provider_id: uuid.UUID) -> LLMProvider | None:
        return self.session.get(LLMProvider, provider_id)
