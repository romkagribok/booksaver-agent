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


CommandHandler = Callable[[IncomingCommand], None]


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
