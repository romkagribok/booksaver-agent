from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from booksaver.daemon.check_coordinator import (
    CheckCoordinator,
    ImmediateAdmission,
    InventoryCompletion,
)
from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.account_sync import (
    AccountReservation,
    EligibilityReason,
    InventoryCompleteness,
    ReservationLifecycle,
)
from booksaver.domain.mobile_web import GeniusEvidence, PriceSourceProvenance
from booksaver.domain.user import User
from booksaver.domain.user_session import UserSessionHealth, UserSessionStatusView
from booksaver.domain.value_objects import DataDirectory
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)

from .client import TelegramBotClient
from .command_catalog import help_text
from .router import CallbackRouter, CommandRouter, IncomingCallback, IncomingCommand

Reply = Callable[[int, str], None]
Send = Callable[[int, str, dict[str, Any] | None], None]

logger = logging.getLogger(__name__)

_ELIGIBILITY_LABELS = {
    EligibilityReason.PAST_OR_COMPLETED: "stay is past or completed",
    EligibilityReason.CANCELLED: "cancelled",
    EligibilityReason.NOT_UPCOMING: "not an upcoming stay",
    EligibilityReason.NON_REFUNDABLE: "non-refundable",
    EligibilityReason.REFUNDABILITY_UNKNOWN: "refundability unavailable",
    EligibilityReason.MISSING_CONFIRMATION: "confirmation unavailable",
    EligibilityReason.MISSING_PROPERTY: "property identity unavailable",
    EligibilityReason.MISSING_STAY_DATES: "stay dates unavailable",
    EligibilityReason.MISSING_ROOM_TYPE: "room type unavailable",
    EligibilityReason.MISSING_OCCUPANCY: "occupancy unavailable",
    EligibilityReason.MISSING_BOOKED_TOTAL: "booked total unavailable",
    EligibilityReason.NOT_OBSERVED: "not present in the latest complete account refresh",
}


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


_NOT_RECOGNIZED = "You're not recognized by this bot."


def _format_session_status(
    status: UserSessionStatusView, telegram_user_id: int
) -> list[str]:
    health = status.health.value.replace("_", " ")
    lines = [f"Session: {health} (encrypted, per-user Booking.com session)"]
    if status.health is UserSessionHealth.READY:
        lines.append(
            "Last validated: "
            f"{status.validated_at.isoformat() if status.validated_at else 'not yet'}"
        )
        expires = status.expires_at.isoformat() if status.expires_at else "not reported"
        lines.append(
            f"Session expires: {expires}"
        )
    else:
        lines.append("Action: send /connect to sign in to Booking.com securely.")
    return lines


def _format_price_source(source: PriceSourceProvenance) -> str:
    detail = f"source=authenticated mobile web ({source.profile_id.value})"
    if source.genius_evidence is GeniusEvidence.APPLIED_OR_PRESENT:
        detail += "; Genius evidence visible"
    return detail


def register_readonly_commands(
    router: CommandRouter,
    reply: Reply,
    db_path: Path,
    scheduler: Scheduler,
    *,
    callback_router: CallbackRouter | None = None,
    client: TelegramBotClient | None = None,
    send: Send | None = None,
    is_owner: Callable[[int], bool] | None = None,
    check_coordinator: CheckCoordinator | None = None,
) -> None:
    """Registers /start, /help, /status, /bookings, /savings, /checks (US-036).

    Every handler here is a read-only inbound-adapter concern: it only reads
    through the existing SQLite repositories (the same ones the CLI uses) and
    formats a chat-sized reply — no domain logic lives in this module.

    `/bookings`, `/savings`, and `/checks` are sender-scoped (US-025/US-029):
    the sender is resolved via `UserRepository.get_by_telegram_id` and only
    that user's rows are shown — no query path here can surface another
    user's data. An unresolved or revoked sender gets a polite refusal;
    admission (who is even allowed to reach a command handler) is the
    parallel bolt-009 worker's access-control layer, not this module.
    `/status` combines daemon health with only the caller's active-booking
    count. It never enumerates exact records or includes another user's count.
    """

    def _resolve_active_user(store: SqliteStore, telegram_user_id: int) -> User | None:
        user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
        return user if user is not None and user.is_active else None

    def _start(cmd: IncomingCommand) -> None:
        include_admin = is_owner(cmd.chat_id) if is_owner is not None else True
        reply(
            cmd.chat_id,
            f"Welcome to BookSaver.\n\n{help_text(include_owner_only=include_admin)}",
        )

    def _help(cmd: IncomingCommand) -> None:
        include_admin = is_owner(cmd.chat_id) if is_owner is not None else True
        reply(cmd.chat_id, help_text(include_owner_only=include_admin))

    def _status(cmd: IncomingCommand) -> None:
        if not db_path.exists():
            reply(cmd.chat_id, _NOT_RECOGNIZED)
            return
        with SqliteStore(db_path) as store:
            user = _resolve_active_user(store, cmd.user_id)
            if user is None:
                reply(cmd.chat_id, _NOT_RECOGNIZED)
                return
            active_booking_count = len(
                SqliteBookingRepository(store).list_active_for_user(user.user_id)
            )
            session_status = EncryptedUserSessionRepository(
                DataDirectory(path=db_path.parent)
            ).status(user.user_id)

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

        lines.extend(_format_session_status(session_status, cmd.user_id))

        lines.append(f"Your active bookings: {active_booking_count}")
        reply(cmd.chat_id, "\n".join(lines))

    def _render_inventory(
        reservations: tuple[AccountReservation, ...],
        completion: InventoryCompletion | None = None,
    ) -> list[str]:
        today = datetime.now(UTC).date()
        reservations = tuple(
            reservation
            for reservation in reservations
            if reservation.observation.lifecycle is ReservationLifecycle.UPCOMING
            and reservation.observation.check_in is not None
            and reservation.observation.check_in > today
        )
        report = completion.report if completion is not None else None
        if not reservations:
            if report is not None and report.failure_detail:
                return [
                    "Booking.com refresh failed: "
                    f"{report.failure_detail}\n"
                    "No future synchronized reservations are available."
                ]
            return ["No future reservations found in your Booking.com account."]

        if report is None:
            header = "Your future Booking.com reservations:"
        elif report.succeeded:
            eligible = sum(
                reservation.eligibility.is_eligible for reservation in reservations
            )
            header = (
                "Future Booking.com reservations refreshed "
                f"({eligible} eligible, {len(reservations) - eligible} ineligible):"
            )
        elif report.completeness is InventoryCompleteness.INCOMPLETE:
            header = (
                "Booking.com refresh was incomplete; no missing reservations were "
                "removed. Showing future synchronized observations:"
            )
        elif report.failure_detail:
            header = (
                f"Booking.com refresh failed: {report.failure_detail}\n"
                "Showing the last safe future reservations:"
            )
        else:
            header = (
                "Booking.com refresh failed. Showing the last safe future reservations:"
            )

        entries: list[str] = []
        for reservation in reservations:
            item = reservation.observation
            name = item.property_name or item.confirmation_id or "Reservation"
            dates = (
                f"{item.check_in}→{item.check_out}"
                if item.check_in is not None and item.check_out is not None
                else "dates unavailable"
            )
            total = (
                f"{item.booked_total.amount} {item.booked_total.currency}"
                if item.booked_total is not None
                else "total unavailable"
            )
            if reservation.eligibility.is_eligible:
                eligibility = "eligible for price-drop checks"
            else:
                reasons = ", ".join(
                    _ELIGIBILITY_LABELS[reason]
                    for reason in reservation.eligibility.reasons
                )
                eligibility = f"ineligible: {reasons}"
            entries.append(
                f"{name}\n"
                f"  Confirmation: {item.confirmation_id or 'unavailable'}\n"
                f"  {dates} · {total} · {item.lifecycle.value}\n"
                f"  {eligibility}"
            )

        messages: list[str] = []
        current = header
        for entry in entries:
            candidate = f"{current}\n\n{entry}"
            if len(candidate) > 3800 and current != header:
                messages.append(current)
                current = f"More future Booking.com reservations:\n\n{entry}"
            else:
                current = candidate
        messages.append(current)
        return messages

    def _send_inventory(
        chat_id: int,
        completion: InventoryCompletion,
    ) -> None:
        for message in _render_inventory(completion.reservations, completion):
            reply(chat_id, message)

    def _bookings(cmd: IncomingCommand) -> None:
        if not db_path.exists():
            reply(cmd.chat_id, "No synchronized reservations yet. Send /connect first.")
            return
        if check_coordinator is not None:
            admission = check_coordinator.request_inventory(
                cmd.user_id,
                lambda completion: _send_inventory(cmd.chat_id, completion),
            )
            if admission is ImmediateAdmission.ACCEPTED:
                reply(cmd.chat_id, "Refreshing reservations from Booking.com…")
            elif admission is ImmediateAdmission.BUSY:
                reply(
                    cmd.chat_id,
                    "BookSaver is using the browser right now. Try /bookings again shortly.",
                )
            else:
                reply(cmd.chat_id, "BookSaver is shutting down.")
            return
        with SqliteStore(db_path) as store:
            user = _resolve_active_user(store, cmd.user_id)
            if user is None:
                reply(cmd.chat_id, _NOT_RECOGNIZED)
                return
            reservations = tuple(
                SqliteAccountReservationRepository(store).list_for_user(user.user_id)
            )
        for message in _render_inventory(reservations):
            reply(cmd.chat_id, message)

    def _savings(cmd: IncomingCommand) -> None:
        if not db_path.exists():
            reply(cmd.chat_id, "No savings opportunities detected yet.")
            return
        with SqliteStore(db_path) as store:
            user = _resolve_active_user(store, cmd.user_id)
            if user is None:
                reply(cmd.chat_id, _NOT_RECOGNIZED)
                return
            opportunities = SqliteSavingsRepository(store).list_all_for_user(user.user_id)
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

    def _checks_text(telegram_user_id: int, booking_id: str) -> str:
        if not db_path.exists():
            return "No checks recorded yet."
        with SqliteStore(db_path) as store:
            user = _resolve_active_user(store, telegram_user_id)
            if user is None:
                return _NOT_RECOGNIZED
            # Telegram displays the first eight characters of booking UUIDs.
            # Resolve that prefix only within the caller's own booking scope;
            # ambiguous/short/cross-user prefixes use the same not-found reply.
            owned_ids = [
                booking.booking_id
                for booking in SqliteBookingRepository(store).list_all_for_user(user.user_id)
            ]
            resolved_booking_id: str | None
            if booking_id in owned_ids:
                resolved_booking_id = booking_id
            elif len(booking_id) >= 8:
                prefix_matches = [value for value in owned_ids if value.startswith(booking_id)]
                resolved_booking_id = (
                    prefix_matches[0] if len(prefix_matches) == 1 else None
                )
            else:
                resolved_booking_id = None
            if resolved_booking_id is None:
                # Same message for "doesn't exist" and "not yours" — don't
                # leak which booking ids exist to a different user.
                return f"No checks recorded for booking '{booking_id}'."
            results = SqliteCheckHistoryRepository(store).get_recent(
                resolved_booking_id, limit=5
            )
        if not results:
            return f"No checks recorded for booking '{booking_id}'."
        lines = [f"Recent checks for {booking_id}:"]
        for result in results:
            if result.failure_reason is not None:
                detail = f"{result.failure_reason.code.value}: {result.failure_reason.detail[:40]}"
            elif result.live_price is not None:
                detail = f"{result.live_price.amount} {result.live_price.currency}"
            else:
                detail = "ok"
            if result.price_source is not None:
                detail += f"  {_format_price_source(result.price_source)}"
            lines.append(f"{result.checked_at.isoformat()[:19]}  {result.outcome.value}  {detail}")
        return "\n".join(lines)

    def _checks(cmd: IncomingCommand) -> None:
        booking_id = cmd.args.strip()
        if not booking_id:
            if callback_router is None or client is None or send is None:
                reply(cmd.chat_id, "Usage: /checks <booking_id>")
                return
            if not db_path.exists():
                reply(cmd.chat_id, "No bookings registered yet.")
                return
            with SqliteStore(db_path) as store:
                user = _resolve_active_user(store, cmd.user_id)
                if user is None:
                    reply(cmd.chat_id, _NOT_RECOGNIZED)
                    return
                bookings = SqliteBookingRepository(store).list_all_for_user(user.user_id)
            if not bookings:
                reply(cmd.chat_id, "No bookings registered yet.")
                return
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": (
                                f"{booking.property.name[:35]} · "
                                f"{booking.stay_dates.check_in:%b %d}–"
                                f"{booking.stay_dates.check_out:%b %d}"
                            ),
                            "callback_data": f"checks:{booking.booking_id}",
                        }
                    ]
                    for booking in bookings[:10]
                ]
            }
            send(cmd.chat_id, "Choose a booking to view recent checks:", keyboard)
            return
        reply(cmd.chat_id, _checks_text(cmd.user_id, booking_id))

    if callback_router is not None and client is not None:

        def _checks_callback(callback: IncomingCallback) -> None:
            booking_id = callback.data.removeprefix("checks:")
            text = _checks_text(callback.user_id, booking_id)
            try:
                client.answer_callback_query(callback.callback_query_id)
            except Exception:
                logger.warning(
                    "Could not answer checks callback %s",
                    callback.callback_query_id,
                )
            try:
                client.edit_message_text(callback.chat_id, callback.message_id, text)
            except Exception:
                # The read is complete even if the original Telegram message
                # was deleted before it could be edited.
                logger.warning(
                    "Could not edit checks result message %s", callback.message_id
                )

        callback_router.register("checks:", _checks_callback)

    router.register("/start", _start)
    router.register("/help", _help)
    router.register("/status", _status)
    router.register("/bookings", _bookings)
    router.register("/savings", _savings)
    router.register("/checks", _checks)
