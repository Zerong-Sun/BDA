from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .metrics import (
    DATABASE_POOL_CHECKED_OUT,
    update_database_pool_capacity_metrics,
)

settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
)
SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "checkout")
def _database_connection_checked_out(*_args: object) -> None:
    DATABASE_POOL_CHECKED_OUT.inc()
    update_database_pool_capacity_metrics(engine.pool)


@event.listens_for(engine, "checkin")
def _database_connection_checked_in(*_args: object) -> None:
    DATABASE_POOL_CHECKED_OUT.dec()
    update_database_pool_capacity_metrics(engine.pool)


update_database_pool_capacity_metrics(engine.pool)

# Register every mapped table before any request, worker, script, or isolated
# integration test starts using the session factory.  Importing models only from
# API modules made foreign-key resolution depend on incidental import order
# (for example workflow_nodes.model_plugin_id -> model_plugins.id).
from .. import all_models as _all_models  # noqa: E402,F401


def get_session() -> Generator[Session]:
    with SessionFactory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@contextmanager
def session_scope() -> Generator[Session]:
    with SessionFactory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
