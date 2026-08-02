"""US-063: optional Telegram username persistence and schema-v9 migration."""

import sqlite3
from pathlib import Path

import pytest

from booksaver.infrastructure.persistence.sqlite_store import (
    SCHEMA_VERSION,
    SqliteStore,
    SqliteUserRepository,
)

_V8_USERS_DDL = """\
CREATE TABLE schema_meta (version INTEGER NOT NULL, applied_at TEXT NOT NULL);
INSERT INTO schema_meta VALUES (8, '2026-07-11T00:00:00+00:00');
CREATE TABLE users (
    user_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE,
    role             TEXT    NOT NULL CHECK(role IN ('owner', 'user')),
    access_state     TEXT    NOT NULL DEFAULT 'active'
        CHECK(access_state IN ('active', 'revoked')),
    encrypted_key    BLOB,
    created_at       TEXT    NOT NULL
);
CREATE UNIQUE INDEX idx_users_single_owner
    ON users(role) WHERE role = 'owner';
CREATE TABLE invite_codes (
    code       TEXT PRIMARY KEY,
    issued_by  INTEGER NOT NULL REFERENCES users(user_id),
    issued_at  TEXT NOT NULL,
    expires_at TEXT,
    used_by    INTEGER REFERENCES users(user_id),
    used_at    TEXT
);
INSERT INTO users VALUES (
    1, 111, 'owner', 'active', NULL, '2026-07-11T00:00:00+00:00'
);
INSERT INTO users VALUES (
    2, 222, 'user', 'active', X'63697068657274657874',
    '2026-07-11T00:01:00+00:00'
);
INSERT INTO invite_codes VALUES (
    'preserved-code', 1, '2026-07-11T00:02:00+00:00', NULL, 2,
    '2026-07-11T00:03:00+00:00'
);
"""


def _make_v8_db(db_path: Path, *, username_column_exists: bool = False) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_V8_USERS_DDL)
    if username_column_exists:
        conn.execute("ALTER TABLE users ADD COLUMN telegram_username TEXT")
    conn.commit()
    conn.close()


class TestSchemaV9Migration:
    def test_fresh_database_has_optional_username_column(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "fresh.db") as store:
            columns = {r[1] for r in store.conn.execute("PRAGMA table_info(users)")}
            owner = SqliteUserRepository(store).get_owner()
            version = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()

        assert version[0] == SCHEMA_VERSION == 13
        assert "telegram_username" in columns
        assert owner.telegram_username is None

    def test_v8_migration_preserves_users_keys_and_invites(self, tmp_path: Path) -> None:
        db_path = tmp_path / "v8.db"
        _make_v8_db(db_path)

        with SqliteStore(db_path) as store:
            repo = SqliteUserRepository(store)
            invited = repo.get_by_id(2)
            invite = store.conn.execute(
                "SELECT code, used_by FROM invite_codes WHERE code = 'preserved-code'"
            ).fetchone()
            versions = [
                r[0]
                for r in store.conn.execute(
                    "SELECT version FROM schema_meta ORDER BY version"
                ).fetchall()
            ]

        assert invited is not None
        assert invited.telegram_user_id == 222
        assert invited.telegram_username is None
        assert invited.encrypted_key == b"ciphertext"
        assert tuple(invite) == ("preserved-code", 2)
        assert versions == [8, 9, 10, 11, 12, 13]

    def test_v9_migration_is_guarded_and_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "partial-v9.db"
        _make_v8_db(db_path, username_column_exists=True)

        with SqliteStore(db_path):
            pass
        with SqliteStore(db_path) as store:
            columns = [
                r[1]
                for r in store.conn.execute("PRAGMA table_info(users)").fetchall()
            ]
            versions = [
                r[0]
                for r in store.conn.execute(
                    "SELECT version FROM schema_meta ORDER BY version"
                ).fetchall()
            ]

        assert columns.count("telegram_username") == 1
        assert versions == [8, 9, 10, 11, 12, 13]


class TestTelegramUsernameRepository:
    def test_normalizes_updates_and_clears_username_only_on_change(
        self, tmp_path: Path
    ) -> None:
        with SqliteStore(tmp_path / "users.db") as store:
            repo = SqliteUserRepository(store)
            user = repo.get_or_create_by_telegram_id(222)

            before = store.conn.total_changes
            assert repo.set_telegram_username(user.user_id, "  @RomanMarchuk  ")
            after_first = store.conn.total_changes
            assert not repo.set_telegram_username(user.user_id, "@RomanMarchuk")
            after_same = store.conn.total_changes
            stored = repo.get_by_id(user.user_id)

            assert repo.set_telegram_username(user.user_id, None)
            after_clear = store.conn.total_changes
            assert not repo.set_telegram_username(user.user_id, "  @  ")
            after_empty = store.conn.total_changes
            cleared = repo.get_by_id(user.user_id)

        assert after_first == before + 1
        assert after_same == after_first
        assert stored is not None and stored.telegram_username == "RomanMarchuk"
        assert after_clear == after_same + 1
        assert after_empty == after_clear
        assert cleared is not None and cleared.telegram_username is None

    def test_unknown_user_update_raises(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "users.db") as store:
            repo = SqliteUserRepository(store)
            with pytest.raises(KeyError, match="No user with id '999'"):
                repo.set_telegram_username(999, "nobody")

    def test_purge_removes_username_with_user_row(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "users.db") as store:
            repo = SqliteUserRepository(store)
            user = repo.get_or_create_by_telegram_id(222)
            repo.set_telegram_username(user.user_id, "@temporary")

            repo.purge(user.user_id)

            assert repo.get_by_id(user.user_id) is None
            assert (
                store.conn.execute(
                    "SELECT telegram_username FROM users WHERE user_id = ?",
                    (user.user_id,),
                ).fetchone()
                is None
            )
