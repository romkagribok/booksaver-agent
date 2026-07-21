from __future__ import annotations

import hashlib
import hmac
import json
import threading
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

from booksaver.domain.remote_auth import TelegramMiniAppIdentity


class TelegramInitDataError(ValueError):
    """Raised without echoing the signed payload or bot token."""


class TelegramInitDataVerifier:
    def __init__(self, bot_token: str, max_age_seconds: int = 300) -> None:
        if not bot_token:
            raise ValueError("bot_token must be non-empty")
        if max_age_seconds < 1:
            raise ValueError("max_age_seconds must be positive")
        self._bot_token = bot_token.encode("utf-8")
        self._max_age = timedelta(seconds=max_age_seconds)
        self._seen: dict[bytes, datetime] = {}
        self._lock = threading.Lock()

    def verify(
        self,
        raw: str,
        expected_user_id: int,
        now: datetime | None = None,
    ) -> TelegramMiniAppIdentity:
        now = now or datetime.now(UTC)
        try:
            pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        except ValueError as exc:
            raise TelegramInitDataError("Invalid Telegram authorization data") from exc
        if not pairs or len({key for key, _ in pairs}) != len(pairs):
            raise TelegramInitDataError("Invalid Telegram authorization data")
        values = dict(pairs)
        supplied_hash = values.pop("hash", None)
        if supplied_hash is None or len(supplied_hash) != 64:
            raise TelegramInitDataError("Invalid Telegram authorization data")
        check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        secret = hmac.new(b"WebAppData", self._bot_token, hashlib.sha256).digest()
        expected_hash = hmac.new(
            secret, check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(supplied_hash.lower(), expected_hash):
            raise TelegramInitDataError("Invalid Telegram authorization data")
        try:
            authenticated_at = datetime.fromtimestamp(int(values["auth_date"]), tz=UTC)
            user = json.loads(values["user"])
            telegram_user_id = int(user["id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, OverflowError) as exc:
            raise TelegramInitDataError("Invalid Telegram authorization data") from exc
        age = now - authenticated_at
        if age < timedelta(seconds=-30) or age > self._max_age:
            raise TelegramInitDataError("Telegram authorization data is stale")
        if telegram_user_id != expected_user_id:
            raise TelegramInitDataError("Telegram user does not match this connection")
        replay_key = hashlib.sha256(raw.encode("utf-8")).digest()
        with self._lock:
            self._seen = {
                key: expires_at
                for key, expires_at in self._seen.items()
                if expires_at >= now
            }
            if replay_key in self._seen:
                raise TelegramInitDataError("Telegram authorization data was already used")
            self._seen[replay_key] = authenticated_at + self._max_age
        return TelegramMiniAppIdentity(telegram_user_id, authenticated_at)
