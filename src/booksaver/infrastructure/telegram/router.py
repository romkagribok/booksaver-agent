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
    """Parsed Telegram ``callback_query`` update with sender/chat identity."""

    user_id: int
    chat_id: int
    callback_query_id: str
    message_id: int
    data: str


CallbackHandler = Callable[[IncomingCallback], None]


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


class CallbackRouter:
    """Prefix router for independent inline-keyboard feature families."""

    def __init__(self) -> None:
        self._handlers: dict[str, CallbackHandler] = {}

    def register(self, prefix: str, handler: CallbackHandler) -> None:
        if not prefix:
            raise ValueError("Callback prefix must not be empty")
        if prefix in self._handlers:
            raise ValueError(f"Callback prefix already registered: {prefix}")
        self._handlers[prefix] = handler

    def dispatch(self, callback: IncomingCallback) -> bool:
        matches = [prefix for prefix in self._handlers if callback.data.startswith(prefix)]
        if not matches:
            return False
        prefix = max(matches, key=len)
        self._handlers[prefix](callback)
        return True

    def known_prefixes(self) -> list[str]:
        return sorted(self._handlers)
