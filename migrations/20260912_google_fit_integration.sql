-- PPIS Google Fit connection migration
-- Safe to run more than once on PostgreSQL.

BEGIN;

CREATE TABLE IF NOT EXISTS google_fitness_connections (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE
        REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(30) NOT NULL DEFAULT 'google_fit',
    access_token TEXT NULL,
    refresh_token TEXT NOT NULL,
    token_type VARCHAR(30) NOT NULL DEFAULT 'Bearer',
    scope TEXT NULL,
    expires_at TIMESTAMPTZ NULL,
    last_sync_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_google_fitness_connections_user_id
    ON google_fitness_connections(user_id);

COMMIT;
