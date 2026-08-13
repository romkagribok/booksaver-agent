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
-- v13: recovery audit columns are a caller-scoped, content-free operational
-- record. NULL recovery_outcome means that no complete audit has been attached;
-- this intentionally distinguishes legacy/interrupted rows from not_needed.
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
    session_revision    TEXT NOT NULL,
    recovery_outcome    TEXT
        CHECK(recovery_outcome IS NULL OR recovery_outcome IN (
            'not_needed', 'recovered', 'partial', 'unavailable', 'gave_up',
            'blocked', 'provider_error', 'budget_exhausted'
        )),
    recovery_step       TEXT,
    recovery_providers_json TEXT,
    recovery_models_json TEXT,
    recovery_roles_json TEXT,
    recovery_prompt_versions_json TEXT,
    recovery_llm_calls  INTEGER
        CHECK(recovery_llm_calls IS NULL OR recovery_llm_calls >= 0),
    recovery_input_tokens INTEGER
        CHECK(recovery_input_tokens IS NULL OR recovery_input_tokens >= 0),
    recovery_output_tokens INTEGER
        CHECK(recovery_output_tokens IS NULL OR recovery_output_tokens >= 0),
    recovery_action_count INTEGER
        CHECK(recovery_action_count IS NULL OR recovery_action_count >= 0),
    recovery_duration_ms INTEGER
        CHECK(recovery_duration_ms IS NULL OR recovery_duration_ms >= 0),
    recovery_trace_json TEXT
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

-- v14: restart-safe deployment-wide adaptive-model spend and aggregate-only
-- qualification results (ADR-031).  Reservation rows contain only bounded
-- machine metadata; no page content, prompts, URLs, booking identity, or keys.
CREATE TABLE IF NOT EXISTS llm_spend_days (
    utc_date TEXT PRIMARY KEY,
    reserved_micro_usd INTEGER NOT NULL CHECK(reserved_micro_usd >= 0),
    charged_micro_usd INTEGER NOT NULL CHECK(charged_micro_usd >= 0),
    limit_micro_usd INTEGER NOT NULL
        CHECK(limit_micro_usd > 0 AND limit_micro_usd <= 10000000),
    price_table_version TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_cost_reservations (
    reservation_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    job_kind TEXT NOT NULL CHECK(job_kind IN (
        'bookings_sync', 'check_now', 'scheduled_slot', 'remote_auth', 'qualification'
    )),
    caller_user_id INTEGER NOT NULL REFERENCES users(user_id),
    utc_date TEXT NOT NULL REFERENCES llm_spend_days(utc_date),
    attempt_ordinal INTEGER NOT NULL CHECK(attempt_ordinal >= 1),
    provider TEXT NOT NULL CHECK(provider = 'anthropic'),
    model TEXT NOT NULL CHECK(model IN ('claude-sonnet-5', 'claude-opus-5')),
    role TEXT NOT NULL CHECK(role IN (
        'recovery', 'interpretation', 'extraction', 'classification', 'diagnostic'
    )),
    prompt_version TEXT NOT NULL,
    trigger TEXT NOT NULL CHECK(trigger IN (
        'initial_ambiguous', 'semantic_no_progress', 'repeated_invalid_schema',
        'unsafe_proposal_rejected', 'unresolved_low_confidence',
        'unverified_sonnet_exhaustion'
    )),
    outcome TEXT CHECK(outcome IS NULL OR outcome IN (
        'completed', 'recovered', 'diagnosed', 'quality_failed', 'provider_failed', 'stopped'
    )),
    reserved_micro_usd INTEGER NOT NULL CHECK(reserved_micro_usd >= 0),
    charged_micro_usd INTEGER CHECK(charged_micro_usd IS NULL OR charged_micro_usd >= 0),
    status TEXT NOT NULL CHECK(status IN ('reserved', 'charged', 'conservative')),
    input_tokens INTEGER CHECK(input_tokens IS NULL OR input_tokens >= 0),
    output_tokens INTEGER CHECK(output_tokens IS NULL OR output_tokens >= 0),
    latency_ms INTEGER CHECK(latency_ms IS NULL OR latency_ms >= 0),
    created_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(job_id, attempt_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_llm_reservations_day_status
    ON llm_cost_reservations(utc_date, status);
CREATE INDEX IF NOT EXISTS idx_llm_reservations_job_ordinal
    ON llm_cost_reservations(job_id, attempt_ordinal);
CREATE INDEX IF NOT EXISTS idx_llm_reservations_caller
    ON llm_cost_reservations(caller_user_id);

CREATE TABLE IF NOT EXISTS llm_profile_qualifications (
    qualification_id TEXT PRIMARY KEY,
    profile_identity TEXT NOT NULL,
    fixture_version TEXT NOT NULL,
    runs INTEGER NOT NULL CHECK(runs >= 0),
    correct_runs INTEGER NOT NULL CHECK(correct_runs >= 0 AND correct_runs <= runs),
    diagnosis_runs INTEGER NOT NULL CHECK(diagnosis_runs >= 0 AND diagnosis_runs <= runs),
    diagnosis_correct_runs INTEGER NOT NULL
        CHECK(diagnosis_correct_runs >= 0 AND diagnosis_correct_runs <= diagnosis_runs),
    schema_valid_runs INTEGER NOT NULL
        CHECK(schema_valid_runs >= 0 AND schema_valid_runs <= runs),
    prohibited_action_proposals INTEGER NOT NULL CHECK(prohibited_action_proposals >= 0),
    prohibited_action_executions INTEGER NOT NULL CHECK(prohibited_action_executions >= 0),
    escalation_count INTEGER NOT NULL CHECK(escalation_count >= 0),
    total_calls INTEGER NOT NULL CHECK(total_calls >= 0),
    total_actions INTEGER NOT NULL CHECK(total_actions >= 0),
    input_tokens INTEGER NOT NULL CHECK(input_tokens >= 0),
    output_tokens INTEGER NOT NULL CHECK(output_tokens >= 0),
    latency_ms INTEGER NOT NULL CHECK(latency_ms >= 0),
    estimated_micro_usd INTEGER NOT NULL CHECK(estimated_micro_usd >= 0),
    gate_result TEXT NOT NULL CHECK(gate_result IN ('passed', 'failed')),
    completed_at TEXT NOT NULL,
    override_owner_user_id INTEGER REFERENCES users(user_id),
    override_reason TEXT,
    overridden_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_qualifications_profile_fixture
    ON llm_profile_qualifications(profile_identity, fixture_version, completed_at DESC);

-- v15: content-free DOM-drift incident correlation, durable owner-alert state,
-- and short-lived encrypted diagnostics (ADR-034).  Caller identity and page
-- content never appear in these metadata tables.  The only caller linkage is
-- inside dom_drift_diagnostics.ciphertext so user purge can remain private.
CREATE TABLE IF NOT EXISTS dom_drift_incidents (
    incident_id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE CHECK(length(fingerprint) = 64),
    journey TEXT NOT NULL CHECK(length(journey) BETWEEN 1 AND 64),
    registered_step TEXT NOT NULL CHECK(length(registered_step) BETWEEN 1 AND 96),
    terminal_class TEXT NOT NULL CHECK(length(terminal_class) BETWEEN 1 AND 64),
    verifier_category TEXT NOT NULL CHECK(length(verifier_category) BETWEEN 1 AND 128),
    structural_digest TEXT NOT NULL CHECK(length(structural_digest) = 64),
    model_roles_json TEXT NOT NULL CHECK(length(model_roles_json) <= 256),
    provider_state TEXT NOT NULL CHECK(length(provider_state) BETWEEN 1 AND 64),
    budget_state TEXT NOT NULL CHECK(length(budget_state) BETWEEN 1 AND 64),
    provenance TEXT NOT NULL CHECK(provenance IN (
        'sonnet_assisted', 'opus_assisted', 'model_diagnosed',
        'code_maintenance_required'
    )),
    state TEXT NOT NULL CHECK(state IN ('observing', 'open', 'resolved')),
    severity TEXT NOT NULL CHECK(severity IN ('observing', 'maintenance_required')),
    recovered INTEGER NOT NULL CHECK(recovered IN (0, 1)),
    occurrence_count INTEGER NOT NULL CHECK(occurrence_count >= 1),
    window_occurrence_count INTEGER NOT NULL CHECK(window_occurrence_count >= 1),
    window_started_at TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    opened_at TEXT,
    resolved_at TEXT,
    alert_suppressed_until TEXT,
    evidence_state TEXT NOT NULL CHECK(evidence_state IN (
        'pending', 'available', 'unavailable', 'expired', 'purged',
        'corrupt', 'undecryptable', 'oversized'
    ))
);

CREATE INDEX IF NOT EXISTS idx_dom_drift_incidents_state_last
    ON dom_drift_incidents(state, last_observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_dom_drift_incidents_step_state
    ON dom_drift_incidents(journey, registered_step, state);

CREATE TABLE IF NOT EXISTS dom_drift_alerts (
    alert_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES dom_drift_incidents(incident_id),
    generation INTEGER NOT NULL CHECK(generation >= 1),
    severity TEXT NOT NULL CHECK(severity IN ('observing', 'maintenance_required')),
    delivery_state TEXT NOT NULL CHECK(delivery_state IN (
        'pending', 'in_flight', 'delivered', 'retryable_failed', 'failed',
        'delivery_unknown', 'suppressed'
    )),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    next_attempt_at TEXT,
    claimed_at TEXT,
    delivered_at TEXT,
    failure_code TEXT CHECK(failure_code IS NULL OR length(failure_code) <= 64),
    created_at TEXT NOT NULL,
    UNIQUE(incident_id, generation)
);

CREATE INDEX IF NOT EXISTS idx_dom_drift_alerts_due
    ON dom_drift_alerts(delivery_state, next_attempt_at, created_at);

CREATE TABLE IF NOT EXISTS dom_drift_diagnostics (
    incident_id TEXT PRIMARY KEY REFERENCES dom_drift_incidents(incident_id),
    envelope_version INTEGER NOT NULL CHECK(envelope_version >= 1),
    ciphertext BLOB NOT NULL,
    byte_size INTEGER NOT NULL CHECK(byte_size > 0 AND byte_size <= 1048576),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL CHECK(expires_at > created_at),
    evidence_state TEXT NOT NULL CHECK(evidence_state = 'available')
);

CREATE INDEX IF NOT EXISTS idx_dom_drift_diagnostics_expiry
    ON dom_drift_diagnostics(expires_at);

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
