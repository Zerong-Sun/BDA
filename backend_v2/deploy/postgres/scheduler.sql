-- Run after migrations as a PostgreSQL administrator (Compose: bda) using psql.
-- Pass BDA_V2_SCHEDULER_PASSWORD through the process environment, never argv.
-- This login connects directly to PostgreSQL and is used ONLY by scheduler.
\set ON_ERROR_STOP on
\getenv scheduler_password BDA_V2_SCHEDULER_PASSWORD
BEGIN;
SELECT length(:'scheduler_password') >= 32 AS password_valid \gset
\if :password_valid
\else
  -- psql's \quit ignores exit-code arguments and returns success. Raise an
  -- actual SQL error so ON_ERROR_STOP rolls back and exits nonzero.
  DO $$ BEGIN
    RAISE EXCEPTION 'BDA_V2_SCHEDULER_PASSWORD must contain at least 32 characters';
  END $$;
\endif
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bda_scheduler') THEN
    CREATE ROLE bda_scheduler LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOINHERIT BYPASSRLS;
  END IF;
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'bda_scheduler' AND
      (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolinherit
       OR NOT rolbypassrls OR NOT rolcanlogin)) THEN
    RAISE EXCEPTION 'Existing bda_scheduler has unexpected capabilities';
  END IF;
END $$;
SELECT format('ALTER ROLE bda_scheduler PASSWORD %L', :'scheduler_password') \gexec
GRANT CONNECT ON DATABASE bda_v2 TO bda_scheduler;
GRANT USAGE ON SCHEMA public TO bda_scheduler;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bda_scheduler;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bda_scheduler;
-- Defaults apply to the role running this script. In production run these as
-- the actual Alembic object owner (or FOR ROLE that owner), too.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bda_scheduler;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO bda_scheduler;
COMMIT;
