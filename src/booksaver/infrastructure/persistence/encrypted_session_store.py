from __future__ import annotations

import base64
import importlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from booksaver.domain.errors import SecretKeyError, SessionRevokedError
from booksaver.domain.session import SessionStatus
from booksaver.domain.user_session import (
    SessionResolution,
    SessionUnavailableReason,
    UserSessionHealth,
    UserSessionMetadata,
    UserSessionSnapshot,
    UserSessionStatusView,
)
from booksaver.domain.value_objects import DataDirectory, Platform
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore

_FORMAT_VERSION = 1
_LOCK_API = importlib.import_module("msvcrt" if os.name == "nt" else "fcntl")


class EncryptedUserSessionRepository:
    """Fernet-encrypted, atomic browser-state storage scoped by local user ID."""

    def __init__(
        self,
        data_directory: DataDirectory,
        key_store: FernetKeyStore | None = None,
    ) -> None:
        self._directory = data_directory.path / "booking_sessions"
        self._key_store = key_store or FernetKeyStore(purpose="Booking.com session")

    def _path(self, owner_user_id: int) -> Path:
        if owner_user_id <= 0:
            raise ValueError("Session owner user id must be positive")
        return self._directory / f"user-{owner_user_id}-booking-com.session"

    def _revocation_path(self, owner_user_id: int) -> Path:
        if owner_user_id <= 0:
            raise ValueError("Session owner user id must be positive")
        return self._directory / f"user-{owner_user_id}-booking-com.revoked"

    def save(self, snapshot: UserSessionSnapshot) -> None:
        with self._owner_lock(snapshot.metadata.owner_user_id):
            self._save_unlocked(snapshot)

    def _save_unlocked(self, snapshot: UserSessionSnapshot) -> None:
        path = self._path(snapshot.metadata.owner_user_id)
        if self._revocation_path(snapshot.metadata.owner_user_id).exists():
            raise SessionRevokedError("Session owner has been permanently purged")
        # A valid-looking but different Fernet key must not silently replace a
        # bundle encrypted with the operator's real key. Prove the current
        # bundle is readable before any replacement write begins.
        if path.exists():
            self._load_snapshot(path, snapshot.metadata.owner_user_id)
        encrypted = self._encrypt_snapshot(snapshot)
        envelope = self._envelope(snapshot.metadata, encrypted)
        self._atomic_write(path, envelope)

    def resolve(
        self, owner_user_id: int, now: datetime | None = None
    ) -> SessionResolution:
        path = self._path(owner_user_id)
        if not path.exists():
            return SessionResolution.unavailable(SessionUnavailableReason.MISSING)
        try:
            snapshot = self._load_snapshot(path, expected_owner=owner_user_id)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, SecretKeyError):
            return SessionResolution.unavailable(SessionUnavailableReason.INVALID)

        health = snapshot.metadata.health(now or datetime.now(UTC))
        if health is UserSessionHealth.EXPIRED:
            return SessionResolution.unavailable(SessionUnavailableReason.EXPIRED)
        if health is UserSessionHealth.REAUTH_REQUIRED:
            return SessionResolution.unavailable(SessionUnavailableReason.REAUTH_REQUIRED)
        return SessionResolution.ready(snapshot)

    def status(
        self, owner_user_id: int, now: datetime | None = None
    ) -> UserSessionStatusView:
        path = self._path(owner_user_id)
        if not path.exists():
            return UserSessionStatusView(owner_user_id, UserSessionHealth.MISSING)
        try:
            snapshot = self._load_snapshot(path, expected_owner=owner_user_id)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, SecretKeyError):
            return UserSessionStatusView(owner_user_id, UserSessionHealth.INVALID)
        metadata = snapshot.metadata
        return UserSessionStatusView(
            owner_user_id=owner_user_id,
            health=metadata.health(now or datetime.now(UTC)),
            revision_id=metadata.revision_id,
            imported_at=metadata.imported_at,
            validated_at=metadata.validated_at,
            expires_at=metadata.expires_at,
        )

    def compare_and_replace(
        self, owner_user_id: int, expected_revision: str, snapshot: UserSessionSnapshot
    ) -> bool:
        if snapshot.metadata.owner_user_id != owner_user_id:
            raise ValueError("Replacement session owner does not match target")
        if snapshot.metadata.revision_id != expected_revision:
            return False
        with self._owner_lock(owner_user_id):
            current = self._ready_snapshot_unlocked(owner_user_id)
            if current is None or current.metadata.revision_id != expected_revision:
                return False
            self._save_unlocked(snapshot)
            return True

    def mark_reauth_required(self, owner_user_id: int, expected_revision: str) -> bool:
        with self._owner_lock(owner_user_id):
            snapshot = self._ready_snapshot_unlocked(owner_user_id)
            if snapshot is None or snapshot.metadata.revision_id != expected_revision:
                return False
            updated = UserSessionSnapshot(
                metadata=UserSessionMetadata(
                    owner_user_id=owner_user_id,
                    revision_id=expected_revision,
                    platform=snapshot.metadata.platform,
                    imported_at=snapshot.metadata.imported_at,
                    expires_at=snapshot.metadata.expires_at,
                    status=SessionStatus.REQUIRES_REAUTH,
                    validated_at=snapshot.metadata.validated_at,
                ),
                cookies=snapshot.cookies,
            )
            self._save_unlocked(updated)
            return True

    def delete(self, owner_user_id: int) -> bool:
        path = self._path(owner_user_id)
        with self._owner_lock(owner_user_id):
            if not path.exists():
                return False
            try:
                path.unlink()
            except FileNotFoundError:
                return False
            return True

    def revoke(self, owner_user_id: int) -> bool:
        """Permanently prevent session recreation for a purged local user ID."""
        path = self._path(owner_user_id)
        revocation_path = self._revocation_path(owner_user_id)
        with self._owner_lock(owner_user_id):
            deleted = False
            try:
                path.unlink()
                deleted = True
            except FileNotFoundError:
                pass
            # The marker is written before releasing the same lock used by save.
            # A cookie import that validated the user before purge can therefore
            # never write authentication state after this revocation boundary.
            self._atomic_write(revocation_path, "purged\n")
            return deleted

    def _ready_snapshot_unlocked(self, owner_user_id: int) -> UserSessionSnapshot | None:
        path = self._path(owner_user_id)
        if not path.exists():
            return None
        try:
            snapshot = self._load_snapshot(path, expected_owner=owner_user_id)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, SecretKeyError):
            return None
        if snapshot.metadata.health(datetime.now(UTC)) is not UserSessionHealth.READY:
            return None
        return snapshot

    @contextmanager
    def _owner_lock(self, owner_user_id: int) -> Iterator[None]:
        """Serialize replacement/revocation against imports for one owner."""
        self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._directory.chmod(0o700)
        lock_path = self._directory / f".user-{owner_user_id}.lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        locked = False
        try:
            os.chmod(lock_path, 0o600)
            if os.name == "nt":
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"\0")
                os.lseek(fd, 0, os.SEEK_SET)
                _LOCK_API.locking(fd, _LOCK_API.LK_LOCK, 1)
            else:
                _LOCK_API.flock(fd, _LOCK_API.LOCK_EX)
            locked = True
            yield
        finally:
            if locked:
                if os.name == "nt":
                    os.lseek(fd, 0, os.SEEK_SET)
                    _LOCK_API.locking(fd, _LOCK_API.LK_UNLCK, 1)
                else:
                    _LOCK_API.flock(fd, _LOCK_API.LOCK_UN)
            os.close(fd)

    def _encrypt_snapshot(self, snapshot: UserSessionSnapshot) -> bytes:
        payload = json.dumps(
            {"cookies_b64": base64.b64encode(snapshot.cookies).decode("ascii")},
            separators=(",", ":"),
        )
        return self._key_store.encrypt(payload)

    @staticmethod
    def _envelope(metadata: UserSessionMetadata, encrypted: bytes) -> str:
        return json.dumps(
            {
                "version": _FORMAT_VERSION,
                "owner_user_id": metadata.owner_user_id,
                "revision_id": metadata.revision_id,
                "platform": metadata.platform.value,
                "imported_at": metadata.imported_at.isoformat(),
                "validated_at": (
                    metadata.validated_at.isoformat() if metadata.validated_at else None
                ),
                "expires_at": metadata.expires_at.isoformat() if metadata.expires_at else None,
                "status": metadata.status.value,
                "fernet_token": encrypted.decode("ascii"),
            },
            separators=(",", ":"),
        )

    def _load_snapshot(self, path: Path, expected_owner: int) -> UserSessionSnapshot:
        raw: dict[str, Any] = json.loads(path.read_text())
        if raw["version"] != _FORMAT_VERSION or raw["owner_user_id"] != expected_owner:
            raise ValueError("Invalid user session envelope")
        plaintext = self._key_store.decrypt(raw["fernet_token"].encode("ascii"))
        secret: dict[str, Any] = json.loads(plaintext)
        cookies = base64.b64decode(secret["cookies_b64"], validate=True)
        metadata = UserSessionMetadata(
            owner_user_id=expected_owner,
            revision_id=raw["revision_id"],
            platform=Platform(raw["platform"]),
            imported_at=datetime.fromisoformat(raw["imported_at"]),
            validated_at=(
                datetime.fromisoformat(raw["validated_at"])
                if raw.get("validated_at")
                else None
            ),
            expires_at=(
                datetime.fromisoformat(raw["expires_at"]) if raw.get("expires_at") else None
            ),
            status=SessionStatus(raw["status"]),
        )
        return UserSessionSnapshot(metadata=metadata, cookies=cookies)

    def _atomic_write(self, path: Path, payload: str) -> None:
        self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._directory.chmod(0o700)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._directory,
                prefix=".session-",
                delete=False,
            ) as temp:
                temp_path = Path(temp.name)
                os.chmod(temp.name, 0o600)
                temp.write(payload)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_path, path)
            path.chmod(0o600)
            directory_fd = os.open(self._directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
