"""US-026: real multi-user access control (owner/invite modes)."""

from datetime import UTC, datetime

from booksaver.domain.user import UserAccessState
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteInviteCodeRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.access import AccessControl, RateLimiter

OWNER_CHAT_ID = 555


def _store(tmp_path):
    return SqliteStore(tmp_path / "t.db")


class TestOwnerMode:
    def test_owner_chat_is_always_allowed(self, tmp_path):
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=tmp_path / "t.db", mode="owner")
        assert ac.authorize(OWNER_CHAT_ID, OWNER_CHAT_ID, "/status", "") is True

    def test_stranger_is_refused_without_touching_the_database(self, tmp_path):
        db_path = tmp_path / "t.db"
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="owner")
        assert ac.authorize(999, 999, "/status", "") is False
        assert not db_path.exists()  # never opened a store for an owner-mode refusal

    def test_start_with_a_code_does_not_admit_in_owner_mode(self, tmp_path):
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=tmp_path / "t.db", mode="owner")
        assert ac.authorize(999, 999, "/start", "ABCDEF") is False

    def test_owner_first_message_links_telegram_id_to_owner_row(self, tmp_path):
        db_path = tmp_path / "t.db"
        with _store(tmp_path) as store:
            assert SqliteUserRepository(store).get_owner().telegram_user_id is None
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="owner")
        assert ac.authorize(OWNER_CHAT_ID, OWNER_CHAT_ID, "/register", "") is True
        with _store(tmp_path) as store:
            users = SqliteUserRepository(store)
            owner = users.get_owner()
            assert owner.telegram_user_id == OWNER_CHAT_ID
            # sender-scoped handlers can now resolve the owner as a user
            assert users.get_by_telegram_id(OWNER_CHAT_ID) is not None

    def test_owner_link_never_rebinds_an_existing_telegram_id(self, tmp_path):
        db_path = tmp_path / "t.db"
        with _store(tmp_path) as store:
            users = SqliteUserRepository(store)
            users.link_telegram_id(users.get_owner().user_id, 111)
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="owner")
        assert ac.authorize(222, OWNER_CHAT_ID, "/status", "") is True
        with _store(tmp_path) as store:
            assert SqliteUserRepository(store).get_owner().telegram_user_id == 111


class TestInviteMode:
    def test_stranger_without_a_code_is_refused(self, tmp_path):
        db_path = tmp_path / "t.db"
        with _store(tmp_path):
            pass  # ensure the DB exists so this isn't a false-positive owner check
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="invite")
        assert ac.authorize(999, 999, "/status", "") is False

    def test_stranger_with_a_valid_code_is_admitted(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="invite")
        assert ac.authorize(999, 999, "/start", invite.code) is True

        with SqliteStore(db_path) as store:
            admitted = SqliteUserRepository(store).get_by_telegram_id(999)
        assert admitted is not None
        assert admitted.access_state is UserAccessState.ACTIVE

    def test_code_is_single_use(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="invite")
        assert ac.authorize(999, 999, "/start", invite.code) is True
        assert ac.authorize(1000, 1000, "/start", invite.code) is False

    def test_invalid_code_is_refused_identically_to_no_code(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path):
            pass
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="invite")
        assert ac.authorize(999, 999, "/start", "not-a-real-code") is False

    def test_active_admitted_user_is_allowed_on_later_commands(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            SqliteUserRepository(store).get_or_create_by_telegram_id(999)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="invite")
        assert ac.authorize(999, 999, "/bookings", "") is True

    def test_revoked_user_is_refused(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            users = SqliteUserRepository(store)
            user = users.get_or_create_by_telegram_id(999)
            users.set_access_state(user.user_id, UserAccessState.REVOKED)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="invite")
        assert ac.authorize(999, 999, "/bookings", "") is False

    def test_expired_code_cannot_admit(self, tmp_path):
        from datetime import timedelta

        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            invite = SqliteInviteCodeRepository(store).issue(
                issued_by=owner.user_id, expires_at=datetime.now(UTC) - timedelta(hours=1)
            )

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="invite")
        assert ac.authorize(999, 999, "/start", invite.code) is False


class TestModeSwitch:
    def test_set_mode_changes_behavior_at_runtime(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path):
            pass
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="owner")
        assert ac.authorize(999, 999, "/status", "") is False
        ac.set_mode("invite")
        assert ac.mode == "invite"

    def test_set_mode_rejects_unknown_value(self, tmp_path):
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=tmp_path / "t.db")
        import pytest

        with pytest.raises(ValueError, match="Unknown access mode"):
            ac.set_mode("open")


class TestRefusalRateLimiting:
    def test_refuses_once_then_rate_limits(self, tmp_path):
        limiter = RateLimiter(max_events=1, window_seconds=3600)
        ac = AccessControl(
            owner_chat_id=OWNER_CHAT_ID,
            db_path=tmp_path / "t.db",
            mode="owner",
            refusal_limiter=limiter,
        )
        assert ac.should_send_refusal(999) is True
        assert ac.should_send_refusal(999) is False
