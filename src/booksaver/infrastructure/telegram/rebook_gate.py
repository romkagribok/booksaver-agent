from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from booksaver.application.ports import (
    ConfirmationGate,
    RebookEventRepository,
    RebookSessionRepository,
)
from booksaver.application.rebook_service import RebookSessionService, UnknownOpportunityError
from booksaver.domain.models import Booking
from booksaver.domain.rebook import (
    ConfirmationAnswer,
    ConfirmationPrompt,
    EventType,
    RebookAction,
    RebookEvent,
    RebookSession,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteRebookEventRepository,
    SqliteRebookSessionRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)

from .client import TelegramBotClient
from .router import CommandRouter, IncomingCallback, IncomingCommand

logger = logging.getLogger(__name__)

Reply = Callable[[int, str], None]

_ACTION_LABELS = {
    RebookAction.CANCEL_EXISTING: "CANCEL your existing reservation",
    RebookAction.BOOK_NEW: "BOOK the new, cheaper offer",
}

_SEARCH_RESULTS_URL = "https://www.booking.com/searchresults.html"

# How often the blocking wait re-checks the daemon stop_event while parked on
# an inline-keyboard answer — keeps daemon shutdown responsive even with a
# long rebook_confirm_timeout_seconds (US-032 "daemon shutdown while parked").
_POLL_INTERVAL_SECONDS = 1.0


def build_deep_link_url(booking: Booking) -> str:
    """US-033: a Booking.com search-results URL reproducing the opportunity's
    property, dates, and occupancy — the same param names the search journey
    uses to reach the verified property page (`monitor/search_journey.py`'s
    `_search_results_url`: ``ss``/``checkin``/``checkout``/``group_adults``/
    ``group_children``/``no_rooms``). Sent to the user's own device; the VPS
    browser never navigates here (ADR-012/ADR-016 ActionGuard untouched).
    """
    occ = booking.occupancy
    params = {
        "ss": booking.property.name,
        "checkin": booking.stay_dates.check_in.isoformat(),
        "checkout": booking.stay_dates.check_out.isoformat(),
        "sb": "1",
        "src": "searchresults",
    }
    if occ is not None:
        params["group_adults"] = str(occ.adults)
        params["group_children"] = str(occ.children)
        params["no_rooms"] = str(occ.rooms)
    return f"{_SEARCH_RESULTS_URL}?{urlencode(params)}"


# ── inline-keyboard yes/no bridge ──────────────────────────────────────────


@dataclass
class _PendingPrompt:
    chat_id: int
    user_id: int
    message_id: int
    event: threading.Event = field(default_factory=threading.Event)
    approved: bool | None = None  # None until answered


class PendingPromptRegistry:
    """Thread-safe nonce -> in-flight inline-keyboard prompt map.

    The worker thread that sent the prompt blocks on `_PendingPrompt.event`;
    the bot loop thread (on a matching `callback_query`) resolves it here and
    sets the event. A nonce is unique per prompt (uuid4 hex) and removed once
    resolved or abandoned, so it can never be replayed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingPrompt] = {}

    def register(self, nonce: str, prompt: _PendingPrompt) -> None:
        with self._lock:
            self._pending[nonce] = prompt

    def discard(self, nonce: str) -> None:
        with self._lock:
            self._pending.pop(nonce, None)

    def resolve(self, nonce: str, chat_id: int, user_id: int, approved: bool) -> bool:
        """Answer a pending prompt. Returns False (and does nothing) if the
        nonce is unknown, or the answer came from a different chat/user than
        the one the prompt was sent to (US-032: "only the owning user's tap
        counts") — both are silently ignored, not errors."""
        with self._lock:
            prompt = self._pending.get(nonce)
            if prompt is None:
                return False
            if prompt.chat_id != chat_id or prompt.user_id != user_id:
                return False
            prompt.approved = approved
        prompt.event.set()
        return True


def wait_with_shutdown(
    event: threading.Event, stop_event: threading.Event, timeout_seconds: float
) -> bool:
    """Block on `event` up to `timeout_seconds`, polling `stop_event` too so a
    daemon shutdown parked on a rebook confirmation aborts promptly rather
    than waiting out the full (possibly 10-minute) timeout. Returns True only
    if `event` itself was set (an answer arrived)."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        if stop_event.is_set():
            return False
        if event.wait(timeout=min(remaining, _POLL_INTERVAL_SECONDS)):
            return True


def _make_keyboard(nonce: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Yes", "callback_data": f"rebook:{nonce}:yes"},
                {"text": "No", "callback_data": f"rebook:{nonce}:no"},
            ]
        ]
    }


class _SessionIdCapturingRepo:
    """Wraps `RebookSessionRepository` purely to observe the session_id the
    (unmodified) `RebookSessionService` assigns on `add()` — the gate needs it
    to attach extra Telegram audit metadata to the SAME rebook_events trail
    (US-032's "extend the audit mechanism additively"), and has no other way
    to learn it since `ConfirmationGate.ask()` only receives a `ConfirmationPrompt`,
    not the session. Every call still delegates to the real repository
    unchanged."""

    def __init__(self, inner: RebookSessionRepository, box: dict[str, str]) -> None:
        self._inner = inner
        self._box = box

    def add(self, session: RebookSession) -> None:
        self._box["session_id"] = session.session_id
        self._inner.add(session)

    def update(self, session: RebookSession) -> None:
        self._inner.update(session)

    def get(self, session_id: str) -> RebookSession | None:
        return self._inner.get(session_id)


class TelegramConfirmationGate:
    """`ConfirmationGate` adapter (US-032): one inline-keyboard yes/no prompt
    per mandatory confirmation, via the blocking bridge documented in
    `PendingPromptRegistry`/`wait_with_shutdown`. Only an explicit "Yes" tap
    approves; "No", a timeout, or a daemon shutdown while parked all decline
    (fail-safe, mirroring `TerminalConfirmationGate`'s EOF-declines behaviour).
    """

    def __init__(
        self,
        client: TelegramBotClient,
        registry: PendingPromptRegistry,
        chat_id: int,
        telegram_user_id: int,
        timeout_seconds: float,
        stop_event: threading.Event,
        event_repo: RebookEventRepository,
        session_id_box: dict[str, str],
    ) -> None:
        self._client = client
        self._registry = registry
        self._chat_id = chat_id
        self._telegram_user_id = telegram_user_id
        self._timeout_seconds = timeout_seconds
        self._stop_event = stop_event
        self._events = event_repo
        self._session_id_box = session_id_box

    @property
    def channel_name(self) -> str:
        return "telegram"

    def ask(self, prompt: ConfirmationPrompt) -> ConfirmationAnswer:
        nonce = uuid.uuid4().hex
        text = (
            f"CONFIRMATION REQUIRED: {_ACTION_LABELS[prompt.action]}\n\n"
            f"You paid   : {prompt.old_price.amount} {prompt.old_price.currency}\n"
            f"New price  : {prompt.new_price.amount} {prompt.new_price.currency}\n"
            f"Refunds    : {prompt.refundability_summary}\n\n"
            "Nothing happens unless you tap Yes."
        )
        sent = self._client.send_message(
            self._chat_id, text, reply_markup=_make_keyboard(nonce)
        )
        message_id = int(sent.get("message_id", 0))

        pending = _PendingPrompt(
            chat_id=self._chat_id, user_id=self._telegram_user_id, message_id=message_id
        )
        self._registry.register(nonce, pending)
        try:
            answered = wait_with_shutdown(pending.event, self._stop_event, self._timeout_seconds)
        finally:
            self._registry.discard(nonce)

        now = datetime.now(UTC)
        if not answered:
            approved = False
            outcome_label = (
                "Cancelled — daemon is shutting down." if self._stop_event.is_set() else
                "Expired — no answer received in time. Treated as a decline."
            )
        else:
            approved = bool(pending.approved)
            outcome_label = "You tapped: Yes" if approved else "You tapped: No"

        try:
            self._client.edit_message_text(
                self._chat_id, message_id, f"{text}\n\n{outcome_label}"
            )
        except Exception:
            logger.warning("Could not edit rebook confirmation message %s", message_id)

        self._record_audit(prompt.action, approved, message_id, now)
        return ConfirmationAnswer(approved=approved, answered_at=now)

    def _record_audit(
        self, action: RebookAction, approved: bool, message_id: int, at: datetime
    ) -> None:
        session_id = self._session_id_box.get("session_id")
        if session_id is None:
            logger.warning("No session_id captured — skipping Telegram audit event")
            return
        detail = (
            f"telegram_answer action={action.value} approved={approved} "
            f"chat_id={self._chat_id} message_id={message_id} at={at.isoformat()}"
        )
        event_type = EventType.CONFIRMED if approved else EventType.DECLINED
        self._events.append(RebookEvent.record(session_id, event_type, detail))


def answer_callback(
    registry: PendingPromptRegistry, client: TelegramBotClient, callback: IncomingCallback
) -> None:
    """Wire target for `BotLoop(callback_handler=...)`: resolves a pending
    rebook prompt from a `rebook:<nonce>:<yes|no>` callback_data payload.
    Anything else (unknown prefix, malformed nonce, wrong chat/user) is
    silently ignored — Telegram still gets `answerCallbackQuery` so its client
    spinner stops either way."""
    try:
        prefix, nonce, choice = callback.data.split(":", 2)
    except ValueError:
        return
    if prefix != "rebook" or choice not in ("yes", "no"):
        return
    resolved = registry.resolve(nonce, callback.chat_id, callback.user_id, choice == "yes")
    try:
        client.answer_callback_query(callback.callback_query_id)
    except Exception:
        logger.warning("Could not answer callback query %s", callback.callback_query_id)
    if not resolved:
        logger.info("Ignored rebook callback for unknown/mismatched nonce %s", nonce)


# ── device handoff + outcome follow-up (US-033) ────────────────────────────


class TelegramNavigator:
    """`Navigator` callback (US-033) invoked by the (unchanged)
    `RebookSessionService`. Never opens a browser — it sends the user a link
    to open on their own device. The service calls this exactly twice, in a
    fixed order: cancellation page, then the new-offer page. The FIRST call's
    URL (built by the service's own `_cancel_url`) is relayed as-is — it is
    the existing reservation's manage page and carries no dates/occupancy to
    reproduce. The SECOND call is replaced with our own deep link
    (`build_deep_link_url`) so it carries the opportunity's property, dates,
    and occupancy, per US-033 — the service's own `_rebook_url` has neither.
    """

    def __init__(
        self,
        client: TelegramBotClient,
        chat_id: int,
        booking: Booking,
        event_repo: RebookEventRepository,
        session_id_box: dict[str, str],
    ) -> None:
        self._client = client
        self._chat_id = chat_id
        self._booking = booking
        self._events = event_repo
        self._session_id_box = session_id_box
        self.cancel_handoff_sent = False
        self.book_handoff_sent = False

    def __call__(self, url: str, description: str) -> None:
        is_book_step = self.cancel_handoff_sent  # cancel step always comes first
        if is_book_step:
            link = build_deep_link_url(self._booking)
            self.book_handoff_sent = True
            kind = "book"
        else:
            link = url
            self.cancel_handoff_sent = True
            kind = "cancel"

        self._client.send_message(
            self._chat_id,
            f">>> {description}:\n{link}\n\n"
            "Open this on YOUR OWN device to finish — this bot never books or "
            "cancels for you. Before paying, double-check the new rate is still "
            "shown as refundable at checkout.",
        )
        self._record_handoff(kind, link)

    def _record_handoff(self, kind: str, link: str) -> None:
        session_id = self._session_id_box.get("session_id")
        if session_id is None:
            return
        detail = (
            f"telegram_handoff kind={kind} chat_id={self._chat_id} "
            f"url={link} at={datetime.now(UTC).isoformat()}"
        )
        self._events.append(RebookEvent.record(session_id, EventType.ACTION_EXECUTED, detail))


def _ask_outcome(
    client: TelegramBotClient,
    registry: PendingPromptRegistry,
    chat_id: int,
    telegram_user_id: int,
    question: str,
    timeout_seconds: float,
    stop_event: threading.Event,
) -> bool | None:
    """One inline-keyboard "did you complete it?" question. Returns True
    (completed), False (abandoned), or None (no answer — timeout/shutdown)."""
    nonce = uuid.uuid4().hex
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Completed", "callback_data": f"rebook:{nonce}:yes"},
                {"text": "Abandoned", "callback_data": f"rebook:{nonce}:no"},
            ]
        ]
    }
    sent = client.send_message(chat_id, question, reply_markup=keyboard)
    message_id = int(sent.get("message_id", 0))
    pending = _PendingPrompt(chat_id=chat_id, user_id=telegram_user_id, message_id=message_id)
    registry.register(nonce, pending)
    try:
        answered = wait_with_shutdown(pending.event, stop_event, timeout_seconds)
    finally:
        registry.discard(nonce)
    if not answered:
        return None
    return bool(pending.approved)


def run_outcome_followup(
    client: TelegramBotClient,
    registry: PendingPromptRegistry,
    chat_id: int,
    telegram_user_id: int,
    navigator: TelegramNavigator,
    event_repo: RebookEventRepository,
    session_id: str,
    timeout_seconds: float,
    stop_event: threading.Event,
) -> None:
    """US-033: after the guided session ends, ask (separately) whether the
    cancellation and/or the new booking were actually completed on the user's
    device — for each handoff that was actually sent. Not answering leaves a
    distinct "handoff sent, outcome unreported" event (the handoff event
    `TelegramNavigator` already recorded stands on its own; this appends an
    explicit "unreported" marker so the two cases are told apart in the log).
    """
    steps: list[tuple[str, str]] = []
    if navigator.cancel_handoff_sent:
        steps.append(("cancellation", "Did you complete cancelling the old reservation?"))
    if navigator.book_handoff_sent:
        steps.append(("booking", "Did you complete booking the new offer?"))

    for kind, question in steps:
        outcome = _ask_outcome(
            client, registry, chat_id, telegram_user_id, question, timeout_seconds, stop_event
        )
        if outcome is None:
            detail = f"telegram_outcome kind={kind} status=unreported"
        else:
            status = "completed" if outcome else "abandoned"
            detail = f"telegram_outcome kind={kind} status={status}"
        event_repo.append(RebookEvent.record(session_id, EventType.ACTION_EXECUTED, detail))


# ── /rebook command wiring ─────────────────────────────────────────────────


class _ActiveSessionGuard:
    """US-032: one active rebook session per (local) user at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: set[int] = set()

    def try_acquire(self, user_id: int) -> bool:
        with self._lock:
            if user_id in self._active:
                return False
            self._active.add(user_id)
            return True

    def release(self, user_id: int) -> None:
        with self._lock:
            self._active.discard(user_id)


def register_rebook_command(
    router: CommandRouter,
    reply: Reply,
    client: TelegramBotClient,
    db_path: Path,
    stop_event: threading.Event,
    confirm_timeout_seconds: float,
) -> Callable[[IncomingCallback], None]:
    """Registers `/rebook` (US-032/US-033) and returns the callback_handler to
    wire into `BotLoop(callback_handler=...)`.

    `/rebook` (no args) lists the sender's own actionable savings opportunities.
    `/rebook <id>` starts the existing, unchanged `RebookSessionService` with a
    `TelegramConfirmationGate` + `TelegramNavigator`, in a dedicated worker
    thread — `RebookSessionService.run()` stays synchronous; only the adapters
    it is given differ from the CLI's `TerminalConfirmationGate`.
    """
    registry = PendingPromptRegistry()
    session_guard = _ActiveSessionGuard()

    def _list_opportunities(cmd: IncomingCommand) -> None:
        if not db_path.exists():
            reply(cmd.chat_id, "No savings opportunities detected yet.")
            return
        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_by_telegram_id(cmd.user_id)
            if user is None or not user.is_active:
                reply(cmd.chat_id, "You're not recognized by this bot.")
                return
            opportunities = SqliteSavingsRepository(store).list_all_for_user(user.user_id)
        if not opportunities:
            reply(cmd.chat_id, "No savings opportunities to rebook right now.")
            return
        lines = ["Your savings opportunities — start a guided rebook with /rebook <id>:"]
        for opp in opportunities[:10]:
            lines.append(
                f"{opp.opportunity_id} — booking {opp.booking_id[:8]}: "
                f"saved {opp.amount_saved.amount} {opp.amount_saved.currency} "
                f"({opp.percent_saved}%)"
            )
        reply(cmd.chat_id, "\n".join(lines))

    def _run_session(
        chat_id: int,
        telegram_user_id: int,
        local_user_id: int,
        opportunity_id: str,
    ) -> None:
        try:
            with SqliteStore(db_path) as store:
                session_id_box: dict[str, str] = {}
                event_repo = SqliteRebookEventRepository(store)
                session_repo: RebookSessionRepository = _SessionIdCapturingRepo(
                    SqliteRebookSessionRepository(store), session_id_box
                )
                booking_repo = SqliteBookingRepository(store)
                savings_repo = SqliteSavingsRepository(store)

                opportunity = savings_repo.get(opportunity_id)
                if opportunity is None:
                    reply(chat_id, f"No savings opportunity found with id '{opportunity_id}'.")
                    return
                booking = booking_repo.get_by_id(opportunity.booking_id)
                if booking is None:
                    reply(chat_id, "That opportunity's booking no longer exists.")
                    return

                gate: ConfirmationGate = TelegramConfirmationGate(
                    client=client,
                    registry=registry,
                    chat_id=chat_id,
                    telegram_user_id=telegram_user_id,
                    timeout_seconds=confirm_timeout_seconds,
                    stop_event=stop_event,
                    event_repo=event_repo,
                    session_id_box=session_id_box,
                )
                navigator = TelegramNavigator(
                    client=client,
                    chat_id=chat_id,
                    booking=booking,
                    event_repo=event_repo,
                    session_id_box=session_id_box,
                )
                service = RebookSessionService(
                    savings_repo=savings_repo,
                    booking_repo=booking_repo,
                    session_repo=session_repo,
                    event_repo=event_repo,
                    gate=gate,
                    navigator=navigator,
                )
                try:
                    session = service.run(opportunity_id)
                except UnknownOpportunityError as e:
                    reply(chat_id, f"Error: {e}")
                    return
                except Exception as e:
                    logger.exception("Telegram rebook session failed")
                    reply(chat_id, f"Rebook session failed: {e}")
                    return

                reply(
                    chat_id,
                    f"Rebook session {session.session_id} ended: {session.state.value}.",
                )

                if navigator.cancel_handoff_sent or navigator.book_handoff_sent:
                    run_outcome_followup(
                        client=client,
                        registry=registry,
                        chat_id=chat_id,
                        telegram_user_id=telegram_user_id,
                        navigator=navigator,
                        event_repo=event_repo,
                        session_id=session.session_id,
                        timeout_seconds=confirm_timeout_seconds,
                        stop_event=stop_event,
                    )
        finally:
            session_guard.release(local_user_id)

    def _rebook(cmd: IncomingCommand) -> None:
        opportunity_id = cmd.args.strip()
        if not opportunity_id:
            _list_opportunities(cmd)
            return

        if not db_path.exists():
            reply(cmd.chat_id, "No local database yet — nothing to rebook.")
            return

        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_by_telegram_id(cmd.user_id)
            if user is None or not user.is_active:
                reply(cmd.chat_id, "You're not recognized by this bot.")
                return
            opportunity = SqliteSavingsRepository(store).get(opportunity_id)
            if opportunity is None:
                reply(cmd.chat_id, f"No savings opportunity found with id '{opportunity_id}'.")
                return
            owner = SqliteUserRepository(store).get_owner_of_booking(opportunity.booking_id)
            if owner is None or owner.user_id != user.user_id:
                # Same message for "doesn't exist" and "not yours" — don't leak
                # whether an opportunity belonging to someone else exists.
                reply(cmd.chat_id, f"No savings opportunity found with id '{opportunity_id}'.")
                return

        if not session_guard.try_acquire(user.user_id):
            reply(
                cmd.chat_id,
                "You already have a rebook session in progress. Finish or let it "
                "time out before starting another.",
            )
            return

        reply(
            cmd.chat_id,
            f"Starting a guided rebook for {opportunity_id}. "
            "I'll ask you to confirm each step here.",
        )
        thread = threading.Thread(
            target=_run_session,
            args=(cmd.chat_id, cmd.user_id, user.user_id, opportunity_id),
            name=f"rebook-{opportunity_id[:8]}",
            daemon=True,
        )
        thread.start()

    router.register("/rebook", _rebook)

    def _callback_handler(callback: IncomingCallback) -> None:
        answer_callback(registry, client, callback)

    return _callback_handler
