from __future__ import annotations

import logging
from collections.abc import Callable

from booksaver.domain.models import Booking, BookingStatus
from booksaver.domain.rebook import (
    ConfirmationPrompt,
    EventType,
    RebookAction,
    RebookEvent,
    RebookSession,
)
from booksaver.domain.savings import SavingsOpportunity

from .ports import (
    BookingRepository,
    ConfirmationGate,
    RebookEventRepository,
    RebookSessionRepository,
    SavingsRepository,
)

logger = logging.getLogger(__name__)

# Opens a URL for the user (or prints it). Injected so tests need no browser.
Navigator = Callable[[str, str], None]


class UnknownOpportunityError(Exception):
    pass


class SupersededOpportunityError(UnknownOpportunityError):
    pass


def _cancel_url(booking: Booking) -> str:
    ref = booking.property.booking_com_ref
    if ref.startswith(("http://", "https://")):
        return ref
    return "https://secure.booking.com/myreservations.html"


def _rebook_url(booking: Booking) -> str:
    return (
        "https://www.booking.com/searchresults.html"
        f"?ss={booking.property.name.replace(' ', '+')}"
        f"&checkin={booking.stay_dates.check_in.isoformat()}"
        f"&checkout={booking.stay_dates.check_out.isoformat()}"
    )


class RebookSessionService:
    """Runs a guided rebook session (US-010/011/012).

    Only invoked from an explicit CLI or Telegram request — the scheduler has no
    path to this service, which is the structural guarantee behind US-010's
    "no rebook automation without explicit intent". Per ADR-012 the destructive
    final click stays with the human: each approved step navigates to the right
    page and hands off.
    """

    def __init__(
        self,
        savings_repo: SavingsRepository,
        booking_repo: BookingRepository,
        session_repo: RebookSessionRepository,
        event_repo: RebookEventRepository,
        gate: ConfirmationGate,
        navigator: Navigator,
    ) -> None:
        self._savings = savings_repo
        self._bookings = booking_repo
        self._sessions = session_repo
        self._events = event_repo
        self._gate = gate
        self._navigate = navigator

    def run(self, opportunity_id: str) -> RebookSession:
        opportunity = self._savings.get(opportunity_id)
        if opportunity is None:
            raise UnknownOpportunityError(
                f"No savings opportunity found with id '{opportunity_id}'. "
                "Run 'booksaver savings list' to see available opportunities."
            )
        booking = self._bookings.get_by_id(opportunity.booking_id)
        if booking is None:
            raise UnknownOpportunityError(
                f"Opportunity '{opportunity_id}' references unknown booking "
                f"'{opportunity.booking_id}'."
            )
        current = self._savings.get_current_for_booking(opportunity.booking_id)
        if (
            booking.status is not BookingStatus.ACTIVE
            or current is None
            or current.opportunity_id != opportunity_id
        ):
            raise SupersededOpportunityError(
                f"Savings opportunity '{opportunity_id}' is no longer current. "
                "Run a fresh check and choose the current opportunity."
            )

        session = RebookSession.start(opportunity_id, booking.booking_id)
        if not self._sessions.add_if_opportunity_current(session):
            raise SupersededOpportunityError(
                f"Savings opportunity '{opportunity_id}' is no longer current. "
                "Run a fresh check and choose the current opportunity."
            )
        self._log(session, EventType.STARTED, f"opportunity {opportunity_id}")

        try:
            # Gate 1: cancel the existing reservation
            if not self._confirm_step(session, opportunity, booking, RebookAction.CANCEL_EXISTING):
                return session
            self._navigate(_cancel_url(booking), "cancellation page for your reservation")
            session.mark_cancel_executed()
            self._sessions.update(session)
            self._log(
                session,
                EventType.ACTION_EXECUTED,
                "opened cancellation page; final cancel click is yours (ADR-012)",
            )

            # Gate 2: book the new offer — a fresh confirmation (US-011)
            if not self._confirm_step(session, opportunity, booking, RebookAction.BOOK_NEW):
                return session
            self._navigate(_rebook_url(booking), "rebook search for the same stay")
            session.mark_book_executed()
            self._sessions.update(session)
            self._log(
                session,
                EventType.ACTION_EXECUTED,
                "opened rebook page; final booking click is yours (ADR-012)",
            )
            self._log(session, EventType.COMPLETED, "guided rebook session completed")
            return session
        except Exception as exc:
            if not session.is_terminal:
                session.fail(str(exc))
                self._sessions.update(session)
                self._log(session, EventType.ERROR, str(exc))
            raise

    def _confirm_step(
        self,
        session: RebookSession,
        opportunity: SavingsOpportunity,
        booking: Booking,
        action: RebookAction,
    ) -> bool:
        """Run one confirmation gate. Returns False if the user declined (session over)."""
        if action is RebookAction.CANCEL_EXISTING:
            session.await_cancel_confirmation()
        # (book gate: mark_cancel_executed already moved us to AWAITING_BOOK_CONFIRMATION)
        self._sessions.update(session)

        prompt = ConfirmationPrompt(
            action=action,
            old_price=opportunity.baseline_price,
            new_price=opportunity.live_price,
            refundability_summary=(
                f"Original: {booking.refundability.note or 'refundable'}. "
                "New offer: confirmed refundable at detection time."
            ),
        )
        self._log(session, EventType.CONFIRMATION_REQUESTED, action.value)

        answer = self._gate.ask(prompt)
        if not answer.approved:
            session.decline()
            self._sessions.update(session)
            self._log(session, EventType.DECLINED, f"user declined {action.value}")
            logger.info("User declined %s — session ended safely, nothing changed", action.value)
            return False

        session.approve()
        self._sessions.update(session)
        self._log(session, EventType.CONFIRMED, action.value)
        return True

    def _log(self, session: RebookSession, event_type: EventType, detail: str) -> None:
        self._events.append(RebookEvent.record(session.session_id, event_type, detail))
