from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from booksaver.application.remote_auth import (
    RemoteAuthBusy,
    RemoteAuthenticationManager,
    RemoteAuthUnavailable,
)
from booksaver.domain.value_objects import TelegramBotSettings
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository

from .client import TelegramBotClient
from .router import CallbackRouter, CommandRouter, IncomingCallback, IncomingCommand

logger = logging.getLogger(__name__)

Reply = Callable[[int, str], None]
Send = Callable[[int, str, dict[str, Any] | None], None]


def _launch_message(
    manager: RemoteAuthenticationManager,
    telegram_user_id: int,
    chat_id: int,
) -> tuple[str, dict[str, Any] | None]:
    try:
        launch = manager.create(telegram_user_id, chat_id)
    except (RemoteAuthBusy, RemoteAuthUnavailable) as exc:
        return str(exc), None
    return (
        "Open the secure login below and complete Booking.com sign-in. "
        "The link expires shortly; BookSaver never asks for your password in chat.",
        {
            "inline_keyboard": [
                [
                    {
                        "text": "Open secure Booking.com login",
                        "web_app": {"url": launch.url},
                    }
                ]
            ]
        },
    )


def register_connect_command(
    *,
    router: CommandRouter,
    callback_router: CallbackRouter,
    reply: Reply,
    send: Send,
    client: TelegramBotClient,
    manager: RemoteAuthenticationManager | None,
) -> None:
    def _command(cmd: IncomingCommand) -> None:
        if manager is None or not manager.enabled:
            reply(
                cmd.chat_id,
                "Secure Booking.com connection is not configured on this BookSaver server yet.",
            )
            return
        text, markup = _launch_message(manager, cmd.user_id, cmd.chat_id)
        send(cmd.chat_id, text, markup)

    def _callback(callback: IncomingCallback) -> None:
        if manager is None or not manager.enabled:
            text = "Secure Booking.com connection is not configured yet."
            markup = None
        else:
            text, markup = _launch_message(manager, callback.user_id, callback.chat_id)
        try:
            client.answer_callback_query(callback.callback_query_id)
        except Exception:
            logger.warning("Could not answer connect callback")
        try:
            client.edit_message_text(
                callback.chat_id, callback.message_id, text, reply_markup=markup
            )
        except Exception:
            logger.warning("Could not update reconnect message")

    router.register("/connect", _command)
    callback_router.register("connect:start", _callback)


class ReconnectNotifier:
    """Best-effort, per-user cooldown for scheduled auth-required prompts."""

    def __init__(
        self,
        db_path: Path,
        client: TelegramBotClient,
        bot_settings: TelegramBotSettings,
        cooldown_seconds: int = 86_400,
    ) -> None:
        self._db_path = db_path
        self._client = client
        self._bot_settings = bot_settings
        self._cooldown = cooldown_seconds
        self._sent_at: dict[int, float] = {}
        self._lock = threading.Lock()

    def notify(self, local_user_id: int) -> None:
        now = time.monotonic()
        with self._lock:
            last = self._sent_at.get(local_user_id)
            if last is not None and now - last < self._cooldown:
                return
            self._sent_at[local_user_id] = now
        try:
            with SqliteStore(self._db_path) as store:
                user = SqliteUserRepository(store).get_by_id(local_user_id)
            if user is None or not user.is_active or user.telegram_user_id is None:
                self.clear(local_user_id)
                return
            chat_id = (
                self._bot_settings.owner_chat_id
                if user.is_owner
                else user.telegram_user_id
            )
            if chat_id is None:
                self.clear(local_user_id)
                return
            self._client.send_message(
                chat_id,
                "Your Booking.com connection is missing or expired. Reconnect to resume "
                "authenticated mobile-web price checks.",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "Reconnect Booking.com", "callback_data": "connect:start"}]
                    ]
                },
            )
        except Exception:
            with self._lock:
                self._sent_at.pop(local_user_id, None)
            logger.warning("Could not send reconnect notice for user %s", local_user_id)

    def clear(self, local_user_id: int) -> None:
        with self._lock:
            self._sent_at.pop(local_user_id, None)
