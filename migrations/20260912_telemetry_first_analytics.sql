-- PPIS telemetry-first analytics migration
-- Required because Base.metadata.create_all() does not alter existing tables.
-- Safe to run more than once on PostgreSQL.

BEGIN;

ALTER TABLE daily_scores
    ADD COLUMN IF NOT EXISTS data_coverage DOUBLE PRECISION NOT NULL DEFAULT 0;

ALTER TABLE daily_scores
    ADD COLUMN IF NOT EXISTS stress_data_coverage DOUBLE PRECISION NOT NULL DEFAULT 0;

ALTER TABLE notification_preferences
    ADD COLUMN IF NOT EXISTS daily_report_email BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE notification_preferences
    ADD COLUMN IF NOT EXISTS last_daily_report_date DATE NULL;

COMMIT;
