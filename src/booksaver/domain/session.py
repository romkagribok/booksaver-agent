from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum

from .value_objects import Platform


class SessionStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REQUIRES_REAUTH = "requires_reauth"


class SessionMode(Enum):
    """Whether a check runs with a restored Booking.com session or logged out.

    A display-less VPS can never run headed `booksaver auth`, so the absence of
    a usable session is an expected, first-class mode (US-035/FR-8) rather than
    an error: the search journey still works unauthenticated and returns real
    public bookable totals. ``AUTHENTICATED`` means cookies were restored from a
    saved session; ``LOGGED_OUT`` means the journey runs with no session at all.
    """

    LOGGED_OUT = "logged_out"
    AUTHENTICATED = "authenticated"


@dataclass(frozen=True)
class SessionState:
    session_id: str
    platform: Platform
    cookies: bytes  # opaque browser cookie blob (Playwright JSON)
    authenticated_at: datetime
    expires_at: datetime | None
    status: SessionStatus

    @classmethod
    def new(
        cls,
        platform: Platform,
        cookies: bytes,
        authenticated_at: datetime,
        expires_at: datetime | None = None,
    ) -> SessionState:
        return cls(
            session_id=str(uuid.uuid4()),
            platform=platform,
            cookies=cookies,
            authenticated_at=authenticated_at,
            expires_at=expires_at,
            status=SessionStatus.ACTIVE,
        )

    def with_status(self, status: SessionStatus) -> SessionState:
        return replace(self, status=status)

    def with_cookies(self, cookies: bytes) -> SessionState:
        return replace(self, cookies=cookies)

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or datetime.now(UTC)) >= self.expires_at
