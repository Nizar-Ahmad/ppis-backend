-- PPIS Google Health API migration.
-- Safe/idempotent PostgreSQL migration.
--
-- The previous google_fitness_connections table is intentionally
-- left in place for rollback safety. Google Fit OAuth tokens are
-- not copied because the Google Health API requires different scopes.

BEGIN;

CREATE TABLE IF NOT EXISTS google_health_connections (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE
        REFERENCES users(id)
        ON DELETE CASCADE,

    provider VARCHAR(30)
        NOT NULL
        DEFAULT 'google_health',

    access_token TEXT NULL,

    refresh_token TEXT
        NOT NULL,

    token_type VARCHAR(30)
        NOT NULL
        DEFAULT 'Bearer',

    scope TEXT NULL,

    expires_at TIMESTAMPTZ NULL,

    last_sync_at TIMESTAMPTZ NULL,

    created_at TIMESTAMPTZ
        NOT NULL,

    updated_at TIMESTAMPTZ
        NOT NULL
);

CREATE INDEX IF NOT EXISTS
    ix_google_health_connections_user_id
ON google_health_connections(user_id);

COMMIT;
