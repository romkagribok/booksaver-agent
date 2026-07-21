from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from booksaver.application.user_sessions import (
    AuthenticatedSessionProvider,
    SessionTargetError,
    UserSessionService,
)
from booksaver.domain.user import User, UserAccessState, UserRole
from booksaver.domain.user_session import SessionUnavailableReason
from booksaver.domain.value_objects import DataDirectory
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)


class Users:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.user_id: user for user in users}

    def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return next(
            (u for u in self.users.values() if u.telegram_user_id == telegram_user_id),
            None,
        )


def _user(
    user_id: int,
    telegram_id: int,
    *,
    state: UserAccessState = UserAccessState.ACTIVE,
    role: UserRole = UserRole.USER,
) -> User:
    return User(user_id, telegram_id, role, state, datetime.now(UTC))


def _cookies() -> str:
    return json.dumps(
        [
            {
                "name": "session",
                "value": "top-secret",
                "domain": ".booking.com",
                "expires": (datetime.now(UTC) + timedelta(days=2)).timestamp(),
            }
        ]
    )


def _repo(tmp_path) -> EncryptedUserSessionRepository:
    return EncryptedUserSessionRepository(
        DataDirectory.of(str(tmp_path)),
        FernetKeyStore(secret_key=Fernet.generate_key().decode()),
    )


def test_import_targets_stable_local_user_and_provider_resolves_only_that_user(
    tmp_path,
) -> None:
    users = Users([_user(1, 101), _user(2, 202)])
    repo = _repo(tmp_path)
    service = UserSessionService(users, repo)

    imported = service.import_cookies(202, _cookies())

    assert imported.owner_user_id == 2
    assert repo.resolve(1).unavailable_reason is SessionUnavailableReason.MISSING
    assert AuthenticatedSessionProvider(users, repo).resolve(2).is_ready


@pytest.mark.parametrize(
    "known_user",
    [None, _user(2, 202, state=UserAccessState.REVOKED)],
)
def test_import_rejects_unknown_or_revoked_target_without_writing(
    tmp_path, known_user: User | None
) -> None:
    users = Users([known_user] if known_user else [])
    repo = _repo(tmp_path)

    with pytest.raises(SessionTargetError, match="active admitted"):
        UserSessionService(users, repo).import_cookies(202, _cookies())

    assert repo.resolve(2).unavailable_reason is SessionUnavailableReason.MISSING


def test_provider_blocks_resolution_and_refresh_after_revocation(tmp_path) -> None:
    user = _user(2, 202)
    users = Users([user])
    repo = _repo(tmp_path)
    service = UserSessionService(users, repo)
    service.import_cookies(202, _cookies())
    ready = repo.resolve(2)
    assert ready.snapshot is not None

    user.access_state = UserAccessState.REVOKED
    provider = AuthenticatedSessionProvider(users, repo)

    assert (
        provider.resolve(2).unavailable_reason
        is SessionUnavailableReason.ACCESS_REVOKED
    )
    assert not provider.refresh(
        2,
        ready.snapshot.metadata.revision_id,
        b"new-cookie",
        datetime.now(UTC),
    )


def test_legacy_migration_is_owner_only_and_never_overwrites_existing(tmp_path) -> None:
    from booksaver.domain.session import SessionState
    from booksaver.domain.value_objects import Platform

    users = Users([_user(1, 101, role=UserRole.OWNER), _user(2, 202)])
    repo = _repo(tmp_path)
    service = UserSessionService(users, repo)
    legacy = SessionState.new(Platform.BOOKING_COM, b"legacy", datetime.now(UTC))

    with pytest.raises(SessionTargetError, match="must be the owner"):
        service.migrate_legacy_owner(202, legacy)

    service.migrate_legacy_owner(101, legacy)
    with pytest.raises(SessionTargetError, match="already has"):
        service.migrate_legacy_owner(101, legacy)
