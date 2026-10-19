from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .models import DeliveryPackage


class DeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, package_id: uuid.UUID) -> DeliveryPackage | None:
        return self.session.get(DeliveryPackage, package_id)

    def list_newest(self, project_id: uuid.UUID, after: tuple[datetime, uuid.UUID] | None, limit: int) -> list[DeliveryPackage]:
        query = select(DeliveryPackage).where(DeliveryPackage.project_id == project_id)
        if after:
            created_at, identifier = after
            query = query.where(or_(DeliveryPackage.created_at < created_at,
                                    and_(DeliveryPackage.created_at == created_at, DeliveryPackage.id < identifier)))
        return list(self.session.scalars(query.order_by(DeliveryPackage.created_at.desc(), DeliveryPackage.id.desc()).limit(limit + 1)))

    def list_project(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[DeliveryPackage]:
        query = select(DeliveryPackage).where(DeliveryPackage.project_id == project_id)
        if after:
            query = query.where(DeliveryPackage.id > after)
        return list(self.session.scalars(query.order_by(DeliveryPackage.id).limit(limit + 1)))
