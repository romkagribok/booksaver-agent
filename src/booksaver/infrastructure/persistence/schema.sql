CREATE TABLE IF NOT EXISTS schema_meta (
    version    INTEGER NOT NULL,
    applied_at TEXT    NOT NULL
);

-- v7: added by intent 003 bolt 009 (user-access-and-keys, US-029) — multi-user
-- foundation. Exactly one 'owner' row exists at all times (partial unique
-- index below). encrypted_key is an opaque, nullable blob reserved for the
-- later personal-key intake slice (US-027); nothing reads/writes it yet.
-- v9: telegram_username is optional, mutable display metadata (US-063). It is
-- deliberately nullable and non-unique; authorization continues to use only
-- telegram_user_id.
CREATE TABLE IF NOT EXISTS users (
    user_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE,
    telegram_username TEXT,
    role             TEXT    NOT NULL CHECK(role IN ('owner', 'user')),
    access_state     TEXT    NOT NULL DEFAULT 'active'
        CHECK(access_state IN ('active', 'revoked')),
    encrypted_key    BLOB,
    created_at       TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_single_owner
    ON users(role) WHERE role = 'owner';

-- v8: added by intent 003 bolt 009 (user-access-and-keys, US-026) — owner-issued
-- single-use invite codes for `invite` access mode. Purely additive (no rebuild
-- of an existing table needed), per the same CREATE-IF-NOT-EXISTS pattern as
-- savings_opportunities (v3), rebook_sessions/events (v4), and check_traces (v6).
CREATE TABLE IF NOT EXISTS invite_codes (
    code       TEXT    PRIMARY KEY,
    issued_by  INTEGER NOT NULL REFERENCES users(user_id),
    issued_at  TEXT    NOT NULL,
    expires_at TEXT,
    used_by    INTEGER REFERENCES users(user_id),
    used_at    TEXT
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id       TEXT    PRIMARY KEY,
    platform         TEXT    NOT NULL CHECK(platform = 'booking_com'),
    product_type     TEXT    NOT NULL CHECK(product_type = 'hotel'),
    confirmation_id  TEXT    NOT NULL,
    property_name    TEXT    NOT NULL,
    property_ref     TEXT    NOT NULL,
    check_in         TEXT    NOT NULL,
    check_out        TEXT    NOT NULL CHECK(check_out > check_in),
    room_type        TEXT    NOT NULL,
    baseline_amount  TEXT    NOT NULL,
    baseline_currency TEXT   NOT NULL,
    refundable       INTEGER NOT NULL CHECK(refundable = 1),
    refund_note      TEXT    NOT NULL DEFAULT '',
    refund_deadline  TEXT,
    registered_at    TEXT    NOT NULL,
    status           TEXT    NOT NULL DEFAULT 'active',
    -- v5: occupancy (ADR-014). NULL is reserved for rows registered before v5;
    -- new registrations always set all three (enforced in the domain layer).
    occ_adults       INTEGER CHECK(occ_adults IS NULL OR occ_adults >= 1),
    occ_children     INTEGER CHECK(occ_children IS NULL OR occ_children >= 0),
    occ_rooms        INTEGER CHECK(occ_rooms IS NULL OR occ_rooms >= 1),
    -- v7: ownership (US-029). Pre-v7 rows are backfilled to the owner user.
    user_id          INTEGER NOT NULL REFERENCES users(user_id),
    UNIQUE(user_id, confirmation_id)
);

CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);

-- v11: Booking.com account inventory is authoritative (ADR-027). These rows
-- include ineligible/incomplete/cancelled reservations; `bookings` above is the
-- strict derived monitoring projection for eligible rows only.
CREATE TABLE IF NOT EXISTS booking_sync_runs (
    run_id             TEXT PRIMARY KEY,
    user_id            INTEGER NOT NULL REFERENCES users(user_id),
    trigger             TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    completed_at        TEXT NOT NULL,
    completeness        TEXT NOT NULL
        CHECK(completeness IN ('complete', 'incomplete', 'failed')),
    failure_code        TEXT,
    failure_detail      TEXT,
    discovered_count    INTEGER NOT NULL,
    eligible_count      INTEGER NOT NULL,
    ineligible_count    INTEGER NOT NULL,
    session_revision    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_booking_sync_runs_user
    ON booking_sync_runs(user_id, completed_at DESC);

CREATE TABLE IF NOT EXISTS account_reservations (
    account_reservation_id TEXT PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(user_id),
    remote_key_hash         TEXT NOT NULL,
    confirmation_id         TEXT,
    property_name           TEXT,
    property_ref            TEXT,
    check_in                TEXT,
    check_out               TEXT,
    room_type               TEXT,
    baseline_amount         TEXT,
    baseline_currency       TEXT,
    refundable              INTEGER,
    refund_note             TEXT NOT NULL DEFAULT '',
    refund_deadline         TEXT,
    occ_adults              INTEGER,
    occ_children            INTEGER,
    occ_rooms               INTEGER,
    remote_lifecycle        TEXT NOT NULL,
    eligibility_status      TEXT NOT NULL
        CHECK(eligibility_status IN ('eligible', 'ineligible')),
    eligibility_reasons     TEXT NOT NULL DEFAULT '[]',
    snapshot_revision       INTEGER NOT NULL DEFAULT 1,
    first_observed_at       TEXT NOT NULL,
    last_observed_at        TEXT NOT NULL,
    last_sync_run_id        TEXT NOT NULL REFERENCES booking_sync_runs(run_id),
    monitoring_booking_id   TEXT UNIQUE REFERENCES bookings(booking_id),
    UNIQUE(user_id, remote_key_hash)
);

CREATE INDEX IF NOT EXISTS idx_account_reservations_user
    ON account_reservations(user_id, last_observed_at DESC);

-- v12: durable per-user randomized daily monitoring slots (ADR-029). The
-- schedule owns execution lifecycle only; booking checks and their outcomes
-- remain in the existing booking-scoped tables below.
CREATE TABLE IF NOT EXISTS scheduled_check_slots (
    user_id       INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    schedule_date TEXT    NOT NULL,
    ordinal       INTEGER NOT NULL CHECK(ordinal >= 0),
    planned_at    TEXT    NOT NULL,
    status        TEXT    NOT NULL
        CHECK(status IN ('planned', 'running', 'completed', 'missed')),
    started_at    TEXT,
    finished_at   TEXT,
    miss_reason   TEXT,
    created_at    TEXT    NOT NULL,
    PRIMARY KEY (user_id, schedule_date, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_scheduled_slots_due
    ON scheduled_check_slots(status, planned_at, user_id, ordinal);

CREATE INDEX IF NOT EXISTS idx_scheduled_slots_user_next
    ON scheduled_check_slots(user_id, status, planned_at);

-- v2: finalised by Unit 2 (booking-com-price-monitor)
-- v5: extraction_method also allows 'agent' (bolt 007 agent-assisted checks)
CREATE TABLE IF NOT EXISTS check_history (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id              TEXT    NOT NULL UNIQUE,
    booking_id            TEXT    NOT NULL REFERENCES bookings(booking_id),
    checked_at            TEXT    NOT NULL,
    outcome               TEXT    NOT NULL CHECK(outcome IN ('success', 'failure')),
    extraction_method     TEXT    NOT NULL
        CHECK(extraction_method IN ('dom', 'llm', 'none', 'agent')),
    live_amount           TEXT,
    live_currency         TEXT,
    refundable            INTEGER,
    cancellation_deadline TEXT,
    refund_raw_text       TEXT,
    extracted_property    TEXT,
    extracted_room        TEXT,
    extracted_check_in    TEXT,
    extracted_check_out   TEXT,
    failure_code          TEXT,
    failure_detail        TEXT,
    source_channel        TEXT,
    source_device_profile TEXT,
    source_session_revision TEXT,
    source_authentication TEXT,
    source_genius_evidence TEXT,
    source_observed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_check_history_booking
    ON check_history(booking_id, checked_at DESC);

-- v4: added by Unit 4 (guided-rebook) — session state + append-only audit trail
CREATE TABLE IF NOT EXISTS rebook_sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL UNIQUE,
    opportunity_id TEXT NOT NULL,
    booking_id     TEXT NOT NULL REFERENCES bookings(booking_id),
    state          TEXT NOT NULL,
    started_at     TEXT NOT NULL,
    ended_at       TEXT,
    end_reason     TEXT
);

CREATE TABLE IF NOT EXISTS rebook_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL UNIQUE,
    session_id  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
);

-- v6: added by intent 002 bolt 007 (agentic-escalation) — one trace per check
CREATE TABLE IF NOT EXISTS check_traces (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id   TEXT NOT NULL UNIQUE,
    booking_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    trace_json TEXT NOT NULL
);

-- v3: added by Unit 3 (savings-detection-notifications)
CREATE TABLE IF NOT EXISTS savings_opportunities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL UNIQUE,
    booking_id      TEXT NOT NULL REFERENCES bookings(booking_id),
    check_id        TEXT NOT NULL,
    baseline_amount TEXT NOT NULL,
    live_amount     TEXT NOT NULL,
    currency        TEXT NOT NULL,
    amount_saved    TEXT NOT NULL,
    percent_saved   TEXT NOT NULL,
    validated_at    TEXT NOT NULL,
    notified_at     TEXT
);
