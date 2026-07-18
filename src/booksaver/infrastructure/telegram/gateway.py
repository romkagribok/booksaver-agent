from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.models import Config

from .access import AccessControl, RateLimiter
from .admin_commands import register_admin_commands
from .booking_management import register_booking_management_commands
from .bot_loop import BotLoop
from .client import TelegramBotClient
from .command_catalog import api_commands
from .commands_readonly import register_readonly_commands
from .dialogs import DialogManager
from .key_dialogs import KeyIntakeFlow, handle_deletekey
from .key_validator import AnthropicKeyValidator
from .offset_store import TelegramOffsetStore
from .rebook_gate import register_rebook_command  # US-032/US-033 (bolt 011)
from .register_dialog import register_booking_dialog  # US-025 (bolt 010)
from .router import CallbackRouter, CommandRouter, IncomingCallback, IncomingCommand

logger = logging.getLogger(__name__)

BotRunner = Callable[[threading.Event], None]


def build_bot_runner(
    config: Config,
    db_path: Path,
    scheduler: Scheduler,
    client: TelegramBotClient | None = None,
) -> BotRunner | None:
    """Wires client + router + dialogs + access control into a runnable bot loop.

    Returns None (and logs why) when the bot is disabled or misconfigured, so
    `cmd_run`/`lifecycle.start` can skip the thread entirely — laptop mode with
    `[telegram_bot]` absent is unaffected (US-023).

    `client` may be injected (tests use this to supply a fake-transport
    `TelegramBotClient` — no network); production callers omit it and get one
    built from `BOOKSAVER_TELEGRAM_BOT_TOKEN`.
    """
    settings = config.telegram_bot_settings
    if not settings.enabled:
        return None

    token = os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN")
    if client is None and not token:
        logger.warning(
            "telegram_bot.enabled=true but BOOKSAVER_TELEGRAM_BOT_TOKEN is not set — "
            "Telegram bot gateway disabled"
        )
        return None

    assert settings.owner_chat_id is not None  # enforced by load_config/TelegramBotSettings

    if client is None:
        assert token is not None
        client = TelegramBotClient(bot_token=token)
    router = CommandRouter()
    callback_router = CallbackRouter()
    dialog_manager = DialogManager()
    access_control = AccessControl(
        owner_chat_id=settings.owner_chat_id,
        db_path=db_path,
        mode=settings.access_mode,
        refusal_limiter=RateLimiter(max_events=1, window_seconds=3600.0),
    )
    offset_store = TelegramOffsetStore(config.data_directory)

    # ── US-031: per-chat outbound message rate limiting ────────────────────
    # Protects against reply loops / runaway dialogs driving unbounded sends.
    # A breach degrades gracefully (drop + log) rather than crashing the loop
    # or spamming the chat further.
    message_limiter = RateLimiter(
        max_events=config.limits_settings.messages_per_minute_per_chat, window_seconds=60.0
    )

    def _send(
        chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> None:
        if not message_limiter.allow(chat_id):
            logger.warning(
                "Per-chat message rate limit exceeded for chat %s; dropping reply", chat_id
            )
            return
        client.send_message(chat_id, text, reply_markup=reply_markup)

    def _reply(chat_id: int, text: str) -> None:
        _send(chat_id, text)

    # ── end US-031 rate limiting ────────────────────────────────────────────

    register_readonly_commands(
        router=router,
        reply=_reply,
        db_path=db_path,
        scheduler=scheduler,
        callback_router=callback_router,
        client=client,
        send=_send,
        is_owner=access_control.is_owner,
    )

    # ── US-026/US-027/US-028: access modes, personal-key intake, admin ────────
    key_flow = KeyIntakeFlow(
        db_path=db_path,
        validator=AnthropicKeyValidator(),
        delete_message=client.delete_message,
    )

    def _setkey(cmd: IncomingCommand) -> None:
        dialog_manager.cancel(cmd.chat_id)
        _reply(cmd.chat_id, key_flow.start(cmd.chat_id))

    def _deletekey(cmd: IncomingCommand) -> None:
        _reply(cmd.chat_id, handle_deletekey(cmd, db_path))

    router.register("/setkey", _setkey)
    router.register("/deletekey", _deletekey)

    register_admin_commands(
        router=router,
        reply=_reply,
        db_path=db_path,
        access_control=access_control,
        callback_router=callback_router,
        client=client,
        send=_send,
    )
    # ── end US-026/US-027/US-028 wiring ────────────────────────────────────────

    # US-025 (bolt 010): /register guided dialog
    register_booking_dialog(
        router=router,
        dialog_manager=dialog_manager,
        reply=_reply,
        db_path=db_path,
        limits_settings=config.limits_settings,
    )

    register_booking_management_commands(
        router=router,
        callback_router=callback_router,
        dialog_manager=dialog_manager,
        reply=_reply,
        send=_send,
        client=client,
        db_path=db_path,
    )

    def _cancelflow(cmd: IncomingCommand) -> None:
        if key_flow.cancel(cmd.chat_id):
            _reply(cmd.chat_id, "Cancelled the current dialog.")
        elif dialog_manager.cancel(cmd.chat_id):
            _reply(cmd.chat_id, "Cancelled the current dialog.")
        else:
            _reply(cmd.chat_id, "No active dialog to cancel.")

    router.register("/cancelflow", _cancelflow)

    # US-032/US-033 (bolt 011): /rebook + inline-keyboard confirmation gate +
    # device-handoff deep link. Kept in its own module (rebook_gate.py); this
    # block only wires it into the shared router/client/reply and returns the
    # callback_query handler BotLoop needs.
    rebook_callback_handler = register_rebook_command(
        router=router,
        reply=_reply,
        client=client,
        db_path=db_path,
        stop_event=scheduler.stop_event,
        confirm_timeout_seconds=settings.rebook_confirm_timeout_seconds,
        send=_send,
    )
    callback_router.register("rebook:", rebook_callback_handler)
    # ── end US-032/US-033 wiring ─────────────────────────────────────────────

    def _dialog_handler(cmd: IncomingCommand) -> bool:
        if key_flow.is_pending(cmd.chat_id):
            _reply(cmd.chat_id, key_flow.handle(cmd))
            return True
        if not dialog_manager.has_active(cmd.chat_id):
            return False
        reply_text = dialog_manager.handle_message(cmd.chat_id, cmd.user_id, cmd.raw_text)
        _reply(cmd.chat_id, reply_text)
        return True

    def _access_guard(cmd: IncomingCommand) -> bool:
        return access_control.authorize(cmd.user_id, cmd.chat_id, cmd.command, cmd.args)

    def _on_refused(cmd: IncomingCommand) -> None:
        access_control.log_refusal(cmd.user_id, cmd.command)
        if access_control.should_send_refusal(cmd.chat_id):
            _reply(cmd.chat_id, "This bot is private and only available to invited users.")

    def _callback_handler(callback: IncomingCallback) -> None:
        if not access_control.authorize(
            callback.user_id, callback.chat_id, "/callback", ""
        ):
            try:
                client.answer_callback_query(
                    callback.callback_query_id, text="This action is not available."
                )
            except Exception:
                logger.warning("Could not answer refused Telegram callback")
            return
        try:
            handled = callback_router.dispatch(callback)
        except Exception:
            logger.exception("Error handling Telegram callback family")
            try:
                client.answer_callback_query(
                    callback.callback_query_id, text="This action could not be completed."
                )
            except Exception:
                logger.warning("Could not answer failed Telegram callback")
            return
        if not handled:
            try:
                client.answer_callback_query(
                    callback.callback_query_id, text="This action has expired."
                )
            except Exception:
                logger.warning("Could not answer unknown Telegram callback")

    loop = BotLoop(
        client=client,
        router=router,
        offset_store=offset_store,
        poll_timeout_seconds=settings.poll_timeout_seconds,
        access_guard=_access_guard,
        on_refused=_on_refused,
        dialog_handler=_dialog_handler,
        callback_handler=_callback_handler,
    )

    def _sync_commands() -> None:
        publications = (
            (
                api_commands(include_owner_only=False),
                {"type": "all_private_chats"},
                "private-chat",
            ),
            (
                api_commands(include_owner_only=True),
                {"type": "chat", "chat_id": settings.owner_chat_id},
                "owner-chat",
            ),
        )
        for commands, scope, label in publications:
            try:
                client.set_my_commands(commands, scope)
            except Exception:
                logger.warning(
                    "Could not publish Telegram %s command menu; continuing", label
                )

    def _run(stop_event: threading.Event) -> None:
        _sync_commands()
        loop.run(stop_event)

    return _run
