from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from .client import TelegramApiError, TelegramBotClient
from .offset_store import TelegramOffsetStore
from .router import CommandRouter, IncomingCallback, IncomingCommand

logger = logging.getLogger(__name__)

_RETRY_WAIT_SECONDS = 5.0


def _parse_command(text: str) -> tuple[str, str]:
    parts = text.strip().split(maxsplit=1)
    command = parts[0].split("@", 1)[0]  # strip @botname suffix (group chats)
    args = parts[1] if len(parts) > 1 else ""
    return command, args


class BotLoop:
    """Long-poll update loop (US-023): fetch -> dispatch -> advance offset.

    Runs as a thread beside the scheduler in the daemon process (see
    `daemon/lifecycle.py`). A slow or failed price check never delays replies
    because this loop owns its own DB connection and never touches the browser.
    """

    def __init__(
        self,
        client: TelegramBotClient,
        router: CommandRouter,
        offset_store: TelegramOffsetStore,
        poll_timeout_seconds: int,
        access_guard: Callable[[IncomingCommand], bool],
        on_refused: Callable[[IncomingCommand], None],
        dialog_handler: Callable[[IncomingCommand], bool] | None = None,
        # bolt 011 (US-032): inline-keyboard rebook confirmations arrive as
        # `callback_query` updates, not `message`s. Optional + additive — a
        # daemon with no rebook-gate feature wired up (or a test) simply
        # never receives callback_query updates through this hook.
        callback_handler: Callable[[IncomingCallback], None] | None = None,
    ) -> None:
        self._client = client
        self._router = router
        self._offset_store = offset_store
        self._poll_timeout = poll_timeout_seconds
        self._access_guard = access_guard
        self._on_refused = on_refused
        self._dialog_handler = dialog_handler
        self._callback_handler = callback_handler

    def run(self, stop_event: threading.Event) -> None:
        offset = self._offset_store.load()
        logger.info("Telegram bot loop starting (offset=%s)", offset)

        while not stop_event.is_set():
            try:
                updates = self._client.get_updates(offset, timeout=self._poll_timeout)
            except TelegramApiError:
                logger.exception("Telegram getUpdates rejected — retrying")
                stop_event.wait(timeout=_RETRY_WAIT_SECONDS)
                continue
            except OSError:
                logger.exception("Telegram getUpdates network error — retrying")
                stop_event.wait(timeout=_RETRY_WAIT_SECONDS)
                continue

            new_offset = offset
            for update in updates:
                new_offset = update["update_id"] + 1
                try:
                    self._dispatch(update)
                except Exception:
                    logger.exception("Error handling Telegram update %s", update.get("update_id"))

            if updates and new_offset is not None:
                offset = new_offset
                self._offset_store.save(offset)

        logger.info("Telegram bot loop stopped")

    def _dispatch(self, update: dict[str, Any]) -> None:
        callback_query = update.get("callback_query")
        if callback_query is not None:
            self._dispatch_callback(callback_query)
            return

        message = update.get("message")
        if message is None:
            return  # neither a plain text message nor a callback query

        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = chat.get("id")
        user_id = sender.get("id")
        message_id = message.get("message_id", 0)
        text = message.get("text")
        if chat_id is None or user_id is None or not text:
            return

        command, args = _parse_command(text)
        incoming = IncomingCommand(
            user_id=user_id,
            chat_id=chat_id,
            command=command,
            args=args,
            raw_text=text,
            message_id=message_id,
        )

        if not self._access_guard(incoming):
            self._on_refused(incoming)
            return

        if command.startswith("/"):
            if not self._router.dispatch(incoming):
                self._client.send_message(
                    chat_id, f"Unknown command: {command}. Send /help for the list."
                )
            return

        if self._dialog_handler is not None and self._dialog_handler(incoming):
            return

    def _dispatch_callback(self, callback_query: dict[str, Any]) -> None:
        if self._callback_handler is None:
            return  # no feature registered to consume callback queries

        message = callback_query.get("message") or {}
        chat = message.get("chat") or {}
        sender = callback_query.get("from") or {}
        chat_id = chat.get("id")
        user_id = sender.get("id")
        callback_query_id = callback_query.get("id")
        message_id = message.get("message_id", 0)
        data = callback_query.get("data")
        if chat_id is None or user_id is None or callback_query_id is None or data is None:
            return

        self._callback_handler(
            IncomingCallback(
                user_id=user_id,
                chat_id=chat_id,
                callback_query_id=callback_query_id,
                message_id=message_id,
                data=data,
            )
        )
