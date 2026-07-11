from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from booksaver.domain.errors import SecretKeyError
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
from booksaver.infrastructure.telegram.key_validator import KeyValidator

from .router import IncomingCommand

logger = logging.getLogger(__name__)

DeleteMessage = Callable[[int, int], object]


class KeyIntakeFlow:
    """Single-step, per-chat `/setkey` intake (US-027).

    Deliberately not built on the generic `DialogManager`/`DialogDefinition`
    framework: that framework's `on_complete` hook doesn't receive the raw
    Telegram `message_id`, which this flow needs to delete the chat message
    containing the pasted key (redaction requirement). A dedicated tiny
    per-chat pending-set is simpler than threading `message_id` through the
    shared dialog machinery for one caller.
    """

    def __init__(
        self,
        db_path: Path,
        validator: KeyValidator,
        delete_message: DeleteMessage,
        key_store: FernetKeyStore | None = None,
    ) -> None:
        self._db_path = db_path
        self._validator = validator
        self._delete_message = delete_message
        self._key_store = key_store or FernetKeyStore()
        self._pending: set[int] = set()

    def start(self, chat_id: int) -> str:
        self._pending.add(chat_id)
        return (
            "Send your Anthropic API key now (starts with `sk-ant-`). I will "
            "validate it with a minimal live call, encrypt it, and delete this "
            "message. Send /cancelflow to abort."
        )

    def is_pending(self, chat_id: int) -> bool:
        return chat_id in self._pending

    def cancel(self, chat_id: int) -> bool:
        """Abort a pending key intake, if any. Returns whether one existed."""
        was_pending = chat_id in self._pending
        self._pending.discard(chat_id)
        return was_pending

    def handle(self, cmd: IncomingCommand) -> str:
        self._pending.discard(cmd.chat_id)
        api_key = cmd.raw_text.strip()

        self._try_delete(cmd.chat_id, cmd.message_id)

        if not api_key:
            return "That didn't look like a key. Send /setkey to try again."

        if not self._validator.validate(api_key):
            return (
                "That key could not be validated against the Anthropic API. "
                "Send /setkey to try again, or /deletekey if you'd rather use "
                "the shared key."
            )

        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteStore,
            SqliteUserRepository,
        )

        try:
            encrypted = self._key_store.encrypt(api_key)
        except SecretKeyError as exc:
            logger.error("Cannot encrypt personal key: %s", exc)
            return (
                "This bot's operator hasn't configured key encryption yet "
                "(BOOKSAVER_SECRET_KEY is missing or invalid). Your key was not "
                "stored. Please contact the owner."
            )

        with SqliteStore(self._db_path) as store:
            users = SqliteUserRepository(store)
            user = users.get_or_create_by_telegram_id(cmd.user_id)
            users.set_encrypted_key(user.user_id, encrypted)

        return (
            "Your personal Anthropic key is saved, encrypted at rest. Your price "
            "checks now bill your own key. Send /setkey again to rotate it, or "
            "/deletekey to revert to the shared key."
        )

    def _try_delete(self, chat_id: int, message_id: int) -> None:
        if not message_id:
            return
        try:
            self._delete_message(chat_id, message_id)
        except Exception as exc:
            logger.info(
                "Could not delete key-intake message chat_id=%s message_id=%s: %s",
                chat_id,
                message_id,
                exc,
            )


def handle_deletekey(cmd: IncomingCommand, db_path: Path) -> str:
    """`/deletekey` (US-027): clears the stored key, reverting to owner-billed
    checks. No dialog needed — the command itself is the whole flow."""
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        user = users.get_or_create_by_telegram_id(cmd.user_id)
        had_key = user.encrypted_key is not None
        users.set_encrypted_key(user.user_id, None)

    if had_key:
        return "Your personal key was removed. Your checks now bill the shared key again."
    return "You didn't have a personal key set — checks already bill the shared key."
