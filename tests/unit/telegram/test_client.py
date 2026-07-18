from __future__ import annotations

import json

import pytest

from booksaver.infrastructure.telegram.client import TelegramApiError, TelegramBotClient


class FakeTransport:
    """Records calls and returns a canned Telegram API response — no network."""

    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
        self.calls.append((url, json.loads(data.decode("utf-8"))))
        return json.dumps(self.response).encode("utf-8")


def test_get_updates_returns_result_list() -> None:
    transport = FakeTransport({"ok": True, "result": [{"update_id": 1}, {"update_id": 2}]})
    client = TelegramBotClient("token", transport=transport)

    updates = client.get_updates(offset=5, timeout=30)

    assert [u["update_id"] for u in updates] == [1, 2]
    url, body = transport.calls[0]
    assert url.endswith("/getUpdates")
    assert body["offset"] == 5
    assert body["timeout"] == 30


def test_get_updates_empty_result_returns_empty_list() -> None:
    transport = FakeTransport({"ok": True, "result": []})
    client = TelegramBotClient("token", transport=transport)
    assert client.get_updates(offset=None, timeout=30) == []


def test_get_updates_omits_none_offset_from_payload() -> None:
    transport = FakeTransport({"ok": True, "result": []})
    client = TelegramBotClient("token", transport=transport)
    client.get_updates(offset=None, timeout=30)
    _, body = transport.calls[0]
    assert "offset" not in body


def test_send_message_posts_chat_id_and_text() -> None:
    transport = FakeTransport({"ok": True, "result": {"message_id": 42}})
    client = TelegramBotClient("token", transport=transport)

    result = client.send_message(123, "hello")

    assert result == {"message_id": 42}
    _, body = transport.calls[0]
    assert body == {"chat_id": 123, "text": "hello"}


def test_send_message_includes_reply_markup_when_given() -> None:
    transport = FakeTransport({"ok": True, "result": {}})
    client = TelegramBotClient("token", transport=transport)
    markup = {"inline_keyboard": [[{"text": "Yes", "callback_data": "yes"}]]}

    client.send_message(123, "confirm?", reply_markup=markup)

    _, body = transport.calls[0]
    assert body["reply_markup"] == markup


def test_edit_message_text_calls_correct_method() -> None:
    transport = FakeTransport({"ok": True, "result": {}})
    client = TelegramBotClient("token", transport=transport)
    client.edit_message_text(123, 99, "updated")
    url, body = transport.calls[0]
    assert url.endswith("/editMessageText")
    assert body["message_id"] == 99


def test_answer_callback_query_calls_correct_method() -> None:
    transport = FakeTransport({"ok": True, "result": True})
    client = TelegramBotClient("token", transport=transport)
    result = client.answer_callback_query("cb-1", text="ok")
    assert result is True
    url, body = transport.calls[0]
    assert url.endswith("/answerCallbackQuery")
    assert body["callback_query_id"] == "cb-1"


def test_delete_message_calls_correct_method() -> None:
    transport = FakeTransport({"ok": True, "result": True})
    client = TelegramBotClient("token", transport=transport)
    result = client.delete_message(123, 7)
    assert result is True
    url, body = transport.calls[0]
    assert url.endswith("/deleteMessage")
    assert body["message_id"] == 7


def test_set_my_commands_posts_commands_and_scope() -> None:
    transport = FakeTransport({"ok": True, "result": True})
    client = TelegramBotClient("token", transport=transport)
    commands = [{"command": "checks", "description": "Choose a booking"}]
    scope = {"type": "chat", "chat_id": 123}

    assert client.set_my_commands(commands, scope) is True

    url, body = transport.calls[0]
    assert url.endswith("/setMyCommands")
    assert body == {"commands": commands, "scope": scope}


def test_rejected_reply_raises_telegram_api_error() -> None:
    transport = FakeTransport({"ok": False, "description": "Unauthorized"})
    client = TelegramBotClient("token", transport=transport)

    with pytest.raises(TelegramApiError, match="Unauthorized"):
        client.send_message(1, "hi")
