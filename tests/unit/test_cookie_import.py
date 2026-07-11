from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from booksaver.domain.session import SessionStatus
from booksaver.domain.value_objects import Platform
from booksaver.infrastructure.persistence.cookie_import import (
    CookieImportError,
    import_cookies,
)

NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)


def _future_epoch(days: int = 30) -> float:
    return (NOW + timedelta(days=days)).timestamp()


def _past_epoch(days: int = 1) -> float:
    return (NOW - timedelta(days=days)).timestamp()


# ── happy path: both accepted shapes ──────────────────────────────────────────


def test_import_playwright_native_shape() -> None:
    raw = json.dumps(
        [
            {
                "name": "bkng_sso",
                "value": "secretvalue",
                "domain": ".booking.com",
                "path": "/",
                "expires": _future_epoch(),
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }
        ]
    )

    session, summary = import_cookies(raw, now=NOW)

    assert session.platform is Platform.BOOKING_COM
    assert session.status is SessionStatus.ACTIVE
    assert summary.count == 1
    assert summary.domains == ("booking.com",)
    assert summary.earliest_expiry is not None
    cookies = json.loads(session.cookies.decode("utf-8"))
    assert cookies[0]["sameSite"] == "Lax"
    assert cookies[0]["expires"] == pytest.approx(_future_epoch())


def test_import_browser_extension_export_shape() -> None:
    """Cookie-Editor / EditThisCookie style export: expirationDate, sameSite
    as a lowercase Chrome-flavored string."""
    raw = json.dumps(
        [
            {
                "name": "bkng",
                "value": "abc123",
                "domain": "www.booking.com",
                "path": "/",
                "expirationDate": _future_epoch(60),
                "httpOnly": False,
                "secure": True,
                "sameSite": "no_restriction",
            },
            {
                "name": "other_site",
                "value": "xyz",
                "domain": "example.com",
                "path": "/",
                "expirationDate": _future_epoch(60),
            },
        ]
    )

    session, summary = import_cookies(raw, now=NOW)

    assert summary.count == 1  # only the booking.com cookie is kept
    assert summary.domains == ("www.booking.com",)
    cookies = json.loads(session.cookies.decode("utf-8"))
    assert len(cookies) == 1
    assert cookies[0]["sameSite"] == "None"
    assert cookies[0]["name"] == "bkng"


def test_wrapped_in_cookies_key_is_unwrapped() -> None:
    raw = json.dumps(
        {"cookies": [{"name": "a", "value": "b", "domain": "booking.com", "expires": -1}]}
    )
    session, summary = import_cookies(raw, now=NOW)
    assert summary.count == 1


def test_session_cookie_without_expiry_is_accepted_and_not_flagged_expired() -> None:
    raw = json.dumps(
        [{"name": "sess", "value": "v", "domain": ".booking.com", "path": "/"}]
    )
    session, summary = import_cookies(raw, now=NOW)
    assert summary.earliest_expiry is None
    assert session.expires_at is None
    assert session.is_expired(NOW) is False


# ── sameSite / expires normalization ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw_same_site", "expected"),
    [
        ("Strict", "Strict"),
        ("Lax", "Lax"),
        ("None", "None"),
        ("strict", "Strict"),
        ("lax", "Lax"),
        ("no_restriction", "None"),
        ("unspecified", "Lax"),
        (None, "Lax"),
        ("garbage", "Lax"),
    ],
)
def test_same_site_normalization(raw_same_site: str | None, expected: str) -> None:
    cookie: dict = {
        "name": "a",
        "value": "b",
        "domain": "booking.com",
        "expires": _future_epoch(),
    }
    if raw_same_site is not None:
        cookie["sameSite"] = raw_same_site
    session, _ = import_cookies(json.dumps([cookie]), now=NOW)
    normalized = json.loads(session.cookies.decode("utf-8"))[0]
    assert normalized["sameSite"] == expected


def test_expires_normalized_to_float_seconds() -> None:
    epoch = _future_epoch()
    session, _ = import_cookies(
        json.dumps(
            [{"name": "a", "value": "b", "domain": "booking.com", "expirationDate": epoch}]
        ),
        now=NOW,
    )
    normalized = json.loads(session.cookies.decode("utf-8"))[0]
    assert isinstance(normalized["expires"], float)
    assert normalized["expires"] == pytest.approx(epoch)


# ── rejections ─────────────────────────────────────────────────────────────────


def test_rejects_malformed_json() -> None:
    with pytest.raises(CookieImportError, match="not valid JSON"):
        import_cookies("{not json", now=NOW)


def test_rejects_non_array_non_wrapped_json() -> None:
    with pytest.raises(CookieImportError, match="expected a JSON array"):
        import_cookies(json.dumps({"foo": "bar"}), now=NOW)


def test_rejects_no_booking_domain_cookies() -> None:
    raw = json.dumps(
        [{"name": "a", "value": "b", "domain": "example.com", "expires": _future_epoch()}]
    )
    with pytest.raises(CookieImportError, match="no cookies for a booking.com domain"):
        import_cookies(raw, now=NOW)


def test_rejects_all_expired_cookies() -> None:
    raw = json.dumps(
        [
            {"name": "a", "value": "b", "domain": ".booking.com", "expires": _past_epoch()},
            {"name": "c", "value": "d", "domain": "booking.com", "expires": _past_epoch(2)},
        ]
    )
    with pytest.raises(CookieImportError, match="already expired"):
        import_cookies(raw, now=NOW)


def test_partial_expiry_is_accepted_when_at_least_one_cookie_is_valid() -> None:
    raw = json.dumps(
        [
            {"name": "stale", "value": "x", "domain": "booking.com", "expires": _past_epoch()},
            {"name": "fresh", "value": "y", "domain": "booking.com", "expires": _future_epoch()},
        ]
    )
    session, summary = import_cookies(raw, now=NOW)
    assert summary.count == 2  # both are stored; only the earliest expiry drives session expiry
    assert session.expires_at == datetime.fromtimestamp(_past_epoch(), tz=UTC)


def test_rejects_empty_array() -> None:
    with pytest.raises(CookieImportError, match="no usable cookie"):
        import_cookies("[]", now=NOW)


def test_rejects_cookies_missing_required_fields() -> None:
    raw = json.dumps([{"name": "a"}, {"value": "b", "domain": "booking.com"}])
    with pytest.raises(CookieImportError, match="no usable cookie"):
        import_cookies(raw, now=NOW)


# ── never leaks cookie values ─────────────────────────────────────────────────


def test_error_messages_never_include_cookie_values() -> None:
    raw = json.dumps(
        [{"name": "a", "value": "TOP-SECRET-VALUE", "domain": "example.com"}]
    )
    with pytest.raises(CookieImportError) as excinfo:
        import_cookies(raw, now=NOW)
    assert "TOP-SECRET-VALUE" not in str(excinfo.value)
