from __future__ import annotations

import pytest

from booksaver.infrastructure.telegram.router import (
    CallbackRouter,
    CommandRouter,
    IncomingCallback,
    IncomingCommand,
)


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


def _callback(data: str) -> IncomingCallback:
    return IncomingCallback(
        user_id=1,
        chat_id=1,
        callback_query_id="cb-1",
        message_id=10,
        data=data,
    )


def test_callback_router_dispatches_matching_prefix_once() -> None:
    router = CallbackRouter()
    seen: list[str] = []
    router.register("checks:", lambda callback: seen.append(callback.data))
    router.register("admin:", lambda callback: seen.append("wrong"))

    assert router.dispatch(_callback("checks:booking-1")) is True
    assert seen == ["checks:booking-1"]


def test_callback_router_prefers_most_specific_prefix() -> None:
    router = CallbackRouter()
    seen: list[str] = []
    router.register("admin:", lambda callback: seen.append("broad"))
    router.register("admin:mode:", lambda callback: seen.append("specific"))

    router.dispatch(_callback("admin:mode:invite"))

    assert seen == ["specific"]


def test_callback_router_reports_unknown_callback() -> None:
    assert CallbackRouter().dispatch(_callback("stale:anything")) is False


def test_callback_router_rejects_duplicate_or_empty_prefix() -> None:
    router = CallbackRouter()
    router.register("checks:", lambda callback: None)
    with pytest.raises(ValueError, match="already registered"):
        router.register("checks:", lambda callback: None)
    with pytest.raises(ValueError, match="must not be empty"):
        router.register("", lambda callback: None)
