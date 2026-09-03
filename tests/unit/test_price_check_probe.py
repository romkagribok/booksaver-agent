from __future__ import annotations

import sqlite3

from scripts.price_check_probe import _clone_state, _IsolatedConfigSource


def test_isolated_config_source_changes_only_copied_storage_path(tmp_path) -> None:
    raw = {
        "storage": {"data_directory": "/production"},
        "agentic_browser": {"routing": "legacy"},
    }
    isolated = tmp_path / "isolated"

    source = _IsolatedConfigSource(raw, isolated)
    first = source.read()
    first["agentic_browser"]["routing"] = "agentic"

    assert raw["storage"]["data_directory"] == "/production"
    assert source.read()["storage"]["data_directory"] == str(isolated)
    assert source.read()["agentic_browser"]["routing"] == "legacy"


def test_clone_state_copies_consistent_database_and_encrypted_sessions(tmp_path) -> None:
    source_data = tmp_path / "production"
    source_data.mkdir()
    with sqlite3.connect(source_data / "booksaver.db") as connection:
        connection.execute("CREATE TABLE proof (value TEXT NOT NULL)")
        connection.execute("INSERT INTO proof VALUES ('production')")
        connection.commit()
    sessions = source_data / "booking_sessions"
    sessions.mkdir()
    (sessions / "7.session").write_bytes(b"encrypted-session")

    isolated_data = tmp_path / "probe" / "data"
    _clone_state(source_data, isolated_data)

    with sqlite3.connect(isolated_data / "booksaver.db") as connection:
        assert connection.execute("SELECT value FROM proof").fetchone() == (
            "production",
        )
        connection.execute("UPDATE proof SET value = 'probe'")
        connection.commit()
    with sqlite3.connect(source_data / "booksaver.db") as connection:
        assert connection.execute("SELECT value FROM proof").fetchone() == (
            "production",
        )
    assert (isolated_data / "booking_sessions" / "7.session").read_bytes() == (
        b"encrypted-session"
    )
