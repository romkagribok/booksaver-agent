from __future__ import annotations

import sqlite3
from pathlib import Path

from booksaver.infrastructure.persistence.sqlite_store import SCHEMA_VERSION, SqliteStore


def _downgrade_fixture(db_path: Path, version: int) -> None:
    with SqliteStore(db_path) as store:
        store.conn.execute(
            "UPDATE users SET telegram_user_id = 111 WHERE role = 'owner'"
        )
        store.conn.execute(
            "INSERT INTO invite_codes "
            "(code, issued_by, issued_at, expires_at, used_by, used_at) "
            "VALUES ('preserve-me', 1, '2026-08-13T00:00:00+00:00', NULL, NULL, NULL)"
        )
        store.conn.commit()

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        DROP TABLE dom_drift_diagnostics;
        DROP TABLE dom_drift_alerts;
        DROP TABLE dom_drift_incidents;
        """
    )
    conn.execute("DELETE FROM schema_meta WHERE version > ?", (version,))
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (version, applied_at) VALUES (?, ?)",
        (version, f"2026-08-{version:02d}T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()


def test_v13_to_v18_is_additive_and_preserves_existing_data(tmp_path: Path) -> None:
    db_path = tmp_path / "v13.db"
    _downgrade_fixture(db_path, 13)

    with SqliteStore(db_path) as store:
        versions = [
            row[0]
            for row in store.conn.execute(
                "SELECT version FROM schema_meta ORDER BY version"
            ).fetchall()
        ]
        owner = store.conn.execute(
            "SELECT telegram_user_id FROM users WHERE role = 'owner'"
        ).fetchone()
        invite = store.conn.execute(
            "SELECT code FROM invite_codes WHERE code = 'preserve-me'"
        ).fetchone()
        tables = {
            row[0]
            for row in store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert versions[-12:] == [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
    assert owner[0] == 111
    assert invite[0] == "preserve-me"
    assert SCHEMA_VERSION == 25
    assert {"dom_drift_incidents", "dom_drift_alerts", "dom_drift_diagnostics"} <= tables
    assert not {t for t in tables if t.startswith("llm_")}


def test_v23_to_v24_drops_claude_ledgers_and_clears_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "v23.db"
    with SqliteStore(db_path) as store:
        store.conn.execute(
            "INSERT INTO invite_codes "
            "(code, issued_by, issued_at, expires_at, used_by, used_at) "
            "VALUES ('preserve-me', 1, '2026-08-13T00:00:00+00:00', NULL, NULL, NULL)"
        )
        store.conn.commit()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE llm_spend_days (utc_date TEXT PRIMARY KEY);
        CREATE TABLE llm_cost_reservations (
            reservation_id TEXT PRIMARY KEY,
            utc_date TEXT NOT NULL REFERENCES llm_spend_days(utc_date)
        );
        CREATE INDEX idx_llm_reservations_day ON llm_cost_reservations(utc_date);
        CREATE TABLE llm_profile_qualifications (qualification_id TEXT PRIMARY KEY);
        INSERT INTO llm_spend_days VALUES ('2026-08-13');
        INSERT INTO llm_cost_reservations VALUES ('r-1', '2026-08-13');
        INSERT INTO llm_profile_qualifications VALUES ('q-1');
        UPDATE users SET encrypted_key = X'00ff' WHERE role = 'owner';
        DELETE FROM schema_meta WHERE version > 23;
        INSERT INTO schema_meta (version, applied_at) VALUES (23, '2026-08-23T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()

    for _ in range(2):  # the second open must be a no-op
        with SqliteStore(db_path) as store:
            tables = {
                row[0]
                for row in store.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
                ).fetchall()
            }
            keys = store.conn.execute("SELECT encrypted_key FROM users").fetchall()
            invite = store.conn.execute("SELECT code FROM invite_codes").fetchone()
            version = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()

        assert not {name for name in tables if "llm_" in name}
        assert [tuple(row) for row in keys] == [(None,)]
        assert invite[0] == "preserve-me"
        assert version[0] == SCHEMA_VERSION == 25
