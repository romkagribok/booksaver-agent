"""US-064: fixed invite-only multi-user access control."""

from datetime import UTC, datetime

from booksaver.domain.user import UserAccessState
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteInviteCodeRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.access import (
    AccessControl,
    AccessRefusalReason,
    RateLimiter,
)

OWNER_CHAT_ID = 555


def _store(tmp_path):
    return SqliteStore(tmp_path / "t.db")


class TestFixedInviteAccess:
    def test_owner_chat_is_always_allowed(self, tmp_path):
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=tmp_path / "t.db")
        assert ac.authorize(OWNER_CHAT_ID, OWNER_CHAT_ID, "/status", "") is True

    def test_stranger_is_refused(self, tmp_path):
        db_path = tmp_path / "t.db"
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/status", "") is False

    def test_legacy_owner_mode_still_uses_invite_only_admission(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode="owner")
        assert ac.authorize(999, 999, "/start", invite.code) is True

    def test_owner_first_message_links_telegram_id_to_owner_row(self, tmp_path):
        db_path = tmp_path / "t.db"
        with _store(tmp_path) as store:
            assert SqliteUserRepository(store).get_owner().telegram_user_id is None
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
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
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(222, OWNER_CHAT_ID, "/status", "") is True
        with _store(tmp_path) as store:
            assert SqliteUserRepository(store).get_owner().telegram_user_id == 111


class TestInviteRedemption:
    def test_stranger_without_a_code_is_refused(self, tmp_path):
        db_path = tmp_path / "t.db"
        with _store(tmp_path):
            pass  # ensure the DB exists so this isn't a false-positive owner check
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/status", "") is False

    def test_stranger_with_a_valid_code_is_admitted(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/start", invite.code) is True

        with SqliteStore(db_path) as store:
            admitted = SqliteUserRepository(store).get_by_telegram_id(999)
        assert admitted is not None
        assert admitted.access_state is UserAccessState.ACTIVE

    def test_invite_redemption_captures_username(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/start", invite.code, username="NewUser") is True

        with SqliteStore(db_path) as store:
            admitted = SqliteUserRepository(store).get_by_telegram_id(999)
            assert admitted is not None
            assert admitted.telegram_username == "NewUser"

    def test_code_is_single_use(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/start", invite.code) is True
        assert ac.authorize(1000, 1000, "/start", invite.code) is False

    def test_invalid_code_is_refused_identically_to_no_code(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path):
            pass
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/start", "not-a-real-code") is False

    def test_active_admitted_user_is_allowed_on_later_commands(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            SqliteUserRepository(store).get_or_create_by_telegram_id(999)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/bookings", "") is True

    def test_revoked_user_is_refused(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            users = SqliteUserRepository(store)
            user = users.get_or_create_by_telegram_id(999)
            users.set_access_state(user.user_id, UserAccessState.REVOKED)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/bookings", "") is False
        assert ac.refusal_reason(999) is AccessRefusalReason.REVOKED
        assert ac.is_active_telegram_user(999) is False

    def test_expired_code_cannot_admit(self, tmp_path):
        from datetime import timedelta

        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            invite = SqliteInviteCodeRepository(store).issue(
                issued_by=owner.user_id, expires_at=datetime.now(UTC) - timedelta(hours=1)
            )

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/start", invite.code) is False

    def test_unknown_legacy_mode_is_rejected(self, tmp_path):
        import pytest

        with pytest.raises(ValueError, match="Unknown legacy access mode"):
            AccessControl(
                owner_chat_id=OWNER_CHAT_ID,
                db_path=tmp_path / "t.db",
                mode="open",
            )

    def test_unknown_sender_refusal_does_not_disclose_invite_details(self, tmp_path):
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=tmp_path / "t.db")
        assert ac.refusal_reason(999) is AccessRefusalReason.UNKNOWN

    def test_successful_authorization_refreshes_and_clears_username(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_or_create_by_telegram_id(999)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/status", "", username=" @Alice ") is True
        with SqliteStore(db_path) as store:
            assert SqliteUserRepository(store).get_by_id(user.user_id).telegram_username == "Alice"

        assert ac.authorize(999, 999, "/status", "", username=None) is True
        with SqliteStore(db_path) as store:
            assert SqliteUserRepository(store).get_by_id(user.user_id).telegram_username is None

    def test_refused_user_cannot_change_stored_username(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            users = SqliteUserRepository(store)
            user = users.get_or_create_by_telegram_id(999)
            users.set_telegram_username(user.user_id, "Before")
            users.set_access_state(user.user_id, UserAccessState.REVOKED)

        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/status", "", username="After") is False
        with SqliteStore(db_path) as store:
            assert SqliteUserRepository(store).get_by_id(user.user_id).telegram_username == "Before"

    def test_username_projection_failure_does_not_deny_active_user(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            SqliteUserRepository(store).get_or_create_by_telegram_id(999)

        def fail_projection(*_args):
            raise RuntimeError("projection unavailable")

        monkeypatch.setattr(SqliteUserRepository, "set_telegram_username", fail_projection)
        ac = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
        assert ac.authorize(999, 999, "/status", "", username="Alice") is True


class TestRefusalRateLimiting:
    def test_refuses_once_then_rate_limits(self, tmp_path):
        limiter = RateLimiter(max_events=1, window_seconds=3600)
        ac = AccessControl(
            owner_chat_id=OWNER_CHAT_ID,
            db_path=tmp_path / "t.db",
            refusal_limiter=limiter,
        )
        assert ac.should_send_refusal(999) is True
        assert ac.should_send_refusal(999) is False
