"""US-017: occupancy persistence, v5 migration, and legacy-booking backfill."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from booksaver.application.register_booking import register_booking
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
from booksaver.infrastructure.persistence.sqlite_store import (
    SCHEMA_VERSION,
    SqliteBookingRepository,
    SqliteStore,
)

_V4_DDL = """\
CREATE TABLE schema_meta (version INTEGER NOT NULL, applied_at TEXT NOT NULL);
INSERT INTO schema_meta VALUES (4, '2026-07-05T00:00:00+00:00');
CREATE TABLE bookings (
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
CREATE TABLE check_history (
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
INSERT INTO bookings VALUES (
    'legacy-1', 'booking_com', 'hotel', 'CONF-LEGACY', 'Old Hotel', 'old_ref',
    '2026-10-01', '2026-10-05', 'Standard', '300.00', 'EUR', 1, 'Free', NULL,
    '2026-06-01T00:00:00+00:00', 'active'
);
INSERT INTO check_history (
    check_id, booking_id, checked_at, outcome, extraction_method, failure_code,
    failure_detail
) VALUES ('chk-1', 'legacy-1', '2026-06-02T00:00:00+00:00', 'failure', 'none',
          'timeout', 'old row');
"""


def _make_v4_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_V4_DDL)
    conn.commit()
    conn.close()


def _booking_kwargs(confirmation: str = "BKG-OCC") -> dict:
    return dict(
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of(confirmation),
        property=Property(name="Occupancy Hotel", booking_com_ref="occ_ref"),
        stay_dates=StayDates(date(2026, 10, 1), date(2026, 10, 5)),
        room_type=RoomType(label="Family Room"),
        baseline_price=Money.of("500.00", "EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="Free cancellation"),
        occupancy=Occupancy(adults=2, children=2, rooms=1),
    )


class TestOccupancyRoundTrip:
    def test_registered_occupancy_survives_round_trip(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteBookingRepository(store)
            booking, _ = register_booking(repo=repo, **_booking_kwargs())
            fetched = repo.get_by_id(booking.booking_id)
        assert fetched.occupancy == Occupancy(adults=2, children=2, rooms=1)

    def test_db_check_rejects_zero_adults(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            with pytest.raises(sqlite3.IntegrityError):
                store.conn.execute(
                    "UPDATE bookings SET occ_adults = 0"  # no rows, but CHECK still parses
                )
                store.conn.execute(
                    """
                    INSERT INTO bookings (
                        booking_id, platform, product_type, confirmation_id,
                        property_name, property_ref, check_in, check_out, room_type,
                        baseline_amount, baseline_currency, refundable, refund_note,
                        registered_at, status, occ_adults, occ_children, occ_rooms
                    ) VALUES ('x', 'booking_com', 'hotel', 'C-X', 'H', 'r',
                              '2026-10-01', '2026-10-05', 'S', '1', 'EUR', 1, '',
                              '2026-06-01T00:00:00+00:00', 'active', 0, 0, 1)
                    """
                )


class TestV5Migration:
    def test_v4_database_migrates_to_v5(self, tmp_path):
        db_path = tmp_path / "old.db"
        _make_v4_db(db_path)

        with SqliteStore(db_path) as store:
            repo = SqliteBookingRepository(store)
            legacy = repo.get_by_id("legacy-1")
            versions = [
                r[0]
                for r in store.conn.execute(
                    "SELECT version FROM schema_meta ORDER BY version"
                ).fetchall()
            ]
            # The v11 pre-launch cutover intentionally removes old booking state.
            old_checks = store.conn.execute(
                "SELECT check_id, failure_code FROM check_history"
            ).fetchall()
            replacement, _ = register_booking(
                repo=repo, **_booking_kwargs("POST-CUTOVER")
            )
            # The rebuilt history table still accepts the v5 'agent' method.
            store.conn.execute(
                "INSERT INTO check_history (check_id, booking_id, checked_at, outcome,"
                " extraction_method, live_amount, live_currency)"
                " VALUES ('chk-agent', ?, '2026-07-05T00:00:00+00:00',"
                " 'success', 'agent', '250.00', 'EUR')",
                (replacement.booking_id,),
            )

        assert legacy is None
        assert versions[-1] == SCHEMA_VERSION
        assert old_checks == []

    def test_migration_is_idempotent_on_reopen(self, tmp_path):
        db_path = tmp_path / "old.db"
        _make_v4_db(db_path)
        with SqliteStore(db_path):
            pass
        with SqliteStore(db_path) as store:  # second open must not re-migrate/fail
            row = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()
        assert row[0] == SCHEMA_VERSION


class TestSetOccupancy:
    def test_legacy_booking_cannot_be_backfilled_after_cutover(self, tmp_path):
        db_path = tmp_path / "old.db"
        _make_v4_db(db_path)

        with SqliteStore(db_path) as store:
            repo = SqliteBookingRepository(store)
            with pytest.raises(KeyError, match="legacy-1"):
                repo.set_occupancy(
                    "legacy-1", Occupancy(adults=3, children=1, rooms=2)
                )
            assert repo.get_by_id("legacy-1") is None

    def test_unknown_booking_raises_key_error(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteBookingRepository(store)
            with pytest.raises(KeyError, match="no-such-id"):
                repo.set_occupancy("no-such-id", Occupancy(adults=2))
