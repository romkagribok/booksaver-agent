from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from booksaver.domain.account_sync import (
    AccountReservation,
    EligibilityDecision,
    EligibilityReason,
    EligibilityStatus,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    SynchronizationReport,
    SynchronizationTrigger,
    evaluate_eligibility,
    remote_key_hash,
)
from booksaver.domain.agent import CheckTrace, TraceEvent, TraceKind
from booksaver.domain.check_result import (
    CheckOutcome,
    CheckResult,
    ExtractedBookingFields,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
)
from booksaver.domain.errors import BookingRejectedError
from booksaver.domain.mobile_web import (
    AuthenticationEvidence,
    GeniusEvidence,
    MobileProfileId,
    PriceSourceChannel,
    PriceSourceProvenance,
)
from booksaver.domain.models import Booking, BookingStatus
from booksaver.domain.post_rebook import (
    MonitoringDisposition,
    PostRebookContext,
    PostRebookRejected,
    PostRebookRejection,
    PostRebookResult,
    ReplacementFacts,
)
from booksaver.domain.rebook import (
    EventType as RebookEventType,
)
from booksaver.domain.rebook import (
    RebookEvent,
    RebookSession,
)
from booksaver.domain.rebook import (
    SessionState as RebookSessionState,
)
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.user import InviteCode, User, UserAccessState, UserRole
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Occupancy,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)

SCHEMA_VERSION = 11
_SCHEMA_SQL = Path(__file__).parent / "schema.sql"


@dataclass(frozen=True, slots=True)
class AdminUserAggregate:
    """Allowlisted admin projection; contains no Telegram id or booking data."""

    user_id: int
    telegram_username: str | None
    role: UserRole
    access_state: UserAccessState
    active_booking_count: int

# Columns shared by the v2/v4 and v5 check_history definitions (v5 only relaxes
# the extraction_method CHECK to include 'agent'); used to copy data across the
# table rebuild.
_CHECK_HISTORY_COLUMNS = (
    "id, check_id, booking_id, checked_at, outcome, extraction_method, "
    "live_amount, live_currency, refundable, cancellation_deadline, "
    "refund_raw_text, extracted_property, extracted_room, "
    "extracted_check_in, extracted_check_out, failure_code, failure_detail"
)

# An opportunity is actionable only when its source check is the booking's
# latest conclusive market observation.  Successful checks establish a price;
# NO_EQUIVALENT_OFFER establishes that no eligible rate is currently bookable.
# Every other failure is technical or ambiguous and must not erase the last
# successfully verified saving.
_CURRENT_OPPORTUNITIES_CTE = """
WITH current_opportunities AS (
    SELECT
        selected.*,
        b.user_id AS owner_user_id,
        source.checked_at AS source_checked_at,
        source.id AS source_check_order,
        selected.id AS opportunity_order
    FROM savings_opportunities AS selected
    JOIN check_history AS source
      ON source.check_id = selected.check_id
     AND source.booking_id = selected.booking_id
    JOIN bookings AS b ON b.booking_id = selected.booking_id
    WHERE b.status = 'active'
      AND source.outcome = :success_outcome
      AND NOT EXISTS (
          SELECT 1
          FROM check_history AS newer
          WHERE newer.booking_id = source.booking_id
            AND (
                newer.outcome = :success_outcome
                OR newer.failure_code = :no_equivalent_code
            )
            AND (
                newer.checked_at > source.checked_at
                OR (
                    newer.checked_at = source.checked_at
                    AND newer.id > source.id
                )
            )
      )
      AND NOT EXISTS (
          SELECT 1
          FROM savings_opportunities AS duplicate
          WHERE duplicate.booking_id = selected.booking_id
            AND duplicate.check_id = selected.check_id
            AND duplicate.id > selected.id
      )
)
"""


def _current_opportunity_params(**scope: object) -> dict[str, object]:
    return {
        "success_outcome": CheckOutcome.SUCCESS.value,
        "no_equivalent_code": FailureCode.NO_EQUIVALENT_OFFER.value,
        **scope,
    }


def _delete_booking_rows(conn: sqlite3.Connection, booking_id: str) -> None:
    """Delete rows owned through one booking; caller controls the transaction."""
    conn.execute("DELETE FROM savings_opportunities WHERE booking_id = ?", (booking_id,))
    conn.execute(
        "DELETE FROM rebook_events WHERE session_id IN "
        "(SELECT session_id FROM rebook_sessions WHERE booking_id = ?)",
        (booking_id,),
    )
    conn.execute("DELETE FROM rebook_sessions WHERE booking_id = ?", (booking_id,))
    conn.execute("DELETE FROM check_traces WHERE booking_id = ?", (booking_id,))
    conn.execute("DELETE FROM check_history WHERE booking_id = ?", (booking_id,))
    conn.execute("DELETE FROM bookings WHERE booking_id = ?", (booking_id,))


def _has_active_rebook_session(conn: sqlite3.Connection, booking_id: str) -> bool:
    terminal_states = (
        RebookSessionState.COMPLETED.value,
        RebookSessionState.DECLINED.value,
        RebookSessionState.ERROR.value,
    )
    row = conn.execute(
        "SELECT 1 FROM rebook_sessions WHERE booking_id = ? "
        "AND state NOT IN (?, ?, ?) LIMIT 1",
        (booking_id, *terminal_states),
    ).fetchone()
    return row is not None

def _migrate_v2(conn: sqlite3.Connection) -> None:
    # The v1 check_history table was a contract-only stub (id, booking_id,
    # recorded_at) that never held real data; drop it so schema.sql recreates it
    # with the full column set.
    conn.execute("DROP TABLE IF EXISTS check_history")


def _migrate_v5(conn: sqlite3.Connection) -> None:
    # bookings occupancy columns (ADR-014, NULL = legacy occupancy-missing) and a
    # check_history rebuild so extraction_method also allows 'agent' (bolt 007) —
    # SQLite cannot alter a CHECK constraint in place. Guarded per table: a very
    # old database may not have these tables yet (schema.sql creates them fresh,
    # already in v5 shape, after migrations run).
    tables = {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }

    if "bookings" in tables:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(bookings)")}
        if "occ_adults" not in columns:
            conn.execute(
                "ALTER TABLE bookings ADD COLUMN occ_adults INTEGER "
                "CHECK(occ_adults IS NULL OR occ_adults >= 1)"
            )
            conn.execute(
                "ALTER TABLE bookings ADD COLUMN occ_children INTEGER "
                "CHECK(occ_children IS NULL OR occ_children >= 0)"
            )
            conn.execute(
                "ALTER TABLE bookings ADD COLUMN occ_rooms INTEGER "
                "CHECK(occ_rooms IS NULL OR occ_rooms >= 1)"
            )

    if "check_history" in tables:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'check_history'"
        ).fetchone()
        if row and "'agent'" not in row[0]:
            conn.execute(
                """
                CREATE TABLE check_history_v5 (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_id              TEXT    NOT NULL UNIQUE,
                    booking_id            TEXT    NOT NULL REFERENCES bookings(booking_id),
                    checked_at            TEXT    NOT NULL,
                    outcome               TEXT    NOT NULL
                        CHECK(outcome IN ('success', 'failure')),
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
                )
                """
            )
            conn.execute(
                f"INSERT INTO check_history_v5 ({_CHECK_HISTORY_COLUMNS}) "
                f"SELECT {_CHECK_HISTORY_COLUMNS} FROM check_history"
            )
            conn.execute("DROP TABLE check_history")
            conn.execute("ALTER TABLE check_history_v5 RENAME TO check_history")


# Columns of the pre-v7 bookings table (no user_id yet); used to copy data
# across the v7 table rebuild.
_BOOKINGS_COLUMNS = (
    "booking_id, platform, product_type, confirmation_id, property_name, "
    "property_ref, check_in, check_out, room_type, baseline_amount, "
    "baseline_currency, refundable, refund_note, refund_deadline, "
    "registered_at, status, occ_adults, occ_children, occ_rooms"
)


def _ensure_owner_user(conn: sqlite3.Connection) -> int:
    """Idempotently ensure exactly one 'owner' row exists in `users`; return
    its user_id. Safe to call on both a freshly-created `users` table (fresh
    init) and an already-migrated one (re-open) — a partial unique index on
    `users(role) WHERE role = 'owner'` backs the "exactly one owner" invariant
    at the DB level too.
    """
    row = conn.execute("SELECT user_id FROM users WHERE role = 'owner'").fetchone()
    if row is not None:
        return int(row[0])
    cursor = conn.execute(
        "INSERT INTO users (telegram_user_id, role, access_state, encrypted_key, created_at) "
        "VALUES (NULL, 'owner', 'active', NULL, ?)",
        (datetime.now(UTC).isoformat(),),
    )
    assert cursor.lastrowid is not None
    return int(cursor.lastrowid)


def _migrate_v7(conn: sqlite3.Connection) -> None:
    # users table + owner row (ADR-018 scope amendment, US-029). Guarded per
    # table/column the same way _migrate_v5 is: a very old database may not
    # have `bookings` yet (schema.sql creates it fresh, already in v7 shape).
    #
    # check_history/rebook_sessions REFERENCES bookings(booking_id); PRAGMA
    # foreign_keys only takes effect with no pending transaction, so commit
    # first, then disable it for the duration of the bookings table rebuild
    # below (DROP TABLE bookings would otherwise raise FOREIGN KEY constraint
    # failed even though no row is actually orphaned).
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")

    tables = {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }

    if "users" not in tables:
        conn.execute(
            """
            CREATE TABLE users (
                user_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER UNIQUE,
                role             TEXT    NOT NULL CHECK(role IN ('owner', 'user')),
                access_state     TEXT    NOT NULL DEFAULT 'active'
                    CHECK(access_state IN ('active', 'revoked')),
                encrypted_key    BLOB,
                created_at       TEXT    NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX idx_users_single_owner ON users(role) WHERE role = 'owner'"
        )

    owner_id = _ensure_owner_user(conn)

    if "bookings" in tables:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(bookings)")}
        if "user_id" not in columns:
            conn.execute(
                """
                CREATE TABLE bookings_v7 (
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
                    occ_adults       INTEGER CHECK(occ_adults IS NULL OR occ_adults >= 1),
                    occ_children     INTEGER CHECK(occ_children IS NULL OR occ_children >= 0),
                    occ_rooms        INTEGER CHECK(occ_rooms IS NULL OR occ_rooms >= 1),
                    user_id          INTEGER NOT NULL REFERENCES users(user_id)
                )
                """
            )
            conn.execute(
                f"INSERT INTO bookings_v7 ({_BOOKINGS_COLUMNS}, user_id) "
                f"SELECT {_BOOKINGS_COLUMNS}, ? FROM bookings",
                (owner_id,),
            )
            conn.execute("DROP TABLE bookings")
            conn.execute("ALTER TABLE bookings_v7 RENAME TO bookings")
            conn.execute("CREATE INDEX idx_bookings_user ON bookings(user_id)")

    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")


def _migrate_v9(conn: sqlite3.Connection) -> None:
    """Add optional Telegram username display metadata (US-063).

    Guard both the table and the column so reopening a database after a
    partially applied migration is safe. Fresh databases already receive the
    v9 shape from ``schema.sql``.
    """
    tables = {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    if "users" not in tables:
        return

    columns = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    if "telegram_username" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN telegram_username TEXT")


def _migrate_v10(conn: sqlite3.Connection) -> None:
    """Add durable, non-secret authenticated mobile price provenance."""
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    if "check_history" not in tables:
        return
    columns = {row[1] for row in conn.execute("PRAGMA table_info(check_history)")}
    additions = {
        "source_channel": "TEXT",
        "source_device_profile": "TEXT",
        "source_session_revision": "TEXT",
        "source_authentication": "TEXT",
        "source_genius_evidence": "TEXT",
        "source_observed_at": "TEXT",
    }
    for name, column_type in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE check_history ADD COLUMN {name} {column_type}")


def _migrate_v11(conn: sqlite3.Connection) -> None:
    """Destructive pre-launch cutover to authoritative account inventory.

    The product owner confirmed there are no active users of legacy booking
    state. Preserve access/session/key data, remove every booking-scoped row,
    and rebuild `bookings` with caller-scoped confirmation uniqueness.
    """
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    # Earlier version upgrades run in the same connection transaction. Commit
    # those non-destructive steps before starting the all-or-nothing v11 cutover.
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for table in (
            "account_reservations",
            "booking_sync_runs",
            "rebook_events",
            "rebook_sessions",
            "savings_opportunities",
            "check_traces",
            "check_history",
            "bookings",
        ):
            if table in tables:
                conn.execute(f"DELETE FROM {table}")
        for table in ("account_reservations", "booking_sync_runs"):
            if table in tables:
                conn.execute(f"DROP TABLE {table}")
        if "bookings" in tables:
            conn.execute("DROP TABLE bookings")
        conn.execute(
            """
            CREATE TABLE bookings (
                booking_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL CHECK(platform = 'booking_com'),
                product_type TEXT NOT NULL CHECK(product_type = 'hotel'),
                confirmation_id TEXT NOT NULL,
                property_name TEXT NOT NULL,
                property_ref TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT NOT NULL CHECK(check_out > check_in),
                room_type TEXT NOT NULL,
                baseline_amount TEXT NOT NULL,
                baseline_currency TEXT NOT NULL,
                refundable INTEGER NOT NULL CHECK(refundable = 1),
                refund_note TEXT NOT NULL DEFAULT '',
                refund_deadline TEXT,
                registered_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                occ_adults INTEGER CHECK(occ_adults IS NULL OR occ_adults >= 1),
                occ_children INTEGER CHECK(occ_children IS NULL OR occ_children >= 0),
                occ_rooms INTEGER CHECK(occ_rooms IS NULL OR occ_rooms >= 1),
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                UNIQUE(user_id, confirmation_id)
            )
            """
        )
        conn.execute("CREATE INDEX idx_bookings_user ON bookings(user_id)")
        conn.execute(
            """
            CREATE TABLE booking_sync_runs (
                run_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                trigger TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                completeness TEXT NOT NULL
                    CHECK(completeness IN ('complete', 'incomplete', 'failed')),
                failure_code TEXT,
                failure_detail TEXT,
                discovered_count INTEGER NOT NULL,
                eligible_count INTEGER NOT NULL,
                ineligible_count INTEGER NOT NULL,
                session_revision TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX idx_booking_sync_runs_user "
            "ON booking_sync_runs(user_id, completed_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE account_reservations (
                account_reservation_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                remote_key_hash TEXT NOT NULL,
                confirmation_id TEXT,
                property_name TEXT,
                property_ref TEXT,
                check_in TEXT,
                check_out TEXT,
                room_type TEXT,
                baseline_amount TEXT,
                baseline_currency TEXT,
                refundable INTEGER,
                refund_note TEXT NOT NULL DEFAULT '',
                refund_deadline TEXT,
                occ_adults INTEGER,
                occ_children INTEGER,
                occ_rooms INTEGER,
                remote_lifecycle TEXT NOT NULL,
                eligibility_status TEXT NOT NULL
                    CHECK(eligibility_status IN ('eligible', 'ineligible')),
                eligibility_reasons TEXT NOT NULL DEFAULT '[]',
                snapshot_revision INTEGER NOT NULL DEFAULT 1,
                first_observed_at TEXT NOT NULL,
                last_observed_at TEXT NOT NULL,
                last_sync_run_id TEXT NOT NULL REFERENCES booking_sync_runs(run_id),
                monitoring_booking_id TEXT UNIQUE REFERENCES bookings(booking_id),
                UNIQUE(user_id, remote_key_hash)
            )
            """
        )
        conn.execute(
            "CREATE INDEX idx_account_reservations_user "
            "ON account_reservations(user_id, last_observed_at DESC)"
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# v2 -> v3: savings_opportunities is purely additive (CREATE IF NOT EXISTS covers it).
# v3 -> v4: rebook_sessions + rebook_events, also purely additive.
# v5 -> v6: check_traces, also purely additive.
# v6 -> v7: users table + bookings.user_id (US-029).
# v7 -> v8: invite_codes table, also purely additive (US-026) — no migrate
# function needed; schema.sql's CREATE TABLE IF NOT EXISTS covers it, same as
# v3/v4/v6.
# v8 -> v9: users.telegram_username optional display metadata (US-063).
# v9 -> v10: durable authenticated-mobile price provenance (US-087).
# v10 -> v11: destructive booking cutover + authoritative synchronized inventory.
_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    2: _migrate_v2,
    5: _migrate_v5,
    7: _migrate_v7,
    9: _migrate_v9,
    10: _migrate_v10,
    11: _migrate_v11,
}


class SqliteStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        is_new = not self._db_path.exists()
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        if is_new:
            self._db_path.chmod(0o600)
        self._apply_schema()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SqliteStore:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store not connected. Use connect() or a context manager.")
        return self._conn

    def _apply_schema(self) -> None:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta ("
            "version INTEGER NOT NULL, applied_at TEXT NOT NULL)"
        )
        row = self.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()
        current: int | None = row[0]

        if current is not None and current < SCHEMA_VERSION:
            for version in range(current + 1, SCHEMA_VERSION + 1):
                migrate = _MIGRATIONS.get(version)
                if migrate is not None:
                    migrate(self.conn)
                self.conn.execute(
                    "INSERT INTO schema_meta (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(UTC).isoformat()),
                )

        self.conn.executescript(_SCHEMA_SQL.read_text())

        # Fresh init skips the migration loop entirely (schema.sql already
        # creates the v7 shape), so the owner row must still be created here;
        # a migrated database already has one and this is then a no-op.
        _ensure_owner_user(self.conn)

        if current is None:
            self.conn.execute(
                "INSERT INTO schema_meta (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
            )
        self.conn.commit()


class SqliteBookingRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def add(self, booking: Booking, user_id: int | None = None) -> None:
        """Persist a booking under `user_id` (US-029). When omitted, the
        booking is assigned to the owner user — preserving the pre-multi-user
        default for every existing single-owner caller.
        """
        if user_id is None:
            user_id = _ensure_owner_user(self._store.conn)
        self._store.conn.execute(
            """
            INSERT INTO bookings (
                booking_id, platform, product_type, confirmation_id,
                property_name, property_ref, check_in, check_out,
                room_type, baseline_amount, baseline_currency,
                refundable, refund_note, refund_deadline,
                registered_at, status, occ_adults, occ_children, occ_rooms,
                user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                booking.booking_id,
                booking.platform.value,
                booking.product_type.value,
                booking.confirmation_id.value,
                booking.property.name,
                booking.property.booking_com_ref,
                booking.stay_dates.check_in.isoformat(),
                booking.stay_dates.check_out.isoformat(),
                booking.room_type.label,
                str(booking.baseline_price.amount),
                booking.baseline_price.currency,
                1 if booking.refundability.is_refundable else 0,
                booking.refundability.note,
                booking.refundability.deadline.isoformat()
                if booking.refundability.deadline
                else None,
                booking.registered_at.isoformat(),
                booking.status.value,
                booking.occupancy.adults if booking.occupancy else None,
                booking.occupancy.children if booking.occupancy else None,
                booking.occupancy.rooms if booking.occupancy else None,
                user_id,
            ),
        )
        self._store.conn.commit()

    def set_occupancy(self, booking_id: str, occupancy: Occupancy) -> None:
        cursor = self._store.conn.execute(
            "UPDATE bookings SET occ_adults = ?, occ_children = ?, occ_rooms = ? "
            "WHERE booking_id = ?",
            (occupancy.adults, occupancy.children, occupancy.rooms, booking_id),
        )
        self._store.conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"No booking with id '{booking_id}'")

    def update(self, booking: Booking) -> None:
        """Update editable monitoring fields while preserving row identity/ownership.

        The caller supplies an aggregate already validated by the domain value
        objects. Platform, product type, registration timestamp, status, owner,
        and booking id deliberately cannot be changed through this operation.
        """
        conn = self._store.conn
        try:
            with conn:
                if _has_active_rebook_session(conn, booking.booking_id):
                    raise BookingRejectedError(
                        "Finish or decline the active guided rebook before editing this booking"
                    )
                cursor = conn.execute(
                    """
                    UPDATE bookings SET
                        confirmation_id = ?, property_name = ?, property_ref = ?,
                        check_in = ?, check_out = ?, room_type = ?,
                        baseline_amount = ?, baseline_currency = ?,
                        refundable = ?, refund_note = ?, refund_deadline = ?,
                        occ_adults = ?, occ_children = ?, occ_rooms = ?
                    WHERE booking_id = ?
                    """,
                    (
                        booking.confirmation_id.value,
                        booking.property.name,
                        booking.property.booking_com_ref,
                        booking.stay_dates.check_in.isoformat(),
                        booking.stay_dates.check_out.isoformat(),
                        booking.room_type.label,
                        str(booking.baseline_price.amount),
                        booking.baseline_price.currency,
                        1 if booking.refundability.is_refundable else 0,
                        booking.refundability.note,
                        booking.refundability.deadline.isoformat()
                        if booking.refundability.deadline
                        else None,
                        booking.occupancy.adults if booking.occupancy else None,
                        booking.occupancy.children if booking.occupancy else None,
                        booking.occupancy.rooms if booking.occupancy else None,
                        booking.booking_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"No booking with id '{booking.booking_id}'")
                # Savings are facts about the previous dates/room/occupancy/baseline.
                # The schema has no stale state, so retaining them would let /rebook
                # act on an offer that is no longer equivalent to the edited booking.
                conn.execute(
                    "DELETE FROM savings_opportunities WHERE booking_id = ?",
                    (booking.booking_id,),
                )
        except sqlite3.IntegrityError as exc:
            if "confirmation_id" in str(exc):
                raise BookingRejectedError(
                    f"Booking confirmation '{booking.confirmation_id.value}' "
                    "is already registered"
                ) from exc
            raise

    def delete(self, booking_id: str) -> bool:
        """Delete a booking and all local data scoped through it atomically."""
        conn = self._store.conn
        with conn:
            exists = conn.execute(
                "SELECT 1 FROM bookings WHERE booking_id = ?", (booking_id,)
            ).fetchone()
            if exists is None:
                return False
            if _has_active_rebook_session(conn, booking_id):
                raise BookingRejectedError(
                    "Finish or decline the active guided rebook before deleting this booking"
                )
            _delete_booking_rows(conn, booking_id)
        return True

    def _load_post_rebook_state(
        self,
        context: PostRebookContext,
        handoff_kind: str,
    ) -> tuple[Booking, bool, bool]:
        """Load guarded reconciliation state inside an existing write transaction.

        Returns the current booking plus whether this session already archived or
        activated it. Every lookup is deliberately scoped by local owner id.
        """
        conn = self._store.conn
        user = conn.execute(
            "SELECT access_state FROM users WHERE user_id = ?",
            (context.user_id,),
        ).fetchone()
        if user is None or user["access_state"] != "active":
            raise PostRebookRejected(PostRebookRejection.ACCESS_LOST)

        row = conn.execute(
            "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
            (context.source_booking.booking_id, context.user_id),
        ).fetchone()
        if row is None:
            raise PostRebookRejected(PostRebookRejection.STALE)

        session = conn.execute(
            "SELECT state FROM rebook_sessions "
            "WHERE session_id = ? AND booking_id = ? AND opportunity_id = ?",
            (
                context.session_id,
                context.source_booking.booking_id,
                context.opportunity_id,
            ),
        ).fetchone()
        if session is None or session["state"] not in ("completed", "declined", "error"):
            raise PostRebookRejected(PostRebookRejection.STALE)

        handoff = conn.execute(
            "SELECT 1 FROM rebook_events WHERE session_id = ? "
            "AND detail LIKE ? LIMIT 1",
            (context.session_id, f"telegram_handoff kind={handoff_kind} %"),
        ).fetchone()
        if handoff is None:
            raise PostRebookRejected(PostRebookRejection.STALE)

        archived = conn.execute(
            "SELECT 1 FROM rebook_events WHERE session_id = ? "
            "AND detail LIKE 'post_rebook disposition=source_archived%' LIMIT 1",
            (context.session_id,),
        ).fetchone()
        activated = conn.execute(
            "SELECT 1 FROM rebook_events WHERE session_id = ? "
            "AND detail LIKE 'post_rebook disposition=replacement_active%' LIMIT 1",
            (context.session_id,),
        ).fetchone()
        return self._row_to_booking(row), archived is not None, activated is not None

    def _append_post_rebook_event(self, session_id: str, detail: str) -> None:
        self._store.conn.execute(
            "INSERT INTO rebook_events "
            "(event_id, session_id, event_type, detail, occurred_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                session_id,
                RebookEventType.ACTION_EXECUTED.value,
                detail,
                datetime.now(UTC).isoformat(),
            ),
        )

    def archive_cancelled_source(self, context: PostRebookContext) -> PostRebookResult:
        """Archive a user-reported cancelled source and invalidate its savings atomically."""
        conn = self._store.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            current, already_archived, _already_activated = self._load_post_rebook_state(
                context, "cancel"
            )
            archived_source = replace(context.source_booking, status=BookingStatus.ARCHIVED)
            if current == archived_source and already_archived:
                conn.commit()
                return PostRebookResult(
                    MonitoringDisposition.SOURCE_ALREADY_ARCHIVED, current
                )
            if current != context.source_booking:
                raise PostRebookRejected(PostRebookRejection.STALE)

            conn.execute(
                "UPDATE bookings SET status = 'archived' WHERE booking_id = ? AND user_id = ?",
                (context.source_booking.booking_id, context.user_id),
            )
            conn.execute(
                "DELETE FROM savings_opportunities WHERE booking_id = ?",
                (context.source_booking.booking_id,),
            )
            self._append_post_rebook_event(
                context.session_id,
                "post_rebook disposition=source_archived",
            )
            conn.commit()
            return PostRebookResult(MonitoringDisposition.SOURCE_ARCHIVED, archived_source)
        except Exception:
            conn.rollback()
            raise

    def activate_replacement(
        self, context: PostRebookContext, facts: ReplacementFacts
    ) -> PostRebookResult:
        """Activate actual replacement facts over the stable booking id atomically."""
        replacement = replace(
            context.source_booking,
            confirmation_id=facts.confirmation_id,
            property=Property(
                name=context.source_booking.property.name,
                booking_com_ref=facts.property_ref,
            ),
            baseline_price=facts.actual_total,
            status=BookingStatus.ACTIVE,
        )
        conn = self._store.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            current, source_archived, already_activated = self._load_post_rebook_state(
                context, "book"
            )
            if current == replacement and already_activated:
                conn.commit()
                return PostRebookResult(
                    MonitoringDisposition.REPLACEMENT_ALREADY_ACTIVE, current
                )

            archived_source = replace(context.source_booking, status=BookingStatus.ARCHIVED)
            source_is_valid = current == context.source_booking or (
                current == archived_source and source_archived
            )
            if not source_is_valid:
                raise PostRebookRejected(PostRebookRejection.STALE)

            conflict = conn.execute(
                "SELECT 1 FROM bookings WHERE confirmation_id = ? AND booking_id != ? LIMIT 1",
                (facts.confirmation_id.value, context.source_booking.booking_id),
            ).fetchone()
            if conflict is not None:
                raise PostRebookRejected(PostRebookRejection.CONFLICT)

            conn.execute(
                "UPDATE bookings SET confirmation_id = ?, property_ref = ?, "
                "baseline_amount = ?, baseline_currency = ?, status = 'active' "
                "WHERE booking_id = ? AND user_id = ?",
                (
                    facts.confirmation_id.value,
                    facts.property_ref,
                    str(facts.actual_total.amount),
                    facts.actual_total.currency,
                    context.source_booking.booking_id,
                    context.user_id,
                ),
            )
            conn.execute(
                "DELETE FROM savings_opportunities WHERE booking_id = ?",
                (context.source_booking.booking_id,),
            )
            self._append_post_rebook_event(
                context.session_id,
                "post_rebook disposition=replacement_active "
                f"actual_amount={facts.actual_total.amount} "
                f"currency={facts.actual_total.currency}",
            )
            conn.commit()
            return PostRebookResult(MonitoringDisposition.REPLACEMENT_ACTIVE, replacement)
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            if "confirmation_id" in str(exc):
                raise PostRebookRejected(PostRebookRejection.CONFLICT) from exc
            raise
        except Exception:
            conn.rollback()
            raise

    def get_by_id(self, booking_id: str) -> Booking | None:
        row = self._store.conn.execute(
            "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
        return self._row_to_booking(row) if row else None

    def get_by_confirmation(self, confirmation_id: ConfirmationId) -> Booking | None:
        row = self._store.conn.execute(
            "SELECT * FROM bookings WHERE confirmation_id = ?", (confirmation_id.value,)
        ).fetchone()
        return self._row_to_booking(row) if row else None

    def list_active(self) -> list[Booking]:
        rows = self._store.conn.execute(
            "SELECT * FROM bookings WHERE status = 'active' ORDER BY registered_at DESC"
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def list_all(self) -> list[Booking]:
        rows = self._store.conn.execute(
            "SELECT * FROM bookings ORDER BY registered_at DESC"
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def list_active_for_user(self, user_id: int) -> list[Booking]:
        """US-029 scoping: only this user's active bookings — used by CLI/bot
        read paths so no query path can surface another user's data.
        """
        rows = self._store.conn.execute(
            "SELECT * FROM bookings WHERE status = 'active' AND user_id = ? "
            "ORDER BY registered_at DESC",
            (user_id,),
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def list_all_for_user(self, user_id: int) -> list[Booking]:
        rows = self._store.conn.execute(
            "SELECT * FROM bookings WHERE user_id = ? ORDER BY registered_at DESC",
            (user_id,),
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def get_owner_user_id(self, booking_id: str) -> int | None:
        """Resolve the local `user_id` that owns `booking_id` (US-030 alert
        routing). None if the booking doesn't exist.
        """
        row = self._store.conn.execute(
            "SELECT user_id FROM bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
        return int(row[0]) if row is not None else None

    def exists(self, confirmation_id: ConfirmationId) -> bool:
        row = self._store.conn.execute(
            "SELECT 1 FROM bookings WHERE confirmation_id = ?", (confirmation_id.value,)
        ).fetchone()
        return row is not None

    def _row_to_booking(self, row: sqlite3.Row) -> Booking:
        deadline_str: str | None = row["refund_deadline"]
        occupancy = (
            Occupancy(
                adults=row["occ_adults"],
                children=row["occ_children"] if row["occ_children"] is not None else 0,
                rooms=row["occ_rooms"] if row["occ_rooms"] is not None else 1,
            )
            if row["occ_adults"] is not None
            else None
        )
        return Booking(
            booking_id=row["booking_id"],
            platform=Platform(row["platform"]),
            product_type=ProductType(row["product_type"]),
            confirmation_id=ConfirmationId(row["confirmation_id"]),
            property=Property(
                name=row["property_name"],
                booking_com_ref=row["property_ref"],
            ),
            stay_dates=StayDates(
                check_in=date.fromisoformat(row["check_in"]),
                check_out=date.fromisoformat(row["check_out"]),
            ),
            room_type=RoomType(label=row["room_type"]),
            baseline_price=Money(
                amount=Decimal(row["baseline_amount"]),
                currency=row["baseline_currency"],
            ),
            refundability=RefundabilityPolicy(
                is_refundable=bool(row["refundable"]),
                note=row["refund_note"],
                deadline=date.fromisoformat(deadline_str) if deadline_str else None,
            ),
            registered_at=datetime.fromisoformat(row["registered_at"]),
            status=BookingStatus(row["status"]),
            occupancy=occupancy,
        )


class SqliteAccountReservationRepository:
    """Atomic account-inventory reconciliation (ADRs 027-028)."""

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def reconcile(
        self,
        *,
        user_id: int,
        run_id: str,
        trigger: SynchronizationTrigger,
        session_revision: str,
        result: InventoryDiscoveryResult,
        observed_at: datetime,
    ) -> SynchronizationReport:
        conn = self._store.conn
        decisions = [
            (observation, evaluate_eligibility(observation, today=observed_at.date()))
            for observation in result.observations
        ]
        eligible_count = sum(decision.is_eligible for _, decision in decisions)
        report = SynchronizationReport(
            run_id=run_id,
            completeness=result.completeness,
            discovered=len(decisions),
            eligible=eligible_count,
            ineligible=len(decisions) - eligible_count,
            failure_code=result.failure_code,
            failure_detail=result.failure_detail,
        )
        conn.execute("BEGIN IMMEDIATE")
        try:
            owner = conn.execute(
                "SELECT access_state FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if owner is None or owner["access_state"] != UserAccessState.ACTIVE.value:
                raise PermissionError(
                    "Synchronization owner is no longer an active user"
                )
            conn.execute(
                """
                INSERT INTO booking_sync_runs (
                    run_id, user_id, trigger, started_at, completed_at,
                    completeness, failure_code, failure_detail,
                    discovered_count, eligible_count, ineligible_count,
                    session_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    user_id,
                    trigger.value,
                    observed_at.isoformat(),
                    observed_at.isoformat(),
                    result.completeness.value,
                    result.failure_code.value if result.failure_code else None,
                    (result.failure_detail or "")[:500] or None,
                    report.discovered,
                    report.eligible,
                    report.ineligible,
                    session_revision,
                ),
            )
            if result.completeness is not InventoryCompleteness.FAILED:
                for observation, decision in decisions:
                    self._upsert_observation(
                        conn,
                        user_id=user_id,
                        run_id=run_id,
                        observation=observation,
                        decision=decision,
                        observed_at=observed_at,
                    )
                if result.completeness is InventoryCompleteness.COMPLETE:
                    self._mark_unseen_absent(conn, user_id, run_id, observed_at)
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            failed = SynchronizationReport(
                run_id=run_id,
                completeness=InventoryCompleteness.FAILED,
                discovered=report.discovered,
                eligible=0,
                ineligible=report.discovered,
                failure_code=SynchronizationFailureCode.PERSISTENCE_CONFLICT,
                failure_detail=(
                    "The synchronized reservation identities conflict with existing "
                    "caller-scoped state."
                ),
            )
            conn.execute(
                """
                INSERT INTO booking_sync_runs (
                    run_id, user_id, trigger, started_at, completed_at,
                    completeness, failure_code, failure_detail,
                    discovered_count, eligible_count, ineligible_count,
                    session_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    user_id,
                    trigger.value,
                    observed_at.isoformat(),
                    observed_at.isoformat(),
                    failed.completeness.value,
                    SynchronizationFailureCode.PERSISTENCE_CONFLICT.value,
                    failed.failure_detail,
                    failed.discovered,
                    failed.eligible,
                    failed.ineligible,
                    session_revision,
                ),
            )
            conn.commit()
            return failed
        except Exception:
            conn.rollback()
            raise
        return report

    def list_for_user(self, user_id: int) -> list[AccountReservation]:
        rows = self._store.conn.execute(
            "SELECT * FROM account_reservations WHERE user_id = ? "
            "ORDER BY COALESCE(check_in, '9999-12-31'), first_observed_at",
            (user_id,),
        ).fetchall()
        return [self._row_to_account_reservation(row) for row in rows]

    def latest_run_for_user(self, user_id: int) -> SynchronizationReport | None:
        row = self._store.conn.execute(
            "SELECT * FROM booking_sync_runs WHERE user_id = ? "
            "ORDER BY completed_at DESC, rowid DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        code = (
            SynchronizationFailureCode(row["failure_code"])
            if row["failure_code"]
            else None
        )
        return SynchronizationReport(
            run_id=row["run_id"],
            completeness=InventoryCompleteness(row["completeness"]),
            discovered=row["discovered_count"],
            eligible=row["eligible_count"],
            ineligible=row["ineligible_count"],
            failure_code=code,
            failure_detail=row["failure_detail"],
        )

    def _upsert_observation(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: int,
        run_id: str,
        observation: ReservationObservation,
        decision: EligibilityDecision,
        observed_at: datetime,
    ) -> None:
        fingerprint = remote_key_hash(user_id, observation.remote_id)
        existing = conn.execute(
            "SELECT * FROM account_reservations "
            "WHERE user_id = ? AND remote_key_hash = ?",
            (user_id, fingerprint),
        ).fetchone()
        monitoring_booking_id = (
            str(existing["monitoring_booking_id"])
            if existing is not None and existing["monitoring_booking_id"]
            else None
        )
        if decision.is_eligible:
            monitoring_booking_id = self._upsert_projection(
                conn,
                user_id=user_id,
                existing_booking_id=monitoring_booking_id,
                observation=observation,
                observed_at=observed_at,
            )
        elif monitoring_booking_id is not None:
            self._archive_projection(conn, monitoring_booking_id)

        values = self._observation_values(observation, decision)
        if existing is None:
            conn.execute(
                """
                INSERT INTO account_reservations (
                    account_reservation_id, user_id, remote_key_hash,
                    confirmation_id, property_name, property_ref, check_in, check_out,
                    room_type, baseline_amount, baseline_currency, refundable,
                    refund_note, refund_deadline, occ_adults, occ_children, occ_rooms,
                    remote_lifecycle, eligibility_status, eligibility_reasons,
                    snapshot_revision, first_observed_at, last_observed_at,
                    last_sync_run_id, monitoring_booking_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    fingerprint,
                    *values,
                    observed_at.isoformat(),
                    observed_at.isoformat(),
                    run_id,
                    monitoring_booking_id,
                ),
            )
            return

        current = tuple(
            existing[column]
            for column in (
                "confirmation_id",
                "property_name",
                "property_ref",
                "check_in",
                "check_out",
                "room_type",
                "baseline_amount",
                "baseline_currency",
                "refundable",
                "refund_note",
                "refund_deadline",
                "occ_adults",
                "occ_children",
                "occ_rooms",
                "remote_lifecycle",
                "eligibility_status",
                "eligibility_reasons",
            )
        )
        changed = current != values
        conn.execute(
            """
            UPDATE account_reservations SET
                confirmation_id = ?, property_name = ?, property_ref = ?,
                check_in = ?, check_out = ?, room_type = ?,
                baseline_amount = ?, baseline_currency = ?, refundable = ?,
                refund_note = ?, refund_deadline = ?,
                occ_adults = ?, occ_children = ?, occ_rooms = ?,
                remote_lifecycle = ?, eligibility_status = ?,
                eligibility_reasons = ?,
                snapshot_revision = snapshot_revision + ?,
                last_observed_at = ?, last_sync_run_id = ?,
                monitoring_booking_id = ?
            WHERE account_reservation_id = ?
            """,
            (
                *values,
                1 if changed else 0,
                observed_at.isoformat(),
                run_id,
                monitoring_booking_id,
                existing["account_reservation_id"],
            ),
        )

    @staticmethod
    def _observation_values(
        observation: ReservationObservation, decision: EligibilityDecision
    ) -> tuple[Any, ...]:
        total = observation.booked_total
        occupancy = observation.occupancy
        return (
            observation.confirmation_id,
            observation.property_name,
            observation.property_ref,
            observation.check_in.isoformat() if observation.check_in else None,
            observation.check_out.isoformat() if observation.check_out else None,
            observation.room_type,
            str(total.amount) if total else None,
            total.currency if total else None,
            (
                1
                if observation.refundable is True
                else 0
                if observation.refundable is False
                else None
            ),
            observation.refund_note,
            (
                observation.refund_deadline.isoformat()
                if observation.refund_deadline
                else None
            ),
            occupancy.adults if occupancy else None,
            occupancy.children if occupancy else None,
            occupancy.rooms if occupancy else None,
            observation.lifecycle.value,
            decision.status.value,
            json.dumps([reason.value for reason in decision.reasons]),
        )

    def _upsert_projection(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: int,
        existing_booking_id: str | None,
        observation: ReservationObservation,
        observed_at: datetime,
    ) -> str:
        assert observation.confirmation_id is not None
        assert observation.property_name is not None
        assert observation.property_ref is not None
        assert observation.check_in is not None
        assert observation.check_out is not None
        assert observation.room_type is not None
        assert observation.booked_total is not None
        assert observation.refundable is True
        assert observation.occupancy is not None
        booking_id = existing_booking_id or str(uuid.uuid4())
        values = (
            observation.confirmation_id,
            observation.property_name,
            observation.property_ref,
            observation.check_in.isoformat(),
            observation.check_out.isoformat(),
            observation.room_type,
            str(observation.booked_total.amount),
            observation.booked_total.currency,
            observation.refund_note,
            (
                observation.refund_deadline.isoformat()
                if observation.refund_deadline
                else None
            ),
            observation.occupancy.adults,
            observation.occupancy.children,
            observation.occupancy.rooms,
        )
        existing = conn.execute(
            "SELECT confirmation_id, property_name, property_ref, check_in, check_out, "
            "room_type, baseline_amount, baseline_currency, refund_note, refund_deadline, "
            "occ_adults, occ_children, occ_rooms, status FROM bookings WHERE booking_id = ?",
            (booking_id,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO bookings (
                    booking_id, platform, product_type, confirmation_id,
                    property_name, property_ref, check_in, check_out, room_type,
                    baseline_amount, baseline_currency, refundable, refund_note,
                    refund_deadline, registered_at, status,
                    occ_adults, occ_children, occ_rooms, user_id
                ) VALUES (
                    ?, 'booking_com', 'hotel', ?, ?, ?, ?, ?, ?, ?, ?, 1,
                    ?, ?, ?, 'active', ?, ?, ?, ?
                )
                """,
                (booking_id, *values[:10], observed_at.isoformat(), *values[10:], user_id),
            )
            return booking_id
        changed = tuple(existing[:13]) != values or existing["status"] != "active"
        conn.execute(
            """
            UPDATE bookings SET
                confirmation_id = ?, property_name = ?, property_ref = ?,
                check_in = ?, check_out = ?, room_type = ?,
                baseline_amount = ?, baseline_currency = ?, refundable = 1,
                refund_note = ?, refund_deadline = ?,
                occ_adults = ?, occ_children = ?, occ_rooms = ?, status = 'active'
            WHERE booking_id = ? AND user_id = ?
            """,
            (*values, booking_id, user_id),
        )
        if changed:
            conn.execute(
                "DELETE FROM savings_opportunities WHERE booking_id = ?", (booking_id,)
            )
        return booking_id

    @staticmethod
    def _archive_projection(conn: sqlite3.Connection, booking_id: str) -> None:
        cursor = conn.execute(
            "UPDATE bookings SET status = 'archived' "
            "WHERE booking_id = ? AND status != 'archived'",
            (booking_id,),
        )
        if cursor.rowcount:
            conn.execute(
                "DELETE FROM savings_opportunities WHERE booking_id = ?", (booking_id,)
            )

    def _mark_unseen_absent(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        run_id: str,
        observed_at: datetime,
    ) -> None:
        rows = conn.execute(
            "SELECT account_reservation_id, monitoring_booking_id "
            "FROM account_reservations "
            "WHERE user_id = ? AND last_sync_run_id != ? "
            "AND remote_lifecycle != 'absent'",
            (user_id, run_id),
        ).fetchall()
        for row in rows:
            if row["monitoring_booking_id"]:
                self._archive_projection(conn, row["monitoring_booking_id"])
            conn.execute(
                "UPDATE account_reservations SET remote_lifecycle = 'absent', "
                "eligibility_status = 'ineligible', eligibility_reasons = ?, "
                "snapshot_revision = snapshot_revision + 1, last_sync_run_id = ? "
                "WHERE account_reservation_id = ?",
                (
                    json.dumps([EligibilityReason.NOT_OBSERVED.value]),
                    run_id,
                    row["account_reservation_id"],
                ),
            )

    @staticmethod
    def _row_to_account_reservation(row: sqlite3.Row) -> AccountReservation:
        occupancy = (
            Occupancy(row["occ_adults"], row["occ_children"], row["occ_rooms"])
            if row["occ_adults"] is not None
            else None
        )
        total = (
            Money(Decimal(row["baseline_amount"]), row["baseline_currency"])
            if row["baseline_amount"] is not None and row["baseline_currency"]
            else None
        )
        observation = ReservationObservation(
            remote_id=row["remote_key_hash"],
            confirmation_id=row["confirmation_id"],
            lifecycle=ReservationLifecycle(row["remote_lifecycle"]),
            property_name=row["property_name"],
            property_ref=row["property_ref"],
            check_in=date.fromisoformat(row["check_in"]) if row["check_in"] else None,
            check_out=date.fromisoformat(row["check_out"]) if row["check_out"] else None,
            room_type=row["room_type"],
            booked_total=total,
            refundable=(
                bool(row["refundable"]) if row["refundable"] is not None else None
            ),
            refund_note=row["refund_note"],
            refund_deadline=(
                date.fromisoformat(row["refund_deadline"])
                if row["refund_deadline"]
                else None
            ),
            occupancy=occupancy,
            observed_at=datetime.fromisoformat(row["last_observed_at"]),
            extraction_method="persisted",
        )
        reasons = tuple(
            EligibilityReason(value) for value in json.loads(row["eligibility_reasons"])
        )
        return AccountReservation(
            account_reservation_id=row["account_reservation_id"],
            user_id=row["user_id"],
            remote_key_hash=row["remote_key_hash"],
            observation=observation,
            eligibility=EligibilityDecision(
                EligibilityStatus(row["eligibility_status"]), reasons
            ),
            monitoring_booking_id=row["monitoring_booking_id"],
            first_observed_at=datetime.fromisoformat(row["first_observed_at"]),
            last_observed_at=datetime.fromisoformat(row["last_observed_at"]),
            snapshot_revision=row["snapshot_revision"],
        )


class SqliteCheckHistoryRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def add(self, result: CheckResult) -> None:
        ri = result.refund_indicators
        ef = result.extracted_fields
        self._store.conn.execute(
            """
            INSERT INTO check_history (
                check_id, booking_id, checked_at, outcome, extraction_method,
                live_amount, live_currency, refundable, cancellation_deadline,
                refund_raw_text, extracted_property, extracted_room,
                extracted_check_in, extracted_check_out, failure_code, failure_detail,
                source_channel, source_device_profile, source_session_revision,
                source_authentication, source_genius_evidence, source_observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.check_id,
                result.booking_id,
                result.checked_at.isoformat(),
                result.outcome.value,
                result.extraction_method.value,
                str(result.live_price.amount) if result.live_price else None,
                result.live_price.currency if result.live_price else None,
                (None if ri is None or ri.is_refundable is None else int(ri.is_refundable)),
                (
                    ri.cancellation_deadline.isoformat()
                    if ri and ri.cancellation_deadline
                    else None
                ),
                ri.raw_text if ri else None,
                ef.property_name if ef else None,
                ef.room_label if ef else None,
                ef.check_in.isoformat() if ef and ef.check_in else None,
                ef.check_out.isoformat() if ef and ef.check_out else None,
                result.failure_reason.code.value if result.failure_reason else None,
                result.failure_reason.detail if result.failure_reason else None,
                result.price_source.channel.value if result.price_source else None,
                result.price_source.profile_id.value if result.price_source else None,
                result.price_source.session_revision_id if result.price_source else None,
                result.price_source.authentication.value if result.price_source else None,
                result.price_source.genius_evidence.value if result.price_source else None,
                result.price_source.observed_at.isoformat() if result.price_source else None,
            ),
        )
        self._store.conn.commit()

    def get_recent(self, booking_id: str, limit: int = 10) -> list[CheckResult]:
        rows = self._store.conn.execute(
            "SELECT * FROM check_history WHERE booking_id = ? "
            "ORDER BY checked_at DESC, id DESC LIMIT ?",
            (booking_id, limit),
        ).fetchall()
        return [self._row_to_result(r) for r in rows]

    def count_consecutive_failures(self, booking_id: str) -> int:
        rows = self._store.conn.execute(
            "SELECT outcome FROM check_history WHERE booking_id = ? "
            "ORDER BY checked_at DESC, id DESC",
            (booking_id,),
        ).fetchall()
        count = 0
        for row in rows:
            if row["outcome"] != "failure":
                break
            count += 1
        return count

    def _row_to_result(self, row: sqlite3.Row) -> CheckResult:
        live_price = (
            Money(amount=Decimal(row["live_amount"]), currency=row["live_currency"])
            if row["live_amount"] and row["live_currency"]
            else None
        )
        refund_indicators = None
        if row["refundable"] is not None or row["refund_raw_text"] or row["cancellation_deadline"]:
            refund_indicators = RefundIndicators(
                is_refundable=(None if row["refundable"] is None else bool(row["refundable"])),
                cancellation_deadline=(
                    date.fromisoformat(row["cancellation_deadline"])
                    if row["cancellation_deadline"]
                    else None
                ),
                raw_text=row["refund_raw_text"],
            )
        extracted_fields = None
        if any(
            row[k]
            for k in ("extracted_property", "extracted_room", "extracted_check_in",
                      "extracted_check_out")
        ):
            extracted_fields = ExtractedBookingFields(
                property_name=row["extracted_property"],
                room_label=row["extracted_room"],
                check_in=(
                    date.fromisoformat(row["extracted_check_in"])
                    if row["extracted_check_in"]
                    else None
                ),
                check_out=(
                    date.fromisoformat(row["extracted_check_out"])
                    if row["extracted_check_out"]
                    else None
                ),
            )
        failure_reason = (
            FailureReason(code=FailureCode(row["failure_code"]), detail=row["failure_detail"])
            if row["failure_code"]
            else None
        )
        price_source = None
        if row["source_channel"]:
            price_source = PriceSourceProvenance(
                channel=PriceSourceChannel(row["source_channel"]),
                profile_id=MobileProfileId(row["source_device_profile"]),
                session_revision_id=row["source_session_revision"],
                authentication=AuthenticationEvidence(row["source_authentication"]),
                genius_evidence=GeniusEvidence(row["source_genius_evidence"]),
                observed_at=datetime.fromisoformat(row["source_observed_at"]),
            )
        return CheckResult(
            check_id=row["check_id"],
            booking_id=row["booking_id"],
            checked_at=datetime.fromisoformat(row["checked_at"]),
            outcome=CheckOutcome(row["outcome"]),
            extraction_method=ExtractionMethod(row["extraction_method"]),
            live_price=live_price,
            refund_indicators=refund_indicators,
            extracted_fields=extracted_fields,
            failure_reason=failure_reason,
            price_source=price_source,
        )


class SqliteSavingsRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def add(self, opportunity: SavingsOpportunity) -> None:
        self._store.conn.execute(
            """
            INSERT INTO savings_opportunities (
                opportunity_id, booking_id, check_id, baseline_amount,
                live_amount, currency, amount_saved, percent_saved,
                validated_at, notified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity.opportunity_id,
                opportunity.booking_id,
                opportunity.check_id,
                str(opportunity.baseline_price.amount),
                str(opportunity.live_price.amount),
                opportunity.baseline_price.currency,
                str(opportunity.amount_saved.amount),
                str(opportunity.percent_saved),
                opportunity.validated_at.isoformat(),
                opportunity.notified_at.isoformat() if opportunity.notified_at else None,
            ),
        )
        self._store.conn.commit()

    def get(self, opportunity_id: str) -> SavingsOpportunity | None:
        row = self._store.conn.execute(
            "SELECT * FROM savings_opportunities WHERE opportunity_id = ?",
            (opportunity_id,),
        ).fetchone()
        return self._row_to_opportunity(row) if row else None

    def get_current_for_booking(self, booking_id: str) -> SavingsOpportunity | None:
        """Return the opportunity produced by the latest conclusive check.

        Later technical failures do not erase the last verified saving.  A
        later successful non-saving check or explicit no-equivalent result
        leaves no matching row and therefore returns ``None``.
        """
        row = self._store.conn.execute(
            _CURRENT_OPPORTUNITIES_CTE
            + """
            SELECT *
            FROM current_opportunities
            WHERE booking_id = :booking_id
            ORDER BY source_checked_at DESC, source_check_order DESC,
                     opportunity_order DESC
            LIMIT 1
            """,
            _current_opportunity_params(booking_id=booking_id),
        ).fetchone()
        return self._row_to_opportunity(row) if row else None

    def list_for_booking(self, booking_id: str) -> list[SavingsOpportunity]:
        rows = self._store.conn.execute(
            "SELECT * FROM savings_opportunities WHERE booking_id = ? "
            "ORDER BY validated_at DESC, id DESC",
            (booking_id,),
        ).fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    def list_all(self) -> list[SavingsOpportunity]:
        rows = self._store.conn.execute(
            "SELECT * FROM savings_opportunities ORDER BY validated_at DESC"
        ).fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    def list_all_for_user(self, user_id: int) -> list[SavingsOpportunity]:
        """US-029 scoping: savings inherit scope through their booking's
        owner — joined here so a stranger's/another user's opportunities can
        never surface in this user's listing.
        """
        rows = self._store.conn.execute(
            "SELECT s.* FROM savings_opportunities s "
            "JOIN bookings b ON b.booking_id = s.booking_id "
            "WHERE b.user_id = ? "
            "ORDER BY s.validated_at DESC",
            (user_id,),
        ).fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    def list_current_for_user(self, user_id: int) -> list[SavingsOpportunity]:
        """Return current conclusive opportunities for active owned bookings.

        Historical rows remain untouched.  Technical failures are ignored for
        supersession, while later successful or explicit no-equivalent checks
        replace the market state.
        """
        rows = self._store.conn.execute(
            _CURRENT_OPPORTUNITIES_CTE
            + """
            SELECT *
            FROM current_opportunities
            WHERE owner_user_id = :user_id
            ORDER BY source_checked_at DESC, source_check_order DESC,
                     opportunity_order DESC
            """,
            _current_opportunity_params(user_id=user_id),
        ).fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    def mark_notified(self, opportunity_id: str, at: datetime) -> None:
        self._store.conn.execute(
            "UPDATE savings_opportunities SET notified_at = ? WHERE opportunity_id = ?",
            (at.isoformat(), opportunity_id),
        )
        self._store.conn.commit()

    def _row_to_opportunity(self, row: sqlite3.Row) -> SavingsOpportunity:
        currency = row["currency"]
        return SavingsOpportunity(
            opportunity_id=row["opportunity_id"],
            booking_id=row["booking_id"],
            check_id=row["check_id"],
            baseline_price=Money(amount=Decimal(row["baseline_amount"]), currency=currency),
            live_price=Money(amount=Decimal(row["live_amount"]), currency=currency),
            amount_saved=Money(amount=Decimal(row["amount_saved"]), currency=currency),
            percent_saved=Decimal(row["percent_saved"]),
            validated_at=datetime.fromisoformat(row["validated_at"]),
            notified_at=(
                datetime.fromisoformat(row["notified_at"]) if row["notified_at"] else None
            ),
        )


class SqliteRebookSessionRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def add(self, session: RebookSession) -> None:
        self._insert(session)
        self._store.conn.commit()

    def add_if_opportunity_current(self, session: RebookSession) -> bool:
        """Atomically validate actionability and create the guided session.

        ``BEGIN IMMEDIATE`` prevents another connection from appending a newer
        conclusive check between the current-row check and the session insert.
        """
        conn = self._store.conn
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                _CURRENT_OPPORTUNITIES_CTE
                + """
                SELECT 1
                FROM current_opportunities
                WHERE opportunity_id = :opportunity_id
                  AND booking_id = :booking_id
                """,
                _current_opportunity_params(
                    opportunity_id=session.opportunity_id,
                    booking_id=session.booking_id,
                ),
            ).fetchone()
            if row is None:
                conn.rollback()
                return False
            self._insert(session)
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def _insert(self, session: RebookSession) -> None:
        self._store.conn.execute(
            """
            INSERT INTO rebook_sessions (
                session_id, opportunity_id, booking_id, state,
                started_at, ended_at, end_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.opportunity_id,
                session.booking_id,
                session.state.value,
                session.started_at.isoformat(),
                session.ended_at.isoformat() if session.ended_at else None,
                session.end_reason,
            ),
        )

    def update(self, session: RebookSession) -> None:
        self._store.conn.execute(
            "UPDATE rebook_sessions SET state = ?, ended_at = ?, end_reason = ? "
            "WHERE session_id = ?",
            (
                session.state.value,
                session.ended_at.isoformat() if session.ended_at else None,
                session.end_reason,
                session.session_id,
            ),
        )
        self._store.conn.commit()

    def get(self, session_id: str) -> RebookSession | None:
        row = self._store.conn.execute(
            "SELECT * FROM rebook_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return RebookSession(
            session_id=row["session_id"],
            opportunity_id=row["opportunity_id"],
            booking_id=row["booking_id"],
            state=RebookSessionState(row["state"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            end_reason=row["end_reason"],
        )


class SqliteRebookEventRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def append(self, event: RebookEvent) -> None:
        self._store.conn.execute(
            """
            INSERT INTO rebook_events (event_id, session_id, event_type, detail, occurred_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.session_id,
                event.event_type.value,
                event.detail,
                event.occurred_at.isoformat(),
            ),
        )
        self._store.conn.commit()

    def list_for_session(self, session_id: str) -> list[RebookEvent]:
        rows = self._store.conn.execute(
            "SELECT * FROM rebook_events WHERE session_id = ? ORDER BY occurred_at, id",
            (session_id,),
        ).fetchall()
        return [
            RebookEvent(
                event_id=r["event_id"],
                session_id=r["session_id"],
                event_type=RebookEventType(r["event_type"]),
                detail=r["detail"],
                occurred_at=datetime.fromisoformat(r["occurred_at"]),
            )
            for r in rows
        ]


class SqliteCheckTraceRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def add(self, trace: CheckTrace) -> None:
        import json as _json

        payload = _json.dumps(
            [
                {
                    "seq": e.seq,
                    "at": e.at.isoformat(),
                    "kind": e.kind.value,
                    "detail": e.detail,
                }
                for e in trace.events
            ]
        )
        self._store.conn.execute(
            "INSERT INTO check_traces (check_id, booking_id, created_at, trace_json) "
            "VALUES (?, ?, ?, ?)",
            (trace.check_id, trace.booking_id, trace.created_at.isoformat(), payload),
        )
        self._store.conn.commit()

    def get(self, check_id: str) -> CheckTrace | None:
        import json as _json

        row = self._store.conn.execute(
            "SELECT * FROM check_traces WHERE check_id = ?", (check_id,)
        ).fetchone()
        if row is None:
            return None
        events = tuple(
            TraceEvent(
                seq=item["seq"],
                at=datetime.fromisoformat(item["at"]),
                kind=TraceKind(item["kind"]),
                detail=item["detail"],
            )
            for item in _json.loads(row["trace_json"])
        )
        return CheckTrace(
            check_id=row["check_id"],
            booking_id=row["booking_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            events=events,
        )


class SqliteUserRepository:
    """Schema v9 (US-029/US-063). Exactly one owner row is guaranteed by
    `_ensure_owner_user` (called on every connect) and the DB-level partial
    unique index on `users(role) WHERE role = 'owner'`.
    """

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def get_owner(self) -> User:
        row = self._store.conn.execute("SELECT * FROM users WHERE role = 'owner'").fetchone()
        if row is None:
            # Belt and braces: connect() always ensures an owner row exists.
            owner_id = _ensure_owner_user(self._store.conn)
            self._store.conn.commit()
            return self.get_by_id(owner_id)  # type: ignore[return-value]
        return self._row_to_user(row)

    def get_by_id(self, user_id: int) -> User | None:
        row = self._store.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return self._row_to_user(row) if row else None

    def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        row = self._store.conn.execute(
            "SELECT * FROM users WHERE telegram_user_id = ?", (telegram_user_id,)
        ).fetchone()
        return self._row_to_user(row) if row else None

    def get_or_create_by_telegram_id(
        self, telegram_user_id: int, role: UserRole = UserRole.USER
    ) -> User:
        existing = self.get_by_telegram_id(telegram_user_id)
        if existing is not None:
            return existing
        cursor = self._store.conn.execute(
            "INSERT INTO users (telegram_user_id, role, access_state, encrypted_key, created_at) "
            "VALUES (?, ?, 'active', NULL, ?)",
            (telegram_user_id, role.value, datetime.now(UTC).isoformat()),
        )
        self._store.conn.commit()
        assert cursor.lastrowid is not None
        created = self.get_by_id(int(cursor.lastrowid))
        assert created is not None
        return created

    def list_all(self) -> list[User]:
        rows = self._store.conn.execute(
            "SELECT * FROM users ORDER BY created_at"
        ).fetchall()
        return [self._row_to_user(r) for r in rows]

    def list_active(self) -> list[User]:
        rows = self._store.conn.execute(
            "SELECT * FROM users WHERE access_state = 'active' ORDER BY created_at"
        ).fetchall()
        return [self._row_to_user(r) for r in rows]

    def list_admin_aggregates(self) -> list[AdminUserAggregate]:
        """Return only the fields allowlisted for aggregate admin usage.

        Active booking totals are calculated in SQL. No ``Booking`` domain
        objects or exact booking/check/savings/rebook records are loaded.
        """
        rows = self._store.conn.execute(
            """
            SELECT
                u.user_id,
                u.telegram_username,
                u.role,
                u.access_state,
                COUNT(CASE WHEN b.status = 'active' THEN 1 END) AS active_booking_count
            FROM users AS u
            LEFT JOIN bookings AS b ON b.user_id = u.user_id
            GROUP BY
                u.user_id,
                u.telegram_username,
                u.role,
                u.access_state,
                u.created_at
            ORDER BY u.created_at
            """
        ).fetchall()
        return [
            AdminUserAggregate(
                user_id=int(row["user_id"]),
                telegram_username=row["telegram_username"],
                role=UserRole(row["role"]),
                access_state=UserAccessState(row["access_state"]),
                active_booking_count=int(row["active_booking_count"]),
            )
            for row in rows
        ]

    def set_access_state(self, user_id: int, access_state: UserAccessState) -> None:
        cursor = self._store.conn.execute(
            "UPDATE users SET access_state = ? WHERE user_id = ?",
            (access_state.value, user_id),
        )
        self._store.conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"No user with id '{user_id}'")

    def link_telegram_id(self, user_id: int, telegram_user_id: int) -> None:
        """Attach a Telegram identity to an existing user row (used to link
        the config-designated owner chat to the owner row on first contact).
        Only fills a NULL telegram_user_id — never rebinds an existing one."""
        self._store.conn.execute(
            "UPDATE users SET telegram_user_id = ? "
            "WHERE user_id = ? AND telegram_user_id IS NULL",
            (telegram_user_id, user_id),
        )
        self._store.conn.commit()

    def set_telegram_username(
        self, user_id: int, telegram_username: str | None
    ) -> bool:
        """Store current optional Telegram username display metadata.

        Usernames are normalized without leading ``@`` characters. Whitespace
        and an empty username normalize to ``None``. The current value is read
        first so an unchanged username issues no UPDATE. Returns whether the
        stored value changed.
        """
        normalized = None
        if telegram_username is not None:
            normalized = telegram_username.strip().lstrip("@") or None

        user = self.get_by_id(user_id)
        if user is None:
            raise KeyError(f"No user with id '{user_id}'")
        if user.telegram_username == normalized:
            return False

        self._store.conn.execute(
            "UPDATE users SET telegram_username = ? WHERE user_id = ?",
            (normalized, user_id),
        )
        self._store.conn.commit()
        return True

    def get_owner_of_booking(self, booking_id: str) -> User | None:
        """US-027: resolve a booking's owning user, for per-booking LLM key
        resolution (`LLMClientFactory.for_booking`). Joins through
        `bookings.user_id` rather than adding a `User` field to `Booking`
        (see ddd-02 rationale)."""
        row = self._store.conn.execute(
            "SELECT u.* FROM users u JOIN bookings b ON b.user_id = u.user_id "
            "WHERE b.booking_id = ?",
            (booking_id,),
        ).fetchone()
        return self._row_to_user(row) if row else None

    def set_encrypted_key(self, user_id: int, encrypted_key: bytes | None) -> None:
        """US-027: store (or clear, when `encrypted_key` is None) a user's
        Fernet-encrypted personal Anthropic key. `/setkey` rotates by calling
        this again; `/deletekey` calls it with None to revert to owner-billed
        checks."""
        cursor = self._store.conn.execute(
            "UPDATE users SET encrypted_key = ? WHERE user_id = ?",
            (encrypted_key, user_id),
        )
        self._store.conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"No user with id '{user_id}'")

    def purge(self, user_id: int) -> None:
        """US-028 `/admin purge`: irreversibly deletes a non-owner user and
        everything scoped through their bookings. The owner row can never be
        purged (guards the exactly-one-owner invariant)."""
        user = self.get_by_id(user_id)
        if user is None:
            raise KeyError(f"No user with id '{user_id}'")
        if user.is_owner:
            raise ValueError("The owner user cannot be purged")

        conn = self._store.conn
        booking_ids = [
            r[0]
            for r in conn.execute(
                "SELECT booking_id FROM bookings WHERE user_id = ?", (user_id,)
            )
        ]
        # Account rows own the optional monitoring projection FK, so remove
        # them before the ordinary booking-scoped deletion cascade.
        conn.execute("DELETE FROM account_reservations WHERE user_id = ?", (user_id,))
        for booking_id in booking_ids:
            _delete_booking_rows(conn, booking_id)
        conn.execute("DELETE FROM booking_sync_runs WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM invite_codes WHERE used_by = ?", (user_id,))
        conn.execute("UPDATE invite_codes SET issued_by = NULL WHERE issued_by = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            user_id=row["user_id"],
            telegram_user_id=row["telegram_user_id"],
            role=UserRole(row["role"]),
            access_state=UserAccessState(row["access_state"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            encrypted_key=row["encrypted_key"],
            telegram_username=row["telegram_username"],
        )


class SqliteInviteCodeRepository:
    """Schema v8 (US-026/US-064) single-use owner-issued invite codes.

    These are the fixed non-owner admission path; there is no runtime access
    mode switch.
    """

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def issue(self, issued_by: int, expires_at: datetime | None = None) -> InviteCode:
        code = secrets.token_urlsafe(9)  # short enough to type/paste, unguessable
        issued_at = datetime.now(UTC)
        expires_at_str = expires_at.isoformat() if expires_at else None
        self._store.conn.execute(
            "INSERT INTO invite_codes (code, issued_by, issued_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (code, issued_by, issued_at.isoformat(), expires_at_str),
        )
        self._store.conn.commit()
        return InviteCode(
            code=code, issued_by=issued_by, issued_at=issued_at, expires_at=expires_at
        )

    def get(self, code: str) -> InviteCode | None:
        row = self._store.conn.execute(
            "SELECT * FROM invite_codes WHERE code = ?", (code,)
        ).fetchone()
        return self._row_to_invite(row) if row else None

    def redeem(self, code: str, used_by: int, now: datetime) -> InviteCode | None:
        """Atomically redeem `code` for `used_by`. Returns None (no state
        change) when the code doesn't exist, is already used, or is expired —
        callers treat every None the same as "invalid code", never leaking
        which case applied (US-026)."""
        invite = self.get(code)
        if invite is None or invite.is_used or invite.is_expired(now):
            return None
        cursor = self._store.conn.execute(
            "UPDATE invite_codes SET used_by = ?, used_at = ? "
            "WHERE code = ? AND used_by IS NULL",
            (used_by, now.isoformat(), code),
        )
        self._store.conn.commit()
        if cursor.rowcount == 0:
            return None  # lost a race with a concurrent redemption
        return self.get(code)

    def _row_to_invite(self, row: sqlite3.Row) -> InviteCode:
        return InviteCode(
            code=row["code"],
            issued_by=row["issued_by"],
            issued_at=datetime.fromisoformat(row["issued_at"]),
            expires_at=(
                datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            ),
            used_by=row["used_by"],
            used_at=datetime.fromisoformat(row["used_at"]) if row["used_at"] else None,
        )
