from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingCommand:
    """A parsed Telegram message, resolved to a sender/chat identity (US-024)."""

    user_id: int
    chat_id: int
    command: str
    args: str
    raw_text: str
    # Telegram message_id of the incoming message (US-027: needed to delete a
    # chat message containing a pasted API key). Defaults to 0 so existing
    # test/call sites that don't care about it keep working unchanged.
    message_id: int = 0


CommandHandler = Callable[[IncomingCommand], None]


@dataclass(frozen=True)
class IncomingCallback:
    """A parsed Telegram ``callback_query`` update (bolt 011, US-032) — the
    inline-keyboard equivalent of ``IncomingCommand``. Routed straight to a
    single injected handler (``BotLoop(callback_handler=...)``) rather than
    through ``CommandRouter``, since only one feature (rebook confirmations)
    consumes callback queries today; a second consumer can register its own
    ``data`` prefix inside that handler without changing this shape.
    """

    user_id: int
    chat_id: int
    callback_query_id: str
    message_id: int
    data: str


class CommandRouter:
    """Registry API so later bolts can register their own commands/dialogs
    (units 2-4 plug into this router without gateway changes)."""

    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, command: str, handler: CommandHandler) -> None:
        self._handlers[command] = handler

    def dispatch(self, command: IncomingCommand) -> bool:
        """Invoke the handler for `command.command`. Returns False for unknown commands."""
        handler = self._handlers.get(command.command)
        if handler is None:
            return False
        handler(command)
        return True

    def known_commands(self) -> list[str]:
        return sorted(self._handlers)
