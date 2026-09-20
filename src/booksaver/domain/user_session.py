from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum

from booksaver.domain.session import SessionStatus
from booksaver.domain.session_maintenance import (
    VERIFICATION_INTERVAL,
    SessionMaintenanceState,
    as_utc,
)
from booksaver.domain.value_objects import Platform


class UserSessionHealth(Enum):
    MISSING = "missing"
    READY = "ready"
    EXPIRED = "expired"
    REAUTH_REQUIRED = "reauth_required"
    INVALID = "invalid"


class SessionUnavailableReason(Enum):
    MISSING = "missing"
    EXPIRED = "expired"
    REAUTH_REQUIRED = "reauth_required"
    INVALID = "invalid"
    ACCESS_REVOKED = "access_revoked"


@dataclass(frozen=True)
class UserSessionMetadata:
    owner_user_id: int
    revision_id: str
    platform: Platform
    imported_at: datetime
    expires_at: datetime | None
    status: SessionStatus = SessionStatus.ACTIVE
    validated_at: datetime | None = None
    continuity_version: int = 0
    maintenance: SessionMaintenanceState = field(default_factory=SessionMaintenanceState)

    def __post_init__(self) -> None:
        if type(self.continuity_version) is not int or self.continuity_version not in {0, 1}:
            raise ValueError("Unknown session continuity policy")
        for value in (self.imported_at, self.expires_at, self.validated_at):
            if value is not None:
                as_utc(value)

    @classmethod
    def imported(
        cls,
        owner_user_id: int,
        platform: Platform,
        imported_at: datetime,
        expires_at: datetime | None,
    ) -> UserSessionMetadata:
        if owner_user_id <= 0:
            raise ValueError("Session owner user id must be positive")
        return cls(
            owner_user_id=owner_user_id,
            revision_id=str(uuid.uuid4()),
            platform=platform,
            imported_at=imported_at,
            expires_at=expires_at,
        )

    def health(self, now: datetime | None = None) -> UserSessionHealth:
        if self.status is SessionStatus.REQUIRES_REAUTH:
            return UserSessionHealth.REAUTH_REQUIRED
        if self.status is SessionStatus.EXPIRED:
            return UserSessionHealth.EXPIRED
        if (self.continuity_version == 0 and self.expires_at is not None
            and (now or datetime.now(UTC)) >= self.expires_at):
            return UserSessionHealth.EXPIRED
        return UserSessionHealth.READY

    def maintenance_due_at(self, now: datetime) -> datetime:
        if self.maintenance.next_attempt_at is not None:
            return self.maintenance.next_attempt_at
        if self.validated_at is not None and self.health(now) is UserSessionHealth.READY:
            return self.validated_at + VERIFICATION_INTERVAL
        return self.imported_at


@dataclass(frozen=True)
class UserSessionSnapshot:
    metadata: UserSessionMetadata
    cookies: bytes

    def refreshed(
        self,
        cookies: bytes,
        *,
        validated_at: datetime,
        expires_at: datetime | None = None,
    ) -> UserSessionSnapshot:
        verified = as_utc(validated_at)
        return replace(
            self,
            metadata=replace(
                self.metadata,
                status=SessionStatus.ACTIVE,
                validated_at=verified,
                expires_at=expires_at,
                continuity_version=1,
                maintenance=SessionMaintenanceState(
                    next_attempt_at=verified + VERIFICATION_INTERVAL,
                    last_attempt_at=self.metadata.maintenance.last_attempt_at,
                    notice_sent_at=self.metadata.maintenance.notice_sent_at,
                ),
            ),
            cookies=cookies,
        )


@dataclass(frozen=True)
class SessionResolution:
    snapshot: UserSessionSnapshot | None = None
    unavailable_reason: SessionUnavailableReason | None = None

    def __post_init__(self) -> None:
        if (self.snapshot is None) == (self.unavailable_reason is None):
            raise ValueError("SessionResolution must contain exactly one outcome")

    @property
    def is_ready(self) -> bool:
        return self.snapshot is not None

    @classmethod
    def ready(cls, snapshot: UserSessionSnapshot) -> SessionResolution:
        return cls(snapshot=snapshot)

    @classmethod
    def unavailable(cls, reason: SessionUnavailableReason) -> SessionResolution:
        return cls(unavailable_reason=reason)


@dataclass(frozen=True)
class UserSessionStatusView:
    owner_user_id: int
    health: UserSessionHealth
    revision_id: str | None = None
    imported_at: datetime | None = None
    validated_at: datetime | None = None
    expires_at: datetime | None = None
