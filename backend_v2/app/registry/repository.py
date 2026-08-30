from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ModelPlugin, ParameterCatalog


class RegistryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def plugin(self, plugin_id: uuid.UUID) -> ModelPlugin | None:
        return self.session.get(ModelPlugin, plugin_id)

    def resource(self, model: Any, resource_id: uuid.UUID) -> Any | None:
        return self.session.get(model, resource_id)

    def rows(self, model: Any, after: uuid.UUID | None, limit: int) -> list[Any]:
        query = select(model)
        if after:
            query = query.where(model.id > after)
        return list(self.session.scalars(query.order_by(model.id).limit(limit + 1)))

    def parameter_catalog(
        self, plugin_id: uuid.UUID | None, after: uuid.UUID | None, limit: int
    ) -> list[ParameterCatalog]:
        query = select(ParameterCatalog)
        if plugin_id:
            query = query.where(ParameterCatalog.plugin_id == plugin_id)
        if after:
            query = query.where(ParameterCatalog.id > after)
        return list(self.session.scalars(query.order_by(ParameterCatalog.id).limit(limit + 1)))
