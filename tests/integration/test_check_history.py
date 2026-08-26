from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from booksaver.domain.check_result import (
    CheckOutcome,
    CheckResult,
    ExtractedBookingFields,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
)
from booksaver.domain.mobile_web import (
    AuthenticationEvidence,
    GeniusEvidence,
    MobileProfileId,
    PriceSourceChannel,
    PriceSourceProvenance,
)
from booksaver.domain.models import Booking
from booksaver.domain.session import SessionState, SessionStatus
from booksaver.domain.value_objects import (
    ConfirmationId,
    DataDirectory,
    Money,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)
from booksaver.infrastructure.persistence.session_store import LocalSessionRepository
from booksaver.infrastructure.persistence.sqlite_store import (
    SCHEMA_VERSION,
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteStore,
)


def _register_booking(store: SqliteStore, booking_id: str = "b-1") -> Booking:
    booking = Booking(
        booking_id=booking_id,
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId(f"CONF-{booking_id}"),
        property=Property(name="Hotel Test", booking_com_ref="ref-1"),
        stay_dates=StayDates(check_in=date(2026, 9, 1), check_out=date(2026, 9, 5)),
        room_type=RoomType(label="Double"),
        baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="free cancellation"),
        registered_at=datetime.now(UTC),
    )
    SqliteBookingRepository(store).add(booking)
    return booking


def _success_result(booking_id: str) -> CheckResult:
    return CheckResult.success(
        booking_id=booking_id,
        checked_at=datetime.now(UTC),
        live_price=Money(amount=Decimal("380.50"), currency="EUR"),
        extraction_method=ExtractionMethod.DOM,
        refund_indicators=RefundIndicators(
            is_refundable=True,
            cancellation_deadline=date(2026, 8, 25),
            raw_text="Free cancellation until 25 August",
        ),
        extracted_fields=ExtractedBookingFields(
            property_name="Hotel Test",
            room_label="Double",
            check_in=date(2026, 9, 1),
            check_out=date(2026, 9, 5),
        ),
    )


def _price_source() -> PriceSourceProvenance:
    return PriceSourceProvenance(
        channel=PriceSourceChannel.AUTHENTICATED_MOBILE_WEB,
        profile_id=MobileProfileId.ANDROID_CHROMIUM_COMPACT,
        session_revision_id="session-revision-42",
        authentication=AuthenticationEvidence.VALIDATED,
        genius_evidence=GeniusEvidence.APPLIED_OR_PRESENT,
        observed_at=datetime(2026, 9, 1, 14, 30, 45, tzinfo=UTC),
    )


def _failure_result(booking_id: str) -> CheckResult:
    return CheckResult.failure(
        booking_id,
        datetime.now(UTC),
        FailureReason(code=FailureCode.TIMEOUT, detail="page load timed out"),
    )


class TestSqliteCheckHistoryRepository:
    def test_success_round_trip_preserves_all_fields(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteCheckHistoryRepository(store)
            original = _success_result("b-1")
            repo.add(original)

            [loaded] = repo.get_recent("b-1")

        assert loaded.check_id == original.check_id
        assert loaded.outcome is CheckOutcome.SUCCESS
        assert loaded.live_price == original.live_price
        assert loaded.extraction_method is ExtractionMethod.DOM
        assert loaded.refund_indicators == original.refund_indicators
        assert loaded.extracted_fields == original.extracted_fields
        assert loaded.failure_reason is None

    def test_price_source_provenance_round_trip_preserves_all_six_fields(
        self, tmp_path: Path
    ) -> None:
        provenance = _price_source()
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteCheckHistoryRepository(store)
            original = CheckResult.success(
                booking_id="b-1",
                checked_at=datetime.now(UTC),
                live_price=Money(amount=Decimal("379.00"), currency="EUR"),
                extraction_method=ExtractionMethod.DOM,
                price_source=provenance,
            )
            repo.add(original)

            row = store.conn.execute(
                "SELECT source_channel, source_device_profile, "
                "source_session_revision, source_authentication, "
                "source_genius_evidence, source_observed_at "
                "FROM check_history WHERE check_id = ?",
                (original.check_id,),
            ).fetchone()
            [loaded] = repo.get_recent("b-1")

        assert tuple(row) == (
            provenance.channel.value,
            provenance.profile_id.value,
            provenance.session_revision_id,
            provenance.authentication.value,
            provenance.genius_evidence.value,
            provenance.observed_at.isoformat(),
        )
        assert loaded.price_source == provenance

    def test_failure_round_trip(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteCheckHistoryRepository(store)
            repo.add(_failure_result("b-1"))

            [loaded] = repo.get_recent("b-1")

        assert loaded.outcome is CheckOutcome.FAILURE
        assert loaded.live_price is None
        assert loaded.failure_reason is not None
        assert loaded.failure_reason.code is FailureCode.TIMEOUT

    def test_get_recent_returns_newest_first_and_limits(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteCheckHistoryRepository(store)
            for _ in range(5):
                repo.add(_failure_result("b-1"))
            newest = _success_result("b-1")
            repo.add(newest)

            recent = repo.get_recent("b-1", limit=3)

        assert len(recent) == 3
        assert recent[0].check_id == newest.check_id

    def test_count_consecutive_failures(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteCheckHistoryRepository(store)

            repo.add(_failure_result("b-1"))
            repo.add(_success_result("b-1"))
            repo.add(_failure_result("b-1"))
            repo.add(_failure_result("b-1"))

            assert repo.count_consecutive_failures("b-1") == 2

    def test_count_is_zero_after_success(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteCheckHistoryRepository(store)
            repo.add(_failure_result("b-1"))
            repo.add(_success_result("b-1"))

            assert repo.count_consecutive_failures("b-1") == 0

    def test_unknown_check_id_rejected_by_fk(self, tmp_path: Path) -> None:
        import pytest

        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteCheckHistoryRepository(store)
            with pytest.raises(sqlite3.IntegrityError):
                repo.add(_failure_result("no-such-booking"))


class TestSchemaMigration:
    def test_v1_database_migrates_to_v2(self, tmp_path: Path) -> None:
        db_path = tmp_path / "old.db"

        # Build a v1 database by hand: v1 stub check_history + version row
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE schema_meta (version INTEGER NOT NULL, applied_at TEXT NOT NULL);
            INSERT INTO schema_meta VALUES (1, '2026-06-16T00:00:00+00:00');
            CREATE TABLE check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()

        with SqliteStore(db_path) as store:
            _register_booking(store)
            repo = SqliteCheckHistoryRepository(store)
            repo.add(_success_result("b-1"))  # would fail on the v1 stub columns

            [loaded] = repo.get_recent("b-1")
            versions = [
                r[0]
                for r in store.conn.execute(
                    "SELECT version FROM schema_meta ORDER BY version"
                ).fetchall()
            ]

        assert loaded.outcome is CheckOutcome.SUCCESS
        assert versions == list(range(1, SCHEMA_VERSION + 1))

    def test_fresh_database_gets_latest_version_directly(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "new.db") as store:
            row = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()
        assert row[0] == SCHEMA_VERSION

    def test_v9_database_applies_v10_shape_then_removes_legacy_booking_rows(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "v9.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE schema_meta (version INTEGER NOT NULL, applied_at TEXT NOT NULL);
            INSERT INTO schema_meta VALUES (9, '2026-07-11T00:00:00+00:00');

            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER UNIQUE,
                telegram_username TEXT,
                role TEXT NOT NULL,
                access_state TEXT NOT NULL,
                encrypted_key BLOB,
                created_at TEXT NOT NULL
            );
            INSERT INTO users VALUES (
                1, 555, 'owner', 'owner', 'active', NULL,
                '2026-07-11T00:00:00+00:00'
            );

            CREATE TABLE bookings (
                booking_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                product_type TEXT NOT NULL,
                confirmation_id TEXT NOT NULL UNIQUE,
                property_name TEXT NOT NULL,
                property_ref TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT NOT NULL,
                room_type TEXT NOT NULL,
                baseline_amount TEXT NOT NULL,
                baseline_currency TEXT NOT NULL,
                refundable INTEGER NOT NULL,
                refund_note TEXT NOT NULL,
                refund_deadline TEXT,
                registered_at TEXT NOT NULL,
                status TEXT NOT NULL,
                occ_adults INTEGER,
                occ_children INTEGER,
                occ_rooms INTEGER,
                user_id INTEGER NOT NULL
            );
            INSERT INTO bookings VALUES (
                'legacy-booking', 'booking_com', 'hotel', 'LEGACY-CONF',
                'Legacy Hotel', 'legacy-ref', '2026-09-01', '2026-09-05',
                'Double', '400.00', 'EUR', 1, 'Free cancellation', NULL,
                '2026-07-11T00:00:00+00:00', 'active', 2, 0, 1, 1
            );

            CREATE TABLE check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id TEXT NOT NULL UNIQUE,
                booking_id TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                outcome TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                live_amount TEXT,
                live_currency TEXT,
                refundable INTEGER,
                cancellation_deadline TEXT,
                refund_raw_text TEXT,
                extracted_property TEXT,
                extracted_room TEXT,
                extracted_check_in TEXT,
                extracted_check_out TEXT,
                failure_code TEXT,
                failure_detail TEXT
            );
            INSERT INTO check_history (
                check_id, booking_id, checked_at, outcome, extraction_method,
                live_amount, live_currency, refundable, refund_raw_text
            ) VALUES (
                'legacy-check', 'legacy-booking', '2026-07-12T12:00:00+00:00',
                'success', 'dom', '380.50', 'EUR', 1, 'Free cancellation'
            );
            """
        )
        conn.commit()
        conn.close()

        expected_columns = {
            "source_channel",
            "source_device_profile",
            "source_session_revision",
            "source_authentication",
            "source_genius_evidence",
            "source_observed_at",
        }
        with SqliteStore(db_path) as store:
            columns = {
                row[1] for row in store.conn.execute("PRAGMA table_info(check_history)")
            }
            legacy_rows = store.conn.execute(
                "SELECT check_id, booking_id, live_amount, live_currency "
                "FROM check_history"
            ).fetchall()
            version = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()[0]

        assert expected_columns <= columns
        assert legacy_rows == []
        assert version == SCHEMA_VERSION == 17


class TestLocalSessionRepository:
    def test_round_trip(self, tmp_path: Path) -> None:
        data_dir = DataDirectory(path=tmp_path)
        repo = LocalSessionRepository(data_dir)
        session = SessionState.new(
            platform=Platform.BOOKING_COM,
            cookies=b'[{"name": "sid", "value": "abc"}]',
            authenticated_at=datetime.now(UTC),
        )

        repo.save(session)
        loaded = repo.load(Platform.BOOKING_COM)

        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert loaded.cookies == session.cookies
        assert loaded.status is SessionStatus.ACTIVE

    def test_load_returns_none_when_missing(self, tmp_path: Path) -> None:
        repo = LocalSessionRepository(DataDirectory(path=tmp_path))
        assert repo.load(Platform.BOOKING_COM) is None

    def test_corrupt_file_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "session_booking_com.json").write_text("{not json")
        repo = LocalSessionRepository(DataDirectory(path=tmp_path))
        assert repo.load(Platform.BOOKING_COM) is None

    def test_file_permissions_restricted(self, tmp_path: Path) -> None:
        repo = LocalSessionRepository(DataDirectory(path=tmp_path))
        session = SessionState.new(
            platform=Platform.BOOKING_COM,
            cookies=b"[]",
            authenticated_at=datetime.now(UTC),
        )
        repo.save(session)
        mode = (tmp_path / "session_booking_com.json").stat().st_mode
        assert oct(mode)[-3:] == "600"
