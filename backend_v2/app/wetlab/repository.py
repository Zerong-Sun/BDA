from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Protein


class ProteinRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, protein_id: uuid.UUID, *, for_update: bool = False) -> Protein | None:
        if for_update:
            return self.session.scalar(
                select(Protein).where(Protein.id == protein_id).with_for_update()
            )
        return self.session.get(Protein, protein_id)

    def by_digest(self, project_id: uuid.UUID, sequence_sha256: str) -> Protein | None:
        """Find a construct by sequence identity, for duplicate detection."""
        return self.session.scalar(
            select(Protein).where(
                Protein.project_id == project_id,
                Protein.sequence_sha256 == sequence_sha256,
            )
        )

    def list_project(
        self,
        project_id: uuid.UUID,
        after: uuid.UUID | None,
        limit: int,
        *,
        search: str | None = None,
        tag: str | None = None,
    ) -> list[Protein]:
        query = select(Protein).where(Protein.project_id == project_id)
        if search:
            # Name only: searching sequences would require reading the plaintext
            # column into a filter and invites using the API as a sequence oracle.
            query = query.where(Protein.name.ilike(f"%{search}%"))
        if after is not None:
            query = query.where(Protein.id > after)
        rows = list(self.session.scalars(query.order_by(Protein.id).limit(limit + 1)))
        if tag:
            # tags is a JSON array; filtering in Python keeps this portable rather
            # than depending on a JSON containment operator.
            rows = [row for row in rows if tag in (row.tags or [])]
        return rows

    def add(self, protein: Protein) -> Protein:
        self.session.add(protein)
        self.session.flush()
        return protein

    def delete(self, protein: Protein) -> None:
        self.session.delete(protein)
