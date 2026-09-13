from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from backend_v2.scripts import run_scheduler_worker as runner


@pytest.mark.parametrize("url", ["", "postgresql+psycopg://bda:password@postgres/bda_v2", "redis://bda_scheduler@host/0",
                                 "postgresql+psycopg://bda_scheduler@postgres/bda_v2"])
def test_scheduler_rejects_missing_or_shared_login_before_connecting(monkeypatch, url):
    monkeypatch.setattr(runner, "create_engine", lambda *a, **kw: pytest.fail("Unexpected connection"))
    with pytest.raises(ValueError):
        runner.validate_database(url)


@pytest.mark.parametrize("invalid", [None, "rolsuper", "rolcreatedb", "rolcreaterole", "schema_create",
                                     "rolbypassrls", "outbox_access", "heartbeat_access"])
def test_scheduler_checks_capabilities_and_disposes_connections(monkeypatch, invalid):
    row = dict(rolsuper=False, rolcreatedb=False, rolcreaterole=False, schema_create=False,
               rolbypassrls=True, outbox_access=True, heartbeat_access=True)
    if invalid:
        row[invalid] = not row[invalid]
    disposed = []
    result = SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: row))
    connection = SimpleNamespace(execute=lambda _: result)
    engine = SimpleNamespace(connect=lambda: nullcontext(connection), dispose=lambda: disposed.append(True))
    monkeypatch.setattr(runner, "create_engine", lambda *a, **kw: engine)
    if invalid:
        with pytest.raises(ValueError):
            runner.validate_database("postgresql+psycopg://bda_scheduler:password@postgres/bda_v2")
    else:
        runner.validate_database("postgresql+psycopg://bda_scheduler:password@postgres/bda_v2")
    assert disposed == [True]


def test_startup_error_never_prints_connection_secrets(monkeypatch, capsys):
    monkeypatch.setattr(runner.sys, "argv", ["scheduler"])

    def bad(_):
        raise RuntimeError("password=must-not-appear-in-logs")

    monkeypatch.setattr(runner, "validate_database", bad)
    assert runner.main() == 1
    assert "must-not-appear" not in capsys.readouterr().err


def test_startup_executes_only_scheduler_and_reports_actual_queue(monkeypatch):
    monkeypatch.setattr(runner.sys, "argv", ["scheduler"])
    monkeypatch.setattr(runner, "validate_database", lambda _: None)
    monkeypatch.setenv("BDA_V2_WORKER_QUEUES", "research")
    executed = []
    monkeypatch.setattr(runner.os, "execvp", lambda command, args: executed.append((command, args)))
    assert runner.main() == 0
    assert executed == [("celery", runner.WORKER_COMMAND)]
    assert runner.os.environ["BDA_V2_WORKER_QUEUES"] == "scheduler"


def test_startup_refuses_queue_overrides(monkeypatch):
    monkeypatch.setattr(runner.sys, "argv", ["scheduler", "-Q", "research"])
    monkeypatch.setattr(runner, "validate_database", lambda _: pytest.fail("Unexpected connection"))
    assert runner.main() == 1
