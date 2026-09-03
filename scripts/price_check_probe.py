"""Run one notification-free, production-equivalent owner price check.

This operator-only probe enters through the same coordinator method as Telegram ``/checknow``.
It therefore performs the configured inventory synchronization, shared budget admission, session
handling, price executor selection, BookSaver validation, and durable result recording without
sending user notifications.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sqlite3
import tempfile
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from booksaver.application.load_config import load_config
from booksaver.application.ports import ConfigSource
from booksaver.cli.commands import _make_check_coordinator
from booksaver.daemon.check_coordinator import (
    ImmediateAdmission,
    ImmediateCompletion,
    ImmediateCompletionKind,
)
from booksaver.domain.browser_executor import ExecutionRoutingMode, PriceExecutorKind
from booksaver.domain.check_result import CheckOutcome
from booksaver.domain.models import Config
from booksaver.infrastructure.config.toml_env_source import TomlEnvConfigSource
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAgenticQualificationRepository,
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)


class _IsolatedConfigSource(ConfigSource):
    def __init__(self, raw: dict[str, Any], data_directory: Path) -> None:
        self._raw = copy.deepcopy(raw)
        storage = self._raw.setdefault("storage", {})
        if not isinstance(storage, dict):
            raise RuntimeError("storage configuration must be a table")
        storage["data_directory"] = str(data_directory)

    def read(self) -> dict[str, Any]:
        return copy.deepcopy(self._raw)


def _clone_state(source_data: Path, isolated_data: Path) -> None:
    isolated_data.mkdir(mode=0o700, parents=True)
    source_db = source_data / "booksaver.db"
    if not source_db.exists():
        raise RuntimeError("production BookSaver database is missing")
    source_wal = source_data / "booksaver.db-wal"
    if source_wal.exists() and source_wal.stat().st_size:
        raise RuntimeError(
            "production BookSaver database still has an uncheckpointed WAL; stop the daemon "
            "cleanly before replay"
        )
    # A WAL-mode database normally asks SQLite to create coordination files even for a read-only
    # connection.  The production volume is deliberately mounted read-only for this probe, so use
    # immutable mode only after proving there is no uncheckpointed WAL to omit.
    source = sqlite3.connect(f"file:{source_db}?mode=ro&immutable=1", uri=True)
    target = sqlite3.connect(isolated_data / "booksaver.db")
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    (isolated_data / "booksaver.db").chmod(0o600)
    source_sessions = source_data / "booking_sessions"
    if not source_sessions.is_dir():
        raise RuntimeError("production encrypted session directory is missing")
    shutil.copytree(source_sessions, isolated_data / "booking_sessions")


def _selection(cfg: Config, booking_id: str | None) -> tuple[int, str]:
    with SqliteStore(cfg.data_directory.path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        if owner.telegram_user_id is None:
            raise RuntimeError("deployment owner has no Telegram identity")
        bookings = SqliteBookingRepository(store)
        selected = bookings.get_by_id(booking_id) if booking_id else None
        if selected is None:
            active = bookings.list_active_for_user(owner.user_id)
            if len(active) != 1:
                raise RuntimeError(
                    "pass --booking-id when the owner does not have one active booking"
                )
            selected = active[0]
        if bookings.get_owner_user_id(selected.booking_id) != owner.user_id:
            raise RuntimeError("selected booking is not owned by the deployment owner")
    return owner.telegram_user_id, selected.booking_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--booking-id")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= 300:
        parser.error("--timeout-seconds must be between 1 and 300")

    raw = TomlEnvConfigSource(args.config).read()
    production_cfg = load_config(TomlEnvConfigSource(args.config))
    with tempfile.TemporaryDirectory(prefix="booksaver-price-probe-") as root:
        isolated_data = Path(root) / "data"
        _clone_state(production_cfg.data_directory.path, isolated_data)
        cfg = load_config(_IsolatedConfigSource(raw, isolated_data))
        cfg.agentic_browser_settings = replace(
            cfg.agentic_browser_settings,
            routing=ExecutionRoutingMode.OWNER_CANARY,
            price_executor=PriceExecutorKind.BROWSER_USE,
        )
        telegram_user_id, booking_id = _selection(cfg, args.booking_id)
        completed = threading.Event()
        holder: list[ImmediateCompletion] = []

        def capture(completion: ImmediateCompletion) -> None:
            holder.append(completion)
            completed.set()

        coordinator = _make_check_coordinator(
            cfg,
            threading.Event(),
            notifier_builder_override=lambda _cfg: [],
        )
        admission = coordinator.request_immediate(
            telegram_user_id,
            booking_id,
            capture,
        )
        if admission is not ImmediateAdmission.ACCEPTED:
            print(json.dumps({"admission": admission.value}, sort_keys=True))
            return 2
        if not completed.wait(args.timeout_seconds):
            print(
                json.dumps(
                    {"admission": "accepted", "completion": "timeout"},
                    sort_keys=True,
                )
            )
            return 3
        completion = holder[0]
        result = completion.result
        payload: dict[str, object] = {
            "admission": admission.value,
            "completion": completion.kind.value,
            "booking_id": booking_id,
        }
        if result is not None:
            payload.update(
                {
                    "check_id": result.check_id,
                    "outcome": result.outcome.value,
                    "failure_code": (
                        result.failure_reason.code.value
                        if result.failure_reason is not None
                        else None
                    ),
                    "live_price_currency": (
                        result.live_price.currency if result.live_price is not None else None
                    ),
                    "source_channel": (
                        result.price_source.channel.value
                        if result.price_source is not None
                        else None
                    ),
                }
            )
            with SqliteStore(isolated_data / "booksaver.db") as store:
                owner = SqliteUserRepository(store).get_owner()
                check = next(
                    (
                        item
                        for item in SqliteAgenticQualificationRepository(store).list_checks(
                            owner.user_id
                        )
                        if item.check_id == result.check_id
                    ),
                    None,
                )
            if check is not None:
                payload.update(
                    {
                        "executor_policy": check.policy_version,
                        "valid_observation": check.valid_observation,
                        "model_cost_micro_usd": check.model_cost.micro_usd,
                        "duration_ms": check.duration_ms,
                        "fallback_used": check.fallback_used,
                        "violation_count": len(check.violations),
                    }
                )
        elif completion.unavailable_detail:
            payload["unavailable"] = True
        print(json.dumps(payload, sort_keys=True))
        return int(
            completion.kind is not ImmediateCompletionKind.RESULT
            or result is None
            or result.outcome is not CheckOutcome.SUCCESS
            or payload.get("valid_observation") is not True
            or payload.get("executor_policy") != "browser-use-price-v1"
        )


if __name__ == "__main__":
    raise SystemExit(main())
