from __future__ import annotations

import json
import stat
from datetime import UTC, datetime, timedelta

from booksaver.cli.commands import create_parser
from booksaver.domain.session import SessionMode
from booksaver.infrastructure.persistence.session_store import LocalSessionRepository
from booksaver.monitor.session_manager import SessionManager


def _write_config(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[schedule]\ncheck_interval = "6h"\n\n[storage]\ndata_directory = "{data_dir}"\n'
    )
    return config_path, data_dir


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


def test_auth_import_happy_path_stores_session(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path)
    cookie_path = _write_cookie_file(tmp_path)

    parser = create_parser()
    args = parser.parse_args(["--config", str(config_path), "auth", "import", cookie_path])
    rc = args.func(args)

    assert rc == 0
    out = capsys.readouterr().out
    assert "Imported 1 cookie(s)" in out
    assert "booking.com" in out
    assert "supersecret" not in out  # never print cookie values

    session_file = data_dir / "session_booking_com.json"
    assert session_file.exists()
    assert stat.S_IMODE(session_file.stat().st_mode) == 0o600
    # cookies are base64-encoded in the file (LocalSessionRepository, ADR-010)
    # so the raw value never appears in plaintext either
    assert "supersecret" not in session_file.read_text()


def test_auth_import_flips_mode_to_authenticated(tmp_path) -> None:
    config_path, data_dir = _write_config(tmp_path)
    cookie_path = _write_cookie_file(tmp_path)

    parser = create_parser()
    args = parser.parse_args(["--config", str(config_path), "auth", "import", cookie_path])
    assert args.func(args) == 0

    from booksaver.domain.value_objects import DataDirectory

    manager = SessionManager(LocalSessionRepository(DataDirectory.of(str(data_dir))))
    assert manager.current_mode() is SessionMode.AUTHENTICATED


def test_auth_import_rejects_garbage_file(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path)
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json at all")

    parser = create_parser()
    args = parser.parse_args(["--config", str(config_path), "auth", "import", str(bad_file)])
    rc = args.func(args)

    assert rc == 2
    err = capsys.readouterr().err
    assert "Cookie import failed" in err
    assert not (data_dir / "session_booking_com.json").exists()


def test_auth_import_rejects_no_booking_domain(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path)
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(
        json.dumps([{"name": "a", "value": "b", "domain": "example.com", "expires": -1}])
    )

    parser = create_parser()
    args = parser.parse_args(["--config", str(config_path), "auth", "import", str(cookie_file)])
    rc = args.func(args)

    assert rc == 2
    assert "no cookies for a booking.com domain" in capsys.readouterr().err


def test_auth_import_rejects_all_expired(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path)
    past = (datetime.now(UTC) - timedelta(days=1)).timestamp()
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(
        json.dumps([{"name": "a", "value": "b", "domain": "booking.com", "expires": past}])
    )

    parser = create_parser()
    args = parser.parse_args(["--config", str(config_path), "auth", "import", str(cookie_file)])
    rc = args.func(args)

    assert rc == 2
    assert "already expired" in capsys.readouterr().err


def test_auth_import_missing_file(tmp_path, capsys) -> None:
    config_path, data_dir = _write_config(tmp_path)
    parser = create_parser()
    args = parser.parse_args(
        ["--config", str(config_path), "auth", "import", str(tmp_path / "nope.json")]
    )
    rc = args.func(args)
    assert rc == 2
    assert "Error reading" in capsys.readouterr().err


def test_bare_auth_still_routes_to_headed_login(tmp_path) -> None:
    """`booksaver auth` (no subcommand) must keep invoking cmd_auth, not
    cmd_auth_import — the `import` subparser must not shadow the default."""
    config_path, _ = _write_config(tmp_path)
    parser = create_parser()
    args = parser.parse_args(["--config", str(config_path), "auth"])
    from booksaver.cli.commands import cmd_auth

    assert args.func is cmd_auth
