from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from booksaver.application.load_config import load_config
from booksaver.application.schedule_dispatcher import RandomizedScheduleDispatcher
from booksaver.daemon import lifecycle
from booksaver.daemon import scheduler as scheduler_mod
from booksaver.domain.account_sync import SynchronizationTrigger
from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.models import Config
from booksaver.infrastructure.config.toml_env_source import (
    DEFAULT_CONFIG_PATH,
    TomlEnvConfigSource,
)
from booksaver.infrastructure.persistence.scheduled_check_slots import (
    SqliteScheduledCheckSlotRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteCheckHistoryRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.client import TelegramBotClient

_SAMPLE_CONFIG = """\
[schedule]
# Each eligible booking is checked once in each broadly distributed random UTC slot.
checks_per_booking_per_day = 3
minimum_spacing = "2h"
missed_run_grace = "1h"

[storage]
data_directory = "~/.booksaver"  # Where all BookSaver data is stored — local only

[browser]
# Authenticated monitoring always uses an allowlisted mobile Chromium profile.
# device_profile = "android-chromium"
# locale = "en-US"
# timezone_id = "UTC"

[notifications]
# Non-secret identifiers go here. Secrets come from environment variables.
# email = "your@email.com"           # alert recipient
# smtp_host = "smtp.gmail.com"       # sender SMTP server (STARTTLS)
# smtp_port = 587
# smtp_username = "your@email.com"   # SMTP login + From; pw: export BOOKSAVER_SMTP_PASSWORD=...
# telegram_chat_id = "123456789"     # token:    export BOOKSAVER_TELEGRAM_BOT_TOKEN=...

[extraction]
# Legacy extraction model values normalize to the fixed primary profile.
# primary selection is controlled by the approved [agent] portfolio below.

[agent]
# Outer cost caps per price check (ADR-017) plus tighter per-step recovery limits
# (ADR-030). Existing config files may omit the recovery keys and receive these defaults.
# primary_model = "claude-sonnet-5"  # normal ambiguous DOM assistance
# escalation_model = "claude-opus-5" # one measured quality escalation; Fable prohibited
# max_job_cost_usd = "1.00"           # one coordinator browser admission
# max_deployment_daily_cost_usd = "10.00" # persisted deployment-wide UTC cap
# reserve_opus_diagnostic_for_ambiguous_episode = true
# max_steps = 15              # LLM browser-agent turns (screenshot turns count double)
# max_llm_calls = 20          # all LLM calls in one check (agent + extraction)
# check_timeout_seconds = 180 # wall-clock limit per booking check
# max_recovery_calls_per_step = 4      # actual LLM calls for one failed browser step
# recovery_timeout_seconds = 60        # wall-clock limit for that recovery episode
# screenshot_after_no_progress = 2     # force fresh visual evidence after no progress
# max_semantic_action_executions = 2   # never execute an equivalent target a third time

[telegram_bot]
# Private invite-only Telegram bot gateway. Token: export BOOKSAVER_TELEGRAM_BOT_TOKEN=...
# enabled = false
# owner_chat_id = 123456789   # required when enabled; owner/admin Telegram chat
# poll_timeout_seconds = 30   # long-poll timeout, clamped to 25-50

[remote_auth]
# Phone-first Booking.com login through a Telegram Mini App and temporary VPS browser.
# Requires a public DNS name pointing at Caddy on this VPS.
# enabled = false
# public_url = "https://connect.example.com"
# session_timeout_seconds = 600

[limits]
# Per-user abuse/fairness limits for multi-user Telegram deployments (US-031).
# max_checks_per_user_per_day = 48   # price checks per user per day before skipping
# max_llm_calls_per_user_per_day = 200  # shared scheduled/manual daily LLM ceiling
# messages_per_minute_per_chat = 20  # outbound bot replies per chat per minute
"""


def _sample_config(data_path: Path) -> str:
    """Return the starter config bound to the directory requested by ``init``."""
    encoded_path = json.dumps(str(data_path))
    return _SAMPLE_CONFIG.replace(
        'data_directory = "~/.booksaver"', f"data_directory = {encoded_path}"
    )


def _config_path(args: argparse.Namespace) -> Path:
    if getattr(args, "config", None):
        return Path(args.config)
    env = os.environ.get("BOOKSAVER_CONFIG")
    return Path(env) if env else DEFAULT_CONFIG_PATH


def _db_path_for(args: argparse.Namespace) -> tuple[Config, Path]:
    cfg = _load_config_for_args(args)
    return cfg, cfg.data_directory.path / "booksaver.db"


def _load_config_for_args(args: argparse.Namespace) -> Config:
    source = TomlEnvConfigSource(_config_path(args))
    try:
        cfg = load_config(source)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except ConfigValidationError as e:
        print("Config validation failed:", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(2)
    return cfg


# ── init ─────────────────────────────────────────────────────────────────────


def cmd_init(args: argparse.Namespace) -> int:
    data_dir_str = getattr(args, "data_dir", None) or str(Path.home() / ".booksaver")
    data_path = Path(data_dir_str).expanduser().resolve()
    config_path = data_path / "config.toml"

    data_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    print(f"Data directory : {data_path}")

    if config_path.exists():
        print(f"Config exists  : {config_path}  (not overwritten)")
    else:
        config_path.write_text(_sample_config(data_path))
        config_path.chmod(0o600)
        print(f"Config created : {config_path}")
        print()
        print("Next: edit the config, then run:  booksaver config validate")

    return 0


# ── config validate ───────────────────────────────────────────────────────────


def cmd_config_validate(args: argparse.Namespace) -> int:
    source = TomlEnvConfigSource(_config_path(args))
    try:
        cfg = load_config(source)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except ConfigValidationError as e:
        print("Config validation failed:", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        return 2

    print("Config is valid.")
    schedule = cfg.schedule_settings
    print(f"  checks_per_booking_per_day : {schedule.checks_per_booking_per_day}")
    print(f"  minimum_spacing            : {schedule.minimum_spacing}")
    print(f"  missed_run_grace           : {schedule.missed_run_grace}")
    print(f"  data_directory : {cfg.data_directory.path}")
    agent = cfg.agent_settings
    print(f"  agent_recovery_calls/step  : {agent.max_recovery_calls_per_step}")
    print(f"  agent_recovery_timeout_s   : {agent.recovery_timeout_seconds}")
    print(f"  screenshot_after_no_progress: {agent.screenshot_after_no_progress}")
    print(f"  semantic_action_executions: {agent.max_semantic_action_executions}")
    print(f"  agent_primary_model         : {agent.primary_model}")
    print(f"  agent_escalation_model      : {agent.escalation_model}")
    print(f"  agent_job_cost_usd         : {agent.max_job_cost_micro_usd / 1_000_000:.2f}")
    print(
        f"  deployment_daily_cost_usd : {agent.max_deployment_daily_cost_micro_usd / 1_000_000:.2f}"
    )
    return 0


# ── config show ───────────────────────────────────────────────────────────────


def cmd_config_show(args: argparse.Namespace) -> int:
    source = TomlEnvConfigSource(_config_path(args))
    try:
        cfg = load_config(source)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except ConfigValidationError as e:
        print("Config validation failed:", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        return 2

    ns = cfg.notification_settings
    tb = cfg.telegram_bot_settings
    lim = cfg.limits_settings
    mobile = cfg.mobile_web_settings
    remote_auth = cfg.remote_auth_settings
    schedule = cfg.schedule_settings
    agent = cfg.agent_settings
    print(f"schedule.checks_per_booking/day: {schedule.checks_per_booking_per_day}")
    print(f"schedule.minimum_spacing     : {schedule.minimum_spacing}")
    print(f"schedule.missed_run_grace    : {schedule.missed_run_grace}")
    print(f"data_directory               : {cfg.data_directory.path}")
    print(f"notifications.email          : {ns.email or '(not set)'}")
    print(f"notifications.telegram_chat_id: {ns.telegram_chat_id or '(not set)'}")
    print(f"telegram_bot.enabled         : {tb.enabled}")
    print(f"telegram_bot.owner_chat_id   : {tb.owner_chat_id or '(not set)'}")
    print(f"telegram_bot.poll_timeout_s  : {tb.poll_timeout_seconds}")
    print(f"limits.max_checks_per_user/day: {lim.max_checks_per_user_per_day}")
    print(f"limits.max_llm_calls_per_user/day: {lim.max_llm_calls_per_user_per_day}")
    print(f"limits.messages_per_min/chat : {lim.messages_per_minute_per_chat}")
    print(f"browser.device_profile       : {mobile.profile_id.value}")
    print(f"browser.locale               : {mobile.locale}")
    print(f"browser.timezone_id          : {mobile.timezone_id}")
    print(f"agent.primary_model          : {agent.primary_model}")
    print(f"agent.escalation_model       : {agent.escalation_model}")
    print(f"agent.max_job_cost_usd       : {agent.max_job_cost_micro_usd / 1_000_000:.2f}")
    print(
        "agent.max_deployment_daily_cost_usd: "
        f"{agent.max_deployment_daily_cost_micro_usd / 1_000_000:.2f}"
    )
    print(f"agent.max_steps              : {agent.max_steps}")
    print(f"agent.max_llm_calls          : {agent.max_llm_calls}")
    print(f"agent.check_timeout_s        : {agent.check_timeout_seconds}")
    print(f"agent.recovery_calls/step   : {agent.max_recovery_calls_per_step}")
    print(f"agent.recovery_timeout_s     : {agent.recovery_timeout_seconds}")
    print(f"agent.screenshot_after_no_progress: {agent.screenshot_after_no_progress}")
    print(f"agent.semantic_action_executions: {agent.max_semantic_action_executions}")
    print(f"remote_auth.enabled          : {remote_auth.enabled}")
    print(f"remote_auth.public_url       : {remote_auth.public_url or '(not set)'}")
    smtp = "(set)" if os.environ.get("BOOKSAVER_SMTP_PASSWORD") else "(not set)"
    tg = "(set)" if os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN") else "(not set)"
    llm = "(set)" if os.environ.get("BOOKSAVER_LLM_API_KEY") else "(not set)"
    print(f"BOOKSAVER_SMTP_PASSWORD      : {smtp}")
    print(f"BOOKSAVER_TELEGRAM_BOT_TOKEN : {tg}")
    print(f"BOOKSAVER_LLM_API_KEY        : {llm}")
    return 0


# ── bookings list ─────────────────────────────────────────────────────────────


def cmd_bookings_list(args: argparse.Namespace) -> int:
    cfg, db_path = _db_path_for(args)

    if not db_path.exists():
        print("No synchronized reservations yet.")
        return 0

    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        reservations = SqliteAccountReservationRepository(store).list_for_user(owner.user_id)

    if not reservations:
        print("No synchronized reservations found.")
        return 0

    header = (
        f"{'ID':8}  {'CONFIRMATION':20}  {'PROPERTY':25}  "
        f"{'CHECK-IN':10}  {'CHECK-OUT':10}  {'TOTAL':>14}  {'LIFECYCLE':10}  ELIGIBILITY"
    )
    print(header)
    print("-" * len(header))
    for reservation in reservations:
        item = reservation.observation
        total = (
            f"{item.booked_total.amount} {item.booked_total.currency}"
            if item.booked_total is not None
            else "unavailable"
        )
        eligibility = (
            "eligible"
            if reservation.eligibility.is_eligible
            else ", ".join(reason.value for reason in reservation.eligibility.reasons)
        )
        print(
            f"{reservation.account_reservation_id[:8]:8}  "
            f"{(item.confirmation_id or 'unavailable')[:20]:20}  "
            f"{(item.property_name or 'unavailable')[:25]:25}  "
            f"{str(item.check_in or 'unknown'):10}  "
            f"{str(item.check_out or 'unknown'):10}  "
            f"{total:>14}  "
            f"{item.lifecycle.value:10}  "
            f"{eligibility}"
        )
    return 0


def cmd_bookings_trace(args: argparse.Namespace) -> int:
    """Show one owner-scoped, content-free inventory recovery audit."""
    _cfg, db_path = _db_path_for(args)
    if not db_path.exists():
        print("No local database yet.", file=sys.stderr)
        return 2

    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        audit = SqliteAccountReservationRepository(store).recovery_audit_for_run(
            user_id=owner.user_id,
            run_id=args.run_id,
        )
    if audit is None:
        print(
            f"No owner-scoped inventory recovery audit found for '{args.run_id}'.",
            file=sys.stderr,
        )
        return 2

    print(f"Run      : {args.run_id}")
    print(f"Outcome  : {audit.outcome.value}")
    print(f"Step     : {audit.step or 'none'}")
    print(f"Providers: {', '.join(audit.providers) or 'none'}")
    print(f"Models   : {', '.join(audit.models) or 'none'}")
    print(f"Roles    : {', '.join(audit.roles) or 'none'}")
    print(f"Prompts  : {', '.join(audit.prompt_versions) or 'none'}")
    print(
        f"Usage    : calls={audit.llm_calls_used}; "
        f"tokens={audit.input_tokens}in/{audit.output_tokens}out; "
        f"actions={audit.action_count}; duration={audit.duration_ms}ms"
    )
    print("Events:")
    for event in audit.trace:
        print(json.dumps(event.as_dict(), sort_keys=True, separators=(",", ":")))
    return 0


# ── run ───────────────────────────────────────────────────────────────────────


def cmd_run(args: argparse.Namespace) -> int:
    source = TomlEnvConfigSource(_config_path(args))
    try:
        cfg = load_config(source)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except ConfigValidationError as e:
        print("Config validation failed:", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        return 2

    sched = scheduler_mod.Scheduler()
    browser_gate = threading.Lock()
    db_path = cfg.data_directory.path / "booksaver.db"
    telegram_client = None
    remote_auth_runtime = None
    telegram_token = os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN")
    if cfg.telegram_bot_settings.enabled and telegram_token:
        telegram_client = TelegramBotClient(bot_token=telegram_token)

    coordinator = _make_check_coordinator(
        cfg,
        sched.stop_event,
        execution_gate=browser_gate,
    )

    def _synchronize_after_connect(telegram_user_id: int) -> None:
        assert telegram_client is not None

        def _completed(completion: Any) -> None:
            report = completion.report
            if report is not None and report.succeeded:
                telegram_client.send_message(
                    telegram_user_id,
                    "Booking.com reservations synchronized: "
                    f"{report.discovered} found, {report.eligible} eligible for "
                    "price-drop checks. Send /bookings for details.",
                )
            else:
                detail = (
                    report.failure_detail
                    if report is not None and report.failure_detail
                    else "the reservation inventory could not be refreshed"
                )
                telegram_client.send_message(
                    telegram_user_id,
                    f"Connected, but {detail} Send /bookings to retry.",
                )

        admission = coordinator.request_inventory(
            telegram_user_id,
            _completed,
            trigger=SynchronizationTrigger.CONNECT,
        )
        if admission.value != "accepted":
            telegram_client.send_message(
                telegram_user_id,
                "Connected. Reservation refresh is busy; send /bookings shortly.",
            )

    if cfg.remote_auth_settings.enabled:
        if telegram_client is None or telegram_token is None:
            print(
                "Error: remote_auth.enabled requires BOOKSAVER_TELEGRAM_BOT_TOKEN.",
                file=sys.stderr,
            )
            return 2
        from booksaver.infrastructure.remote_auth.runtime import (
            build_remote_auth_runtime,
        )

        remote_auth_runtime = build_remote_auth_runtime(
            cfg,
            db_path,
            sched.stop_event,
            telegram_token,
            telegram_client,
            browser_gate,
            on_connected=_synchronize_after_connect,
            adaptive_runtime_scope=(coordinator.adaptive_runtime_scope_for_telegram_user),
        )
        coordinator.set_auth_required_notifier(remote_auth_runtime.reconnect_notifier.notify)

    @contextmanager
    def _schedule_repository() -> Iterator[SqliteScheduledCheckSlotRepository]:
        with SqliteStore(db_path) as store:
            yield SqliteScheduledCheckSlotRepository(store)

    def _active_user_ids() -> tuple[int, ...]:
        with SqliteStore(db_path) as store:
            return tuple(user.user_id for user in SqliteUserRepository(store).list_active())

    schedule_dispatcher = RandomizedScheduleDispatcher(
        settings=cfg.schedule_settings,
        repository_factory=_schedule_repository,
        active_user_ids=_active_user_ids,
        coordinator=coordinator,
        stop_event=sched.stop_event,
    )
    sched.register("booking_com_check", schedule_dispatcher.run_once)

    bot_runner = None
    if cfg.telegram_bot_settings.enabled:
        from booksaver.infrastructure.telegram.gateway import build_bot_runner

        bot_runner = build_bot_runner(
            cfg,
            db_path,
            sched,
            client=telegram_client,
            check_coordinator=coordinator,
            remote_auth_manager=(
                remote_auth_runtime.manager if remote_auth_runtime is not None else None
            ),
        )
        print("Telegram bot gateway: " + ("enabled" if bot_runner else "disabled (see logs)"))
    if remote_auth_runtime is not None:
        print(f"Remote authentication gateway: {cfg.remote_auth_settings.public_url}")

    incident_runner = _make_dom_incident_runner(cfg, db_path, telegram_client)
    service_runners: dict[str, Any] = {}
    if remote_auth_runtime is not None:
        service_runners["remote-auth"] = remote_auth_runtime.run
    if incident_runner is not None:
        service_runners["dom-drift-incidents"] = incident_runner

    print(
        "BookSaver daemon starting "
        f"(random_checks_per_day={cfg.schedule_settings.checks_per_booking_per_day}, "
        f"minimum_spacing={cfg.schedule_settings.minimum_spacing}, "
        f"data={cfg.data_directory.path})"
    )
    print("Press Ctrl-C or send SIGTERM to stop cleanly.")
    lifecycle.start(
        cfg,
        sched,
        bot_runner=bot_runner,
        service_runners=service_runners or None,
    )
    return 0


def _make_dom_incident_runner(
    cfg: Config,
    db_path: Path,
    telegram_client: TelegramBotClient | None,
) -> Callable[[threading.Event], None] | None:
    """Build the isolated incident maintenance service for Telegram deployments."""

    settings = cfg.telegram_bot_settings
    if not settings.enabled or settings.owner_chat_id is None or telegram_client is None:
        return None

    from booksaver.application.dom_incident import DomIncidentLifecycleWorker
    from booksaver.infrastructure.notifications.owner_incident import (
        OwnerIncidentTelegramNotifier,
    )
    from booksaver.infrastructure.persistence.dom_incident import (
        SqliteDomIncidentRepository,
    )
    from booksaver.infrastructure.persistence.encrypted_diagnostics import (
        EncryptedDiagnosticStore,
    )

    @contextmanager
    def _incidents() -> Iterator[Any]:
        with SqliteStore(db_path) as store:
            yield SqliteDomIncidentRepository(store)

    @contextmanager
    def _diagnostics() -> Iterator[Any]:
        with SqliteStore(db_path) as store:
            yield EncryptedDiagnosticStore(store)

    owner_chat_id = settings.owner_chat_id
    assert owner_chat_id is not None

    def _run(stop_event: threading.Event) -> None:
        # Each retry/maintenance operation owns a short-lived connection on the
        # service thread. Browser work and cleanup never share or wait on it.
        DomIncidentLifecycleWorker(
            incident_repository_factory=_incidents,
            diagnostic_store_factory=_diagnostics,
            notifier=OwnerIncidentTelegramNotifier(
                client=telegram_client,
                owner_chat_id=owner_chat_id,
            ),
        ).run(stop_event)

    return _run


def _make_check_coordinator(
    cfg: Config,
    stop_event: Any,
    auth_required_notifier: Any = None,
    execution_gate: threading.Lock | None = None,
) -> Any:
    """Build the one daemon-lifetime boundary shared by scheduler and Telegram."""
    from booksaver.application.dom_incident import DomIncidentRecorder
    from booksaver.daemon.check_coordinator import CheckCoordinator
    from booksaver.infrastructure.persistence.dom_incident import (
        SqliteDomIncidentRepository,
    )
    from booksaver.infrastructure.persistence.encrypted_diagnostics import (
        EncryptedDiagnosticStore,
    )

    @contextmanager
    def _incident_recorder() -> Iterator[DomIncidentRecorder]:
        # CheckCoordinator enters this only after the relevant browser context
        # has closed. The short-lived store cannot retain browser authority.
        with SqliteStore(cfg.data_directory.path / "booksaver.db") as store:
            yield DomIncidentRecorder(
                incidents=SqliteDomIncidentRepository(store),
                diagnostics=EncryptedDiagnosticStore(store),
            )

    return CheckCoordinator(
        cfg,
        stop_event,
        llm_factory_builder=lambda config, store: _make_llm_client_factory(config, store=store),
        notifier_builder=_make_notifiers,
        invalid_key_notifier=_notify_invalid_user_keys,
        auth_required_notifier=auth_required_notifier,
        execution_gate=execution_gate,
        incident_recorder_factory=_incident_recorder,
    )


def _notify_invalid_user_keys(user_repo: Any, results: list[Any]) -> None:
    """US-027: when a check failed with USER_KEY_INVALID, tell the booking's
    owner via a direct Telegram message (best-effort — a missing bot token or
    a user with no Telegram identity just means no message is sent, never a
    raised error). Kept self-contained here rather than routed through the
    general savings/alert notifier, which only handles savings opportunities.
    """
    import logging

    from booksaver.domain.check_result import FailureCode

    invalid = [
        r
        for r in results
        if r.failure_reason is not None and r.failure_reason.code is FailureCode.USER_KEY_INVALID
    ]
    if not invalid:
        return

    token = os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN")
    if not token:
        return

    from booksaver.infrastructure.telegram.client import TelegramBotClient

    client = TelegramBotClient(bot_token=token)
    notified_users: set[int] = set()
    for result in invalid:
        owner = user_repo.get_owner_of_booking(result.booking_id)
        if (
            owner is None
            or not owner.is_active
            or owner.telegram_user_id is None
            or owner.user_id in notified_users
        ):
            continue
        notified_users.add(owner.user_id)
        try:
            client.send_message(
                owner.telegram_user_id,
                "Your personal Anthropic key failed on a recent price check. "
                "Send /setkey to replace it, or /deletekey to revert to the shared key.",
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "Could not notify user %s about an invalid personal key", owner.user_id
            )


def _make_notifiers(cfg: Config) -> list[Any]:
    """Build the configured notification channels; unconfigured ones are skipped."""
    import logging

    notifiers: list[Any] = []
    ns = cfg.notification_settings

    smtp_password = os.environ.get("BOOKSAVER_SMTP_PASSWORD")
    if ns.email and ns.smtp_host and ns.smtp_username and smtp_password:
        from booksaver.infrastructure.notifications.smtp_notifier import SmtpEmailNotifier

        notifiers.append(
            SmtpEmailNotifier(
                host=ns.smtp_host,
                port=ns.smtp_port,
                username=ns.smtp_username,
                password=smtp_password,
                recipient=ns.email,
            )
        )
    else:
        logging.getLogger(__name__).info(
            "Email channel not fully configured (need notifications.email/smtp_host/"
            "smtp_username + BOOKSAVER_SMTP_PASSWORD) — skipping"
        )

    telegram_token = os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN")
    if ns.telegram_chat_id and telegram_token:
        from booksaver.infrastructure.notifications.telegram_notifier import TelegramNotifier

        notifiers.append(TelegramNotifier(bot_token=telegram_token, chat_id=ns.telegram_chat_id))
    else:
        logging.getLogger(__name__).info(
            "Telegram channel not fully configured (need notifications.telegram_chat_id "
            "+ BOOKSAVER_TELEGRAM_BOT_TOKEN) — skipping"
        )

    return notifiers


def _make_llm_client_factory(cfg: Config, store: Any = None) -> Any:
    """The LLMClientFactory seam (US-029/US-027). Without `store` (the CLI
    paths below that don't have a `Booking` in hand yet), this resolves only
    the owner env-var key — unchanged pre-US-027 behavior. With `store` (the
    scheduler's check job), it also resolves each booking's owning user and,
    if they have a personal key, decrypts and uses it instead (hybrid
    billing).
    """
    from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
    from booksaver.infrastructure.llm.client_factory import AnthropicLLMClientFactory
    from booksaver.infrastructure.persistence.sqlite_store import SqliteUserRepository

    user_repo = SqliteUserRepository(store) if store is not None else None
    key_store = FernetKeyStore() if store is not None else None
    return AnthropicLLMClientFactory(cfg, user_repo=user_repo, key_store=key_store)


def _make_llm_extractor(cfg: Config) -> Any:
    """Behavior unchanged from pre-v7: resolves the owner env-var key, or
    None (DOM-only mode) if unset/anthropic isn't installed. Goes through the
    LLMClientFactory seam so a later slice can resolve per-user keys.
    """
    return _make_llm_client_factory(cfg).for_booking(None)


def _make_agent_brain(cfg: Config) -> Any:
    """Behavior unchanged from pre-v7: resolves the owner env-var key, or
    None (scripted-only mode) if unset/anthropic isn't installed. Goes
    through the LLMClientFactory seam so a later slice can resolve per-user
    keys.
    """
    return _make_llm_client_factory(cfg).agent_brain_for_booking(None)


# ── auth import ──────────────────────────────────────────────────────────────


def cmd_auth_import(args: argparse.Namespace) -> int:
    """US-078: import Booking.com cookies for one admitted Telegram user.

    The VPS-compatible alternative to `booksaver auth` (which needs a display
    for the headed login browser). See the runbook's "cookie-import" section
    for how to export cookies and the security caution around them.
    """
    cfg, db_path = _db_path_for(args)

    from booksaver.application.user_sessions import SessionTargetError, UserSessionService
    from booksaver.domain.errors import SecretKeyError, SessionRevokedError
    from booksaver.infrastructure.persistence.cookie_import import CookieImportError
    from booksaver.infrastructure.persistence.encrypted_session_store import (
        EncryptedUserSessionRepository,
    )

    path = Path(args.file)
    try:
        raw_text = path.read_text()
    except OSError as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        return 2

    try:
        with SqliteStore(db_path) as store:
            service = UserSessionService(
                SqliteUserRepository(store),
                EncryptedUserSessionRepository(cfg.data_directory),
            )
            result = service.import_cookies(args.telegram_user_id, raw_text)
    except CookieImportError as e:
        print(f"Cookie import failed: {e}", file=sys.stderr)
        print(
            "See the 'cookie-import' section of "
            "memory-bank/operations/vps-deployment-runbook.md for export "
            "instructions.",
            file=sys.stderr,
        )
        return 2
    except (SessionTargetError, SecretKeyError, SessionRevokedError) as e:
        print(f"Session import failed: {e}", file=sys.stderr)
        return 2

    summary = result.summary
    print(f"Imported {summary.count} cookie(s) for Telegram user {result.telegram_user_id}.")
    print(f"Domain(s): {', '.join(summary.domains)}")
    if summary.earliest_expiry is not None:
        print(f"Earliest expiry: {summary.earliest_expiry.isoformat()}")
    else:
        print("Earliest expiry: none of the imported cookies carry an explicit expiry")
    print("Encrypted per-user session saved successfully.")
    print(
        "Scheduled checks will now run authenticated until this session expires or "
        "is flagged for re-auth — at which point re-run this import with a fresh export."
    )
    print(
        "Security note: these cookies grant account access — treat the export file "
        "like a password and delete it now that it's imported."
    )
    return 0


def _user_session_service(cfg: Config, store: SqliteStore) -> Any:
    from booksaver.application.user_sessions import UserSessionService
    from booksaver.infrastructure.persistence.encrypted_session_store import (
        EncryptedUserSessionRepository,
    )

    return UserSessionService(
        SqliteUserRepository(store),
        EncryptedUserSessionRepository(cfg.data_directory),
    )


def cmd_auth_status(args: argparse.Namespace) -> int:
    from booksaver.application.user_sessions import SessionTargetError

    cfg, db_path = _db_path_for(args)
    try:
        with SqliteStore(db_path) as store:
            status = _user_session_service(cfg, store).status(args.telegram_user_id)
    except SessionTargetError as e:
        print(f"Session status failed: {e}", file=sys.stderr)
        return 2

    print(f"Telegram user : {args.telegram_user_id}")
    print(f"Session health: {status.health.value}")
    print(f"Imported      : {status.imported_at.isoformat() if status.imported_at else '-'}")
    print(f"Last validated: {status.validated_at.isoformat() if status.validated_at else '-'}")
    print(f"Expires       : {status.expires_at.isoformat() if status.expires_at else '-'}")
    if status.health.value != "ready":
        print(
            "Re-import with: booksaver auth import <file> --telegram-user-id "
            f"{args.telegram_user_id}"
        )
    return 0


def cmd_auth_delete(args: argparse.Namespace) -> int:
    from booksaver.application.user_sessions import SessionTargetError

    cfg, db_path = _db_path_for(args)
    try:
        with SqliteStore(db_path) as store:
            deleted = _user_session_service(cfg, store).delete(args.telegram_user_id)
    except SessionTargetError as e:
        print(f"Session delete failed: {e}", file=sys.stderr)
        return 2
    if deleted:
        print(f"Deleted encrypted session for Telegram user {args.telegram_user_id}.")
    else:
        print(f"No encrypted session exists for Telegram user {args.telegram_user_id}.")
    return 0


# ── stop ──────────────────────────────────────────────────────────────────────


def cmd_stop(args: argparse.Namespace) -> int:
    source = TomlEnvConfigSource(_config_path(args))
    try:
        cfg = load_config(source)
    except (FileNotFoundError, ConfigValidationError) as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 2
    return lifecycle.stop(cfg.data_directory)


# ── savings list ──────────────────────────────────────────────────────────────


def cmd_savings_list(args: argparse.Namespace) -> int:
    from booksaver.infrastructure.persistence.sqlite_store import SqliteSavingsRepository

    cfg, db_path = _db_path_for(args)

    if not db_path.exists():
        print("No savings opportunities detected yet.")
        return 0

    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        opportunities = SqliteSavingsRepository(store).list_all_for_user(owner.user_id)

    if not opportunities:
        print("No savings opportunities detected yet.")
        return 0

    header = (
        f"{'OPPORTUNITY':36}  {'BOOKING':8}  {'BASELINE':>12}  "
        f"{'LIVE':>12}  {'SAVED':>16}  {'NOTIFIED':8}"
    )
    print(header)
    print("-" * len(header))
    for o in opportunities:
        saved_label = f"{o.amount_saved.amount} {o.amount_saved.currency} ({o.percent_saved}%)"
        print(
            f"{o.opportunity_id:36}  "
            f"{o.booking_id[:8]:8}  "
            f"{str(o.baseline_price.amount):>12}  "
            f"{str(o.live_price.amount):>12}  "
            f"{saved_label:>16}  "
            f"{'yes' if o.notified_at else 'no':8}"
        )
    return 0


# ── checks ────────────────────────────────────────────────────────────────────


def cmd_checks_list(args: argparse.Namespace) -> int:
    cfg, db_path = _db_path_for(args)
    if not db_path.exists():
        print("No checks recorded yet.")
        return 0

    with SqliteStore(db_path) as store:
        history = SqliteCheckHistoryRepository(store)
        results = history.get_recent(args.booking_id, limit=args.limit)

    if not results:
        print(f"No checks recorded for booking '{args.booking_id}'.")
        return 0

    header = f"{'CHECK':36}  {'CHECKED AT':25}  {'OUTCOME':8}  {'METHOD':6}  {'DETAIL'}"
    print(header)
    print("-" * 100)
    for r in results:
        if r.failure_reason is not None:
            detail = f"{r.failure_reason.code.value}: {r.failure_reason.detail[:50]}"
        else:
            assert r.live_price is not None
            detail = f"{r.live_price.amount} {r.live_price.currency}"
        print(
            f"{r.check_id:36}  {r.checked_at.isoformat()[:25]:25}  "
            f"{r.outcome.value:8}  {r.extraction_method.value:6}  {detail}"
        )
    print()
    print("Inspect a check with:  booksaver checks trace <CHECK>")
    return 0


def cmd_checks_trace(args: argparse.Namespace) -> int:
    from booksaver.infrastructure.persistence.sqlite_store import SqliteCheckTraceRepository

    cfg, db_path = _db_path_for(args)
    if not db_path.exists():
        print("No local database yet.", file=sys.stderr)
        return 2

    with SqliteStore(db_path) as store:
        trace = SqliteCheckTraceRepository(store).get(args.check_id)

    if trace is None:
        print(f"No trace found for check '{args.check_id}'.", file=sys.stderr)
        return 2

    print(f"Check   : {trace.check_id}")
    print(f"Booking : {trace.booking_id}")
    print(f"Recorded: {trace.created_at.isoformat()}")
    print()
    for event in trace.events:
        print(f"{event.seq:3}  {event.at.isoformat()}  {event.kind.value:19}  {event.detail}")
    return 0


# ── DOM-drift incidents ─────────────────────────────────────────────────────


def cmd_incidents_list(args: argparse.Namespace) -> int:
    """List content-free local incident metadata."""
    _cfg, db_path = _db_path_for(args)
    if not db_path.exists():
        print("No DOM maintenance incidents recorded yet.")
        return 0

    from booksaver.infrastructure.persistence.dom_incident import (
        SqliteDomIncidentRepository,
    )

    with SqliteStore(db_path) as store:
        incidents = SqliteDomIncidentRepository(store).list_incidents(limit=args.limit)
    if not incidents:
        print("No DOM maintenance incidents recorded yet.")
        return 0

    header = (
        f"{'INCIDENT':36}  {'STATE':10}  {'JOURNEY':20}  "
        f"{'STEP':32}  {'COUNT':>5}  {'EVIDENCE':12}  LAST OBSERVED"
    )
    print(header)
    print("-" * len(header))
    for incident in incidents:
        print(
            f"{incident.incident_id!s:36}  "
            f"{incident.state.value:10}  "
            f"{incident.journey.value:20}  "
            f"{incident.step_id.value:32}  "
            f"{incident.occurrence_count:5}  "
            f"{incident.evidence_state.value:12}  "
            f"{incident.last_observed_at.isoformat()}"
        )
    return 0


def cmd_incidents_inspect(args: argparse.Namespace) -> int:
    """Decrypt and print one diagnostic bundle on the local terminal only."""
    try:
        incident_id = uuid.UUID(args.incident_id)
    except (AttributeError, TypeError, ValueError):
        print("Incident ID must be a UUID.", file=sys.stderr)
        return 2

    cfg, db_path = _db_path_for(args)
    if not db_path.exists():
        print(f"No incident found for '{incident_id}'.", file=sys.stderr)
        return 2

    from booksaver.infrastructure.persistence.dom_incident import (
        SqliteDomIncidentRepository,
    )
    from booksaver.infrastructure.persistence.encrypted_diagnostics import (
        EncryptedDiagnosticStore,
    )

    with SqliteStore(db_path) as store:
        incident = SqliteDomIncidentRepository(store).get_incident(incident_id)
        if incident is None:
            print(f"No incident found for '{incident_id}'.", file=sys.stderr)
            return 2
        inspection = EncryptedDiagnosticStore(store).inspect(
            incident_id,
            datetime.now(UTC),
        )

    print(f"Incident       : {incident.incident_id}")
    print(f"State          : {incident.state.value}")
    print(f"Journey        : {incident.journey.value}")
    print(f"Step           : {incident.step_id.value}")
    print(f"Category       : {incident.terminal_reason.value}")
    print(f"Occurrences    : {incident.occurrence_count}")
    print(f"Evidence state : {inspection.evidence_state.value}")
    bundle = inspection.bundle
    if bundle is None:
        return 0
    print(f"Evidence version: {bundle.version}")
    print(f"Created        : {bundle.created_at.isoformat()}")
    print(f"Source users   : {', '.join(str(value) for value in bundle.source_user_ids)}")
    print(f"Structure roles: {', '.join(bundle.structural_roles) or 'none'}")
    print(f"Action outcomes: {', '.join(bundle.action_outcomes) or 'none'}")
    print(f"Terminal reason: {bundle.terminal_reason.value}")
    print(f"Model roles    : {', '.join(role.value for role in bundle.model_roles)}")
    attempts = bundle.model_attempts
    print(f"Model attempts : {len(attempts)}")
    if attempts:
        total_input = sum(attempt.input_tokens or 0 for attempt in attempts)
        total_output = sum(attempt.output_tokens or 0 for attempt in attempts)
        total_latency = sum(attempt.latency_ms or 0 for attempt in attempts)
        total_reserved = sum(attempt.reserved_micro_usd for attempt in attempts)
        total_charged = sum(attempt.charged_micro_usd or 0 for attempt in attempts)
        print(
            "Attempt totals : "
            f"input={total_input} output={total_output} latency_ms={total_latency} "
            f"reserved_micro_usd={total_reserved} charged_micro_usd={total_charged}"
        )
        for attempt in attempts:
            print(
                f"Attempt {attempt.ordinal:>2}    : "
                f"provider={attempt.provider.value} model={attempt.model} "
                f"role={attempt.role.value} trigger={attempt.trigger.value} "
                f"outcome={attempt.outcome.value if attempt.outcome else 'none'} "
                f"status={attempt.status.value} "
                f"input={attempt.input_tokens if attempt.input_tokens is not None else 'none'} "
                f"output={attempt.output_tokens if attempt.output_tokens is not None else 'none'} "
                f"latency_ms={attempt.latency_ms if attempt.latency_ms is not None else 'none'} "
                f"reserved_micro_usd={attempt.reserved_micro_usd} "
                "charged_micro_usd="
                f"{attempt.charged_micro_usd if attempt.charged_micro_usd is not None else 'none'}"
            )
    print(f"Provider state : {bundle.provider_state.value}")
    print(f"Budget state   : {bundle.budget_state.value}")
    print(
        f"Structural image: {len(bundle.structural_image)} bytes"
        if bundle.structural_image is not None
        else "Structural image: unavailable"
    )
    return 0


# ── privacy-safe recovery evaluation ────────────────────────────────────────


def cmd_evaluate_recovery(args: argparse.Namespace) -> int:
    """Run an explicit live-model replay without opening a browser."""
    if not args.live:
        print(
            "Refusing to call the configured model without --live. "
            "Replay never opens Booking.com or reads the BookSaver database.",
            file=sys.stderr,
        )
        return 2
    api_key = os.environ.get("BOOKSAVER_LLM_API_KEY")
    if not api_key:
        print("BOOKSAVER_LLM_API_KEY is required for live replay.", file=sys.stderr)
        return 2

    from booksaver.domain.model_policy import (
        AdaptiveModelPortfolio,
        BrowserJobKind,
        CallerKeyRef,
        ModelCostEstimator,
        ModelProfile,
        ModelRole,
        UsdAmount,
    )

    try:
        evaluation_cost_limit = UsdAmount.from_decimal_string(args.max_cost_usd or "")
    except ValueError:
        print(
            "An explicit --max-cost-usd decimal limit is required for live replay.",
            file=sys.stderr,
        )
        return 2
    if evaluation_cost_limit.micro_usd == 0:
        print("--max-cost-usd must be greater than zero.", file=sys.stderr)
        return 2
    if args.persist and not args.qualify:
        print("--persist is only valid with --qualify.", file=sys.stderr)
        return 2
    if args.qualify and args.fixture:
        print(
            "Qualification only accepts the packaged fixture corpus; custom fixtures "
            "are exploratory and cannot be recorded.",
            file=sys.stderr,
        )
        return 2
    if args.qualify and args.runs != 10:
        print("Qualification requires exactly 10 runs per packaged fixture.", file=sys.stderr)
        return 2

    from booksaver.evaluation import (
        PACKAGED_QUALIFICATION_VERSION,
        ReplayFixtureError,
        ReplayRunner,
        approved_recovery_profiles,
        curated_fixture_directory,
        load_fixture,
        load_fixture_directory,
        plan_profile_replay,
        run_packaged_qualification,
    )
    from booksaver.infrastructure.llm.anthropic_adapter import AnthropicAgentBrain

    fixture_path = (
        Path(args.fixture).expanduser().resolve() if args.fixture else curated_fixture_directory()
    )
    try:
        fixtures = (
            load_fixture_directory(fixture_path)
            if fixture_path.is_dir()
            else (load_fixture(fixture_path),)
        )
    except ReplayFixtureError as exc:
        print(f"Replay fixture rejected: {exc}", file=sys.stderr)
        return 2
    cfg = _load_config_for_args(args)
    portfolio = AdaptiveModelPortfolio()
    profiles: tuple[ModelProfile, ...]
    if args.qualify:
        profiles = approved_recovery_profiles()
    else:
        profiles = (portfolio.primary(ModelRole.RECOVERY, "booking-browser-recovery-v4"),)
    maximum_calls = sum(fixture.max_calls for fixture in fixtures) * args.runs
    if not args.qualify and maximum_calls > 250:
        print(
            "Replay plan rejected: the corpus and run count could make more than "
            "250 provider calls.",
            file=sys.stderr,
        )
        return 2
    plan = plan_profile_replay(fixtures, profiles, runs_per_fixture=args.runs)
    if not args.qualify and plan.maximum_cost > evaluation_cost_limit:
        print(
            "Replay plan rejected before provider access: conservative maximum is "
            f"{plan.maximum_cost.micro_usd} microUSD, above the explicit "
            f"{evaluation_cost_limit.micro_usd} microUSD limit.",
            file=sys.stderr,
        )
        return 2

    if args.qualify:
        from booksaver.application.model_policy import BrowserJobCostBudget
        from booksaver.infrastructure.persistence.model_policy import (
            SqliteQualificationRepository,
            SqliteSpendLedger,
        )

        daily_limit = UsdAmount(cfg.agent_settings.max_deployment_daily_cost_micro_usd)
        if evaluation_cost_limit > daily_limit:
            print(
                "--max-cost-usd cannot exceed the configured deployment UTC-day "
                f"limit ({daily_limit.micro_usd} microUSD).",
                file=sys.stderr,
            )
            return 2
        db_path = cfg.data_directory.path / "booksaver.db"
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()
            budget = BrowserJobCostBudget(
                job_id=f"qualification-{uuid.uuid4().hex}",
                job_kind=BrowserJobKind.QUALIFICATION,
                caller_key_ref=CallerKeyRef(
                    caller_user_id=owner.user_id,
                    funding_mode="shared",
                    provenance="owner_env",
                ),
                ledger=SqliteSpendLedger(store),
                estimator=ModelCostEstimator(),
                job_limit=evaluation_cost_limit,
                day_limit=daily_limit,
                preserve_opus_diagnostic=False,
            )
            report = run_packaged_qualification(
                fixtures,
                lambda profile: AnthropicAgentBrain(api_key=api_key, model=profile.model_id),
                evaluation_cost_limit=evaluation_cost_limit,
                budget=budget,
            )
            qualification_ids = (
                tuple(
                    SqliteQualificationRepository(store).save(profile.result)
                    for profile in report.profiles
                )
                if args.persist
                else ()
            )
        print(
            "qualification-plan: "
            f"corpus={PACKAGED_QUALIFICATION_VERSION}; "
            f"fixtures={report.plan.fixture_count}; "
            f"runs_per_fixture={report.plan.runs_per_fixture}; "
            f"max_calls={report.plan.maximum_provider_calls}; "
            f"max_cost_micro_usd={report.plan.maximum_cost.micro_usd}"
        )
        if report.plan.maximum_cost > evaluation_cost_limit:
            print(
                "qualification-plan-warning: conservative full-plan maximum exceeds "
                "the explicit allowance; per-call admission will stop with a partial "
                "failed report if actual progress consumes the allowance."
            )
        if report.stopped_reason is not None:
            print(f"qualification-stopped: {report.stopped_reason}")
        for profile in report.profiles:
            metrics = profile.result.metrics
            print(
                f"{profile.model}: gate={profile.result.gate.value}; "
                f"accuracy={metrics.correct_runs}/{metrics.runs}; "
                f"diagnosis={metrics.diagnosis_correct_runs}/"
                f"{metrics.diagnosis_runs}; "
                f"schema={metrics.schema_valid_runs}/{metrics.runs}; "
                f"prohibited={metrics.prohibited_action_executions}; "
                f"calls={metrics.total_calls}; actions={metrics.total_actions}; "
                f"latency_ms={metrics.latency_ms}; "
                f"tokens={metrics.input_tokens}in/{metrics.output_tokens}out; "
                f"estimated_cost_micro_usd={metrics.estimated_cost.micro_usd}"
            )
            for fixture_metrics in profile.fixtures:
                outcomes = ",".join(
                    f"{category}:{count}"
                    for category, count in fixture_metrics.outcome_categories
                )
                print(
                    f"  {fixture_metrics.fixture_id}: "
                    f"accuracy={fixture_metrics.correct_runs}/"
                    f"{fixture_metrics.runs}; "
                    f"schema={fixture_metrics.schema_valid_runs}/"
                    f"{fixture_metrics.runs}; "
                    f"safe={fixture_metrics.safe_runs}/{fixture_metrics.runs}; "
                    f"calls={fixture_metrics.total_actual_calls}; "
                    f"actions={fixture_metrics.total_actions}; "
                    f"latency_ms="
                    f"{round(fixture_metrics.total_latency_seconds * 1_000)}; "
                    f"tokens={fixture_metrics.total_input_tokens}in/"
                    f"{fixture_metrics.total_output_tokens}out; "
                    f"estimated_cost_micro_usd="
                    f"{fixture_metrics.estimated_micro_usd}; "
                    f"outcomes={outcomes}"
                )
        if qualification_ids:
            print("qualification-recorded: " + ",".join(qualification_ids))
        return 0 if report.passed else 1

    model = getattr(cfg.agent_settings, "primary_model", cfg.agent_settings.model)
    brain = AnthropicAgentBrain(api_key=api_key, model=model)
    runner = ReplayRunner()
    passed = True
    for fixture in fixtures:
        _runs, aggregate = runner.run(fixture, brain, runs=args.runs)
        correct = aggregate.correct_rate >= 0.9
        safe = aggregate.prohibited_action_executions == 0
        passed = passed and correct and safe
        categories = ", ".join(
            f"{category}={count}" for category, count in aggregate.outcome_categories
        )
        print(
            f"{aggregate.fixture_id}: correct={aggregate.correct_runs}/"
            f"{aggregate.runs}; safe={aggregate.safe_runs}/{aggregate.runs}; "
            f"calls={aggregate.total_actual_calls}; actions={aggregate.total_actions}; "
            f"tokens={aggregate.total_input_tokens}in/"
            f"{aggregate.total_output_tokens}out/{aggregate.total_tokens}total; "
            f"latency={aggregate.total_latency_seconds:.2f}s; "
            f"estimated_cost_micro_usd={aggregate.estimated_micro_usd}; {categories}"
        )
    return 0 if passed else 1


def cmd_validate_model_qualification(args: argparse.Namespace) -> int:
    """Fail release validation unless both fixed profiles are locally approved."""
    from booksaver.evaluation import (
        PACKAGED_QUALIFICATION_VERSION,
        approved_recovery_profiles,
    )
    from booksaver.infrastructure.persistence.model_policy import (
        SqliteQualificationRepository,
    )

    cfg = _load_config_for_args(args)
    db_path = cfg.data_directory.path / "booksaver.db"
    if not db_path.exists():
        print("Model qualification missing: no local database.", file=sys.stderr)
        return 1
    override_id = getattr(args, "override", None)
    override_reason = getattr(args, "reason", None)
    if bool(override_id) != bool(override_reason):
        print(
            "Qualification override requires both --override and --reason.",
            file=sys.stderr,
        )
        return 2
    failures: list[str] = []
    with SqliteStore(db_path) as store:
        repository = SqliteQualificationRepository(store)
        if override_id:
            assert isinstance(override_reason, str)
            owner = SqliteUserRepository(store).get_owner()
            try:
                repository.record_owner_override(
                    override_id,
                    owner_user_id=owner.user_id,
                    reason=override_reason,
                    overridden_at=datetime.now(UTC),
                )
            except (KeyError, PermissionError, ValueError) as exc:
                print(f"Qualification override rejected: {exc}", file=sys.stderr)
                return 2
            print(f"Qualification override recorded locally: {override_id}")
        for profile in approved_recovery_profiles():
            result = repository.latest(profile.identity, PACKAGED_QUALIFICATION_VERSION)
            if result is None:
                failures.append(f"{profile.model_id}=missing")
            elif not result.is_approved:
                failures.append(f"{profile.model_id}=failed")
    if failures:
        print(
            "Model qualification rejected: " + ", ".join(failures),
            file=sys.stderr,
        )
        return 1
    print(
        f"Model qualification is valid for Sonnet 5 and Opus 5 ({PACKAGED_QUALIFICATION_VERSION})."
    )
    return 0


# ── parser ────────────────────────────────────────────────────────────────────


def _no_subcommand(parser: argparse.ArgumentParser) -> argparse.Namespace:
    def _help(args: argparse.Namespace) -> int:
        parser.print_help()
        return 1

    return _help  # type: ignore[return-value]


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="booksaver",
        description="Monitor Booking.com hotel prices for refundable reservations — locally.",
    )
    parser.add_argument(
        "--config", metavar="PATH", help="Config file path (default: ~/.booksaver/config.toml)"
    )
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Create data directory and sample config")
    p_init.add_argument(
        "--data-dir", metavar="PATH", dest="data_dir", help="Data directory (default: ~/.booksaver)"
    )
    p_init.set_defaults(func=cmd_init)

    # config
    p_cfg = sub.add_parser("config", help="Config commands")
    p_cfg.set_defaults(func=_no_subcommand(p_cfg))
    cfg_sub = p_cfg.add_subparsers(dest="config_command")
    p_cfg_val = cfg_sub.add_parser("validate", help="Validate config and data directory")
    p_cfg_val.set_defaults(func=cmd_config_validate)
    p_cfg_show = cfg_sub.add_parser("show", help="Show effective config (secrets redacted)")
    p_cfg_show.set_defaults(func=cmd_config_show)

    # run
    p_run = sub.add_parser("run", help="Start the daemon (foreground; Ctrl-C or SIGTERM to stop)")
    p_run.set_defaults(func=cmd_run)

    # auth
    p_auth = sub.add_parser("auth", help="Per-user Booking.com session commands")
    p_auth.set_defaults(func=_no_subcommand(p_auth))
    auth_sub = p_auth.add_subparsers(dest="auth_command")
    p_auth_import = auth_sub.add_parser(
        "import",
        help=(
            "Import cookies exported from your own browser (VPS-compatible — no "
            "display needed; see the runbook's cookie-import section)"
        ),
    )
    p_auth_import.add_argument(
        "file", metavar="FILE", help="Path to a cookies JSON file exported from your browser"
    )
    p_auth_import.add_argument(
        "--telegram-user-id",
        required=True,
        type=int,
        metavar="ID",
        help="Already-admitted Telegram numeric user ID that owns this session",
    )
    p_auth_import.set_defaults(func=cmd_auth_import)
    p_auth_status = auth_sub.add_parser(
        "status", help="Show redacted per-user Booking.com session health"
    )
    p_auth_status.add_argument("--telegram-user-id", required=True, type=int, metavar="ID")
    p_auth_status.set_defaults(func=cmd_auth_status)
    p_auth_delete = auth_sub.add_parser(
        "delete", help="Delete one Telegram user's encrypted Booking.com session"
    )
    p_auth_delete.add_argument("--telegram-user-id", required=True, type=int, metavar="ID")
    p_auth_delete.set_defaults(func=cmd_auth_delete)
    # stop
    p_stop = sub.add_parser("stop", help="Stop the running daemon gracefully")
    p_stop.set_defaults(func=cmd_stop)

    # bookings
    p_bk = sub.add_parser("bookings", help="Booking commands")
    p_bk.set_defaults(func=_no_subcommand(p_bk))
    bk_sub = p_bk.add_subparsers(dest="bookings_command")
    p_bk_list = bk_sub.add_parser("list", help="List synchronized reservations")
    p_bk_list.set_defaults(func=cmd_bookings_list)
    p_bk_trace = bk_sub.add_parser(
        "trace", help="Show a redacted inventory recovery audit by sync run id"
    )
    p_bk_trace.add_argument("run_id", metavar="SYNC_RUN_ID")
    p_bk_trace.set_defaults(func=cmd_bookings_trace)

    # checks
    p_ck = sub.add_parser("checks", help="Price-check history and traces")
    p_ck.set_defaults(func=_no_subcommand(p_ck))
    ck_sub = p_ck.add_subparsers(dest="checks_command")
    p_ck_list = ck_sub.add_parser("list", help="List recent checks for a booking")
    p_ck_list.add_argument(
        "booking_id", metavar="BOOKING_ID", help="Booking id (see: booksaver bookings list)"
    )
    p_ck_list.add_argument("--limit", type=int, default=10, metavar="N")
    p_ck_list.set_defaults(func=cmd_checks_list)
    p_ck_trace = ck_sub.add_parser(
        "trace", help="Show the step-by-step trace of one check (incl. agent actions)"
    )
    p_ck_trace.add_argument("check_id", metavar="CHECK_ID")
    p_ck_trace.set_defaults(func=cmd_checks_trace)

    # DOM-drift incidents (local-only operator diagnostics)
    p_incidents = sub.add_parser("incidents", help="Inspect local DOM-maintenance incidents")
    p_incidents.set_defaults(func=_no_subcommand(p_incidents))
    incidents_sub = p_incidents.add_subparsers(dest="incidents_command")
    p_incidents_list = incidents_sub.add_parser("list", help="List content-free incident metadata")
    p_incidents_list.add_argument(
        "--limit", type=int, choices=range(1, 501), default=50, metavar="N"
    )
    p_incidents_list.set_defaults(func=cmd_incidents_list)
    p_incidents_inspect = incidents_sub.add_parser(
        "inspect", help="Decrypt one incident diagnostic locally"
    )
    p_incidents_inspect.add_argument("incident_id", metavar="INCIDENT_ID")
    p_incidents_inspect.set_defaults(func=cmd_incidents_inspect)

    # recovery evaluation (explicit opt-in; simulated browser state only)
    p_eval = sub.add_parser("evaluate", help="Run privacy-safe model evaluations (no live browser)")
    p_eval.set_defaults(func=_no_subcommand(p_eval))
    eval_sub = p_eval.add_subparsers(dest="evaluate_command")
    p_eval_recovery = eval_sub.add_parser(
        "recovery", help="Replay sanitized browser-recovery fixtures"
    )
    p_eval_recovery.add_argument(
        "--fixture",
        metavar="PATH",
        help="Approved sanitized fixture JSON file or directory (default: packaged corpus)",
    )
    p_eval_recovery.add_argument("--runs", type=int, choices=range(1, 11), default=10, metavar="N")
    p_eval_recovery.add_argument(
        "--live",
        action="store_true",
        help="Explicitly allow calls to the configured LLM provider",
    )
    p_eval_recovery.add_argument(
        "--max-cost-usd",
        metavar="USD",
        help="Required exact upper cost limit for this live evaluation",
    )
    p_eval_recovery.add_argument(
        "--qualify",
        action="store_true",
        help="Run both approved profiles on the packaged corpus (10 runs each)",
    )
    p_eval_recovery.add_argument(
        "--persist",
        action="store_true",
        help="Persist aggregate qualification results locally (requires --qualify)",
    )
    p_eval_recovery.set_defaults(func=cmd_evaluate_recovery)
    p_eval_qualification = eval_sub.add_parser(
        "qualification",
        help="Validate the locally recorded Sonnet/Opus release gate",
    )
    p_eval_qualification.add_argument(
        "--override",
        metavar="QUALIFICATION_ID",
        help="Explicitly override one local failed qualification record",
    )
    p_eval_qualification.add_argument(
        "--reason",
        help="Required owner audit reason when --override is used",
    )
    p_eval_qualification.set_defaults(func=cmd_validate_model_qualification)

    # savings
    p_sv = sub.add_parser("savings", help="Savings opportunity commands")
    p_sv.set_defaults(func=_no_subcommand(p_sv))
    sv_sub = p_sv.add_subparsers(dest="savings_command")
    p_sv_list = sv_sub.add_parser("list", help="List detected savings opportunities")
    p_sv_list.set_defaults(func=cmd_savings_list)

    return parser
