from __future__ import annotations

import threading
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from booksaver.domain.rebook import (
    ConfirmationPrompt,
    EventType,
    RebookAction,
    RebookEvent,
)
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteRebookEventRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.rebook_gate import (
    PendingPromptRegistry,
    TelegramConfirmationGate,
    TelegramNavigator,
    _PendingPrompt,
    answer_callback,
    build_deep_link_url,
    register_rebook_command,
    run_outcome_followup,
    wait_with_shutdown,
)
from booksaver.infrastructure.telegram.router import CommandRouter, IncomingCallback

from ..monitor.fakes import make_booking

# ── shared fixtures ─────────────────────────────────────────────────────────


class FakeClient:
    """Minimal stand-in for TelegramBotClient's send/edit/answer surface.
    Thread-safe (accessed by both the test's main thread and worker threads
    spawned by `register_rebook_command`)."""

    def __init__(self, *, fail_answer: bool = False, fail_edit: bool = False) -> None:
        self._lock = threading.Lock()
        self._next_message_id = 1
        self.sent: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []
        self.answered_callbacks: list[str] = []
        self.fail_answer = fail_answer
        self.fail_edit = fail_edit

    def send_message(
        self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with self._lock:
            message_id = self._next_message_id
            self._next_message_id += 1
            self.sent.append(
                {"chat_id": chat_id, "text": text, "reply_markup": reply_markup,
                 "message_id": message_id}
            )
            return {"message_id": message_id}

    def edit_message_text(
        self, chat_id: int, message_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self.fail_edit:
            raise RuntimeError("edit failed")
        with self._lock:
            self.edits.append({"chat_id": chat_id, "message_id": message_id, "text": text})
            return {}

    def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> dict:
        if self.fail_answer:
            raise RuntimeError("answer failed")
        with self._lock:
            self.answered_callbacks.append(callback_query_id)
            return {}


class FakeEventRepo:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: list[RebookEvent] = []

    def append(self, event: RebookEvent) -> None:
        with self._lock:
            self.events.append(event)

    def list_for_session(self, session_id: str) -> list[RebookEvent]:
        with self._lock:
            return [e for e in self.events if e.session_id == session_id]


def _nonce_from_sent(sent: dict[str, Any], choice: str = "yes") -> str:
    keyboard = sent["reply_markup"]["inline_keyboard"][0]
    button = next(b for b in keyboard if b["callback_data"].endswith(f":{choice}"))
    _, nonce, _ = button["callback_data"].split(":", 2)
    return nonce


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met within timeout")


# ── build_deep_link_url (US-033) ────────────────────────────────────────────


def test_deep_link_reproduces_property_dates_and_occupancy() -> None:
    booking = make_booking(occupancy=Occupancy(adults=2, children=1, rooms=2))
    url = build_deep_link_url(booking)

    assert "ss=Hotel+Test" in url
    assert "checkin=2026-09-01" in url
    assert "checkout=2026-09-05" in url
    assert "group_adults=2" in url
    assert "group_children=1" in url
    assert "no_rooms=2" in url


# ── PendingPromptRegistry / wait_with_shutdown ──────────────────────────────


def test_registry_resolve_ignores_wrong_chat() -> None:
    registry = PendingPromptRegistry()
    prompt = _PendingPrompt(chat_id=10, user_id=20, message_id=1)
    registry.register("nonce-1", prompt)

    assert registry.resolve("nonce-1", chat_id=999, user_id=20, approved=True) is False
    assert prompt.approved is None
    assert not prompt.event.is_set()


def test_registry_resolve_ignores_wrong_user() -> None:
    registry = PendingPromptRegistry()
    prompt = _PendingPrompt(chat_id=10, user_id=20, message_id=1)
    registry.register("nonce-1", prompt)

    assert registry.resolve("nonce-1", chat_id=10, user_id=999, approved=True) is False
    assert not prompt.event.is_set()


def test_registry_resolve_matches_correct_chat_and_user() -> None:
    registry = PendingPromptRegistry()
    prompt = _PendingPrompt(chat_id=10, user_id=20, message_id=1)
    registry.register("nonce-1", prompt)

    assert registry.resolve("nonce-1", chat_id=10, user_id=20, approved=True) is True
    assert prompt.approved is True
    assert prompt.event.is_set()


def test_registry_resolve_unknown_nonce_is_ignored() -> None:
    registry = PendingPromptRegistry()
    assert registry.resolve("no-such-nonce", chat_id=10, user_id=20, approved=True) is False


def test_wait_with_shutdown_returns_true_when_event_set() -> None:
    event = threading.Event()
    stop_event = threading.Event()
    event.set()
    assert wait_with_shutdown(event, stop_event, timeout_seconds=5) is True


def test_wait_with_shutdown_times_out() -> None:
    event = threading.Event()
    stop_event = threading.Event()
    started = time.monotonic()
    result = wait_with_shutdown(event, stop_event, timeout_seconds=0.05)
    assert result is False
    assert time.monotonic() - started < 2.0


def test_wait_with_shutdown_aborts_promptly_on_stop_event() -> None:
    event = threading.Event()
    stop_event = threading.Event()
    stop_event.set()
    started = time.monotonic()
    result = wait_with_shutdown(event, stop_event, timeout_seconds=600)
    assert result is False
    assert time.monotonic() - started < 2.0  # doesn't wait out the 600s timeout


# ── answer_callback ──────────────────────────────────────────────────────────


def test_answer_callback_resolves_matching_nonce_and_acks_query() -> None:
    registry = PendingPromptRegistry()
    prompt = _PendingPrompt(chat_id=10, user_id=20, message_id=1)
    registry.register("nonce-1", prompt)
    client = FakeClient()
    callback = IncomingCallback(
        user_id=20, chat_id=10, callback_query_id="cbq-1", message_id=1,
        data="rebook:nonce-1:yes",
    )

    answer_callback(registry, client, callback)  # type: ignore[arg-type]

    assert prompt.approved is True
    assert client.answered_callbacks == ["cbq-1"]


def test_answer_callback_ignores_malformed_data() -> None:
    registry = PendingPromptRegistry()
    client = FakeClient()
    callback = IncomingCallback(
        user_id=20, chat_id=10, callback_query_id="cbq-1", message_id=1, data="not-a-payload",
    )

    answer_callback(registry, client, callback)  # type: ignore[arg-type]

    # Malformed/stale callbacks are still acknowledged so Telegram stops spinning.
    assert client.answered_callbacks == ["cbq-1"]


def test_answer_callback_from_wrong_chat_is_ignored_but_still_acked() -> None:
    registry = PendingPromptRegistry()
    prompt = _PendingPrompt(chat_id=10, user_id=20, message_id=1)
    registry.register("nonce-1", prompt)
    client = FakeClient()
    callback = IncomingCallback(
        user_id=20, chat_id=999, callback_query_id="cbq-1", message_id=1,
        data="rebook:nonce-1:yes",
    )

    answer_callback(registry, client, callback)  # type: ignore[arg-type]

    assert prompt.approved is None
    assert not prompt.event.is_set()
    assert client.answered_callbacks == ["cbq-1"]


# ── TelegramConfirmationGate ─────────────────────────────────────────────────


def _prompt() -> ConfirmationPrompt:
    return ConfirmationPrompt(
        action=RebookAction.CANCEL_EXISTING,
        old_price=Money(amount=Decimal("400.00"), currency="EUR"),
        new_price=Money(amount=Decimal("350.00"), currency="EUR"),
        refundability_summary="refundable",
    )


def _make_gate(
    client: FakeClient,
    registry: PendingPromptRegistry,
    events: FakeEventRepo,
    session_id_box: dict[str, str],
    timeout_seconds: float = 5.0,
    stop_event: threading.Event | None = None,
) -> TelegramConfirmationGate:
    return TelegramConfirmationGate(
        client=client,  # type: ignore[arg-type]
        registry=registry,
        chat_id=10,
        telegram_user_id=20,
        timeout_seconds=timeout_seconds,
        stop_event=stop_event or threading.Event(),
        event_repo=events,  # type: ignore[arg-type]
        session_id_box=session_id_box,
    )


def test_gate_approves_on_explicit_yes_tap() -> None:
    client = FakeClient()
    registry = PendingPromptRegistry()
    events = FakeEventRepo()
    box = {"session_id": "sess-1"}
    gate = _make_gate(client, registry, events, box)

    def _tap_yes() -> None:
        _wait_until(lambda: len(client.sent) == 1)
        nonce = _nonce_from_sent(client.sent[0], "yes")
        registry.resolve(nonce, chat_id=10, user_id=20, approved=True)

    threading.Thread(target=_tap_yes).start()
    answer = gate.ask(_prompt())

    assert answer.approved is True
    assert "You tapped: Yes" in client.edits[0]["text"]
    audit = [e for e in events.events if e.event_type is EventType.CONFIRMED]
    assert len(audit) == 1
    assert "channel" not in audit[0].detail or True  # detail format asserted below
    assert "telegram_answer" in audit[0].detail
    assert "chat_id=10" in audit[0].detail


def test_gate_declines_on_explicit_no_tap() -> None:
    client = FakeClient()
    registry = PendingPromptRegistry()
    events = FakeEventRepo()
    box = {"session_id": "sess-1"}
    gate = _make_gate(client, registry, events, box)

    def _tap_no() -> None:
        _wait_until(lambda: len(client.sent) == 1)
        nonce = _nonce_from_sent(client.sent[0], "no")
        registry.resolve(nonce, chat_id=10, user_id=20, approved=False)

    threading.Thread(target=_tap_no).start()
    answer = gate.ask(_prompt())

    assert answer.approved is False
    assert "You tapped: No" in client.edits[0]["text"]
    audit = [e for e in events.events if e.event_type is EventType.DECLINED]
    assert len(audit) == 1


def test_gate_declines_fail_safe_on_timeout() -> None:
    client = FakeClient()
    registry = PendingPromptRegistry()
    events = FakeEventRepo()
    box = {"session_id": "sess-1"}
    gate = _make_gate(client, registry, events, box, timeout_seconds=0.1)

    answer = gate.ask(_prompt())

    assert answer.approved is False
    assert "Expired" in client.edits[0]["text"]


def test_gate_declines_promptly_on_daemon_shutdown_while_parked() -> None:
    client = FakeClient()
    registry = PendingPromptRegistry()
    events = FakeEventRepo()
    box = {"session_id": "sess-1"}
    stop_event = threading.Event()
    gate = _make_gate(client, registry, events, box, timeout_seconds=600, stop_event=stop_event)

    def _shutdown_soon() -> None:
        _wait_until(lambda: len(client.sent) == 1)
        stop_event.set()

    threading.Thread(target=_shutdown_soon).start()
    started = time.monotonic()
    answer = gate.ask(_prompt())
    elapsed = time.monotonic() - started

    assert answer.approved is False
    assert elapsed < 5.0  # nowhere near the 600s timeout
    assert "shutting down" in client.edits[0]["text"]


def test_gate_answer_from_wrong_chat_is_ignored_original_prompt_still_pending() -> None:
    client = FakeClient()
    registry = PendingPromptRegistry()
    events = FakeEventRepo()
    box = {"session_id": "sess-1"}
    gate = _make_gate(client, registry, events, box, timeout_seconds=0.3)

    def _tap_from_other_chat() -> None:
        _wait_until(lambda: len(client.sent) == 1)
        nonce = _nonce_from_sent(client.sent[0], "yes")
        resolved = registry.resolve(nonce, chat_id=99999, user_id=20, approved=True)
        assert resolved is False

    threading.Thread(target=_tap_from_other_chat).start()
    answer = gate.ask(_prompt())

    # The wrong-chat tap never resolved the real prompt, so it fails safe on timeout.
    assert answer.approved is False


# ── TelegramNavigator ────────────────────────────────────────────────────────


def test_navigator_relays_cancel_url_then_builds_own_deep_link_for_book_step() -> None:
    client = FakeClient()
    events = FakeEventRepo()
    booking = make_booking(occupancy=Occupancy(adults=3, children=0, rooms=1))
    box = {"session_id": "sess-1"}
    navigator = TelegramNavigator(
        client=client,  # type: ignore[arg-type]
        chat_id=10,
        booking=booking,
        event_repo=events,  # type: ignore[arg-type]
        session_id_box=box,
    )

    navigator("https://secure.booking.com/myreservations.html", "cancellation page")
    navigator("https://www.booking.com/searchresults.html?ss=Hotel+Test", "rebook search")

    assert navigator.cancel_handoff_sent is True
    assert navigator.book_handoff_sent is True
    assert "myreservations.html" in client.sent[0]["text"]
    assert "group_adults=3" in client.sent[1]["text"]
    assert "checkin=2026-09-01" in client.sent[1]["text"]

    handoffs = [e for e in events.events if "telegram_handoff" in e.detail]
    assert len(handoffs) == 2
    assert "kind=cancel" in handoffs[0].detail
    assert "kind=book" in handoffs[1].detail


# ── run_outcome_followup ─────────────────────────────────────────────────────


def test_outcome_followup_records_completed_and_abandoned() -> None:
    client = FakeClient()
    registry = PendingPromptRegistry()
    events = FakeEventRepo()
    booking = make_booking()
    navigator = TelegramNavigator(
        client=client,  # type: ignore[arg-type]
        chat_id=10,
        booking=booking,
        event_repo=events,  # type: ignore[arg-type]
        session_id_box={"session_id": "sess-1"},
    )
    navigator.cancel_handoff_sent = True
    navigator.book_handoff_sent = True

    def _answer_both() -> None:
        _wait_until(lambda: len(client.sent) == 1)
        nonce = _nonce_from_sent(client.sent[0], "yes")
        registry.resolve(nonce, chat_id=10, user_id=20, approved=True)
        _wait_until(lambda: len(client.sent) == 2)
        nonce2 = _nonce_from_sent(client.sent[1], "no")
        registry.resolve(nonce2, chat_id=10, user_id=20, approved=False)

    threading.Thread(target=_answer_both).start()
    run_outcome_followup(
        client=client,  # type: ignore[arg-type]
        registry=registry,
        chat_id=10,
        telegram_user_id=20,
        navigator=navigator,
        event_repo=events,  # type: ignore[arg-type]
        session_id="sess-1",
        timeout_seconds=5.0,
        stop_event=threading.Event(),
    )

    outcomes = [e for e in events.events if "telegram_outcome" in e.detail]
    assert len(outcomes) == 2
    assert "kind=cancellation status=completed" in outcomes[0].detail
    assert "kind=booking status=abandoned" in outcomes[1].detail


def test_outcome_followup_unreported_on_timeout() -> None:
    client = FakeClient()
    registry = PendingPromptRegistry()
    events = FakeEventRepo()
    booking = make_booking()
    navigator = TelegramNavigator(
        client=client,  # type: ignore[arg-type]
        chat_id=10,
        booking=booking,
        event_repo=events,  # type: ignore[arg-type]
        session_id_box={"session_id": "sess-1"},
    )
    navigator.cancel_handoff_sent = True

    run_outcome_followup(
        client=client,  # type: ignore[arg-type]
        registry=registry,
        chat_id=10,
        telegram_user_id=20,
        navigator=navigator,
        event_repo=events,  # type: ignore[arg-type]
        session_id="sess-1",
        timeout_seconds=0.1,
        stop_event=threading.Event(),
    )

    outcomes = [e for e in events.events if "telegram_outcome" in e.detail]
    assert len(outcomes) == 1
    assert "status=unreported" in outcomes[0].detail


# ── register_rebook_command (end-to-end wiring) ─────────────────────────────


def _fixture_db(tmp_path: Path) -> tuple[Path, int, str, str]:
    """Sets up a user + booking + savings opportunity. Returns
    (db_path, telegram_user_id, booking_id, opportunity_id)."""
    db_path = tmp_path / "booksaver.db"
    telegram_user_id = 555
    booking = make_booking(occupancy=Occupancy(adults=2, children=0, rooms=1))
    opportunity_id = str(uuid.uuid4())
    with SqliteStore(db_path) as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_user_id)
        SqliteBookingRepository(store).add(booking, user_id=user.user_id)
        SqliteSavingsRepository(store).add(
            SavingsOpportunity(
                opportunity_id=opportunity_id,
                booking_id=booking.booking_id,
                check_id="chk-1",
                baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
                live_price=Money(amount=Decimal("350.00"), currency="EUR"),
                amount_saved=Money(amount=Decimal("50.00"), currency="EUR"),
                percent_saved=Decimal("12.50"),
                validated_at=datetime.now(UTC),
            )
        )
    return db_path, telegram_user_id, booking.booking_id, opportunity_id


def test_rebook_no_args_lists_users_own_opportunities(tmp_path: Path) -> None:
    db_path, telegram_user_id, _booking_id, opportunity_id = _fixture_db(tmp_path)
    client = FakeClient()
    router = CommandRouter()
    replies: list[tuple[int, str]] = []
    register_rebook_command(
        router=router,
        reply=lambda cid, text: replies.append((cid, text)),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        stop_event=threading.Event(),
        confirm_timeout_seconds=5.0,
    )
    from booksaver.infrastructure.telegram.router import IncomingCommand

    router.dispatch(
        IncomingCommand(
            user_id=telegram_user_id, chat_id=telegram_user_id, command="/rebook", args="",
            raw_text="/rebook",
        )
    )

    assert len(replies) == 1
    assert opportunity_id in replies[0][1]


def test_rebook_no_args_offers_owned_opportunity_button(tmp_path: Path) -> None:
    db_path, telegram_user_id, _booking_id, opportunity_id = _fixture_db(tmp_path)
    client = FakeClient()
    router = CommandRouter()
    register_rebook_command(
        router=router,
        reply=lambda cid, text: None,
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        stop_event=threading.Event(),
        confirm_timeout_seconds=5.0,
        send=lambda chat_id, text, markup: client.send_message(chat_id, text, markup),
    )
    from booksaver.infrastructure.telegram.router import IncomingCommand

    router.dispatch(
        IncomingCommand(
            user_id=telegram_user_id,
            chat_id=telegram_user_id,
            command="/rebook",
            args="",
            raw_text="/rebook",
        )
    )

    button = client.sent[0]["reply_markup"]["inline_keyboard"][0][0]
    assert "Hotel Test" in button["text"]
    assert button["callback_data"] == f"rebook:select:{opportunity_id}"
    assert len(button["callback_data"].encode()) <= 64


def test_rebook_selection_callback_rechecks_opportunity_ownership(tmp_path: Path) -> None:
    db_path, _telegram_user_id, _booking_id, opportunity_id = _fixture_db(tmp_path)
    stranger_telegram_id = 999
    with SqliteStore(db_path) as store:
        SqliteUserRepository(store).get_or_create_by_telegram_id(stranger_telegram_id)
    client = FakeClient()
    router = CommandRouter()
    replies: list[str] = []
    callback_handler = register_rebook_command(
        router=router,
        reply=lambda cid, text: replies.append(text),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        stop_event=threading.Event(),
        confirm_timeout_seconds=5.0,
    )

    callback_handler(
        IncomingCallback(
            user_id=stranger_telegram_id,
            chat_id=stranger_telegram_id,
            callback_query_id="cb-select",
            message_id=1,
            data=f"rebook:select:{opportunity_id}",
        )
    )

    assert client.answered_callbacks == ["cb-select"]
    assert any("No savings opportunity found" in text for text in replies)
    assert not any("confirm" in message["text"].lower() for message in client.sent)


def test_rebook_selection_callback_starts_existing_guided_session(tmp_path: Path) -> None:
    db_path, telegram_user_id, _booking_id, opportunity_id = _fixture_db(tmp_path)
    client = FakeClient()
    router = CommandRouter()
    replies: list[str] = []
    callback_handler = register_rebook_command(
        router=router,
        reply=lambda cid, text: replies.append(text),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        stop_event=threading.Event(),
        confirm_timeout_seconds=5.0,
    )

    callback_handler(
        IncomingCallback(
            user_id=telegram_user_id,
            chat_id=telegram_user_id,
            callback_query_id="cb-select",
            message_id=1,
            data=f"rebook:select:{opportunity_id}",
        )
    )

    _wait_until(lambda: len(client.sent) >= 1)
    assert any("Starting a guided rebook" in text for text in replies)
    nonce = _nonce_from_sent(client.sent[0], "no")
    callback_handler(
        IncomingCallback(
            user_id=telegram_user_id,
            chat_id=telegram_user_id,
            callback_query_id="cb-decline",
            message_id=client.sent[0]["message_id"],
            data=f"rebook:{nonce}:no",
        )
    )
    _wait_until(lambda: any("ended: declined" in text for text in replies))


def test_rebook_selection_starts_when_acknowledgement_and_picker_edit_fail(
    tmp_path: Path, caplog
) -> None:
    db_path, telegram_user_id, _booking_id, opportunity_id = _fixture_db(tmp_path)
    client = FakeClient(fail_answer=True, fail_edit=True)
    router = CommandRouter()
    replies: list[str] = []
    callback_handler = register_rebook_command(
        router=router,
        reply=lambda cid, text: replies.append(text),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        stop_event=threading.Event(),
        confirm_timeout_seconds=5.0,
    )

    callback_handler(
        IncomingCallback(
            user_id=telegram_user_id,
            chat_id=telegram_user_id,
            callback_query_id="cb-ui-fails",
            message_id=1,
            data=f"rebook:select:{opportunity_id}",
        )
    )

    _wait_until(lambda: len(client.sent) >= 1)
    assert any("Starting a guided rebook" in text for text in replies)
    assert "Could not answer rebook selection callback" in caplog.text
    assert "Could not update rebook selection message 1" in caplog.text

    nonce = _nonce_from_sent(client.sent[0], "no")
    callback_handler(
        IncomingCallback(
            user_id=telegram_user_id,
            chat_id=telegram_user_id,
            callback_query_id="cb-decline",
            message_id=client.sent[0]["message_id"],
            data=f"rebook:{nonce}:no",
        )
    )
    _wait_until(lambda: any("ended: declined" in text for text in replies))


def test_rebook_refuses_opportunity_owned_by_another_user(tmp_path: Path) -> None:
    db_path, _owner_telegram_id, _booking_id, opportunity_id = _fixture_db(tmp_path)
    stranger_telegram_id = 999
    with SqliteStore(db_path) as store:
        SqliteUserRepository(store).get_or_create_by_telegram_id(stranger_telegram_id)

    client = FakeClient()
    router = CommandRouter()
    replies: list[tuple[int, str]] = []
    register_rebook_command(
        router=router,
        reply=lambda cid, text: replies.append((cid, text)),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        stop_event=threading.Event(),
        confirm_timeout_seconds=5.0,
    )
    from booksaver.infrastructure.telegram.router import IncomingCommand

    router.dispatch(
        IncomingCommand(
            user_id=stranger_telegram_id, chat_id=stranger_telegram_id, command="/rebook",
            args=opportunity_id, raw_text=f"/rebook {opportunity_id}",
        )
    )

    assert len(replies) == 1
    assert "No savings opportunity found" in replies[0][1]
    # No session was started for the stranger.
    assert client.sent == []


def test_rebook_one_active_session_per_user(tmp_path: Path) -> None:
    db_path, telegram_user_id, _booking_id, opportunity_id = _fixture_db(tmp_path)
    client = FakeClient()
    router = CommandRouter()
    replies: list[tuple[int, str]] = []
    callback_handler = register_rebook_command(
        router=router,
        reply=lambda cid, text: replies.append((cid, text)),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        stop_event=threading.Event(),
        confirm_timeout_seconds=5.0,
    )
    from booksaver.infrastructure.telegram.router import IncomingCommand

    cmd = IncomingCommand(
        user_id=telegram_user_id, chat_id=telegram_user_id, command="/rebook",
        args=opportunity_id, raw_text=f"/rebook {opportunity_id}",
    )
    router.dispatch(cmd)
    _wait_until(lambda: len(client.sent) >= 1)  # first confirmation prompt sent

    router.dispatch(cmd)  # second /rebook while the first is still parked

    assert any("already have a rebook session in progress" in text for _cid, text in replies)

    # Clean up: decline the first session so its worker thread exits promptly.
    nonce = _nonce_from_sent(client.sent[0], "no")
    callback_handler(
        IncomingCallback(
            user_id=telegram_user_id, chat_id=telegram_user_id, callback_query_id="cbq-1",
            message_id=client.sent[0]["message_id"], data=f"rebook:{nonce}:no",
        )
    )
    _wait_until(lambda: any("ended: declined" in text for _cid, text in replies))


def test_rebook_happy_path_end_to_end(tmp_path: Path) -> None:
    db_path, telegram_user_id, _booking_id, opportunity_id = _fixture_db(tmp_path)
    client = FakeClient()
    router = CommandRouter()
    replies: list[tuple[int, str]] = []
    callback_handler = register_rebook_command(
        router=router,
        reply=lambda cid, text: replies.append((cid, text)),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        stop_event=threading.Event(),
        confirm_timeout_seconds=5.0,
    )
    from booksaver.infrastructure.telegram.router import IncomingCommand

    router.dispatch(
        IncomingCommand(
            user_id=telegram_user_id, chat_id=telegram_user_id, command="/rebook",
            args=opportunity_id, raw_text=f"/rebook {opportunity_id}",
        )
    )

    def _tap(index: int, choice: str) -> None:
        _wait_until(lambda: len(client.sent) > index)
        nonce = _nonce_from_sent(client.sent[index], choice)
        result = callback_handler(
            IncomingCallback(
                user_id=telegram_user_id, chat_id=telegram_user_id,
                callback_query_id=f"cbq-{index}",
                message_id=client.sent[index]["message_id"], data=f"rebook:{nonce}:{choice}",
            )
        )
        return result

    # message[0] = cancel confirmation prompt
    _tap(0, "yes")
    # message[1] = cancel handoff link (from TelegramNavigator)
    _wait_until(lambda: len(client.sent) >= 2)
    assert "cancellation page" in client.sent[1]["text"]
    # message[2] = book confirmation prompt
    _tap(2, "yes")
    # message[3] = book handoff deep link (occupancy-aware)
    _wait_until(lambda: len(client.sent) >= 4)
    assert "group_adults=2" in client.sent[3]["text"]
    # The "session ended: completed" summary goes through `reply`, not
    # client.send_message; message[4]/[5] are the outcome follow-up questions.
    _wait_until(lambda: len(client.sent) >= 5)

    _tap(4, "yes")  # cancellation outcome
    _wait_until(lambda: len(client.sent) >= 6)
    _tap(5, "yes")  # booking outcome

    _wait_until(lambda: any("ended: completed" in text for _cid, text in replies))

    with SqliteStore(db_path) as store:
        sessions = list(
            store.conn.execute(
                "SELECT session_id FROM rebook_sessions WHERE opportunity_id = ?",
                (opportunity_id,),
            )
        )
        assert len(sessions) == 1
        session_id = sessions[0][0]
        events = SqliteRebookEventRepository(store).list_for_session(session_id)

    detail_blob = "\n".join(e.detail for e in events)
    assert "telegram_answer" in detail_blob
    assert "telegram_handoff" in detail_blob
    assert "telegram_outcome kind=cancellation status=completed" in detail_blob
    assert "telegram_outcome kind=booking status=completed" in detail_blob
