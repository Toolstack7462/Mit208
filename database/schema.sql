-- PhishGuard PostgreSQL schema (MIT208 MVP)
-- ------------------------------------------------------------------
-- Run against the phishguard_db database, e.g.:
--   createdb phishguard_db
--   psql -d phishguard_db -f database/schema.sql
--
-- NOTE: The FastAPI backend also auto-creates these tables on startup
-- (SQLAlchemy Base.metadata.create_all), so running this file is OPTIONAL.
-- It is provided for reference and for setting up the DB without the app.
-- ------------------------------------------------------------------

DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS staff_release_requests CASCADE;
DROP TABLE IF EXISTS analyst_reviews CASCADE;
DROP TABLE IF EXISTS email_records CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 1. Users -----------------------------------------------------------
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(32)  NOT NULL DEFAULT 'staff',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_users_role CHECK (role IN ('analyst', 'staff', 'admin'))
);
CREATE INDEX idx_users_email ON users (email);

-- 2. Email records ---------------------------------------------------
CREATE TABLE email_records (
    id            SERIAL PRIMARY KEY,
    message_id    VARCHAR(255) UNIQUE NOT NULL,
    sender        VARCHAR(320) NOT NULL,
    sender_name   VARCHAR(255),
    recipient     VARCHAR(320) NOT NULL,
    subject       VARCHAR(500) NOT NULL DEFAULT '',
    body          TEXT         NOT NULL DEFAULT '',
    status        VARCHAR(32)  NOT NULL DEFAULT 'inbox',     -- inbox | quarantined | released | confirmed_phishing | safe
    risk_score    INTEGER      NOT NULL DEFAULT 0,           -- 0..100
    risk_level    VARCHAR(16)  NOT NULL DEFAULT 'low',       -- low | medium | high | critical
    score_reasons TEXT         NOT NULL DEFAULT '[]',        -- JSON array of explanation strings
    auth_spf      VARCHAR(8)   NOT NULL DEFAULT 'pass',      -- pass | fail | none (simulated)
    auth_dkim     VARCHAR(8)   NOT NULL DEFAULT 'pass',
    auth_dmarc    VARCHAR(8)   NOT NULL DEFAULT 'pass',
    ai_generated  BOOLEAN      NOT NULL DEFAULT FALSE,
    received_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_email_status CHECK (
        status IN ('inbox', 'quarantined', 'released', 'confirmed_phishing', 'safe')),
    CONSTRAINT ck_email_risk_level CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT ck_email_risk_score CHECK (risk_score >= 0 AND risk_score <= 100),
    CONSTRAINT ck_email_spf   CHECK (auth_spf   IN ('pass', 'fail', 'none')),
    CONSTRAINT ck_email_dkim  CHECK (auth_dkim  IN ('pass', 'fail', 'none')),
    CONSTRAINT ck_email_dmarc CHECK (auth_dmarc IN ('pass', 'fail', 'none'))
);
CREATE INDEX idx_email_status ON email_records (status);
CREATE INDEX idx_email_recipient ON email_records (recipient);

-- 3. Analyst reviews -------------------------------------------------
CREATE TABLE analyst_reviews (
    id          SERIAL PRIMARY KEY,
    email_id    INTEGER NOT NULL REFERENCES email_records (id) ON DELETE CASCADE,
    analyst_id  INTEGER NOT NULL REFERENCES users (id),
    action      VARCHAR(32) NOT NULL,                        -- quarantine | release | confirm_phishing | feedback
    verdict     VARCHAR(32),                                 -- phishing | safe | unsure
    feedback    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_review_action CHECK (
        action IN ('quarantine', 'release', 'confirm_phishing', 'feedback'))
);
CREATE INDEX idx_review_email ON analyst_reviews (email_id);
CREATE INDEX idx_review_analyst ON analyst_reviews (analyst_id);

-- 4. Staff release requests -----------------------------------------
CREATE TABLE staff_release_requests (
    id            SERIAL PRIMARY KEY,
    email_id      INTEGER NOT NULL REFERENCES email_records (id) ON DELETE CASCADE,
    requested_by  INTEGER NOT NULL REFERENCES users (id),
    reason        TEXT NOT NULL DEFAULT '',
    status        VARCHAR(16) NOT NULL DEFAULT 'pending',     -- pending | approved | denied
    reviewed_by   INTEGER REFERENCES users (id),
    review_note   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at   TIMESTAMPTZ,
    CONSTRAINT ck_request_status CHECK (status IN ('pending', 'approved', 'denied')),
    -- A decided request must record its reviewer; a pending one must not.
    CONSTRAINT ck_request_decision_complete CHECK (
        (status =  'pending' AND reviewed_by IS     NULL AND reviewed_at IS     NULL) OR
        (status <> 'pending' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);
CREATE INDEX idx_request_status ON staff_release_requests (status);
CREATE INDEX idx_request_requester ON staff_release_requests (requested_by);

-- The API rejects a duplicate open request, but the check and the INSERT are two
-- statements, so two concurrent submissions could both pass. This partial unique
-- index makes "at most one pending request per email per user" atomic.
CREATE UNIQUE INDEX uq_request_one_pending_per_email_user
    ON staff_release_requests (email_id, requested_by)
    WHERE status = 'pending';

-- 5. Audit logs ------------------------------------------------------
CREATE TABLE audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users (id),
    actor_email VARCHAR(255),
    action      VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64),
    entity_id   INTEGER,
    details     TEXT,
    ip_address  VARCHAR(64),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_action ON audit_logs (action);
CREATE INDEX idx_audit_created ON audit_logs (created_at);
CREATE INDEX idx_audit_user ON audit_logs (user_id);
