from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from booksaver.domain.session import SessionState
from booksaver.domain.value_objects import Platform

# US-035 (cookie-import slice): a user exports Booking.com cookies from their
# own browser and loads them via `booksaver auth import <file>`, since headed
# `booksaver auth` (interactive login) cannot run on a display-less VPS.
#
# Accepts two shapes:
#   1. Playwright's native `context.cookies()` JSON (what `booksaver auth`
#      itself already produces) — sameSite already "Strict"/"Lax"/"None",
#      expires already a float epoch-seconds (or -1 for a session cookie).
#   2. The common browser-extension export shape (Cookie-Editor, EditThisCookie,
#      and similar) — an array of objects with name/value/domain/path/
#      expirationDate|expires/secure/httpOnly[/sameSite as a string like
#      "no_restriction"/"lax"/"strict"/"unspecified"].
#
# Both are normalized to Playwright's shape before being stored, so
# `restore_cookies`/`context.add_cookies` never has to special-case the source.


class CookieImportError(ValueError):
    """Raised for anything unusable in an imported cookie export: malformed
    JSON, no cookie objects, no booking.com-domain cookie, or every
    booking.com cookie already expired. The message is written to be shown
    to the user as-is (actionable, never echoes a cookie value)."""


@dataclass(frozen=True)
class ImportSummary:
    """What was imported — safe to print. Never includes cookie values."""

    count: int
    domains: tuple[str, ...]
    earliest_expiry: datetime | None


_VALID_SAME_SITE = {"Strict", "Lax", "None"}
_SAME_SITE_ALIASES = {
    "no_restriction": "None",
    "none": "None",
    "lax": "Lax",
    "strict": "Strict",
    "unspecified": "Lax",
}


def _normalize_same_site(raw: Any) -> str:
    if isinstance(raw, str):
        if raw in _VALID_SAME_SITE:
            return raw
        mapped = _SAME_SITE_ALIASES.get(raw.strip().lower())
        if mapped is not None:
            return mapped
    return "Lax"  # Playwright's own default when a cookie omits sameSite


def _normalize_expires(raw: dict[str, Any]) -> float:
    """Playwright shape: `expires` (float epoch seconds, -1 = session cookie).
    Extension-export shape: `expirationDate` (float epoch seconds) or a
    `session: true` flag with no expiry at all. Missing/invalid -> -1.0,
    Playwright's own sentinel for "no explicit expiry"."""
    for key in ("expirationDate", "expires"):
        value = raw.get(key)
        if isinstance(value, int | float) and value > 0:
            return float(value)
    return -1.0


def _is_booking_domain(domain: str) -> bool:
    return domain.lstrip(".").lower().endswith("booking.com")


def _normalize_cookie(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name, value, domain = raw.get("name"), raw.get("value"), raw.get("domain")
    if not name or value is None or not domain:
        return None
    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": raw.get("path") or "/",
        "expires": _normalize_expires(raw),
        "httpOnly": bool(raw.get("httpOnly", False)),
        "secure": bool(raw.get("secure", True)),
        "sameSite": _normalize_same_site(raw.get("sameSite")),
    }


def import_cookies(
    raw_text: str, now: datetime | None = None
) -> tuple[SessionState, ImportSummary]:
    """Parse, validate, and normalize a cookie export into a storable
    `SessionState`. Raises `CookieImportError` on anything unusable; never
    partially stores a rejected file (validation runs before any SessionState
    is built).

    Only booking.com-domain cookies are kept — cookies for unrelated sites
    that happen to be in the same export are dropped rather than stored.
    """
    now = now or datetime.now(UTC)
    try:
        data: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise CookieImportError(f"not valid JSON ({exc})") from exc

    if isinstance(data, dict) and isinstance(data.get("cookies"), list):
        data = data["cookies"]
    if not isinstance(data, list):
        raise CookieImportError(
            'expected a JSON array of cookie objects (or {"cookies": [...]})'
        )

    normalized = [c for raw in data if (c := _normalize_cookie(raw)) is not None]
    if not normalized:
        raise CookieImportError("no usable cookie objects found in the file")

    booking_cookies = [c for c in normalized if _is_booking_domain(c["domain"])]
    if not booking_cookies:
        raise CookieImportError(
            "no cookies for a booking.com domain were found in this file — export "
            "cookies while logged in on booking.com, not another site"
        )

    now_epoch = now.timestamp()
    still_valid = [c for c in booking_cookies if c["expires"] < 0 or c["expires"] > now_epoch]
    if not still_valid:
        raise CookieImportError(
            "every booking.com cookie in this file is already expired — log in on "
            "booking.com in your browser again, re-export, and re-import"
        )

    domains = tuple(sorted({c["domain"].lstrip(".") for c in booking_cookies}))
    explicit_expiries = [c["expires"] for c in booking_cookies if c["expires"] > 0]
    earliest_expiry = (
        datetime.fromtimestamp(min(explicit_expiries), tz=UTC) if explicit_expiries else None
    )

    session = SessionState.new(
        platform=Platform.BOOKING_COM,
        cookies=json.dumps(booking_cookies).encode("utf-8"),
        authenticated_at=now,
        # Conservative: the session-level expiry is the *earliest* cookie's
        # expiry, so `SessionManager.ensure_active/current_mode` fall back to
        # LOGGED_OUT (and prompt re-import) as soon as any imported cookie
        # goes stale, rather than only once every cookie has.
        expires_at=earliest_expiry,
    )
    return session, ImportSummary(
        count=len(booking_cookies), domains=domains, earliest_expiry=earliest_expiry
    )
