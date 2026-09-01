from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from sqlalchemy import create_engine, event, text
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
_worker_project_id: ContextVar[str | None] = ContextVar("bda_worker_project_id", default=None)


@event.listens_for(engine, "checkout")
def _database_connection_checked_out(*_args: object) -> None:
    DATABASE_POOL_CHECKED_OUT.inc()
    update_database_pool_capacity_metrics(engine.pool)


@event.listens_for(engine, "checkin")
def _database_connection_checked_in(*_args: object) -> None:
    DATABASE_POOL_CHECKED_OUT.dec()
    update_database_pool_capacity_metrics(engine.pool)


update_database_pool_capacity_metrics(engine.pool)


@event.listens_for(SessionFactory.class_, "after_begin")
def _apply_worker_project_context(_session: Session, _transaction: object, connection) -> None:
    """Apply the Celery message's project fence to every worker transaction."""
    project_id = _worker_project_id.get()
    if not project_id or connection.dialect.name != "postgresql":
        return
    connection.execute(
        text("select set_config('bda.worker_project_id', :project_id, true)"),
        {"project_id": project_id},
    )

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


def set_request_rls_context(session: Session, *, user_id: object, is_global_admin: bool) -> None:
    """Set transaction-local values consumed by PostgreSQL RLS policies."""
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    session.execute(
        text("select set_config('bda.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )
    session.execute(
        text("select set_config('bda.is_global_admin', :is_admin, true)"),
        {"is_admin": "true" if is_global_admin else "false"},
    )


def set_worker_rls_context(session: Session, *, project_id: object) -> None:
    """Fence a worker transaction to the project carried by its operation."""
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    session.execute(
        text("select set_config('bda.worker_project_id', :project_id, true)"),
        {"project_id": str(project_id)},
    )


def bind_worker_project_context(project_id: object | None) -> Token[str | None]:
    return _worker_project_id.set(str(project_id) if project_id else None)


def reset_worker_project_context(token: Token[str | None]) -> None:
    _worker_project_id.reset(token)
