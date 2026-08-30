from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DeliveryPackage


class DeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, package_id: uuid.UUID) -> DeliveryPackage | None:
        return self.session.get(DeliveryPackage, package_id)

    def list_project(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[DeliveryPackage]:
        query = select(DeliveryPackage).where(DeliveryPackage.project_id == project_id)
        if after:
            query = query.where(DeliveryPackage.id > after)
        return list(self.session.scalars(query.order_by(DeliveryPackage.id).limit(limit + 1)))
