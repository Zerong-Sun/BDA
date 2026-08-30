from __future__ import annotations

from logging.config import fileConfig

from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.models import Base
from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
settings = get_settings()
database_url = settings.maintenance_database_url or settings.database_url
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        if settings.maintenance_database_role:
            quoted_role = connection.dialect.identifier_preparer.quote(settings.maintenance_database_role)
            connection.exec_driver_sql(f"SET ROLE {quoted_role}")
            # SET ROLE starts SQLAlchemy's autobegin transaction. Commit only that
            # session switch before Alembic opens its managed migration transaction;
            # otherwise a successful-looking run is rolled back when the connection
            # closes because Alembic did not create the outer transaction.
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
