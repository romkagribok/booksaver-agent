CREATE TABLE IF NOT EXISTS schema_meta (
    version    INTEGER NOT NULL,
    applied_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id       TEXT    PRIMARY KEY,
    platform         TEXT    NOT NULL CHECK(platform = 'booking_com'),
    product_type     TEXT    NOT NULL CHECK(product_type = 'hotel'),
    confirmation_id  TEXT    NOT NULL UNIQUE,
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
    occ_rooms        INTEGER CHECK(occ_rooms IS NULL OR occ_rooms >= 1)
);

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
    failure_detail        TEXT
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
