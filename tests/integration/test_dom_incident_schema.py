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
    if version == 13:
        conn.executescript(
            """
            DROP TABLE llm_profile_qualifications;
            DROP TABLE llm_cost_reservations;
            DROP TABLE llm_spend_days;
            """
        )
    conn.execute("DELETE FROM schema_meta WHERE version > ?", (version,))
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (version, applied_at) VALUES (?, ?)",
        (version, f"2026-08-{version:02d}T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()


def test_v13_to_v17_is_additive_and_preserves_existing_data(tmp_path: Path) -> None:
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

    assert versions[-5:] == [13, 14, 15, 16, 17]
    assert owner[0] == 111
    assert invite[0] == "preserve-me"
    assert SCHEMA_VERSION == 17
    assert {
        "llm_spend_days",
        "llm_cost_reservations",
        "llm_profile_qualifications",
        "dom_drift_incidents",
        "dom_drift_alerts",
        "dom_drift_diagnostics",
    } <= tables


def test_v14_to_v15_preserves_spend_and_qualification_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "v14.db"
    _downgrade_fixture(db_path, 14)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO llm_spend_days VALUES (?, ?, ?, ?, ?, ?)",
        (
            "2026-08-13",
            100,
            200,
            10_000_000,
            "anthropic-2026-08-12",
            "2026-08-13T00:00:00+00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO llm_profile_qualifications (
            qualification_id, profile_identity, fixture_version, runs,
            correct_runs, diagnosis_runs, diagnosis_correct_runs,
            schema_valid_runs, prohibited_action_proposals,
            prohibited_action_executions, escalation_count, total_calls,
            total_actions, input_tokens, output_tokens, latency_ms,
            estimated_micro_usd, gate_result, completed_at
        ) VALUES (
            'qualification-1', 'anthropic:sonnet-opus-v1', 'curated-v1',
            10, 10, 10, 10, 10, 0, 0, 1, 11, 2, 1000, 100, 500,
            3000, 'passed', '2026-08-13T00:00:00+00:00'
        )
        """
    )
    conn.commit()
    conn.close()

    with SqliteStore(db_path) as store:
        spend = store.conn.execute(
            "SELECT reserved_micro_usd, charged_micro_usd FROM llm_spend_days"
        ).fetchone()
        qualification = store.conn.execute(
            "SELECT gate_result FROM llm_profile_qualifications "
            "WHERE qualification_id = 'qualification-1'"
        ).fetchone()
        version = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()

    assert tuple(spend) == (100, 200)
    assert qualification[0] == "passed"
    assert version[0] == SCHEMA_VERSION == 17
