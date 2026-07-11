"""US-027: /setkey intake flow and /deletekey."""

from cryptography.fernet import Fernet

from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository
from booksaver.infrastructure.telegram.key_dialogs import KeyIntakeFlow, handle_deletekey
from booksaver.infrastructure.telegram.router import IncomingCommand


class FakeValidator:
    def __init__(self, accept: bool) -> None:
        self.accept = accept
        self.validated: list[str] = []

    def validate(self, api_key: str) -> bool:
        self.validated.append(api_key)
        return self.accept


def _key_store() -> FernetKeyStore:
    return FernetKeyStore(secret_key=Fernet.generate_key().decode("utf-8"))


def _cmd(chat_id: int, user_id: int, text: str, message_id: int = 42) -> IncomingCommand:
    return IncomingCommand(
        user_id=user_id, chat_id=chat_id, command="", args="", raw_text=text,
        message_id=message_id,
    )


class TestKeyIntakeFlow:
    def test_start_marks_chat_pending(self, tmp_path):
        flow = KeyIntakeFlow(
            db_path=tmp_path / "t.db",
            validator=FakeValidator(True),
            delete_message=lambda c, m: None,
        )
        flow.start(chat_id=1)
        assert flow.is_pending(1) is True

    def test_valid_key_is_validated_encrypted_stored_and_message_deleted(self, tmp_path):
        db_path = tmp_path / "t.db"
        deleted: list[tuple[int, int]] = []
        validator = FakeValidator(True)
        flow = KeyIntakeFlow(
            db_path=db_path,
            validator=validator,
            delete_message=lambda c, m: deleted.append((c, m)),
            key_store=_key_store(),
        )
        flow.start(chat_id=10)

        reply = flow.handle(_cmd(chat_id=10, user_id=999, text="sk-ant-real-key", message_id=7))

        assert "saved" in reply.lower()
        assert deleted == [(10, 7)]
        assert validator.validated == ["sk-ant-real-key"]
        assert flow.is_pending(10) is False

        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_by_telegram_id(999)
        assert user is not None
        assert user.encrypted_key is not None
        # never store the plaintext key
        assert b"sk-ant-real-key" not in user.encrypted_key

    def test_invalid_key_is_not_stored(self, tmp_path):
        db_path = tmp_path / "t.db"
        flow = KeyIntakeFlow(
            db_path=db_path,
            validator=FakeValidator(False),
            delete_message=lambda c, m: None,
            key_store=_key_store(),
        )
        flow.start(chat_id=10)

        reply = flow.handle(_cmd(chat_id=10, user_id=999, text="sk-ant-bad-key"))

        assert "could not be validated" in reply
        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_by_telegram_id(999)
        assert user is None or user.encrypted_key is None

    def test_the_key_never_appears_in_any_reply(self, tmp_path):
        flow = KeyIntakeFlow(
            db_path=tmp_path / "t.db",
            validator=FakeValidator(True),
            delete_message=lambda c, m: None,
            key_store=_key_store(),
        )
        flow.start(chat_id=10)
        reply = flow.handle(_cmd(chat_id=10, user_id=999, text="sk-ant-super-secret-value"))
        assert "sk-ant-super-secret-value" not in reply

    def test_deletion_failure_does_not_block_storing_the_key(self, tmp_path):
        def _boom(chat_id: int, message_id: int) -> None:
            raise RuntimeError("Telegram won't let us delete this")

        flow = KeyIntakeFlow(
            db_path=tmp_path / "t.db",
            validator=FakeValidator(True),
            delete_message=_boom,
            key_store=_key_store(),
        )
        flow.start(chat_id=10)
        reply = flow.handle(_cmd(chat_id=10, user_id=999, text="sk-ant-real-key"))
        assert "saved" in reply.lower()

    def test_cancel_reports_whether_a_flow_was_pending(self, tmp_path):
        flow = KeyIntakeFlow(
            db_path=tmp_path / "t.db",
            validator=FakeValidator(True),
            delete_message=lambda c, m: None,
        )
        assert flow.cancel(1) is False
        flow.start(1)
        assert flow.cancel(1) is True
        assert flow.is_pending(1) is False


class TestDeleteKey:
    def test_deletekey_clears_a_stored_key(self, tmp_path):
        db_path = tmp_path / "t.db"
        with SqliteStore(db_path) as store:
            users = SqliteUserRepository(store)
            user = users.get_or_create_by_telegram_id(999)
            users.set_encrypted_key(user.user_id, b"ciphertext")

        reply = handle_deletekey(_cmd(chat_id=10, user_id=999, text=""), db_path)

        assert "removed" in reply
        with SqliteStore(db_path) as store:
            reloaded = SqliteUserRepository(store).get_by_telegram_id(999)
        assert reloaded is not None
        assert reloaded.encrypted_key is None

    def test_deletekey_with_no_key_set_is_a_friendly_no_op(self, tmp_path):
        reply = handle_deletekey(_cmd(chat_id=10, user_id=999, text=""), tmp_path / "t.db")
        assert "didn't have" in reply
