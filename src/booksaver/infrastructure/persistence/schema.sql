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
    status           TEXT    NOT NULL DEFAULT 'active'
);

-- v2: finalised by Unit 2 (booking-com-price-monitor)
CREATE TABLE IF NOT EXISTS check_history (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id              TEXT    NOT NULL UNIQUE,
    booking_id            TEXT    NOT NULL REFERENCES bookings(booking_id),
    checked_at            TEXT    NOT NULL,
    outcome               TEXT    NOT NULL CHECK(outcome IN ('success', 'failure')),
    extraction_method     TEXT    NOT NULL CHECK(extraction_method IN ('dom', 'llm', 'none')),
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
