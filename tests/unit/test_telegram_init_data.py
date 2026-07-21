from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from booksaver.infrastructure.remote_auth.telegram_init_data import (
    TelegramInitDataError,
    TelegramInitDataVerifier,
)

BOT_TOKEN = "123456:telegram-test-token"


def _signed(user_id: int, auth_date: datetime) -> str:
    values = {
        "auth_date": str(int(auth_date.timestamp())),
        "query_id": "AAE-test",
        "user": json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(
        secret, check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(values)


def test_verifies_fresh_signed_identity() -> None:
    now = datetime(2026, 7, 20, 2, 0, tzinfo=UTC)
    identity = TelegramInitDataVerifier(BOT_TOKEN).verify(_signed(42, now), 42, now)
    assert identity.telegram_user_id == 42
    assert identity.authenticated_at == now


def test_rejects_replay_of_valid_signed_identity() -> None:
    now = datetime(2026, 7, 20, 2, 0, tzinfo=UTC)
    raw = _signed(42, now)
    verifier = TelegramInitDataVerifier(BOT_TOKEN)
    verifier.verify(raw, 42, now)
    with pytest.raises(TelegramInitDataError, match="already used"):
        verifier.verify(raw, 42, now)


@pytest.mark.parametrize("mutation", ["hash", "user", "duplicate"])
def test_rejects_tampering_or_duplicate_fields(mutation: str) -> None:
    now = datetime(2026, 7, 20, 2, 0, tzinfo=UTC)
    raw = _signed(42, now)
    if mutation == "hash":
        raw = raw[:-1] + ("0" if raw[-1] != "0" else "1")
    elif mutation == "user":
        raw = raw.replace("first_name", "last_name")
    else:
        raw += "&auth_date=1"
    with pytest.raises(TelegramInitDataError):
        TelegramInitDataVerifier(BOT_TOKEN).verify(raw, 42, now)


def test_rejects_stale_future_and_cross_user_data() -> None:
    now = datetime(2026, 7, 20, 2, 0, tzinfo=UTC)
    verifier = TelegramInitDataVerifier(BOT_TOKEN, max_age_seconds=300)
    with pytest.raises(TelegramInitDataError, match="stale"):
        verifier.verify(_signed(42, now - timedelta(seconds=301)), 42, now)
    with pytest.raises(TelegramInitDataError, match="stale"):
        verifier.verify(_signed(42, now + timedelta(seconds=31)), 42, now)
    with pytest.raises(TelegramInitDataError, match="does not match"):
        verifier.verify(_signed(42, now), 99, now)
