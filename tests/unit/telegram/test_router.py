from __future__ import annotations

from booksaver.infrastructure.telegram.router import CommandRouter, IncomingCommand


def _cmd(command: str = "/status", args: str = "") -> IncomingCommand:
    return IncomingCommand(
        user_id=1, chat_id=1, command=command, args=args, raw_text=f"{command} {args}".strip()
    )


def test_dispatch_invokes_registered_handler() -> None:
    router = CommandRouter()
    calls: list[IncomingCommand] = []
    router.register("/status", calls.append)

    handled = router.dispatch(_cmd("/status"))

    assert handled is True
    assert len(calls) == 1
    assert calls[0].command == "/status"


def test_dispatch_returns_false_for_unknown_command() -> None:
    router = CommandRouter()
    router.register("/status", lambda cmd: None)

    handled = router.dispatch(_cmd("/nope"))

    assert handled is False


def test_register_overwrites_existing_handler_for_same_command() -> None:
    router = CommandRouter()
    calls: list[str] = []
    router.register("/status", lambda cmd: calls.append("first"))
    router.register("/status", lambda cmd: calls.append("second"))

    router.dispatch(_cmd("/status"))

    assert calls == ["second"]


def test_known_commands_lists_registered_commands_sorted() -> None:
    router = CommandRouter()
    router.register("/savings", lambda cmd: None)
    router.register("/bookings", lambda cmd: None)

    assert router.known_commands() == ["/bookings", "/savings"]
