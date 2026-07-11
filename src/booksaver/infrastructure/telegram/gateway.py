from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path

from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.models import Config

from .access import OwnerGuard, RateLimiter
from .bot_loop import BotLoop
from .client import TelegramBotClient
from .commands_readonly import register_readonly_commands
from .dialogs import DialogManager
from .offset_store import TelegramOffsetStore
from .router import CommandRouter, IncomingCommand

logger = logging.getLogger(__name__)

BotRunner = Callable[[threading.Event], None]


def build_bot_runner(
    config: Config,
    db_path: Path,
    scheduler: Scheduler,
    client: TelegramBotClient | None = None,
) -> BotRunner | None:
    """Wires client + router + dialogs + owner guard into a runnable bot loop.

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
    dialog_manager = DialogManager()
    owner_guard = OwnerGuard(
        owner_chat_id=settings.owner_chat_id,
        refusal_limiter=RateLimiter(max_events=1, window_seconds=3600.0),
    )
    offset_store = TelegramOffsetStore(config.data_directory)

    def _reply(chat_id: int, text: str) -> None:
        client.send_message(chat_id, text)

    register_readonly_commands(
        router=router,
        reply=_reply,
        db_path=db_path,
        scheduler=scheduler,
    )

    def _cancelflow(cmd: IncomingCommand) -> None:
        if dialog_manager.cancel(cmd.chat_id):
            _reply(cmd.chat_id, "Cancelled the current dialog.")
        else:
            _reply(cmd.chat_id, "No active dialog to cancel.")

    router.register("/cancelflow", _cancelflow)

    def _dialog_handler(cmd: IncomingCommand) -> bool:
        if not dialog_manager.has_active(cmd.chat_id):
            return False
        reply_text = dialog_manager.handle_message(cmd.chat_id, cmd.user_id, cmd.raw_text)
        _reply(cmd.chat_id, reply_text)
        return True

    def _access_guard(chat_id: int) -> bool:
        return owner_guard.is_owner(chat_id)

    def _on_refused(chat_id: int) -> None:
        if owner_guard.should_send_refusal(chat_id):
            _reply(chat_id, "This bot is private and only available to its owner.")

    loop = BotLoop(
        client=client,
        router=router,
        offset_store=offset_store,
        poll_timeout_seconds=settings.poll_timeout_seconds,
        access_guard=_access_guard,
        on_refused=_on_refused,
        dialog_handler=_dialog_handler,
    )

    return loop.run
