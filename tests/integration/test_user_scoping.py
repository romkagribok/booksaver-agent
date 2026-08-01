"""US-029: schema v7 users table, v6->v7 migration, and repository scoping."""

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from booksaver.application.register_booking import register_booking
from booksaver.domain.user import UserAccessState, UserRole
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
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)

_V6_DDL = """\
CREATE TABLE schema_meta (version INTEGER NOT NULL, applied_at TEXT NOT NULL);
INSERT INTO schema_meta VALUES (6, '2026-07-06T00:00:00+00:00');
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
    status           TEXT    NOT NULL DEFAULT 'active',
    occ_adults       INTEGER CHECK(occ_adults IS NULL OR occ_adults >= 1),
    occ_children     INTEGER CHECK(occ_children IS NULL OR occ_children >= 0),
    occ_rooms        INTEGER CHECK(occ_rooms IS NULL OR occ_rooms >= 1)
);
CREATE TABLE check_history (
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
CREATE TABLE rebook_sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL UNIQUE,
    opportunity_id TEXT NOT NULL,
    booking_id     TEXT NOT NULL REFERENCES bookings(booking_id),
    state          TEXT NOT NULL,
    started_at     TEXT NOT NULL,
    ended_at       TEXT,
    end_reason     TEXT
);
CREATE TABLE rebook_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL UNIQUE,
    session_id  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
);
CREATE TABLE check_traces (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id   TEXT NOT NULL UNIQUE,
    booking_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    trace_json TEXT NOT NULL
);
CREATE TABLE savings_opportunities (
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
INSERT INTO bookings VALUES (
    'legacy-1', 'booking_com', 'hotel', 'CONF-LEGACY-1', 'Old Hotel', 'old_ref',
    '2026-10-01', '2026-10-05', 'Standard', '300.00', 'EUR', 1, 'Free', NULL,
    '2026-06-01T00:00:00+00:00', 'active', 2, 0, 1
);
INSERT INTO bookings VALUES (
    'legacy-2', 'booking_com', 'hotel', 'CONF-LEGACY-2', 'Other Hotel', 'other_ref',
    '2026-11-01', '2026-11-05', 'Suite', '500.00', 'EUR', 1, 'Free', NULL,
    '2026-06-02T00:00:00+00:00', 'active', 2, 0, 1
);
"""


def _make_v6_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_V6_DDL)
    conn.commit()
    conn.close()


def _booking_kwargs(confirmation: str, property_name: str = "Hotel Test") -> dict:
    return dict(
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of(confirmation),
        property=Property(name=property_name, booking_com_ref=f"ref-{confirmation}"),
        stay_dates=StayDates(date(2026, 10, 1), date(2026, 10, 5)),
        room_type=RoomType(label="Double"),
        baseline_price=Money.of("400.00", "EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="Free cancellation"),
        occupancy=Occupancy(adults=2),
    )


class TestV7Migration:
    def test_v6_database_migrates_to_v7(self, tmp_path):
        db_path = tmp_path / "old.db"
        _make_v6_db(db_path)

        with SqliteStore(db_path) as store:
            versions = [
                r[0]
                for r in store.conn.execute(
                    "SELECT version FROM schema_meta ORDER BY version"
                ).fetchall()
            ]
            users = SqliteUserRepository(store).list_all()
            legacy1 = SqliteBookingRepository(store).get_by_id("legacy-1")
            legacy2 = SqliteBookingRepository(store).get_by_id("legacy-2")
            owner_bookings = SqliteBookingRepository(store).list_all_for_user(
                users[0].user_id
            )

        assert versions[-1] == SCHEMA_VERSION == 12
        assert len(users) == 1
        assert users[0].role is UserRole.OWNER
        assert users[0].access_state is UserAccessState.ACTIVE
        assert users[0].telegram_user_id is None
        assert legacy1 is None and legacy2 is None
        assert owner_bookings == []

    def test_migration_is_idempotent_on_reopen(self, tmp_path):
        db_path = tmp_path / "old.db"
        _make_v6_db(db_path)
        with SqliteStore(db_path):
            pass
        with SqliteStore(db_path) as store:  # second open must not re-migrate/fail
            row = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()
            users = SqliteUserRepository(store).list_all()
        assert row[0] == SCHEMA_VERSION
        assert len(users) == 1  # still exactly one owner, not re-created

    def test_fresh_init_creates_v7_directly(self, tmp_path):
        with SqliteStore(tmp_path / "fresh.db") as store:
            row = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()
            users = SqliteUserRepository(store).list_all()
        assert row[0] == SCHEMA_VERSION == 12
        assert len(users) == 1
        assert users[0].role is UserRole.OWNER

    def test_laptop_single_user_mode_unchanged(self, tmp_path):
        """Owner-only deployment: registering + listing behaves exactly as
        pre-v7 (booking auto-assigned to the sole owner user)."""
        with SqliteStore(tmp_path / "laptop.db") as store:
            repo = SqliteBookingRepository(store)
            owner = SqliteUserRepository(store).get_owner()
            booking, _ = register_booking(repo=repo, **_booking_kwargs("BKG-LAPTOP"))
            active = repo.list_active_for_user(owner.user_id)
            unscoped_active = repo.list_active()
        assert len(active) == 1
        assert active[0].booking_id == booking.booking_id
        assert len(unscoped_active) == 1


class TestExactlyOneOwner:
    def test_owner_uniqueness_enforced_at_db_level(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            with pytest.raises(sqlite3.IntegrityError):
                store.conn.execute(
                    "INSERT INTO users (telegram_user_id, role, access_state, "
                    "encrypted_key, created_at) VALUES (999, 'owner', 'active', "
                    "NULL, '2026-07-11T00:00:00+00:00')"
                )


class TestUserRepository:
    def test_get_or_create_by_telegram_id_is_idempotent(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteUserRepository(store)
            u1 = repo.get_or_create_by_telegram_id(555)
            u2 = repo.get_or_create_by_telegram_id(555)
        assert u1.user_id == u2.user_id
        assert u1.role is UserRole.USER
        assert u1.access_state is UserAccessState.ACTIVE

    def test_set_access_state_revokes_user(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteUserRepository(store)
            invited = repo.get_or_create_by_telegram_id(777)
            repo.set_access_state(invited.user_id, UserAccessState.REVOKED)
            reloaded = repo.get_by_id(invited.user_id)
        assert reloaded is not None
        assert reloaded.access_state is UserAccessState.REVOKED

    def test_set_access_state_unknown_user_raises(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteUserRepository(store)
            with pytest.raises(KeyError):
                repo.set_access_state(9999, UserAccessState.REVOKED)


class TestCrossUserIsolation:
    """FR-5 / US-029: no query path can return another user's data."""

    def _two_users_with_bookings(self, store) -> tuple[int, int]:
        users = SqliteUserRepository(store)
        bookings = SqliteBookingRepository(store)

        user_a = users.get_owner()
        user_b = users.get_or_create_by_telegram_id(4242)

        register_booking(
            repo=bookings, user_id=user_a.user_id,
            **_booking_kwargs("CONF-A", "Hotel A"),
        )
        register_booking(
            repo=bookings, user_id=user_b.user_id,
            **_booking_kwargs("CONF-B", "Hotel B"),
        )
        return user_a.user_id, user_b.user_id

    def test_bookings_list_active_is_isolated(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            bookings = SqliteBookingRepository(store)
            user_a_id, user_b_id = self._two_users_with_bookings(store)

            a_active = bookings.list_active_for_user(user_a_id)
            b_active = bookings.list_active_for_user(user_b_id)

        assert {b.property.name for b in a_active} == {"Hotel A"}
        assert {b.property.name for b in b_active} == {"Hotel B"}
        assert not ({b.booking_id for b in a_active} & {b.booking_id for b in b_active})

    def test_bookings_list_all_is_isolated(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            bookings = SqliteBookingRepository(store)
            user_a_id, user_b_id = self._two_users_with_bookings(store)

            a_all = bookings.list_all_for_user(user_a_id)
            b_all = bookings.list_all_for_user(user_b_id)

        assert len(a_all) == 1 and a_all[0].property.name == "Hotel A"
        assert len(b_all) == 1 and b_all[0].property.name == "Hotel B"

    def test_savings_list_all_for_user_is_isolated(self, tmp_path):
        from booksaver.domain.savings import SavingsOpportunity
        from tests.integration.test_savings_repo import _add_checked_opportunity

        with SqliteStore(tmp_path / "t.db") as store:
            bookings = SqliteBookingRepository(store)
            savings = SqliteSavingsRepository(store)
            user_a_id, user_b_id = self._two_users_with_bookings(store)

            booking_a = bookings.list_all_for_user(user_a_id)[0]
            booking_b = bookings.list_all_for_user(user_b_id)[0]

            from datetime import UTC, datetime

            def _opportunity(booking_id: str, suffix: str) -> SavingsOpportunity:
                return SavingsOpportunity(
                    opportunity_id=f"opp-{suffix}",
                    booking_id=booking_id,
                    check_id=f"chk-{suffix}",
                    baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
                    live_price=Money(amount=Decimal("350.00"), currency="EUR"),
                    amount_saved=Money(amount=Decimal("50.00"), currency="EUR"),
                    percent_saved=Decimal("12.50"),
                    validated_at=datetime.now(UTC),
                    notified_at=None,
                )

            _add_checked_opportunity(
                store, savings, _opportunity(booking_a.booking_id, "a")
            )
            _add_checked_opportunity(
                store, savings, _opportunity(booking_b.booking_id, "b")
            )

            a_savings = savings.list_all_for_user(user_a_id)
            b_savings = savings.list_all_for_user(user_b_id)
            a_current = savings.list_current_for_user(user_a_id)
            b_current = savings.list_current_for_user(user_b_id)

        assert [o.opportunity_id for o in a_savings] == ["opp-a"]
        assert [o.opportunity_id for o in b_savings] == ["opp-b"]
        assert [o.opportunity_id for o in a_current] == ["opp-a"]
        assert [o.opportunity_id for o in b_current] == ["opp-b"]

    def test_users_are_isolated_from_each_other_via_telegram_id(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteUserRepository(store)
            owner = repo.get_owner()
            invited = repo.get_or_create_by_telegram_id(9001)

        assert owner.user_id != invited.user_id
        assert owner.role is UserRole.OWNER
        assert invited.role is UserRole.USER


class TestGetOwnerOfBooking:
    """US-027: resolving a booking's owning user for per-booking key resolution."""

    def test_resolves_the_booking_owner(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            bookings = SqliteBookingRepository(store)
            invited = users.get_or_create_by_telegram_id(555)
            booking, _ = register_booking(
                repo=bookings, user_id=invited.user_id, **_booking_kwargs("CONF-OWNER")
            )
            owner_of_booking = users.get_owner_of_booking(booking.booking_id)

        assert owner_of_booking is not None
        assert owner_of_booking.user_id == invited.user_id

    def test_unknown_booking_returns_none(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            assert SqliteUserRepository(store).get_owner_of_booking("nope") is None


class TestSetEncryptedKey:
    """US-027: storing/clearing a user's encrypted personal key."""

    def test_set_and_clear_round_trips(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            user = users.get_or_create_by_telegram_id(101)
            users.set_encrypted_key(user.user_id, b"ciphertext")
            with_key = users.get_by_id(user.user_id)
            users.set_encrypted_key(user.user_id, None)
            without_key = users.get_by_id(user.user_id)

        assert with_key is not None and with_key.encrypted_key == b"ciphertext"
        assert without_key is not None and without_key.encrypted_key is None

    def test_unknown_user_raises(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            with pytest.raises(KeyError):
                SqliteUserRepository(store).set_encrypted_key(9999, b"x")


class TestPurgeUser:
    """US-028 `/admin purge`: deletes a non-owner user and everything scoped
    through their bookings."""

    def test_purge_deletes_user_and_their_bookings(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            bookings = SqliteBookingRepository(store)
            victim = users.get_or_create_by_telegram_id(202)
            booking, _ = register_booking(
                repo=bookings, user_id=victim.user_id, **_booking_kwargs("CONF-PURGE")
            )

            users.purge(victim.user_id)

            remaining_user = users.get_by_id(victim.user_id)
            remaining_booking = bookings.get_by_id(booking.booking_id)

        assert remaining_user is None
        assert remaining_booking is None

    def test_purge_owner_is_rejected(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            owner = users.get_owner()
            with pytest.raises(ValueError, match="owner"):
                users.purge(owner.user_id)

    def test_purge_unknown_user_raises(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            with pytest.raises(KeyError):
                SqliteUserRepository(store).purge(9999)


class TestInviteCodeRepository:
    """US-026: schema v8 single-use invite codes."""

    def test_issue_then_redeem_admits_a_new_user(self, tmp_path):
        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteInviteCodeRepository,
        )

        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            invites = SqliteInviteCodeRepository(store)
            owner = users.get_owner()

            invite = invites.issue(issued_by=owner.user_id)
            new_user = users.get_or_create_by_telegram_id(303)
            redeemed = invites.redeem(invite.code, used_by=new_user.user_id, now=_now())

        assert redeemed is not None
        assert redeemed.used_by == new_user.user_id
        assert redeemed.is_used

    def test_redeeming_twice_fails_the_second_time(self, tmp_path):
        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteInviteCodeRepository,
        )

        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            invites = SqliteInviteCodeRepository(store)
            owner = users.get_owner()
            invite = invites.issue(issued_by=owner.user_id)
            user_a = users.get_or_create_by_telegram_id(404)
            user_b = users.get_or_create_by_telegram_id(405)

            first = invites.redeem(invite.code, used_by=user_a.user_id, now=_now())
            second = invites.redeem(invite.code, used_by=user_b.user_id, now=_now())

        assert first is not None
        assert second is None

    def test_redeeming_unknown_code_returns_none(self, tmp_path):
        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteInviteCodeRepository,
        )

        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            invites = SqliteInviteCodeRepository(store)
            user_a = users.get_or_create_by_telegram_id(406)
            assert invites.redeem("does-not-exist", used_by=user_a.user_id, now=_now()) is None

    def test_expired_code_cannot_be_redeemed(self, tmp_path):
        from datetime import timedelta

        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteInviteCodeRepository,
        )

        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            invites = SqliteInviteCodeRepository(store)
            owner = users.get_owner()
            now = _now()
            invite = invites.issue(issued_by=owner.user_id, expires_at=now - timedelta(hours=1))
            user_a = users.get_or_create_by_telegram_id(407)

            result = invites.redeem(invite.code, used_by=user_a.user_id, now=now)

        assert result is None

    def test_issued_codes_are_unique(self, tmp_path):
        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteInviteCodeRepository,
        )

        with SqliteStore(tmp_path / "t.db") as store:
            users = SqliteUserRepository(store)
            invites = SqliteInviteCodeRepository(store)
            owner = users.get_owner()
            codes = {invites.issue(issued_by=owner.user_id).code for _ in range(10)}

        assert len(codes) == 10


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC)
