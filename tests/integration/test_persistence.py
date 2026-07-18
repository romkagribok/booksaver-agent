from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from booksaver.application.manage_booking import delete_booking, update_booking
from booksaver.application.register_booking import register_booking
from booksaver.domain.errors import BookingRejectedError
from booksaver.domain.models import BookingStatus
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
    SqliteBookingRepository,
    SqliteStore,
)


@pytest.fixture
def store(tmp_path):
    with SqliteStore(tmp_path / "booksaver.db") as s:
        yield s


@pytest.fixture
def repo(store):
    return SqliteBookingRepository(store)


def _make_booking(confirmation: str = "BKG-001") -> dict:
    return dict(
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of(confirmation),
        property=Property(name="Grand Hotel", booking_com_ref="grand_ref"),
        stay_dates=StayDates(date(2026, 10, 1), date(2026, 10, 5)),
        room_type=RoomType(label="Deluxe Double"),
        baseline_price=Money.of("350.00", "EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="Free cancellation"),
        occupancy=Occupancy(adults=2),
    )


class TestSqliteBookingRepository:
    def test_add_and_get_by_id(self, repo):
        booking, _ = register_booking(repo=repo, **_make_booking())
        fetched = repo.get_by_id(booking.booking_id)
        assert fetched is not None
        assert fetched.booking_id == booking.booking_id

    def test_get_by_confirmation(self, repo):
        booking, _ = register_booking(repo=repo, **_make_booking("BKG-CONF"))
        fetched = repo.get_by_confirmation(ConfirmationId.of("BKG-CONF"))
        assert fetched is not None
        assert fetched.confirmation_id.value == "BKG-CONF"

    def test_exists_true_after_add(self, repo):
        register_booking(repo=repo, **_make_booking("BKG-EXISTS"))
        assert repo.exists(ConfirmationId.of("BKG-EXISTS")) is True

    def test_exists_false_before_add(self, repo):
        assert repo.exists(ConfirmationId.of("BKG-NOPE")) is False

    def test_list_active_returns_active_only(self, repo):
        register_booking(repo=repo, **_make_booking("BKG-A"))
        register_booking(repo=repo, **_make_booking("BKG-B"))
        active = repo.list_active()
        assert len(active) == 2
        assert all(b.status == BookingStatus.ACTIVE for b in active)

    def test_duplicate_confirmation_rejected(self, repo):
        register_booking(repo=repo, **_make_booking("BKG-DUP"))
        with pytest.raises(BookingRejectedError, match="already registered"):
            register_booking(repo=repo, **_make_booking("BKG-DUP"))

    def test_round_trip_preserves_all_fields(self, repo):
        inputs = _make_booking("BKG-ROUNDTRIP")
        booking, _ = register_booking(repo=repo, **inputs)
        fetched = repo.get_by_id(booking.booking_id)

        assert fetched is not None
        assert fetched.platform == Platform.BOOKING_COM
        assert fetched.product_type == ProductType.HOTEL
        assert fetched.confirmation_id.value == "BKG-ROUNDTRIP"
        assert fetched.property.name == "Grand Hotel"
        assert fetched.property.booking_com_ref == "grand_ref"
        assert fetched.stay_dates.check_in == date(2026, 10, 1)
        assert fetched.stay_dates.check_out == date(2026, 10, 5)
        assert fetched.room_type.label == "Deluxe Double"
        assert fetched.baseline_price.amount == Decimal("350.00")
        assert fetched.baseline_price.currency == "EUR"
        assert fetched.refundability.is_refundable is True
        assert fetched.status == BookingStatus.ACTIVE

    def test_money_stored_as_decimal_not_float(self, repo, store):
        register_booking(repo=repo, **_make_booking("BKG-DECIMAL"))
        row = store.conn.execute(
            "SELECT baseline_amount FROM bookings WHERE confirmation_id = ?",
            ("BKG-DECIMAL",),
        ).fetchone()
        # Must be a string in the DB, never a float
        assert isinstance(row["baseline_amount"], str)
        assert Decimal(row["baseline_amount"]) == Decimal("350.00")

    def test_get_by_id_returns_none_for_unknown(self, repo):
        assert repo.get_by_id("nonexistent-uuid") is None

    def test_get_by_confirmation_returns_none_for_unknown(self, repo):
        assert repo.get_by_confirmation(ConfirmationId.of("BKG-UNKNOWN")) is None

    def test_update_changes_monitoring_fields_and_preserves_identity_metadata(self, repo, store):
        booking, _ = register_booking(repo=repo, **_make_booking("BKG-EDIT"))
        owner_id = repo.get_owner_user_id(booking.booking_id)
        replacement = replace(
            booking,
            confirmation_id=ConfirmationId.of("BKG-EDITED"),
            property=Property(name="Revised Hotel", booking_com_ref="revised-ref"),
            stay_dates=StayDates(date(2026, 11, 2), date(2026, 11, 7)),
            room_type=RoomType("King Suite"),
            baseline_price=Money.of("410.50", "USD"),
            refundability=RefundabilityPolicy(
                is_refundable=True,
                note="Free until October",
                deadline=date(2026, 10, 20),
            ),
            occupancy=Occupancy(adults=3, children=1, rooms=2),
        )

        update_booking(repo, replacement)

        updated = repo.get_by_id(booking.booking_id)
        assert updated is not None
        assert updated.booking_id == booking.booking_id
        assert updated.registered_at == booking.registered_at
        assert updated.status == booking.status
        assert repo.get_owner_user_id(booking.booking_id) == owner_id
        assert updated.confirmation_id.value == "BKG-EDITED"
        assert updated.property.name == "Revised Hotel"
        assert updated.stay_dates == StayDates(date(2026, 11, 2), date(2026, 11, 7))
        assert updated.room_type.label == "King Suite"
        assert updated.baseline_price == Money.of("410.50", "USD")
        assert updated.occupancy == Occupancy(adults=3, children=1, rooms=2)
        assert [item.booking_id for item in repo.list_active()] == [booking.booking_id]

    def test_update_invalidates_stale_savings_but_preserves_audit_history(self, repo, store):
        booking, _ = register_booking(repo=repo, **_make_booking("BKG-STALE"))
        booking_id = booking.booking_id
        now = datetime.now(UTC).isoformat()
        store.conn.execute(
            "INSERT INTO check_history "
            "(check_id, booking_id, checked_at, outcome, extraction_method) "
            "VALUES (?, ?, ?, 'failure', 'none')",
            ("check-stale", booking_id, now),
        )
        store.conn.execute(
            "INSERT INTO savings_opportunities "
            "(opportunity_id, booking_id, check_id, baseline_amount, live_amount, currency, "
            "amount_saved, percent_saved, validated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("opp-stale", booking_id, "check-stale", "350", "300", "EUR", "50", "14", now),
        )
        store.conn.execute(
            "INSERT INTO rebook_sessions "
            "(session_id, opportunity_id, booking_id, state, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("session-stale", "opp-stale", booking_id, "completed", now),
        )
        store.conn.execute(
            "INSERT INTO rebook_events "
            "(event_id, session_id, event_type, detail, occurred_at) VALUES (?, ?, ?, ?, ?)",
            ("event-stale", "session-stale", "intent_recorded", "", now),
        )
        store.conn.commit()

        update_booking(
            repo,
            replace(
                booking,
                stay_dates=StayDates(date(2026, 12, 1), date(2026, 12, 5)),
            ),
        )

        assert store.conn.execute(
            "SELECT COUNT(*) FROM savings_opportunities WHERE booking_id = ?", (booking_id,)
        ).fetchone()[0] == 0
        assert store.conn.execute(
            "SELECT COUNT(*) FROM check_history WHERE booking_id = ?", (booking_id,)
        ).fetchone()[0] == 1
        assert store.conn.execute(
            "SELECT COUNT(*) FROM rebook_sessions WHERE booking_id = ?", (booking_id,)
        ).fetchone()[0] == 1
        assert store.conn.execute(
            "SELECT COUNT(*) FROM rebook_events WHERE session_id = 'session-stale'"
        ).fetchone()[0] == 1

    def test_update_rejects_confirmation_id_owned_by_another_booking(self, repo):
        booking, _ = register_booking(repo=repo, **_make_booking("BKG-ONE"))
        register_booking(repo=repo, **_make_booking("BKG-TWO"))

        with pytest.raises(BookingRejectedError, match="already registered"):
            update_booking(
                repo, replace(booking, confirmation_id=ConfirmationId.of("BKG-TWO"))
            )

        assert repo.get_by_id(booking.booking_id).confirmation_id.value == "BKG-ONE"

    def test_update_missing_booking_raises_key_error(self, repo):
        booking, _ = register_booking(repo=repo, **_make_booking("BKG-GONE"))
        assert delete_booking(repo, booking.booking_id) is True

        with pytest.raises(KeyError, match="No booking"):
            update_booking(repo, booking)

    def test_delete_removes_all_booking_scoped_rows_and_scheduler_reads(self, repo, store):
        booking, _ = register_booking(repo=repo, **_make_booking("BKG-DELETE"))
        booking_id = booking.booking_id
        now = datetime.now(UTC).isoformat()
        store.conn.execute(
            "INSERT INTO check_history "
            "(check_id, booking_id, checked_at, outcome, extraction_method) "
            "VALUES (?, ?, ?, 'failure', 'none')",
            ("check-delete", booking_id, now),
        )
        store.conn.execute(
            "INSERT INTO check_traces (check_id, booking_id, created_at, trace_json) "
            "VALUES (?, ?, ?, ?)",
            ("check-delete", booking_id, now, "{}"),
        )
        store.conn.execute(
            "INSERT INTO savings_opportunities "
            "(opportunity_id, booking_id, check_id, baseline_amount, live_amount, currency, "
            "amount_saved, percent_saved, validated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("opp-delete", booking_id, "check-delete", "350", "300", "EUR", "50", "14", now),
        )
        store.conn.execute(
            "INSERT INTO rebook_sessions "
            "(session_id, opportunity_id, booking_id, state, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("session-delete", "opp-delete", booking_id, "completed", now),
        )
        store.conn.execute(
            "INSERT INTO rebook_events "
            "(event_id, session_id, event_type, detail, occurred_at) VALUES (?, ?, ?, ?, ?)",
            ("event-delete", "session-delete", "intent_recorded", "", now),
        )
        store.conn.commit()

        assert delete_booking(repo, booking_id) is True

        assert repo.get_by_id(booking_id) is None
        assert booking_id not in {item.booking_id for item in repo.list_active()}
        for table in (
            "check_history",
            "check_traces",
            "savings_opportunities",
            "rebook_sessions",
        ):
            assert store.conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE booking_id = ?", (booking_id,)
            ).fetchone()[0] == 0
        assert store.conn.execute(
            "SELECT COUNT(*) FROM rebook_events WHERE session_id = 'session-delete'"
        ).fetchone()[0] == 0

    def test_delete_missing_booking_is_safe_no_op(self, repo):
        assert delete_booking(repo, "missing") is False

    @pytest.mark.parametrize("operation", ["update", "delete"])
    def test_mutation_refuses_an_active_guided_rebook(self, repo, store, operation):
        booking, _ = register_booking(repo=repo, **_make_booking("BKG-IN-USE"))
        now = datetime.now(UTC).isoformat()
        store.conn.execute(
            "INSERT INTO rebook_sessions "
            "(session_id, opportunity_id, booking_id, state, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("active-session", "active-opportunity", booking.booking_id, "started", now),
        )
        store.conn.commit()

        with pytest.raises(BookingRejectedError, match="active guided rebook"):
            if operation == "update":
                update_booking(
                    repo,
                    replace(booking, room_type=RoomType("Should Not Persist")),
                )
            else:
                delete_booking(repo, booking.booking_id)

        unchanged = repo.get_by_id(booking.booking_id)
        assert unchanged is not None
        assert unchanged.room_type.label == "Deluxe Double"
