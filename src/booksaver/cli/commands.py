from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from booksaver.application.load_config import load_config
from booksaver.application.register_booking import register_booking
from booksaver.daemon import lifecycle
from booksaver.daemon import scheduler as scheduler_mod
from booksaver.domain.errors import BookingRejectedError, ConfigValidationError
from booksaver.domain.models import Config
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
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
    SqliteStore,
)

_SAMPLE_CONFIG = """\
[schedule]
check_interval = "6h"            # How often to check for price drops (e.g. "30m", "6h", "1d")

[storage]
data_directory = "~/.booksaver"  # Where all BookSaver data is stored — local only

[notifications]
# Non-secret identifiers go here. Secrets come from environment variables.
# email = "your@email.com"           # password: export BOOKSAVER_SMTP_PASSWORD=...
# telegram_chat_id = "123456789"     # token:    export BOOKSAVER_TELEGRAM_BOT_TOKEN=...

[extraction]
# LLM model selection goes here. API key comes from an environment variable.
# model = "claude-sonnet-4-6"        # key:      export BOOKSAVER_LLM_API_KEY=...
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
    except ValueError as e:
        print(f"Invalid input: {e}", file=sys.stderr)
        return 2

    ensure_data_dir(cfg.data_directory)
    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
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
    return 0


# ── bookings list ─────────────────────────────────────────────────────────────

def cmd_bookings_list(args: argparse.Namespace) -> int:
    cfg, db_path = _db_path_for(args)

    if not db_path.exists():
        print("No bookings registered yet.")
        return 0

    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        bookings = repo.list_all() if getattr(args, "all", False) else repo.list_active()

    if not bookings:
        label = "bookings" if getattr(args, "all", False) else "active bookings"
        print(f"No {label} found.")
        return 0

    header = (
        f"{'ID':8}  {'CONFIRMATION':20}  {'PROPERTY':25}  "
        f"{'CHECK-IN':10}  {'CHECK-OUT':10}  {'BASELINE':>14}  {'STATUS':8}"
    )
    print(header)
    print("-" * len(header))
    for b in bookings:
        print(
            f"{b.booking_id[:8]:8}  "
            f"{b.confirmation_id.value[:20]:20}  "
            f"{b.property.name[:25]:25}  "
            f"{str(b.stay_dates.check_in):10}  "
            f"{str(b.stay_dates.check_out):10}  "
            f"{str(b.baseline_price.amount) + ' ' + b.baseline_price.currency:>14}  "
            f"{b.status.value:8}"
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

    def _placeholder_job() -> None:
        import logging
        logging.getLogger(__name__).info("Price check tick (no monitor registered yet)")

    sched.register("placeholder_check", _placeholder_job)

    print(f"BookSaver daemon starting (interval={cfg.check_interval}, data={cfg.data_directory.path})")  # noqa: E501
    print("Press Ctrl-C or send SIGTERM to stop cleanly.")
    lifecycle.start(cfg, sched)
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
    p_reg.set_defaults(func=cmd_register)

    # run
    p_run = sub.add_parser("run", help="Start the daemon (foreground; Ctrl-C or SIGTERM to stop)")
    p_run.set_defaults(func=cmd_run)

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

    return parser
