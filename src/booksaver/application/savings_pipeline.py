from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from booksaver.domain.check_result import CheckOutcome, CheckResult
from booksaver.domain.models import Booking
from booksaver.domain.savings import RejectionReason, SavingsOpportunity, detect_savings

from .ports import BookingRepository, Notifier, SavingsRepository

logger = logging.getLogger(__name__)

# US-030: given a booking, resolve which notifier(s) should receive its alert
# (e.g. the booking's owning user's Telegram chat, not a single fixed list).
NotifierResolver = Callable[[Booking], "list[Notifier]"]


@dataclass(frozen=True)
class ChannelOutcome:
    channel: str
    ok: bool
    error: str | None = None


def render_alert(opportunity: SavingsOpportunity, booking: Booking) -> tuple[str, str]:
    """Subject + body shared by all channels (US-009 core facts + rebook pointer)."""
    saved = opportunity.amount_saved
    subject = (
        f"BookSaver: save {saved.amount} {saved.currency} "
        f"({opportunity.percent_saved}%) on {booking.property.name}"
    )
    body = (
        f"Savings opportunity found for your Booking.com reservation.\n"
        f"\n"
        f"Property     : {booking.property.name}\n"
        f"Confirmation : {booking.confirmation_id.value}\n"
        f"Stay         : {booking.stay_dates.check_in} -> {booking.stay_dates.check_out}\n"
        f"Room         : {booking.room_type.label}\n"
        f"\n"
        f"You paid     : {opportunity.baseline_price.amount} "
        f"{opportunity.baseline_price.currency}\n"
        f"Live price   : {opportunity.live_price.amount} {opportunity.live_price.currency}\n"
        f"You save     : {saved.amount} {saved.currency} ({opportunity.percent_saved}%)\n"
        f"\n"
        f"The cheaper offer is confirmed refundable and matches your stay and room.\n"
        f"\n"
        f"To start a guided rebook (nothing is cancelled or purchased without your\n"
        f"explicit confirmation), run:\n"
        f"\n"
        f"    booksaver rebook {opportunity.opportunity_id}\n"
    )
    return subject, body


class NotificationDispatcher:
    """Attempts every configured channel independently; never raises (US-009).

    `notifiers` is a fixed static list, used as-is for every booking — the
    pre-US-030 behavior (still the default, and what most tests construct).
    `resolver` (US-030) instead picks the channel(s) per-booking, e.g. routing
    a savings alert to the booking's owning user's own Telegram chat. When
    both are given, `resolver` wins.
    """

    def __init__(
        self,
        notifiers: list[Notifier] | None = None,
        resolver: NotifierResolver | None = None,
    ) -> None:
        self._notifiers = notifiers or []
        self._resolver = resolver

    def dispatch(self, opportunity: SavingsOpportunity, booking: Booking) -> list[ChannelOutcome]:
        notifiers = self._resolver(booking) if self._resolver is not None else self._notifiers
        if not notifiers:
            logger.warning(
                "Savings found for %s but no notification channels are configured/resolved",
                booking.booking_id,
            )
            return []

        subject, body = render_alert(opportunity, booking)
        outcomes: list[ChannelOutcome] = []
        for notifier in notifiers:
            try:
                notifier.send(subject, body)
                logger.info("Notification sent via %s", notifier.channel_name)
                outcomes.append(ChannelOutcome(channel=notifier.channel_name, ok=True))
            except Exception as exc:
                logger.error("Notification via %s failed: %s", notifier.channel_name, exc)
                outcomes.append(
                    ChannelOutcome(channel=notifier.channel_name, ok=False, error=str(exc))
                )
        return outcomes


class SavingsPipeline:
    def __init__(
        self,
        booking_repo: BookingRepository,
        savings_repo: SavingsRepository,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._bookings = booking_repo
        self._savings = savings_repo
        self._dispatcher = dispatcher

    def process(self, results: list[CheckResult]) -> list[SavingsOpportunity]:
        """Evaluate successful check results; persist + notify validated opportunities."""
        opportunities: list[SavingsOpportunity] = []
        for result in results:
            if result.outcome is not CheckOutcome.SUCCESS:
                continue
            booking = self._bookings.get_by_id(result.booking_id)
            if booking is None:
                logger.warning("Check %s references unknown booking %s",
                               result.check_id, result.booking_id)
                continue

            detection = detect_savings(booking, result)
            if isinstance(detection, RejectionReason):
                logger.info(
                    "No savings for booking %s: %s", booking.booking_id, detection.value
                )
                continue

            self._savings.add(detection)
            logger.info(
                "Savings opportunity %s: save %s %s (%s%%)",
                detection.opportunity_id,
                detection.amount_saved.amount,
                detection.amount_saved.currency,
                detection.percent_saved,
            )

            outcomes = self._dispatcher.dispatch(detection, booking)
            if any(o.ok for o in outcomes):
                self._savings.mark_notified(detection.opportunity_id, datetime.now(UTC))

            opportunities.append(detection)
        return opportunities
