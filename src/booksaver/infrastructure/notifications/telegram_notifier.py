from __future__ import annotations

import json
import ssl
import urllib.request


def _ssl_context() -> ssl.SSLContext:
    """Prefer certifi's CA bundle — macOS python.org builds often lack system roots."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class TelegramNotifier:
    """Notifier adapter posting to the Telegram Bot API via stdlib urllib (ADR-011)."""

    def __init__(self, bot_token: str, chat_id: str, timeout: float = 10.0) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout

    @property
    def channel_name(self) -> str:
        return "telegram"

    def send(self, subject: str, body: str) -> None:
        payload = json.dumps({"chat_id": self._chat_id, "text": f"{subject}\n\n{body}"})
        request = urllib.request.Request(
            self._url,
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(
            request, timeout=self._timeout, context=_ssl_context()
        ) as response:
            reply = json.loads(response.read().decode("utf-8"))
        if not reply.get("ok"):
            raise RuntimeError(f"Telegram API rejected the message: {reply}")
