from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

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
from booksaver.domain.models import Booking, BookingStatus
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
from booksaver.domain.user import User, UserAccessState, UserRole
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

SCHEMA_VERSION = 7
_SCHEMA_SQL = Path(__file__).parent / "schema.sql"

# Columns shared by the v2/v4 and v5 check_history definitions (v5 only relaxes
# the extraction_method CHECK to include 'agent'); used to copy data across the
# table rebuild.
_CHECK_HISTORY_COLUMNS = (
    "id, check_id, booking_id, checked_at, outcome, extraction_method, "
    "live_amount, live_currency, refundable, cancellation_deadline, "
    "refund_raw_text, extracted_property, extracted_room, "
    "extracted_check_in, extracted_check_out, failure_code, failure_detail"
)

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


# v2 -> v3: savings_opportunities is purely additive (CREATE IF NOT EXISTS covers it).
# v3 -> v4: rebook_sessions + rebook_events, also purely additive.
# v5 -> v6: check_traces, also purely additive.
# v6 -> v7: users table + bookings.user_id (US-029).
_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    2: _migrate_v2,
    5: _migrate_v5,
    7: _migrate_v7,
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
                extracted_check_in, extracted_check_out, failure_code, failure_detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def list_for_booking(self, booking_id: str) -> list[SavingsOpportunity]:
        rows = self._store.conn.execute(
            "SELECT * FROM savings_opportunities WHERE booking_id = ? "
            "ORDER BY validated_at DESC",
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
        self._store.conn.commit()

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
    """Schema v7 (US-029). Exactly one 'owner' row is guaranteed to exist by
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

    def set_access_state(self, user_id: int, access_state: UserAccessState) -> None:
        cursor = self._store.conn.execute(
            "UPDATE users SET access_state = ? WHERE user_id = ?",
            (access_state.value, user_id),
        )
        self._store.conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"No user with id '{user_id}'")

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            user_id=row["user_id"],
            telegram_user_id=row["telegram_user_id"],
            role=UserRole(row["role"]),
            access_state=UserAccessState(row["access_state"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            encrypted_key=row["encrypted_key"],
        )
