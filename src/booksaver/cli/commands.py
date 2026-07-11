from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from booksaver.application.load_config import load_config
from booksaver.application.register_booking import register_booking
from booksaver.daemon import lifecycle
from booksaver.daemon import scheduler as scheduler_mod
from booksaver.domain.errors import BookingRejectedError, ConfigValidationError
from booksaver.domain.models import Config
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Occupancy,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)
from booksaver.infrastructure.config.toml_env_source import (
    DEFAULT_CONFIG_PATH,
    TomlEnvConfigSource,
)
from booksaver.infrastructure.paths import ensure_data_dir
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteStore,
    SqliteUserRepository,
)

_SAMPLE_CONFIG = """\
[schedule]
check_interval = "6h"            # How often to check for price drops (e.g. "30m", "6h", "1d")

[storage]
data_directory = "~/.booksaver"  # Where all BookSaver data is stored — local only

[notifications]
# Non-secret identifiers go here. Secrets come from environment variables.
# email = "your@email.com"           # alert recipient
# smtp_host = "smtp.gmail.com"       # sender SMTP server (STARTTLS)
# smtp_port = 587
# smtp_username = "your@email.com"   # SMTP login + From; pw: export BOOKSAVER_SMTP_PASSWORD=...
# telegram_chat_id = "123456789"     # token:    export BOOKSAVER_TELEGRAM_BOT_TOKEN=...

[extraction]
# LLM model selection goes here. API key comes from an environment variable.
# model = "claude-sonnet-4-6"        # key:      export BOOKSAVER_LLM_API_KEY=...

[agent]
# Hard cost caps per price check (ADR-017). Deliberately simple for now —
# smarter adaptive budgeting is planned future work if these prove too blunt.
# model = "claude-sonnet-4-6"        # browser-agent model (extraction uses [extraction])
# max_steps = 15              # LLM browser-agent turns (screenshot turns count double)
# max_llm_calls = 20          # all LLM calls in one check (agent + extraction)
# check_timeout_seconds = 180 # wall-clock limit per booking check
"""


def _config_path(args: argparse.Namespace) -> Path:
    if getattr(args, "config", None):
        return Path(args.config)
    env = os.environ.get("BOOKSAVER_CONFIG")
    return Path(env) if env else DEFAULT_CONFIG_PATH


def _db_path_for(args: argparse.Namespace) -> tuple[Config, Path]:
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
    return cfg, cfg.data_directory.path / "booksaver.db"


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
        config_path.write_text(_SAMPLE_CONFIG)
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
    print(f"  check_interval : {cfg.check_interval}")
    print(f"  data_directory : {cfg.data_directory.path}")
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
    print(f"check_interval               : {cfg.check_interval}")
    print(f"data_directory               : {cfg.data_directory.path}")
    print(f"notifications.email          : {ns.email or '(not set)'}")
    print(f"notifications.telegram_chat_id: {ns.telegram_chat_id or '(not set)'}")
    smtp = "(set)" if os.environ.get("BOOKSAVER_SMTP_PASSWORD") else "(not set)"
    tg = "(set)" if os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN") else "(not set)"
    llm = "(set)" if os.environ.get("BOOKSAVER_LLM_API_KEY") else "(not set)"
    print(f"BOOKSAVER_SMTP_PASSWORD      : {smtp}")
    print(f"BOOKSAVER_TELEGRAM_BOT_TOKEN : {tg}")
    print(f"BOOKSAVER_LLM_API_KEY        : {llm}")
    return 0


# ── register ──────────────────────────────────────────────────────────────────

def cmd_register(args: argparse.Namespace) -> int:
    cfg, db_path = _db_path_for(args)

    try:
        confirmation_id = ConfirmationId.of(args.confirmation)
        prop = Property(name=args.property_name, booking_com_ref=args.property_ref)
        check_in = date.fromisoformat(args.check_in)
        check_out = date.fromisoformat(args.check_out)
        stay_dates = StayDates(check_in=check_in, check_out=check_out)
        room_type = RoomType(label=args.room_type)
        baseline_price = Money.of(args.amount, args.currency)
        refundability = RefundabilityPolicy(
            is_refundable=True,
            note=args.refund_note,
            deadline=date.fromisoformat(args.refund_deadline) if args.refund_deadline else None,
        )
        occupancy = Occupancy(adults=args.adults, children=args.children, rooms=args.rooms)
    except ValueError as e:
        print(f"Invalid input: {e}", file=sys.stderr)
        return 2

    ensure_data_dir(cfg.data_directory)
    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        owner = SqliteUserRepository(store).get_owner()
        try:
            booking, _ = register_booking(
                repo=repo,
                platform=Platform.BOOKING_COM,
                product_type=ProductType.HOTEL,
                confirmation_id=confirmation_id,
                property=prop,
                stay_dates=stay_dates,
                room_type=room_type,
                baseline_price=baseline_price,
                refundability=refundability,
                occupancy=occupancy,
                user_id=owner.user_id,
            )
        except BookingRejectedError as e:
            print(f"Registration rejected: {e}", file=sys.stderr)
            return 2

    print(f"Registered: {booking.booking_id}")
    print(f"  Confirmation : {booking.confirmation_id.value}")
    print(f"  Property     : {booking.property.name}")
    print(f"  Stay         : {booking.stay_dates.check_in} → {booking.stay_dates.check_out}")
    print(f"  Room         : {booking.room_type.label}")
    print(f"  Baseline     : {booking.baseline_price.amount} {booking.baseline_price.currency}")
    print(f"  Occupancy    : {booking.occupancy}")
    return 0


# ── bookings set-occupancy ────────────────────────────────────────────────────

def cmd_bookings_set_occupancy(args: argparse.Namespace) -> int:
    cfg, db_path = _db_path_for(args)
    if not db_path.exists():
        print("No bookings registered yet.", file=sys.stderr)
        return 2

    try:
        occupancy = Occupancy(adults=args.adults, children=args.children, rooms=args.rooms)
    except ValueError as e:
        print(f"Invalid input: {e}", file=sys.stderr)
        return 2

    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        try:
            repo.set_occupancy(args.booking_id, occupancy)
        except KeyError as e:
            print(f"Error: {e.args[0]}", file=sys.stderr)
            return 2

    print(f"Occupancy set to {occupancy} for booking {args.booking_id}")
    print("Scheduled checks for this booking will now run the search journey.")
    return 0


# ── bookings list ─────────────────────────────────────────────────────────────

def cmd_bookings_list(args: argparse.Namespace) -> int:
    cfg, db_path = _db_path_for(args)

    if not db_path.exists():
        print("No bookings registered yet.")
        return 0

    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        owner = SqliteUserRepository(store).get_owner()
        bookings = (
            repo.list_all_for_user(owner.user_id)
            if getattr(args, "all", False)
            else repo.list_active_for_user(owner.user_id)
        )

    if not bookings:
        label = "bookings" if getattr(args, "all", False) else "active bookings"
        print(f"No {label} found.")
        return 0

    header = (
        f"{'ID':8}  {'CONFIRMATION':20}  {'PROPERTY':25}  "
        f"{'CHECK-IN':10}  {'CHECK-OUT':10}  {'BASELINE':>14}  {'OCC':>7}  {'STATUS':8}"
    )
    print(header)
    print("-" * len(header))
    for b in bookings:
        occ = str(b.occupancy) if b.occupancy else "MISSING"
        print(
            f"{b.booking_id[:8]:8}  "
            f"{b.confirmation_id.value[:20]:20}  "
            f"{b.property.name[:25]:25}  "
            f"{str(b.stay_dates.check_in):10}  "
            f"{str(b.stay_dates.check_out):10}  "
            f"{str(b.baseline_price.amount) + ' ' + b.baseline_price.currency:>14}  "
            f"{occ:>7}  "
            f"{b.status.value:8}"
        )
    if any(b.occupancy is None for b in bookings):
        print()
        print(
            "Bookings marked OCC=MISSING predate the occupancy field; set it with:\n"
            "  booksaver bookings set-occupancy <BOOKING_ID> --adults N"
        )
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
    sched.register("booking_com_check", _make_check_job(cfg))

    print(f"BookSaver daemon starting (interval={cfg.check_interval}, data={cfg.data_directory.path})")  # noqa: E501
    print("Press Ctrl-C or send SIGTERM to stop cleanly.")
    lifecycle.start(cfg, sched)
    return 0


def _make_check_job(cfg: Config) -> Callable[[], None]:
    """Build the scheduler job for Booking.com checks.

    All heavyweight resources (browser, DB connection) are created per tick and
    released afterwards, so a crashed tick never poisons the next one and the
    daemon holds no browser between intervals.
    """
    from booksaver.infrastructure.persistence.session_store import LocalSessionRepository
    from booksaver.monitor.failure_tracker import FailureTracker
    from booksaver.monitor.search_check_job import BookingComSearchMonitor
    from booksaver.monitor.session_manager import SessionManager

    def _job() -> None:
        from booksaver.application.savings_pipeline import NotificationDispatcher, SavingsPipeline
        from booksaver.infrastructure.browser.playwright_adapter import (
            PlaywrightInteractiveBrowser,
        )
        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteCheckTraceRepository,
            SqliteSavingsRepository,
        )
        from booksaver.monitor.trace import SnapshotWriter

        llm = _make_llm_extractor(cfg)
        brain = _make_agent_brain(cfg)
        db_path = cfg.data_directory.path / "booksaver.db"
        with (
            SqliteStore(db_path) as store,
            PlaywrightInteractiveBrowser(headless=True) as browser,
        ):
            history = SqliteCheckHistoryRepository(store)
            booking_repo = SqliteBookingRepository(store)
            monitor = BookingComSearchMonitor(
                browser=browser,
                session_manager=SessionManager(LocalSessionRepository(cfg.data_directory)),
                check_history=history,
                booking_repo=booking_repo,
                failure_tracker=FailureTracker(history),
                llm=llm,
                brain=brain,
                agent_settings=cfg.agent_settings,
                trace_repo=SqliteCheckTraceRepository(store),
                snapshot_writer=SnapshotWriter(cfg.data_directory.path / "snapshots"),
            )
            results = monitor.run_all_active()

            pipeline = SavingsPipeline(
                booking_repo=booking_repo,
                savings_repo=SqliteSavingsRepository(store),
                dispatcher=NotificationDispatcher(_make_notifiers(cfg)),
            )
            pipeline.process(results)

    return _job


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


def _make_llm_client_factory(cfg: Config) -> Any:
    """The LLMClientFactory seam (US-029). Wraps env-var key resolution today;
    a later slice swaps this for per-user (owner-or-personal-key) resolution
    without touching `_make_llm_extractor`/`_make_agent_brain` call sites.
    """
    from booksaver.infrastructure.llm.client_factory import AnthropicLLMClientFactory

    return AnthropicLLMClientFactory(cfg)


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


# ── auth ──────────────────────────────────────────────────────────────────────

def cmd_auth(args: argparse.Namespace) -> int:
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

    try:
        from booksaver.infrastructure.browser.playwright_adapter import interactive_login
    except ImportError:
        print(
            "Error: playwright is not installed.\n"
            "Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 2

    from datetime import UTC, datetime

    from booksaver.domain.session import SessionState
    from booksaver.infrastructure.persistence.session_store import LocalSessionRepository

    print("Opening a browser window for Booking.com login...")
    cookies = interactive_login()
    if not json.loads(cookies.decode("utf-8")):
        print("No cookies captured — login may not have completed.", file=sys.stderr)
        return 2

    ensure_data_dir(cfg.data_directory)
    session = SessionState.new(
        platform=Platform.BOOKING_COM,
        cookies=cookies,
        authenticated_at=datetime.now(UTC),
    )
    LocalSessionRepository(cfg.data_directory).save(session)
    print(f"Session saved to {cfg.data_directory.path}/session_booking_com.json")
    print("Scheduled checks will now reuse this session until it expires.")
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
    print()
    print("Start a guided rebook with:  booksaver rebook <OPPORTUNITY>")
    return 0


# ── rebook ────────────────────────────────────────────────────────────────────

def _open_or_print(url: str, description: str, use_browser: bool) -> None:
    print(f"\n>>> {description}:\n    {url}")
    if not use_browser:
        return
    try:
        import webbrowser

        webbrowser.open(url)
        print("    (opened in your browser)")
    except Exception:
        print("    (could not open a browser — visit the URL manually)")


def cmd_rebook(args: argparse.Namespace) -> int:
    from booksaver.application.rebook_service import (
        RebookSessionService,
        UnknownOpportunityError,
    )
    from booksaver.domain.rebook import SessionState
    from booksaver.infrastructure.cli_confirmation import TerminalConfirmationGate
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteRebookEventRepository,
        SqliteRebookSessionRepository,
        SqliteSavingsRepository,
    )

    cfg, db_path = _db_path_for(args)
    if not db_path.exists():
        print("No local database yet — no savings opportunities to rebook.", file=sys.stderr)
        return 2

    use_browser = not getattr(args, "no_browser", False)

    with SqliteStore(db_path) as store:
        service = RebookSessionService(
            savings_repo=SqliteSavingsRepository(store),
            booking_repo=SqliteBookingRepository(store),
            session_repo=SqliteRebookSessionRepository(store),
            event_repo=SqliteRebookEventRepository(store),
            gate=TerminalConfirmationGate(),
            navigator=lambda url, desc: _open_or_print(url, desc, use_browser),
        )
        try:
            session = service.run(args.opportunity_id)
        except UnknownOpportunityError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Rebook session failed: {e}", file=sys.stderr)
            return 2

    print()
    if session.state is SessionState.COMPLETED:
        print(f"Guided rebook session {session.session_id} completed.")
        print("Remember: the final cancel/booking clicks on Booking.com are yours to make.")
    elif session.state is SessionState.DECLINED:
        print(f"Session {session.session_id} ended: declined. Nothing was changed.")
    print(f"Audit trail: booksaver rebook-log {session.session_id}")
    return 0


def cmd_rebook_log(args: argparse.Namespace) -> int:
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteRebookEventRepository,
        SqliteRebookSessionRepository,
    )

    cfg, db_path = _db_path_for(args)
    if not db_path.exists():
        print("No local database yet.", file=sys.stderr)
        return 2

    with SqliteStore(db_path) as store:
        session = SqliteRebookSessionRepository(store).get(args.session_id)
        events = SqliteRebookEventRepository(store).list_for_session(args.session_id)

    if session is None:
        print(f"No rebook session found with id '{args.session_id}'.", file=sys.stderr)
        return 2

    print(f"Session : {session.session_id}")
    print(f"Booking : {session.booking_id}")
    print(f"State   : {session.state.value}")
    print(f"Started : {session.started_at.isoformat()}")
    if session.ended_at:
        print(f"Ended   : {session.ended_at.isoformat()}  ({session.end_reason})")
    print()
    for event in events:
        detail = f"  — {event.detail}" if event.detail else ""
        print(f"{event.occurred_at.isoformat()}  {event.event_type.value:24}{detail}")
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
    p_init.add_argument("--data-dir", metavar="PATH", dest="data_dir",
                        help="Data directory (default: ~/.booksaver)")
    p_init.set_defaults(func=cmd_init)

    # config
    p_cfg = sub.add_parser("config", help="Config commands")
    p_cfg.set_defaults(func=_no_subcommand(p_cfg))
    cfg_sub = p_cfg.add_subparsers(dest="config_command")
    p_cfg_val = cfg_sub.add_parser("validate", help="Validate config and data directory")
    p_cfg_val.set_defaults(func=cmd_config_validate)
    p_cfg_show = cfg_sub.add_parser("show", help="Show effective config (secrets redacted)")
    p_cfg_show.set_defaults(func=cmd_config_show)

    # register
    p_reg = sub.add_parser("register", help="Register a refundable Booking.com hotel booking")
    p_reg.add_argument("--confirmation", required=True, metavar="ID",
                       help="Booking.com confirmation number")
    p_reg.add_argument("--property", required=True, metavar="NAME", dest="property_name",
                       help="Hotel name")
    p_reg.add_argument("--property-ref", required=True, metavar="REF", dest="property_ref",
                       help="Booking.com property ID or URL")
    p_reg.add_argument("--check-in", required=True, metavar="YYYY-MM-DD", dest="check_in")
    p_reg.add_argument("--check-out", required=True, metavar="YYYY-MM-DD", dest="check_out")
    p_reg.add_argument("--room-type", required=True, metavar="LABEL", dest="room_type")
    p_reg.add_argument("--amount", required=True, metavar="DECIMAL",
                       help="Total amount paid")
    p_reg.add_argument("--currency", required=True, metavar="ISO",
                       help="3-letter currency code (e.g. EUR)")
    p_reg.add_argument("--refund-note", required=True, metavar="TEXT", dest="refund_note",
                       help="Refundability confirmation (e.g. 'Free cancellation until Aug 1')")
    p_reg.add_argument("--refund-deadline", metavar="YYYY-MM-DD", dest="refund_deadline",
                       help="Refund deadline date (optional)")
    p_reg.add_argument("--adults", required=True, type=int, metavar="N",
                       help="Adults the booking is for (search checks use the real party size)")
    p_reg.add_argument("--children", type=int, default=0, metavar="N",
                       help="Children the booking is for (default: 0)")
    p_reg.add_argument("--rooms", type=int, default=1, metavar="N",
                       help="Rooms booked (default: 1)")
    p_reg.set_defaults(func=cmd_register)

    # run
    p_run = sub.add_parser("run", help="Start the daemon (foreground; Ctrl-C or SIGTERM to stop)")
    p_run.set_defaults(func=cmd_run)

    # auth
    p_auth = sub.add_parser("auth", help="Log in to Booking.com in a browser; save session locally")
    p_auth.set_defaults(func=cmd_auth)

    # stop
    p_stop = sub.add_parser("stop", help="Stop the running daemon gracefully")
    p_stop.set_defaults(func=cmd_stop)

    # bookings
    p_bk = sub.add_parser("bookings", help="Booking commands")
    p_bk.set_defaults(func=_no_subcommand(p_bk))
    bk_sub = p_bk.add_subparsers(dest="bookings_command")
    p_bk_list = bk_sub.add_parser("list", help="List registered bookings")
    p_bk_list.add_argument("--all", action="store_true", help="Include archived bookings")
    p_bk_list.set_defaults(func=cmd_bookings_list)
    p_bk_occ = bk_sub.add_parser(
        "set-occupancy",
        help="Set occupancy on a booking registered before the occupancy field existed",
    )
    p_bk_occ.add_argument("booking_id", metavar="BOOKING_ID")
    p_bk_occ.add_argument("--adults", required=True, type=int, metavar="N")
    p_bk_occ.add_argument("--children", type=int, default=0, metavar="N")
    p_bk_occ.add_argument("--rooms", type=int, default=1, metavar="N")
    p_bk_occ.set_defaults(func=cmd_bookings_set_occupancy)

    # rebook
    p_rb = sub.add_parser(
        "rebook",
        help="Start a guided rebook (explicit confirmations before any cancel/purchase)",
    )
    p_rb.add_argument("opportunity_id", metavar="OPPORTUNITY_ID",
                      help="Savings opportunity id (see: booksaver savings list)")
    p_rb.add_argument("--no-browser", action="store_true", dest="no_browser",
                      help="Print URLs instead of opening a browser")
    p_rb.set_defaults(func=cmd_rebook)

    # rebook-log
    p_rl = sub.add_parser("rebook-log", help="Show the audit trail of a rebook session")
    p_rl.add_argument("session_id", metavar="SESSION_ID")
    p_rl.set_defaults(func=cmd_rebook_log)

    # checks
    p_ck = sub.add_parser("checks", help="Price-check history and traces")
    p_ck.set_defaults(func=_no_subcommand(p_ck))
    ck_sub = p_ck.add_subparsers(dest="checks_command")
    p_ck_list = ck_sub.add_parser("list", help="List recent checks for a booking")
    p_ck_list.add_argument("booking_id", metavar="BOOKING_ID",
                           help="Booking id (see: booksaver bookings list)")
    p_ck_list.add_argument("--limit", type=int, default=10, metavar="N")
    p_ck_list.set_defaults(func=cmd_checks_list)
    p_ck_trace = ck_sub.add_parser(
        "trace", help="Show the step-by-step trace of one check (incl. agent actions)"
    )
    p_ck_trace.add_argument("check_id", metavar="CHECK_ID")
    p_ck_trace.set_defaults(func=cmd_checks_trace)

    # savings
    p_sv = sub.add_parser("savings", help="Savings opportunity commands")
    p_sv.set_defaults(func=_no_subcommand(p_sv))
    sv_sub = p_sv.add_subparsers(dest="savings_command")
    p_sv_list = sv_sub.add_parser("list", help="List detected savings opportunities")
    p_sv_list.set_defaults(func=cmd_savings_list)

    return parser
