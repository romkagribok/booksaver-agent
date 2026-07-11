from __future__ import annotations

import json
import ssl
import urllib.request
from collections.abc import Callable
from typing import Any

TelegramTransport = Callable[[str, bytes, float], bytes]


def _ssl_context() -> ssl.SSLContext:
    """Prefer certifi's CA bundle — macOS python.org builds often lack system roots."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _default_transport(url: str, data: bytes, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
        return response.read()  # type: ignore[no-any-return]


class TelegramApiError(RuntimeError):
    """Raised when the Telegram Bot API responds with ``ok: false``."""


class TelegramBotClient:
    """Thin stdlib-urllib wrapper around the Telegram Bot API (extends ADR-011).

    A ``transport`` may be injected so tests never touch the network.
    """

    def __init__(
        self,
        bot_token: str,
        timeout: float = 10.0,
        transport: TelegramTransport | None = None,
    ) -> None:
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._timeout = timeout
        self._transport = transport or _default_transport

    def _call(
        self, method: str, params: dict[str, Any], timeout: float | None = None
    ) -> Any:
        body = {k: v for k, v in params.items() if v is not None}
        payload = json.dumps(body).encode("utf-8")
        raw = self._transport(f"{self._base_url}/{method}", payload, timeout or self._timeout)
        reply: dict[str, Any] = json.loads(raw.decode("utf-8"))
        if not reply.get("ok"):
            raise TelegramApiError(f"Telegram API rejected {method}: {reply}")
        return reply.get("result")

    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        result = self._call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": ["message", "callback_query"],
            },
            timeout=timeout + 10,
        )
        return list(result) if result else []

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self._call(
            "sendMessage",
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup},
        )
        return dict(result) if result else {}

    def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self._call(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": reply_markup,
            },
        )
        return dict(result) if result else {}

    def answer_callback_query(
        self, callback_query_id: str, text: str | None = None
    ) -> dict[str, Any]:
        result = self._call(
            "answerCallbackQuery",
            {"callback_query_id": callback_query_id, "text": text},
        )
        return dict(result) if result else {}

    def delete_message(self, chat_id: int | str, message_id: int) -> dict[str, Any]:
        result = self._call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        return dict(result) if result else {}
