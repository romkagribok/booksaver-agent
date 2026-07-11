from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from booksaver.daemon.scheduler import Scheduler
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteSavingsRepository,
    SqliteStore,
)

from .router import CommandRouter, IncomingCommand

Reply = Callable[[int, str], None]

HELP_TEXT = (
    "BookSaver commands:\n"
    "/start - welcome message\n"
    "/help - this message\n"
    "/status - daemon health, bookings, next scheduled run\n"
    "/bookings - list monitored bookings\n"
    "/savings - list detected savings opportunities\n"
    "/checks <booking_id> - recent check history for a booking\n"
    "/cancelflow - cancel an in-progress dialog"
)


def _format_timedelta(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def register_readonly_commands(
    router: CommandRouter,
    reply: Reply,
    db_path: Path,
    scheduler: Scheduler,
) -> None:
    """Registers /start, /help, /status, /bookings, /savings, /checks (US-036).

    Every handler here is a read-only inbound-adapter concern: it only reads
    through the existing SQLite repositories (the same ones the CLI uses) and
    formats a chat-sized reply — no domain logic lives in this module.
    """

    def _start(cmd: IncomingCommand) -> None:
        reply(cmd.chat_id, "Welcome to BookSaver. Send /help to see what I can do.")

    def _help(cmd: IncomingCommand) -> None:
        reply(cmd.chat_id, HELP_TEXT)

    def _status(cmd: IncomingCommand) -> None:
        lines = ["BookSaver status"]
        started = scheduler.started_at
        if started is not None:
            uptime = datetime.now(UTC) - started
            lines.append(f"Uptime: {_format_timedelta(uptime)}")
        else:
            lines.append("Uptime: scheduler not started yet")

        next_run = scheduler.next_run_at
        lines.append(
            f"Next scheduled run: {next_run.isoformat() if next_run else 'pending first tick'}"
        )

        if not db_path.exists():
            lines.append("No bookings registered yet.")
            reply(cmd.chat_id, "\n".join(lines))
            return

        with SqliteStore(db_path) as store:
            bookings = SqliteBookingRepository(store).list_active()
            history = SqliteCheckHistoryRepository(store)
            lines.append(f"Bookings monitored: {len(bookings)}")
            for booking in bookings:
                recent = history.get_recent(booking.booking_id, limit=1)
                if recent:
                    result = recent[0]
                    lines.append(
                        f"  {booking.property.name[:24]} ({booking.booking_id[:8]}): "
                        f"{result.outcome.value} at {result.checked_at.isoformat()[:19]}"
                    )
                else:
                    lines.append(
                        f"  {booking.property.name[:24]} ({booking.booking_id[:8]}): "
                        "no checks yet"
                    )
        reply(cmd.chat_id, "\n".join(lines))

    def _bookings(cmd: IncomingCommand) -> None:
        if not db_path.exists():
            reply(cmd.chat_id, "No bookings registered yet.")
            return
        with SqliteStore(db_path) as store:
            bookings = SqliteBookingRepository(store).list_active()
        if not bookings:
            reply(cmd.chat_id, "No active bookings.")
            return
        lines = ["Your active bookings:"]
        for booking in bookings:
            lines.append(
                f"{booking.booking_id[:8]} — {booking.property.name} "
                f"{booking.stay_dates.check_in}→{booking.stay_dates.check_out} "
                f"{booking.baseline_price.amount} {booking.baseline_price.currency}"
            )
        reply(cmd.chat_id, "\n".join(lines))

    def _savings(cmd: IncomingCommand) -> None:
        if not db_path.exists():
            reply(cmd.chat_id, "No savings opportunities detected yet.")
            return
        with SqliteStore(db_path) as store:
            opportunities = SqliteSavingsRepository(store).list_all()
        if not opportunities:
            reply(cmd.chat_id, "No savings opportunities detected yet.")
            return
        lines = ["Savings opportunities:"]
        for opp in opportunities[:10]:
            lines.append(
                f"{opp.opportunity_id[:8]} — booking {opp.booking_id[:8]}: "
                f"saved {opp.amount_saved.amount} {opp.amount_saved.currency} "
                f"({opp.percent_saved}%)"
            )
        reply(cmd.chat_id, "\n".join(lines))

    def _checks(cmd: IncomingCommand) -> None:
        booking_id = cmd.args.strip()
        if not booking_id:
            reply(cmd.chat_id, "Usage: /checks <booking_id>")
            return
        if not db_path.exists():
            reply(cmd.chat_id, "No checks recorded yet.")
            return
        with SqliteStore(db_path) as store:
            results = SqliteCheckHistoryRepository(store).get_recent(booking_id, limit=5)
        if not results:
            reply(cmd.chat_id, f"No checks recorded for booking '{booking_id}'.")
            return
        lines = [f"Recent checks for {booking_id}:"]
        for result in results:
            if result.failure_reason is not None:
                detail = f"{result.failure_reason.code.value}: {result.failure_reason.detail[:40]}"
            elif result.live_price is not None:
                detail = f"{result.live_price.amount} {result.live_price.currency}"
            else:
                detail = "ok"
            lines.append(f"{result.checked_at.isoformat()[:19]}  {result.outcome.value}  {detail}")
        reply(cmd.chat_id, "\n".join(lines))

    router.register("/start", _start)
    router.register("/help", _help)
    router.register("/status", _status)
    router.register("/bookings", _bookings)
    router.register("/savings", _savings)
    router.register("/checks", _checks)
