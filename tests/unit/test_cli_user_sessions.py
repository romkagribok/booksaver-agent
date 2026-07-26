from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet

from booksaver.cli.commands import create_parser
from booksaver.domain.session import SessionState
from booksaver.domain.user import UserRole
from booksaver.domain.user_session import SessionUnavailableReason
from booksaver.domain.value_objects import DataDirectory, Platform
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.session_store import LocalSessionRepository
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteStore,
    SqliteUserRepository,
)

OWNER_TELEGRAM_ID = 555


@pytest.fixture(autouse=True)
def _secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOKSAVER_SECRET_KEY", Fernet.generate_key().decode())


def _setup(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[schedule]\ncheck_interval = "6h"\n\n[storage]\ndata_directory = "{data_dir}"\n'
    )
    with SqliteStore(data_dir / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        users.link_telegram_id(owner.user_id, OWNER_TELEGRAM_ID)
    return config_path, data_dir


def _auth_args(config_path, command: str, telegram_user_id: int = OWNER_TELEGRAM_ID):
    return create_parser().parse_args(
        [
            "--config",
            str(config_path),
            "auth",
            command,
            "--telegram-user-id",
            str(telegram_user_id),
        ]
    )


def test_auth_status_is_redacted_and_delete_is_targeted(tmp_path, capsys) -> None:
    config_path, data_dir = _setup(tmp_path)

    status_args = _auth_args(config_path, "status")
    assert status_args.func(status_args) == 0
    output = capsys.readouterr().out
    assert "Session health: missing" in output
    assert "Re-import with:" in output

    delete_args = _auth_args(config_path, "delete")
    assert delete_args.func(delete_args) == 0
    assert "No encrypted session exists" in capsys.readouterr().out
    assert not list((data_dir / "booking_sessions").glob("*.session"))


def test_explicit_legacy_migration_moves_only_owner_session(tmp_path, capsys) -> None:
    config_path, data_dir = _setup(tmp_path)
    legacy_repo = LocalSessionRepository(DataDirectory.of(str(data_dir)))
    legacy_repo.save(
        SessionState.new(
            Platform.BOOKING_COM,
            b'[{"name":"session","value":"legacy-secret"}]',
            datetime.now(UTC),
        )
    )

    args = _auth_args(config_path, "migrate-legacy")
    assert args.func(args) == 0

    assert "Migrated the legacy global session" in capsys.readouterr().out
    assert not (data_dir / "session_booking_com.json").exists()
    repo = EncryptedUserSessionRepository(DataDirectory.of(str(data_dir)))
    resolved = repo.resolve(1)
    assert resolved.is_ready
    assert resolved.snapshot is not None
    assert b"legacy-secret" in resolved.snapshot.cookies


def test_legacy_migration_rejects_non_owner_without_removing_source(
    tmp_path, capsys
) -> None:
    config_path, data_dir = _setup(tmp_path)
    with SqliteStore(data_dir / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(
            777, role=UserRole.USER
        )
    legacy_path = data_dir / "session_booking_com.json"
    LocalSessionRepository(DataDirectory.of(str(data_dir))).save(
        SessionState.new(Platform.BOOKING_COM, b"legacy", datetime.now(UTC))
    )

    args = _auth_args(config_path, "migrate-legacy", 777)
    assert args.func(args) == 2

    assert "must be the owner" in capsys.readouterr().err
    assert legacy_path.exists()
    assert (
        EncryptedUserSessionRepository(DataDirectory.of(str(data_dir)))
        .resolve(user.user_id)
        .unavailable_reason
        is SessionUnavailableReason.MISSING
    )


def test_unknown_user_status_and_delete_fail_closed(tmp_path, capsys) -> None:
    config_path, _ = _setup(tmp_path)

    for command in ("status", "delete"):
        args = _auth_args(config_path, command, 999999)
        assert args.func(args) == 2

    assert capsys.readouterr().err.count("No active admitted Telegram user") == 2
