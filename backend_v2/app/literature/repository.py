from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    LiteratureChunk,
    LiteratureClaim,
    LiteratureDocument,
    LiteratureEvidence,
    LiteratureRelation,
    LiteratureRetrievalTrace,
    LiteratureSearchRun,
    LiteratureSubscription,
)


class LiteratureRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_documents(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[LiteratureDocument]:
        q = select(LiteratureDocument).where(LiteratureDocument.project_id == project_id)
        if after:
            q = q.where(LiteratureDocument.id > after)
        return list(self.session.scalars(q.order_by(LiteratureDocument.id).limit(limit + 1)))

    def document(self, document_id: uuid.UUID) -> LiteratureDocument | None:
        return self.session.get(LiteratureDocument, document_id)

    def document_detail(
        self, document_id: uuid.UUID
    ) -> tuple[list[LiteratureChunk], list[LiteratureClaim], list[LiteratureEvidence]]:
        chunks = list(
            self.session.scalars(
                select(LiteratureChunk)
                .where(LiteratureChunk.document_id == document_id)
                .order_by(LiteratureChunk.position)
            )
        )
        claims = list(self.session.scalars(select(LiteratureClaim).where(LiteratureClaim.document_id == document_id)))
        evidence = (
            list(
                self.session.scalars(
                    select(LiteratureEvidence).where(LiteratureEvidence.claim_id.in_([claim.id for claim in claims]))
                )
            )
            if claims
            else []
        )
        return chunks, claims, evidence

    def chunk(self, chunk_id: uuid.UUID) -> LiteratureChunk | None:
        return self.session.get(LiteratureChunk, chunk_id)

    def list_chunks(self, document_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[LiteratureChunk]:
        query = select(LiteratureChunk).where(LiteratureChunk.document_id == document_id)
        if after:
            query = query.where(LiteratureChunk.id > after)
        return list(self.session.scalars(query.order_by(LiteratureChunk.id).limit(limit + 1)))

    def claim(self, claim_id: uuid.UUID) -> LiteratureClaim | None:
        return self.session.get(LiteratureClaim, claim_id)

    def list_claims(
        self,
        project_id: uuid.UUID,
        after: uuid.UUID | None,
        limit: int,
        review_status: str | None,
    ) -> list[LiteratureClaim]:
        query = (
            select(LiteratureClaim)
            .join(LiteratureDocument, LiteratureDocument.id == LiteratureClaim.document_id)
            .where(LiteratureDocument.project_id == project_id)
        )
        if after:
            query = query.where(LiteratureClaim.id > after)
        if review_status:
            query = query.where(LiteratureClaim.review_status == review_status)
        return list(self.session.scalars(query.order_by(LiteratureClaim.id).limit(limit + 1)))

    def evidence(self, evidence_id: uuid.UUID) -> LiteratureEvidence | None:
        return self.session.get(LiteratureEvidence, evidence_id)

    def list_evidence(self, claim_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[LiteratureEvidence]:
        query = select(LiteratureEvidence).where(LiteratureEvidence.claim_id == claim_id)
        if after:
            query = query.where(LiteratureEvidence.id > after)
        return list(self.session.scalars(query.order_by(LiteratureEvidence.id).limit(limit + 1)))

    def relation(self, relation_id: uuid.UUID) -> LiteratureRelation | None:
        return self.session.get(LiteratureRelation, relation_id)

    def list_relations(
        self,
        project_id: uuid.UUID,
        after: uuid.UUID | None,
        limit: int,
        review_status: str | None,
    ) -> list[LiteratureRelation]:
        query = select(LiteratureRelation).where(LiteratureRelation.project_id == project_id)
        if after:
            query = query.where(LiteratureRelation.id > after)
        if review_status:
            query = query.where(LiteratureRelation.review_status == review_status)
        return list(self.session.scalars(query.order_by(LiteratureRelation.id).limit(limit + 1)))

    def subscription(self, subscription_id: uuid.UUID) -> LiteratureSubscription | None:
        return self.session.get(LiteratureSubscription, subscription_id)

    def list_subscriptions(self, project_id: uuid.UUID) -> list[LiteratureSubscription]:
        return list(
            self.session.scalars(
                select(LiteratureSubscription)
                .where(LiteratureSubscription.project_id == project_id)
                .order_by(LiteratureSubscription.id)
            )
        )

    def search_run(self, search_run_id: uuid.UUID) -> LiteratureSearchRun | None:
        return self.session.get(LiteratureSearchRun, search_run_id)

    def list_search_runs(
        self,
        project_id: uuid.UUID,
        after: uuid.UUID | None,
        limit: int,
    ) -> list[LiteratureSearchRun]:
        query = select(LiteratureSearchRun).where(LiteratureSearchRun.project_id == project_id)
        if after:
            query = query.where(LiteratureSearchRun.id > after)
        return list(self.session.scalars(query.order_by(LiteratureSearchRun.id).limit(limit + 1)))

    def traces_for_search(self, search_run_id: uuid.UUID) -> list[LiteratureRetrievalTrace]:
        return list(
            self.session.scalars(
                select(LiteratureRetrievalTrace)
                .where(LiteratureRetrievalTrace.search_run_id == search_run_id)
                .order_by(LiteratureRetrievalTrace.created_at, LiteratureRetrievalTrace.id)
            )
        )

    def list_document_traces(
        self,
        document_id: uuid.UUID,
        after: uuid.UUID | None,
        limit: int,
    ) -> list[LiteratureRetrievalTrace]:
        query = select(LiteratureRetrievalTrace).where(LiteratureRetrievalTrace.document_id == document_id)
        if after:
            query = query.where(LiteratureRetrievalTrace.id > after)
        return list(self.session.scalars(query.order_by(LiteratureRetrievalTrace.id).limit(limit + 1)))
