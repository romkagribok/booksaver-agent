"""Code-owned session verification outcomes and durable maintenance timing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

VERIFICATION_INTERVAL = timedelta(hours=24)
UNCERTAINTY_NOTICE_AFTER = timedelta(hours=48)
MAINTENANCE_TIMEOUT = timedelta(seconds=60)
RETRY_DELAYS = (timedelta(minutes=15), timedelta(hours=1),
                timedelta(hours=6), timedelta(hours=24))


class SessionMaintenanceCleanupError(RuntimeError):
    """Owned browser processes could not be confirmed stopped; prohibit new admission."""


def require_utc(value: datetime | None) -> None:
    if value is not None and (not isinstance(value, datetime)
                             or value.tzinfo is None or value.utcoffset() != timedelta(0)):
        raise ValueError("Session maintenance timestamps must be aware UTC")


class SessionVerificationOutcome(Enum):
    AUTHENTICATED = "authenticated"
    SIGNED_OUT = "signed_out"
    INTERACTION_REQUIRED = "interaction_required"
    RETRY_LATER = "retry_later"


@dataclass(frozen=True, slots=True)
class SessionVerificationResult:
    outcome: SessionVerificationOutcome
    cookies: bytes | None = field(default=None, repr=False)
    verified_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, SessionVerificationOutcome):
            raise ValueError("Unknown session verification outcome")
        require_utc(self.verified_at)
        if self.outcome is SessionVerificationOutcome.AUTHENTICATED:
            if not isinstance(self.cookies, bytes) or not self.cookies or self.verified_at is None:
                raise ValueError("Authenticated session requires verified cookies and time")
        elif self.cookies is not None or self.verified_at is not None:
            raise ValueError("Unverified result cannot carry session material")


class SessionMaintenanceStatus(Enum):
    VERIFIED = "verified"
    RETRY_LATER = "retry_later"
    REAUTH_REQUIRED = "reauth_required"
    NOT_DUE = "not_due"
    UNAVAILABLE = "unavailable"
    BUSY = "busy"
    STOPPING = "stopping"
    STALE = "stale"
    DISABLED = "disabled"


class SessionNotice(Enum):
    SIGNED_OUT = "signed_out"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class SessionMaintenanceRun:
    status: SessionMaintenanceStatus
    next_attempt_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SessionMaintenanceState:
    next_attempt_at: datetime | None = None
    last_attempt_at: datetime | None = None
    failure_started_at: datetime | None = None
    consecutive_failures: int = 0
    attempt_id: str | None = field(default=None, repr=False)
    notice_sent_at: datetime | None = None

    def __post_init__(self) -> None:
        for instant in (self.next_attempt_at, self.last_attempt_at,
                        self.failure_started_at, self.notice_sent_at):
            require_utc(instant)
        if type(self.consecutive_failures) is not int or not 0 <= self.consecutive_failures <= 4:
            raise ValueError("Invalid bounded session retry count")
        if self.attempt_id is not None and (
            not isinstance(self.attempt_id, str) or not 1 <= len(self.attempt_id) <= 100
        ):
            raise ValueError("Invalid session maintenance attempt identity")
        if self.consecutive_failures and (
            self.last_attempt_at is None or self.failure_started_at is None
        ):
            raise ValueError("Session retries require failure and attempt timestamps")
        if self.attempt_id is not None and not self.consecutive_failures:
            raise ValueError("Session attempt requires a durable retry claim")


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Session time must be timezone-aware")
    return value.astimezone(UTC)
