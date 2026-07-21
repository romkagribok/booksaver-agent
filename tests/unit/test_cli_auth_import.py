from __future__ import annotations

import json
import stat
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from booksaver.cli.commands import create_parser
from booksaver.domain.user_session import SessionUnavailableReason
from booksaver.domain.value_objects import DataDirectory
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteStore,
    SqliteUserRepository,
)

TELEGRAM_USER_ID = 555


@pytest.fixture(autouse=True)
def _secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOKSAVER_SECRET_KEY", Fernet.generate_key().decode())


def _write_config(tmp_path, *, admit_user: bool = True):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[schedule]\ncheck_interval = "6h"\n\n[storage]\ndata_directory = "{data_dir}"\n'
    )
    if admit_user:
        with SqliteStore(data_dir / "booksaver.db") as store:
            users = SqliteUserRepository(store)
            users.link_telegram_id(users.get_owner().user_id, TELEGRAM_USER_ID)
    return config_path, data_dir


def _import_args(config_path, cookie_path: str):
    return create_parser().parse_args(
        [
            "--config",
            str(config_path),
            "auth",
            "import",
            cookie_path,
            "--telegram-user-id",
            str(TELEGRAM_USER_ID),
        ]
    )


def _write_cookie_file(tmp_path, expires_in_days: int = 30) -> str:
    epoch = (datetime.now(UTC) + timedelta(days=expires_in_days)).timestamp()
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(
        json.dumps(
            [
                {
                    "name": "bkng_sso",
                    "value": "supersecret",
                    "domain": ".booking.com",
                    "path": "/",
                    "expirationDate": epoch,
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "no_restriction",
                }
            ]
        )
    )
    return str(cookie_file)


def test_auth_import_happy_path_stores_encrypted_user_session(
    tmp_path, capsys
) -> None:
    config_path, data_dir = _write_config(tmp_path)
    cookie_path = _write_cookie_file(tmp_path)

    rc = _import_args(config_path, cookie_path).func(
        _import_args(config_path, cookie_path)
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "Imported 1 cookie(s)" in out
    assert f"Telegram user {TELEGRAM_USER_ID}" in out
    assert "booking.com" in out
    assert "supersecret" not in out

    owner_session = data_dir / "booking_sessions" / "user-1-booking-com.session"
    assert owner_session.exists()
    assert stat.S_IMODE(owner_session.stat().st_mode) == 0o600
    assert "supersecret" not in owner_session.read_text()
    assert not (data_dir / "session_booking_com.json").exists()


def test_auth_import_makes_only_target_user_session_ready(tmp_path) -> None:
    config_path, data_dir = _write_config(tmp_path)
    cookie_path = _write_cookie_file(tmp_path)
    with SqliteStore(data_dir / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        other = users.get_or_create_by_telegram_id(777)

    args = _import_args(config_path, cookie_path)
    assert args.func(args) == 0

    repo = EncryptedUserSessionRepository(DataDirectory.of(str(data_dir)))
    assert repo.resolve(1).is_ready
    assert (
        repo.resolve(other.user_id).unavailable_reason
        is SessionUnavailableReason.MISSING
    )


def test_auth_import_rejects_unknown_target_without_writing(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path, admit_user=False)
    cookie_path = _write_cookie_file(tmp_path)

    args = _import_args(config_path, cookie_path)
    assert args.func(args) == 2

    assert "No active admitted Telegram user" in capsys.readouterr().err
    assert not (data_dir / "booking_sessions").exists()


def test_auth_import_rejects_garbage_file(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path)
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json at all")

    args = _import_args(config_path, str(bad_file))
    rc = args.func(args)

    assert rc == 2
    assert "Cookie import failed" in capsys.readouterr().err
    assert not (data_dir / "booking_sessions").exists()


def test_auth_import_rejects_no_booking_domain(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path)
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(
        json.dumps([{"name": "a", "value": "b", "domain": "example.com", "expires": -1}])
    )

    args = _import_args(config_path, str(cookie_file))
    assert args.func(args) == 2
    assert "no cookies for a booking.com domain" in capsys.readouterr().err
    assert not (data_dir / "booking_sessions").exists()


def test_auth_import_rejects_all_expired(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path)
    past = (datetime.now(UTC) - timedelta(days=1)).timestamp()
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(
        json.dumps(
            [{"name": "a", "value": "b", "domain": "booking.com", "expires": past}]
        )
    )

    args = _import_args(config_path, str(cookie_file))
    assert args.func(args) == 2
    assert "already expired" in capsys.readouterr().err
    assert not (data_dir / "booking_sessions").exists()


def test_auth_import_missing_file(tmp_path, capsys) -> None:
    config_path, _ = _write_config(tmp_path)
    args = _import_args(config_path, str(tmp_path / "nope.json"))
    assert args.func(args) == 2
    assert "Error reading" in capsys.readouterr().err


def test_auth_import_requires_explicit_telegram_user_id(tmp_path) -> None:
    config_path, _ = _write_config(tmp_path)
    cookie_path = _write_cookie_file(tmp_path)

    with pytest.raises(SystemExit) as exc:
        create_parser().parse_args(
            ["--config", str(config_path), "auth", "import", cookie_path]
        )

    assert exc.value.code == 2


def test_bare_auth_still_routes_to_headed_login(tmp_path) -> None:
    """The scoped import subparser must not shadow headed laptop auth."""
    config_path, _ = _write_config(tmp_path)
    args = create_parser().parse_args(["--config", str(config_path), "auth"])
    from booksaver.cli.commands import cmd_auth

    assert args.func is cmd_auth
