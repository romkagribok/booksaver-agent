from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum

from booksaver.domain.session import SessionStatus
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
        if self.expires_at is not None and (now or datetime.now(UTC)) >= self.expires_at:
            return UserSessionHealth.EXPIRED
        return UserSessionHealth.READY


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
        return replace(
            self,
            metadata=replace(
                self.metadata,
                status=SessionStatus.ACTIVE,
                validated_at=validated_at,
                expires_at=expires_at if expires_at is not None else self.metadata.expires_at,
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
