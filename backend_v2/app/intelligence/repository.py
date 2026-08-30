from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DesignRoute, IntelligenceEvidence, IntelligenceHotspot, IntelligenceReport, IntelligenceRun


class IntelligenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_project(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[IntelligenceRun]:
        q = select(IntelligenceRun).where(IntelligenceRun.project_id == project_id)
        if after:
            q = q.where(IntelligenceRun.id > after)
        return list(self.session.scalars(q.order_by(IntelligenceRun.id).limit(limit + 1)))

    def run(self, run_id: uuid.UUID) -> IntelligenceRun | None:
        return self.session.get(IntelligenceRun, run_id)

    def report(self, report_id: uuid.UUID) -> IntelligenceReport | None:
        return self.session.get(IntelligenceReport, report_id)

    def evidence(self, evidence_id: uuid.UUID) -> IntelligenceEvidence | None:
        return self.session.get(IntelligenceEvidence, evidence_id)

    def hotspot(self, hotspot_id: uuid.UUID) -> IntelligenceHotspot | None:
        return self.session.get(IntelligenceHotspot, hotspot_id)

    def route(self, route_id: uuid.UUID) -> DesignRoute | None:
        return self.session.get(DesignRoute, route_id)

    def detail(
        self, run_id: uuid.UUID
    ) -> tuple[
        IntelligenceReport | None,
        list[IntelligenceEvidence],
        list[IntelligenceHotspot],
        list[DesignRoute],
    ]:
        report = self.session.scalar(select(IntelligenceReport).where(IntelligenceReport.run_id == run_id))
        evidence = list(
            self.session.scalars(
                select(IntelligenceEvidence)
                .where(IntelligenceEvidence.run_id == run_id)
                .order_by(IntelligenceEvidence.id)
            )
        )
        hotspots = list(
            self.session.scalars(
                select(IntelligenceHotspot)
                .where(IntelligenceHotspot.run_id == run_id)
                .order_by(IntelligenceHotspot.id)
            )
        )
        routes = list(
            self.session.scalars(select(DesignRoute).where(DesignRoute.run_id == run_id).order_by(DesignRoute.id))
        )
        return report, evidence, hotspots, routes
