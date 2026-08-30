-- Run once as a PostgreSQL administrator, before the first production migration.
-- Login roles and passwords are provisioned by the site's secret manager; these
-- NOLOGIN roles are stable capability groups and deliberately cannot authenticate.

CREATE ROLE bda_migrator NOLOGIN NOINHERIT BYPASSRLS;
CREATE ROLE bda_app NOLOGIN NOINHERIT NOBYPASSRLS;
CREATE ROLE bda_worker NOLOGIN NOINHERIT NOBYPASSRLS;
CREATE ROLE bda_maintenance NOLOGIN NOINHERIT BYPASSRLS;

GRANT CONNECT ON DATABASE bda_v2 TO bda_migrator, bda_app, bda_worker, bda_maintenance;
GRANT USAGE ON SCHEMA public TO bda_migrator, bda_app, bda_worker, bda_maintenance;

-- The migrator owns schema changes. Grant your maintenance login this role and use
-- that login only in BDA_V2_MAINTENANCE_DATABASE_URL.
GRANT CREATE ON SCHEMA public TO bda_migrator;

-- Run these grants after the initial migration, then retain the default privileges for
-- future Alembic-created objects. The role executing Alembic must be bda_migrator (or a
-- login SET ROLE-ing to it), otherwise PostgreSQL applies defaults to the wrong owner.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bda_app, bda_worker, bda_maintenance;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bda_app, bda_worker, bda_maintenance;
ALTER DEFAULT PRIVILEGES FOR ROLE bda_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bda_app, bda_worker, bda_maintenance;
ALTER DEFAULT PRIVILEGES FOR ROLE bda_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO bda_app, bda_worker, bda_maintenance;

-- Example site bindings (replace these LOGIN role names with secret-managed roles).
-- Alembic connects as bda_migration_login and immediately SET ROLE bda_migrator;
-- the login itself therefore needs no schema privileges beyond membership.
-- GRANT bda_migrator TO bda_migration_login;
-- GRANT bda_app TO bda_api_login;
-- GRANT bda_worker TO bda_worker_login;
-- GRANT bda_maintenance TO bda_maintenance_login;

-- Required assertions before enabling writes:
--   SELECT rolname, rolbypassrls FROM pg_roles
--    WHERE rolname IN ('bda_migrator', 'bda_app', 'bda_worker', 'bda_maintenance');
--   SELECT tableowner, count(*) FROM pg_tables
--    WHERE schemaname = 'public' GROUP BY tableowner;
-- API and worker LOGIN roles must not own public tables and must have NOBYPASSRLS.
-- Only the scheduler deployment may use bda_maintenance; it must never consume
-- operation queues or serve requests.
