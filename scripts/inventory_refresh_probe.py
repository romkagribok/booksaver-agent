"""Replay one caller's inventory with isolated state and no Telegram notifications.

Run only after the production daemon has been stopped and its data volume mounted read-only.
Like the daemon, this keeps the selected caller, production config, disclosure,
and session. The deployment must use its usual single coordinator again after replay completes.
"""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
import threading
from pathlib import Path

from booksaver.application.load_config import load_config
from booksaver.cli.commands import _make_check_coordinator
from booksaver.daemon.check_coordinator import ImmediateAdmission, InventoryCompletion
from booksaver.domain.models import Config
from booksaver.infrastructure.config.toml_env_source import TomlEnvConfigSource
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteInventoryExecutionMetricsRepository,
    SqliteStore,
    SqliteUserRepository,
)
from scripts.price_check_probe import _clone_state, _IsolatedConfigSource


def _caller(cfg: Config, user_id: int) -> int:
    with SqliteStore(cfg.data_directory.path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_by_id(user_id)
        if user is None or not user.is_active or user.telegram_user_id is None:
            raise ValueError("Selected caller must be active and linked to Telegram")
        return user.telegram_user_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    args = parser.parse_args()
    if args.user_id < 1:
        parser.error("--user-id must be positive")
    logging.basicConfig(level=logging.WARNING)
    source = TomlEnvConfigSource(args.config)
    raw = source.read()
    production_cfg = load_config(source)
    with tempfile.TemporaryDirectory(prefix="booksaver-inventory-probe-") as root:
        isolated_data = Path(root) / "data"
        _clone_state(production_cfg.data_directory.path, isolated_data)
        cfg = load_config(_IsolatedConfigSource(raw, isolated_data))
        telegram_user_id = _caller(cfg, args.user_id)
        done = threading.Event()
        stop = threading.Event()
        results: list[InventoryCompletion] = []

        def capture(completion: InventoryCompletion) -> None:
            results.append(completion)
            done.set()

        coordinator = _make_check_coordinator(
            cfg, stop, auth_required_notifier=None,
            notifier_builder_override=lambda _cfg: [],
        )
        with SqliteStore(isolated_data / "booksaver.db") as store:
            if not coordinator._is_active_user(store, args.user_id):
                raise ValueError("Caller is not an active user")
        admission = coordinator.request_inventory(telegram_user_id, capture)
        if admission is not ImmediateAdmission.ACCEPTED:
            print(json.dumps({"admission": admission.value}))
            return 2
        if not done.wait(300):
            stop.set()
            print(json.dumps({"completion": "timeout"}))
            return 3
        report = results[0].report
        if report is None:
            print(json.dumps({"completion": "unavailable"}))
            return 2
        payload: dict[str, object] = {
            "user_id": args.user_id,
            "completeness": report.completeness.value,
            "failure_code": report.failure_code.value if report.failure_code else None,
            "discovered": report.discovered,
            "eligible": report.eligible,
            "empty_upcoming": report.upcoming_empty_observed,
        }
        with SqliteStore(isolated_data / "booksaver.db") as store:
            metrics = SqliteInventoryExecutionMetricsRepository(store).get_for_run(
                user_id=args.user_id, run_id=report.run_id,
            )
        if metrics is not None:
            payload.update({
                "terminal": metrics.terminal_status,
                "accepted": metrics.accepted_count,
                "rejected": metrics.rejected_count,
                "model_cost_micro_usd": metrics.model_cost_micro_usd,
                "duration_ms": metrics.latency_ms,
            })
        print(json.dumps(payload, sort_keys=True))
        return int(not (
            report.accepted_positive_observations or report.upcoming_empty_observed
        ))


if __name__ == "__main__":
    raise SystemExit(main())
