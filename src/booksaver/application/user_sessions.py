from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from booksaver.domain.session import SessionState
from booksaver.domain.session_maintenance import SessionNotice, SessionVerificationResult
from booksaver.domain.user import User, UserRole
from booksaver.domain.user_session import (
    SessionResolution,
    SessionUnavailableReason,
    UserSessionHealth,
    UserSessionMetadata,
    UserSessionSnapshot,
    UserSessionStatusView,
)
from booksaver.infrastructure.persistence.cookie_import import ImportSummary, import_cookies


class UserLookup(Protocol):
    def get_by_id(self, user_id: int) -> User | None: ...
    def get_by_telegram_id(self, telegram_user_id: int) -> User | None: ...


class UserSessionRepository(Protocol):
    def save(self, snapshot: UserSessionSnapshot) -> None: ...
    def resolve(
        self, owner_user_id: int, now: datetime | None = None
    ) -> SessionResolution: ...
    def status(
        self, owner_user_id: int, now: datetime | None = None
    ) -> UserSessionStatusView: ...
    def compare_and_replace(
        self, owner_user_id: int, expected_revision: str, snapshot: UserSessionSnapshot
    ) -> bool: ...
    def mark_reauth_required(self, owner_user_id: int, expected_revision: str) -> bool: ...
    def delete(self, owner_user_id: int) -> bool: ...
    def load_for_maintenance(self, owner_user_id: int) -> UserSessionSnapshot | None: ...
    def claim_maintenance(
        self, owner_user_id: int, expected_revision: str, now: datetime,
    ) -> UserSessionSnapshot | None: ...
    def complete_maintenance(
        self, owner_user_id: int, expected_revision: str, attempt_id: str,
        result: SessionVerificationResult, now: datetime,
    ) -> UserSessionSnapshot | None: ...
    def claim_session_notice(
        self, owner_user_id: int, expected_revision: str, now: datetime,
    ) -> SessionNotice | None: ...


class SessionTargetError(ValueError):
    pass


@dataclass(frozen=True)
class UserSessionImportResult:
    owner_user_id: int
    telegram_user_id: int
    revision_id: str
    summary: ImportSummary


class UserSessionService:
    def __init__(self, users: UserLookup, sessions: UserSessionRepository) -> None:
        self._users = users
        self._sessions = sessions

    def import_cookies(
        self, telegram_user_id: int, raw_text: str
    ) -> UserSessionImportResult:
        user = self._target(telegram_user_id, require_active=True)
        session, summary = import_cookies(raw_text)
        snapshot = self._snapshot(user.user_id, session)
        self._sessions.save(snapshot)
        return UserSessionImportResult(
            owner_user_id=user.user_id,
            telegram_user_id=telegram_user_id,
            revision_id=snapshot.metadata.revision_id,
            summary=summary,
        )

    def migrate_legacy_owner(
        self, telegram_user_id: int, legacy: SessionState
    ) -> UserSessionImportResult:
        user = self._target(telegram_user_id, require_active=True)
        if user.role is not UserRole.OWNER:
            raise SessionTargetError("Legacy session migration target must be the owner")
        if self._sessions.status(user.user_id).health is not UserSessionHealth.MISSING:
            raise SessionTargetError(
                "The owner already has a per-user session; delete it explicitly before migration"
            )
        # Moving an old owner bundle is not server verification. Retain its old
        # aggregate expiry until the verification-only maintenance path succeeds.
        snapshot = UserSessionSnapshot(
            metadata=UserSessionMetadata.imported(
                owner_user_id=user.user_id,
                platform=legacy.platform,
                imported_at=legacy.authenticated_at,
                expires_at=legacy.expires_at,
            ),
            cookies=legacy.cookies,
        )
        self._sessions.save(snapshot)
        return UserSessionImportResult(
            owner_user_id=user.user_id,
            telegram_user_id=telegram_user_id,
            revision_id=snapshot.metadata.revision_id,
            summary=ImportSummary(count=0, domains=(), earliest_expiry=legacy.expires_at),
        )

    def status(self, telegram_user_id: int) -> UserSessionStatusView:
        user = self._target(telegram_user_id, require_active=False)
        return self._sessions.status(user.user_id)

    def delete(self, telegram_user_id: int) -> bool:
        user = self._target(telegram_user_id, require_active=False)
        return self._sessions.delete(user.user_id)

    @staticmethod
    def _snapshot(user_id: int, session: SessionState) -> UserSessionSnapshot:
        return UserSessionSnapshot(
            metadata=replace(UserSessionMetadata.imported(
                owner_user_id=user_id,
                platform=session.platform,
                imported_at=session.authenticated_at,
                expires_at=None,
            ), continuity_version=1),
            cookies=session.cookies,
        )

    def _target(self, telegram_user_id: int, *, require_active: bool) -> User:
        user = self._users.get_by_telegram_id(telegram_user_id)
        if user is None or (require_active and not user.is_active):
            raise SessionTargetError("No active admitted Telegram user matches that ID")
        return user


class AuthenticatedSessionProvider:
    """Fail-closed runtime boundary for one booking owner's session."""

    def __init__(self, users: UserLookup, sessions: UserSessionRepository) -> None:
        self._users = users
        self._sessions = sessions

    def resolve(self, owner_user_id: int) -> SessionResolution:
        user = self._users.get_by_id(owner_user_id)
        if user is None or not user.is_active:
            return SessionResolution.unavailable(SessionUnavailableReason.ACCESS_REVOKED)
        return self._sessions.resolve(owner_user_id)

    def refresh(
        self,
        owner_user_id: int,
        expected_revision: str,
        cookies: bytes,
        validated_at: datetime,
        expires_at: datetime | None = None,
    ) -> bool:
        resolved = self.resolve(owner_user_id)
        snapshot = resolved.snapshot
        if snapshot is None and resolved.unavailable_reason is SessionUnavailableReason.EXPIRED:
            snapshot = self._sessions.load_for_maintenance(owner_user_id)
        if snapshot is None:
            return False
        refreshed = snapshot.refreshed(
            cookies,
            validated_at=validated_at,
            expires_at=expires_at,
        )
        return self._sessions.compare_and_replace(
            owner_user_id, expected_revision, refreshed
        )

    def mark_reauth_required(
        self, owner_user_id: int, expected_revision: str
    ) -> bool:
        user = self._users.get_by_id(owner_user_id)
        if user is None or not user.is_active:
            return False
        return self._sessions.mark_reauth_required(owner_user_id, expected_revision)
