from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from scripts import inventory_refresh_probe as probe

from booksaver.application.load_config import load_config
from booksaver.daemon.check_coordinator import (
    CheckCoordinator,
    ImmediateAdmission,
    InventoryCompletion,
)
from booksaver.domain.account_sync import InventoryCompleteness, SynchronizationReport
from booksaver.domain.models import Config
from booksaver.domain.user import UserAccessState, UserRole
from booksaver.infrastructure.config.toml_env_source import TomlEnvConfigSource
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAgenticDisclosureConsentRepository,
    SqliteStore,
    SqliteUserRepository,
)


def _production(tmp_path: Path) -> tuple[Path, Config, int]:
    data = tmp_path / "production"
    data.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[storage]\ndata_directory = "{data}"\n'
        '[agentic_browser]\nprice_executor = "jev"\n',
    )
    cfg = load_config(TomlEnvConfigSource(config_path))
    with SqliteStore(data / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        users.link_telegram_id(owner.user_id, 111111)
        invitee = users.get_or_create_by_telegram_id(222222, UserRole.USER)
    sessions = data / "booking_sessions"
    sessions.mkdir()
    (sessions / "test.session").write_bytes(b"PRIVATE-ENCRYPTED-SESSION")
    return config_path, cfg, invitee.user_id


def test_caller_selects_exact_invitee_without_owner_fallback(tmp_path: Path) -> None:
    _config_path, cfg, invitee_id = _production(tmp_path)

    assert probe._caller(cfg, invitee_id) == 222222
    with pytest.raises(ValueError, match="Selected caller"):
        probe._caller(cfg, 999999)


@pytest.mark.parametrize("state", ["revoked", "unlinked"])
def test_caller_refuses_unavailable_selected_user(tmp_path: Path, state: str) -> None:
    _config_path, cfg, invitee_id = _production(tmp_path)
    with SqliteStore(cfg.data_directory.path / "booksaver.db") as store:
        if state == "revoked":
            SqliteUserRepository(store).set_access_state(invitee_id, UserAccessState.REVOKED)
        else:
            store.conn.execute(
                "UPDATE users SET telegram_user_id = NULL WHERE user_id = ?", (invitee_id,),
            )
            store.conn.commit()

    with pytest.raises(ValueError, match="Selected caller"):
        probe._caller(cfg, invitee_id)


@pytest.mark.parametrize("consent", ["current", "missing", "stale"])
def test_probe_preserves_caller_routing_and_consent_without_notifications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    consent: str,
) -> None:
    config_path, cfg, invitee_id = _production(tmp_path)
    if consent != "missing":
        with SqliteStore(cfg.data_directory.path / "booksaver.db") as store:
            SqliteAgenticDisclosureConsentRepository(store).acknowledge(
                user_id=invitee_id,
                disclosure_version=(
                    cfg.agentic_browser_settings.disclosure_version
                    if consent == "current" else "old-disclosure"
                ),
                acknowledged_at=datetime.now(UTC),
            )
    requested: list[int] = []
    admitted: list[int] = []

    class _Coordinator:
        def __init__(self, isolated_cfg: Config) -> None:
            self._config = isolated_cfg
            self._inventory_synchronizer = None

        def _is_active_user(self, store: SqliteStore, user_id: int) -> bool:
            admitted.append(user_id)
            return CheckCoordinator._is_active_user(store, user_id)

        def request_inventory(self, telegram_user_id: int, callback: Any) -> ImmediateAdmission:
            requested.append(telegram_user_id)
            # A fake worker mutates only the disposable clone, just as actual replay would.
            session = self._config.data_directory.path / "booking_sessions" / "test.session"
            assert session.read_bytes() == b"PRIVATE-ENCRYPTED-SESSION"
            session.write_bytes(b"ISOLATED-REFRESH")
            callback(InventoryCompletion(SynchronizationReport(
                run_id="test-empty-run",
                completeness=InventoryCompleteness.INCOMPLETE,
                discovered=0,
                eligible=0,
                ineligible=0,
                upcoming_empty_observed=True,
            )))
            return ImmediateAdmission.ACCEPTED

    def make_coordinator(isolated_cfg: Config, _stop: Any, **kwargs: Any) -> _Coordinator:
        assert isolated_cfg.data_directory.path != cfg.data_directory.path
        assert isolated_cfg.agentic_browser_settings == cfg.agentic_browser_settings
        assert kwargs["auth_required_notifier"] is None
        assert kwargs["notifier_builder_override"](isolated_cfg) == []
        return _Coordinator(isolated_cfg)

    monkeypatch.setattr(probe, "_make_check_coordinator", make_coordinator)
    monkeypatch.setattr("sys.argv", [
        "inventory_refresh_probe", "--config", str(config_path), "--user-id", str(invitee_id),
    ])

    # ADR-062: disclosure no longer gates an invitee, so every consent state is admitted.
    assert probe.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["user_id"] == invitee_id
    assert payload["empty_upcoming"] is True
    assert requested == [222222]
    assert "PRIVATE" not in json.dumps(payload)
    assert admitted == [invitee_id]
    assert (cfg.data_directory.path / "booking_sessions" / "test.session").read_bytes() == (
        b"PRIVATE-ENCRYPTED-SESSION"
    )
