from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from booksaver.domain.remote_auth import AttemptLaunch
from booksaver.domain.user import UserRole
from booksaver.domain.value_objects import TelegramBotSettings
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository
from booksaver.infrastructure.telegram.connect_command import (
    ReconnectNotifier,
    register_connect_command,
)
from booksaver.infrastructure.telegram.router import (
    CallbackRouter,
    CommandRouter,
    IncomingCallback,
    IncomingCommand,
)


class StubManager:
    enabled = True

    def __init__(self) -> None:
        self.created: list[tuple[int, int]] = []

    def create(self, user_id: int, chat_id: int) -> AttemptLaunch:
        self.created.append((user_id, chat_id))
        return AttemptLaunch(
            "https://connect.example.test/connect/one-time-token",
            datetime.now(UTC) + timedelta(minutes=10),
        )


class FakeClient:
    def __init__(self) -> None:
        self.answers: list[str] = []
        self.edits: list[tuple[int, int, str, dict[str, Any] | None]] = []
        self.sent: list[tuple[int, str, dict[str, Any] | None]] = []

    def answer_callback_query(self, callback_id: str) -> None:
        self.answers.append(callback_id)

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        self.edits.append((chat_id, message_id, text, reply_markup))

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        self.sent.append((chat_id, text, reply_markup))


def _register(
    manager: StubManager | None,
    invitee_disclosure: Any = None,
    acknowledge_disclosure: Any = None,
) -> tuple[CommandRouter, CallbackRouter, FakeClient, list[tuple[int, str, object]]]:
    router = CommandRouter()
    callbacks = CallbackRouter()
    client = FakeClient()
    sent: list[tuple[int, str, object]] = []
    register_connect_command(
        router=router,
        callback_router=callbacks,
        reply=lambda chat_id, text: sent.append((chat_id, text, None)),
        send=lambda chat_id, text, markup: sent.append((chat_id, text, markup)),
        client=client,  # type: ignore[arg-type]
        manager=manager,  # type: ignore[arg-type]
        invitee_disclosure=invitee_disclosure,
        acknowledge_disclosure=acknowledge_disclosure,
    )
    return router, callbacks, client, sent


def test_connect_uses_telegram_web_app_button_without_chat_credentials() -> None:
    manager = StubManager()
    router, _callbacks, _client, sent = _register(manager)

    router.dispatch(IncomingCommand(123, 123, "/connect", "", "/connect"))

    assert manager.created == [(123, 123)]
    text = sent[0][1]
    assert "Booking.com email and password" in text
    assert "Google, Apple, or another external provider is disabled" in text
    assert "never asks for your password in Telegram chat" in text
    assert "password=" not in text
    markup = sent[0][2]
    assert isinstance(markup, dict)
    button = markup["inline_keyboard"][0][0]
    assert button == {
        "text": "Open secure Booking.com login",
        "web_app": {"url": "https://connect.example.test/connect/one-time-token"},
    }


def test_connect_shows_versioned_agentic_disclosure_when_caller_is_invited() -> None:
    manager = StubManager()
    disclosure = (
        "Privacy disclosure (anthropic-visible-booking-page-v1): the deployment "
        "owner's Anthropic account may process visible page content and screenshots."
    )
    router, _callbacks, _client, sent = _register(
        manager,
        invitee_disclosure=lambda _user_id: disclosure,
    )

    router.dispatch(IncomingCommand(123, 123, "/connect", "", "/connect"))

    assert disclosure in sent[0][1]
    assert manager.created == []
    assert sent[0][2] == {
        "inline_keyboard": [
            [
                {
                    "text": "I understand and continue",
                    "callback_data": "connect:consent",
                }
            ]
        ]
    }


def test_invitee_consent_is_recorded_before_secure_login_launch() -> None:
    manager = StubManager()
    pending = {123: True}
    acknowledgements: list[int] = []

    def disclosure(user_id: int) -> str | None:
        return "versioned disclosure" if pending.get(user_id) else None

    def acknowledge(user_id: int) -> None:
        acknowledgements.append(user_id)
        pending[user_id] = False

    _router, callbacks, client, _sent = _register(
        manager,
        invitee_disclosure=disclosure,
        acknowledge_disclosure=acknowledge,
    )

    callbacks.dispatch(IncomingCallback(123, 123, "consent-1", 8, "connect:consent"))

    assert acknowledgements == [123]
    assert manager.created == [(123, 123)]
    assert client.answers == ["consent-1"]
    assert "Open the secure login" in client.edits[0][2]


def test_reconnect_callback_is_acknowledged_and_replaces_prompt() -> None:
    manager = StubManager()
    _router, callbacks, client, _sent = _register(manager)

    callbacks.dispatch(IncomingCallback(123, 123, "callback-1", 8, "connect:start"))

    assert manager.created == [(123, 123)]
    assert client.answers == ["callback-1"]
    assert client.edits[0][:3] == (
        123,
        8,
        "Open the secure login below and sign in with your Booking.com email and password. "
        "Signing in with Google, Apple, or another external provider is disabled. "
        "The link expires shortly; BookSaver never asks for your password in Telegram chat.",
    )


def test_connect_explains_when_operator_has_not_enabled_gateway() -> None:
    router, _callbacks, _client, sent = _register(None)
    router.dispatch(IncomingCommand(123, 123, "/connect", "", "/connect"))
    assert sent == [
        (
            123,
            "Secure Booking.com connection is not configured on this BookSaver server yet.",
            None,
        )
    ]


def test_reconnect_notifier_scopes_delivery_and_applies_cooldown(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(
            222,
            UserRole.USER,
        )
    client = FakeClient()
    notifier = ReconnectNotifier(
        db_path,
        client,  # type: ignore[arg-type]
        TelegramBotSettings(enabled=True, owner_chat_id=111, access_mode="invite"),
    )

    notifier.notify(user.user_id)
    notifier.notify(user.user_id)

    assert len(client.sent) == 1
    chat_id, text, markup = client.sent[0]
    assert chat_id == 222
    assert "missing or expired" in text
    assert markup == {
        "inline_keyboard": [[{"text": "Reconnect Booking.com", "callback_data": "connect:start"}]]
    }
