from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

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
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)

SCHEMA_VERSION = 3
_SCHEMA_SQL = Path(__file__).parent / "schema.sql"

# v1 -> v2: the v1 check_history table was a contract-only stub (id, booking_id,
# recorded_at) that never held real data; it is dropped and recreated with the
# full column set from schema.sql.
# v2 -> v3: savings_opportunities is purely additive; the CREATE IF NOT EXISTS in
# schema.sql covers it, so no migration statements are needed.
_MIGRATIONS: dict[int, list[str]] = {
    2: ["DROP TABLE IF EXISTS check_history"],
    3: [],
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
                for stmt in _MIGRATIONS.get(version, []):
                    self.conn.execute(stmt)
                self.conn.execute(
                    "INSERT INTO schema_meta (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(UTC).isoformat()),
                )

        self.conn.executescript(_SCHEMA_SQL.read_text())

        if current is None:
            self.conn.execute(
                "INSERT INTO schema_meta (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
            )
        self.conn.commit()


class SqliteBookingRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def add(self, booking: Booking) -> None:
        self._store.conn.execute(
            """
            INSERT INTO bookings (
                booking_id, platform, product_type, confirmation_id,
                property_name, property_ref, check_in, check_out,
                room_type, baseline_amount, baseline_currency,
                refundable, refund_note, refund_deadline,
                registered_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        self._store.conn.commit()

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

    def exists(self, confirmation_id: ConfirmationId) -> bool:
        row = self._store.conn.execute(
            "SELECT 1 FROM bookings WHERE confirmation_id = ?", (confirmation_id.value,)
        ).fetchone()
        return row is not None

    def _row_to_booking(self, row: sqlite3.Row) -> Booking:
        deadline_str: str | None = row["refund_deadline"]
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
