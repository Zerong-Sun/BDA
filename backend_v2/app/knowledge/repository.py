from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from .models import KnowledgeEntry


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _filtered(self, project_id: uuid.UUID, query: str = "", entry_type: str | None = None) -> Select[tuple[KnowledgeEntry]]:
        if len(query) > 500:
            raise DomainError("knowledge_query_too_long", "Knowledge search is limited to 500 characters", status_code=422)
        statement = select(KnowledgeEntry).where(KnowledgeEntry.project_id == project_id)
        if entry_type:
            statement = statement.where(KnowledgeEntry.entry_type == entry_type)
        else:
            statement = statement.where(KnowledgeEntry.entry_type != "bot_work_record")
        term = query.strip()
        if term:
            # Search decoded tag values, not serialized JSON: a Unicode tag may
            # be stored as an escape sequence in SQLite's JSON representation.
            if self.session.get_bind().dialect.name == "sqlite":
                tags = func.json_each(KnowledgeEntry.tags).table_valued("value").alias("knowledge_tags")
            else:
                tags = func.json_array_elements_text(KnowledgeEntry.tags).table_valued("value").render_derived(name="knowledge_tags")
            tag_match = select(1).select_from(tags).where(tags.c.value.icontains(term, autoescape=True)).correlate(KnowledgeEntry).exists()
            statement = statement.where(or_(KnowledgeEntry.title.icontains(term, autoescape=True),
                                            KnowledgeEntry.content.icontains(term, autoescape=True), tag_match))
        return statement

    def list_project(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int,
                     *, query: str = "", entry_type: str | None = None) -> list[KnowledgeEntry]:
        q = self._filtered(project_id, query, entry_type)
        if after:
            q = q.where(KnowledgeEntry.id > after)
        return list(self.session.scalars(q.order_by(KnowledgeEntry.id).limit(limit + 1)))

    def search(self, project_id: uuid.UUID, query: str, *, limit: int = 12) -> list[KnowledgeEntry]:
        """Apply predicates across the project before taking recent matching rows."""
        statement = self._filtered(project_id, query).order_by(KnowledgeEntry.updated_at.desc(), KnowledgeEntry.id)
        return list(self.session.scalars(statement.limit(max(1, min(limit, 50)))))

    def get(self, entry_id: uuid.UUID) -> KnowledgeEntry | None:
        return self.session.get(KnowledgeEntry, entry_id)
