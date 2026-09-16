"""Upgrade previously deployed feature heads without losing persisted rows."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from backend_v2.app.core import config as settings_module
from backend_v2.app.identity.models import User
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from alembic import command

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration test disabled")


@pytest.mark.parametrize("previous", [
    "0056_workflow_gates", "0059_workflow_gates",
    "0056_copilot_task_contracts", "0061_autopilot_stage_operator",
    "0057_plugin_output_routing", "0058_staged_port_paths",
    "0062_proteinmpnn_parser", "0064_public_integration",
])
def test_existing_feature_head_upgrades_and_downgrades(previous, monkeypatch):
    settings = settings_module.get_settings()
    source = make_url(settings.database_url)
    name = "bda_migration_" + uuid.uuid4().hex
    admin = create_engine(source, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    target = source.set(database=name)
    engine = create_engine(target, poolclass=NullPool)
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "backend_v2/alembic.ini"))
    config.set_main_option("script_location", str(root / "backend_v2/alembic"))
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings.model_copy(update={
        "database_url": target.render_as_string(hide_password=False),
        "maintenance_database_url": None, "maintenance_database_role": None,
    }))
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        command.upgrade(config, previous)
        with Session(engine) as session:
            user = User(username="migration-canary", display_name="Keep this row", role="researcher")
            session.add(user)
            session.commit()
        command.upgrade(config, "head")
        with Session(engine) as session:
            assert session.scalar(select(User.display_name).where(User.username == "migration-canary")) == "Keep this row"
            assert session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0070_af3_msa_port"
        assert {"workflow_results", "workflow_gate_evaluations"} <= set(inspect(engine).get_table_names())
        command.check(config)
        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()
