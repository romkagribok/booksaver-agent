from __future__ import annotations

import stat
import threading
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from booksaver.domain.errors import SecretKeyError, SessionRevokedError
from booksaver.domain.user_session import (
    SessionUnavailableReason,
    UserSessionMetadata,
    UserSessionSnapshot,
)
from booksaver.domain.value_objects import DataDirectory, Platform
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)


def _key() -> str:
    return Fernet.generate_key().decode()


def _snapshot(user_id: int = 7, *, expires_at: datetime | None = None) -> UserSessionSnapshot:
    now = datetime.now(UTC)
    return UserSessionSnapshot(
        metadata=UserSessionMetadata.imported(
            owner_user_id=user_id,
            platform=Platform.BOOKING_COM,
            imported_at=now,
            expires_at=expires_at or now + timedelta(days=5),
        ),
        cookies=b'[{"name":"secret-cookie","value":"secret-value"}]',
    )


def _repo(tmp_path, secret: str) -> EncryptedUserSessionRepository:
    return EncryptedUserSessionRepository(
        DataDirectory.of(str(tmp_path)), FernetKeyStore(secret_key=secret)
    )


def test_round_trip_is_encrypted_and_permissions_are_restrictive(tmp_path) -> None:
    repo = _repo(tmp_path, _key())
    snapshot = _snapshot()

    repo.save(snapshot)

    path = tmp_path / "booking_sessions" / "user-7-booking-com.session"
    payload = path.read_bytes()
    assert b"secret-cookie" not in payload
    assert b"secret-value" not in payload
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    resolved = repo.resolve(7)
    assert resolved.snapshot == snapshot


def test_different_valid_key_cannot_destroy_existing_bundle(tmp_path) -> None:
    original_key = _key()
    original = _repo(tmp_path, original_key)
    snapshot = _snapshot()
    original.save(snapshot)
    before = (tmp_path / "booking_sessions" / "user-7-booking-com.session").read_bytes()

    with pytest.raises(SecretKeyError):
        _repo(tmp_path, _key()).save(_snapshot())

    after = (tmp_path / "booking_sessions" / "user-7-booking-com.session").read_bytes()
    assert after == before
    assert original.resolve(7).snapshot == snapshot


def test_expired_and_reauth_required_are_typed_unavailable_results(tmp_path) -> None:
    repo = _repo(tmp_path, _key())
    expired = _snapshot(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    repo.save(expired)
    assert repo.resolve(7).unavailable_reason is SessionUnavailableReason.EXPIRED

    repo.delete(7)
    ready = _snapshot()
    repo.save(ready)
    assert repo.mark_reauth_required(7, ready.metadata.revision_id)
    assert (
        repo.resolve(7).unavailable_reason
        is SessionUnavailableReason.REAUTH_REQUIRED
    )


def test_refresh_is_revision_guarded_and_owner_scoped(tmp_path) -> None:
    repo = _repo(tmp_path, _key())
    snapshot = _snapshot()
    repo.save(snapshot)
    refreshed = snapshot.refreshed(b"new-secret", validated_at=datetime.now(UTC))

    assert not repo.compare_and_replace(7, "stale-revision", refreshed)
    assert repo.resolve(7).snapshot == snapshot
    assert repo.compare_and_replace(7, snapshot.metadata.revision_id, refreshed)
    assert repo.resolve(7).snapshot == refreshed

    foreign = _snapshot(user_id=8)
    with pytest.raises(ValueError, match="owner"):
        repo.compare_and_replace(7, refreshed.metadata.revision_id, foreign)


def test_delete_affects_only_target_user(tmp_path) -> None:
    repo = _repo(tmp_path, _key())
    repo.save(_snapshot(7))
    repo.save(_snapshot(8))

    assert repo.delete(7)
    assert repo.resolve(7).unavailable_reason is SessionUnavailableReason.MISSING
    assert repo.resolve(8).is_ready


def test_delete_checks_for_session_only_after_owner_lock_is_acquired(tmp_path) -> None:
    repo = _repo(tmp_path, _key())
    path = tmp_path / "booking_sessions" / "user-7-booking-com.session"
    deleted: list[bool] = []
    finished = threading.Event()

    def _delete() -> None:
        deleted.append(repo.delete(7))
        finished.set()

    with repo._owner_lock(7):
        thread = threading.Thread(target=_delete)
        thread.start()
        assert not finished.wait(0.05)
        path.write_text("session-created-before-lock-release")

    thread.join(timeout=1)
    assert deleted == [True]
    assert not path.exists()


def test_revoke_blocks_future_session_writes_without_affecting_other_users(tmp_path) -> None:
    repo = _repo(tmp_path, _key())
    repo.save(_snapshot(7))
    repo.save(_snapshot(8))

    assert repo.revoke(7)
    assert not repo.revoke(7)
    assert not (tmp_path / "booking_sessions" / "user-7-booking-com.session").exists()
    assert (tmp_path / "booking_sessions" / "user-7-booking-com.revoked").exists()
    with pytest.raises(SessionRevokedError, match="permanently purged"):
        repo.save(_snapshot(7))
    assert repo.resolve(8).is_ready
