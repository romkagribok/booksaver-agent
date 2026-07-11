"""US-028: owner-only /admin commands."""

from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository
from booksaver.infrastructure.telegram.access import AccessControl
from booksaver.infrastructure.telegram.admin_commands import register_admin_commands
from booksaver.infrastructure.telegram.router import CommandRouter, IncomingCommand

OWNER_CHAT_ID = 555


def _cmd(chat_id: int, args: str, user_id: int | None = None) -> IncomingCommand:
    return IncomingCommand(
        user_id=user_id if user_id is not None else chat_id,
        chat_id=chat_id,
        command="/admin",
        args=args,
        raw_text=f"/admin {args}".strip(),
    )


def _wire(tmp_path, mode: str = "owner"):
    db_path = tmp_path / "t.db"
    with SqliteStore(db_path):
        pass
    router = CommandRouter()
    sent: list[tuple[int, str]] = []
    access_control = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path, mode=mode)
    register_admin_commands(
        router=router, reply=lambda c, t: sent.append((c, t)), db_path=db_path,
        access_control=access_control,
    )
    return router, sent, db_path, access_control


class TestNonOwnerRefusal:
    def test_non_owner_is_refused_regardless_of_mode(self, tmp_path):
        for mode in ("owner", "invite"):
            router, sent, _db, _ac = _wire(tmp_path, mode=mode)
            router.dispatch(_cmd(chat_id=999, args="users"))
            assert sent == [(999, "Admin commands are owner-only.")]


class TestUsersListing:
    def test_lists_users_with_key_and_booking_counts(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="users"))

        assert len(sent) == 1
        assert "Users:" in sent[0][1]
        assert "tg=42" in sent[0][1]


class TestRevoke:
    def test_revokes_a_user_by_telegram_id(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="revoke 42"))

        assert "revoked" in sent[-1][1]
        with SqliteStore(db_path) as store:
            reloaded = SqliteUserRepository(store).get_by_telegram_id(42)
        assert reloaded is not None
        assert reloaded.access_state.value == "revoked"

    def test_owner_cannot_be_revoked(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args=f"revoke {owner.user_id}"))

        assert "cannot be revoked" in sent[-1][1]


class TestPurge:
    def test_purge_requires_explicit_confirmation(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="purge 42"))

        assert "confirm" in sent[-1][1]
        with SqliteStore(db_path) as store:
            still_there = SqliteUserRepository(store).get_by_telegram_id(42)
        assert still_there is not None

    def test_purge_with_confirm_deletes_the_user(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="purge 42 confirm"))

        assert "purged" in sent[-1][1]
        with SqliteStore(db_path) as store:
            gone = SqliteUserRepository(store).get_by_telegram_id(42)
        assert gone is None


class TestInvite:
    def test_issues_a_redeemable_code(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="invite"))

        assert "Invite code:" in sent[-1][1]
        code = sent[-1][1].split("Invite code: ")[1].split("\n")[0]

        from booksaver.infrastructure.persistence.sqlite_store import SqliteInviteCodeRepository

        with SqliteStore(db_path) as store:
            invite = SqliteInviteCodeRepository(store).get(code)
        assert invite is not None
        assert not invite.is_used


class TestModeSwitch:
    def test_mode_switch_requires_confirmation_then_applies(self, tmp_path):
        router, sent, _db, access_control = _wire(tmp_path, mode="owner")

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="mode invite"))
        assert "confirm" in sent[-1][1]
        assert access_control.mode == "owner"

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="mode invite confirm"))
        assert access_control.mode == "invite"

    def test_unknown_mode_is_rejected(self, tmp_path):
        router, sent, _db, access_control = _wire(tmp_path)
        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="mode public confirm"))
        assert access_control.mode == "owner"
        assert "Usage" in sent[-1][1]


class TestUsageFallback:
    def test_no_subcommand_shows_usage(self, tmp_path):
        router, sent, _db, _ac = _wire(tmp_path)
        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args=""))
        assert "Usage" in sent[-1][1]

    def test_unknown_subcommand_shows_usage(self, tmp_path):
        router, sent, _db, _ac = _wire(tmp_path)
        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="frobnicate"))
        assert "Usage" in sent[-1][1]
