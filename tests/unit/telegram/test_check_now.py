from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from booksaver.daemon.check_coordinator import (
    ImmediateAdmission,
    ImmediateCompletion,
    ImmediateCompletionKind,
)
from booksaver.domain.check_result import (
    CheckResult,
    ExtractionMethod,
    FailureCode,
    FailureReason,
)
from booksaver.domain.mobile_web import (
    GeniusEvidence,
    MobileProfileId,
    PriceSourceProvenance,
)
from booksaver.domain.models import Booking
from booksaver.domain.user import UserRole
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
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.check_now import register_check_now_command
from booksaver.infrastructure.telegram.router import (
    CallbackRouter,
    CommandRouter,
    IncomingCallback,
    IncomingCommand,
)


class FakeClient:
    def __init__(self) -> None:
        self.answers: list[str] = []
        self.edits: list[str] = []

    def answer_callback_query(self, callback_id: str, text: str | None = None) -> None:
        self.answers.append(callback_id)

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        self.edits.append(text)


class FakeCoordinator:
    def __init__(self, admission: ImmediateAdmission = ImmediateAdmission.ACCEPTED) -> None:
        self.admission = admission
        self.requests: list[tuple[int, str]] = []
        self.completions: list[Any] = []

    def request_immediate(self, user_id: int, booking_id: str, callback: Any) -> Any:
        self.requests.append((user_id, booking_id))
        self.completions.append(callback)
        return self.admission


def _booking(booking_id: str, name: str) -> Booking:
    return Booking(
        booking_id=booking_id,
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of(f"CONF-{booking_id}"),
        property=Property(name=name, booking_com_ref="https://booking.com/hotel/test"),
        stay_dates=StayDates(date(2026, 10, 1), date(2026, 10, 5)),
        room_type=RoomType("King"),
        baseline_price=Money(Decimal("400"), "EUR"),
        refundability=RefundabilityPolicy(True, "free cancellation"),
        registered_at=datetime.now(UTC),
        occupancy=Occupancy(2),
    )


def _setup(tmp_path: Path, coordinator: FakeCoordinator):
    db_path = tmp_path / "booksaver.db"
    router, callbacks = CommandRouter(), CallbackRouter()
    client = FakeClient()
    sent: list[tuple[int, str, dict[str, Any] | None]] = []
    register_check_now_command(
        router=router,
        callback_router=callbacks,
        reply=lambda chat, text: sent.append((chat, text, None)),
        send=lambda chat, text, markup: sent.append((chat, text, markup)),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
        coordinator=coordinator,  # type: ignore[arg-type]
    )
    return db_path, router, callbacks, client, sent


def _add_user_booking(db_path: Path, telegram_id: int, booking: Booking) -> None:
    with SqliteStore(db_path) as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(
            telegram_id, UserRole.USER
        )
        SqliteBookingRepository(store).add(booking, user_id=user.user_id)


def _price_source(genius: GeniusEvidence) -> PriceSourceProvenance:
    return PriceSourceProvenance(
        profile_id=MobileProfileId.ANDROID_CHROMIUM,
        session_revision_id="revision-7",
        genius_evidence=genius,
        observed_at=datetime.now(UTC),
    )


def test_no_arg_picker_is_scoped_and_callback_payload_is_safe(tmp_path: Path) -> None:
    coordinator = FakeCoordinator()
    db_path, router, _callbacks, _client, sent = _setup(tmp_path, coordinator)
    own = _booking("11111111-1111-4111-8111-111111111111", "Own Hotel")
    foreign = _booking("22222222-2222-4222-8222-222222222222", "Foreign Hotel")
    _add_user_booking(db_path, 101, own)
    _add_user_booking(db_path, 202, foreign)

    router.dispatch(IncomingCommand(101, 101, "/checknow", "", "/checknow"))

    markup = sent[-1][2]
    assert markup is not None
    button = markup["inline_keyboard"][0][0]
    assert "Own Hotel" in button["text"]
    assert "Foreign Hotel" not in str(markup)
    assert button["callback_data"] == f"checknow:{own.booking_id}"
    assert len(button["callback_data"].encode()) <= 64


def test_typed_unique_prefix_starts_background_request(tmp_path: Path) -> None:
    coordinator = FakeCoordinator()
    db_path, router, _callbacks, _client, sent = _setup(tmp_path, coordinator)
    booking = _booking("11111111-1111-4111-8111-111111111111", "Own Hotel")
    _add_user_booking(db_path, 101, booking)

    router.dispatch(IncomingCommand(101, 101, "/checknow", "11111111", "raw"))

    assert coordinator.requests == [(101, booking.booking_id)]
    assert "Checking Own Hotel now" in sent[-1][1]


def test_short_and_foreign_selectors_are_non_disclosing(tmp_path: Path) -> None:
    coordinator = FakeCoordinator()
    db_path, router, _callbacks, _client, sent = _setup(tmp_path, coordinator)
    _add_user_booking(
        db_path, 202, _booking("22222222-2222-4222-8222-222222222222", "Secret")
    )

    for selector in ("2222", "22222222"):
        router.dispatch(IncomingCommand(101, 101, "/checknow", selector, "raw"))

    assert coordinator.requests == []
    assert all("not available" in item[1] for item in sent)
    assert all("Secret" not in item[1] for item in sent)


def test_callback_rechecks_scope_acknowledges_and_handles_busy(tmp_path: Path) -> None:
    coordinator = FakeCoordinator(ImmediateAdmission.BUSY)
    db_path, _router, callbacks, client, _sent = _setup(tmp_path, coordinator)
    booking = _booking("11111111-1111-4111-8111-111111111111", "Own Hotel")
    _add_user_booking(db_path, 101, booking)

    callbacks.dispatch(IncomingCallback(101, 101, "cb-1", 9, f"checknow:{booking.booking_id}"))

    assert client.answers == ["cb-1"]
    assert "already running" in client.edits[-1]


def test_background_completion_is_sent_to_requesting_chat(tmp_path: Path) -> None:
    coordinator = FakeCoordinator()
    db_path, router, _callbacks, _client, sent = _setup(tmp_path, coordinator)
    booking = _booking("11111111-1111-4111-8111-111111111111", "Own Hotel")
    _add_user_booking(db_path, 101, booking)
    router.dispatch(IncomingCommand(101, 101, "/checknow", booking.booking_id, "raw"))

    coordinator.completions[0](
        ImmediateCompletion(kind=ImmediateCompletionKind.UNAVAILABLE)
    )

    assert sent[-1][0] == 101
    assert "not available" in sent[-1][1]


def test_success_completion_names_property_price_and_check(tmp_path: Path) -> None:
    coordinator = FakeCoordinator()
    db_path, router, _callbacks, _client, sent = _setup(tmp_path, coordinator)
    booking = _booking("11111111-1111-4111-8111-111111111111", "Own Hotel")
    _add_user_booking(db_path, 101, booking)
    router.dispatch(IncomingCommand(101, 101, "/checknow", booking.booking_id, "raw"))
    result = CheckResult.success(
        booking.booking_id,
        datetime.now(UTC),
        Money(Decimal("315.50"), "EUR"),
        ExtractionMethod.DOM,
    )

    coordinator.completions[0](
        ImmediateCompletion(
            ImmediateCompletionKind.RESULT,
            result=result,
            property_name="Own Hotel",
        )
    )

    assert "Own Hotel" in sent[-1][1]
    assert "315.50 EUR" in sent[-1][1]
    assert result.check_id[:8] in sent[-1][1]


def test_success_completion_reports_authenticated_mobile_and_genius_observed(
    tmp_path: Path,
) -> None:
    coordinator = FakeCoordinator()
    db_path, router, _callbacks, _client, sent = _setup(tmp_path, coordinator)
    booking = _booking("11111111-1111-4111-8111-111111111111", "Own Hotel")
    _add_user_booking(db_path, 101, booking)
    router.dispatch(IncomingCommand(101, 101, "/checknow", booking.booking_id, "raw"))
    result = CheckResult.success(
        booking.booking_id,
        datetime.now(UTC),
        Money(Decimal("315.50"), "EUR"),
        ExtractionMethod.DOM,
        price_source=_price_source(GeniusEvidence.APPLIED_OR_PRESENT),
    )

    coordinator.completions[0](
        ImmediateCompletion(
            ImmediateCompletionKind.RESULT,
            result=result,
            property_name="Own Hotel",
        )
    )

    assert "Source: authenticated mobile web (android-chromium)" in sent[-1][1]
    assert "Genius observed/present" in sent[-1][1]


def test_success_completion_reports_when_genius_not_observed(tmp_path: Path) -> None:
    coordinator = FakeCoordinator()
    db_path, router, _callbacks, _client, sent = _setup(tmp_path, coordinator)
    booking = _booking("11111111-1111-4111-8111-111111111111", "Own Hotel")
    _add_user_booking(db_path, 101, booking)
    router.dispatch(IncomingCommand(101, 101, "/checknow", booking.booking_id, "raw"))
    result = CheckResult.success(
        booking.booking_id,
        datetime.now(UTC),
        Money(Decimal("315.50"), "EUR"),
        ExtractionMethod.DOM,
        price_source=_price_source(GeniusEvidence.NOT_OBSERVED),
    )

    coordinator.completions[0](
        ImmediateCompletion(
            ImmediateCompletionKind.RESULT,
            result=result,
            property_name="Own Hotel",
        )
    )

    assert "Source: authenticated mobile web (android-chromium)" in sent[-1][1]
    assert "Genius not observed" in sent[-1][1]


def test_currency_failure_is_actionable_in_completion(tmp_path: Path) -> None:
    coordinator = FakeCoordinator()
    db_path, router, _callbacks, _client, sent = _setup(tmp_path, coordinator)
    booking = _booking("11111111-1111-4111-8111-111111111111", "Own Hotel")
    _add_user_booking(db_path, 101, booking)
    router.dispatch(IncomingCommand(101, 101, "/checknow", booking.booking_id, "raw"))
    result = CheckResult.failure(
        booking.booking_id,
        datetime.now(UTC),
        FailureReason(
            FailureCode.CURRENCY_MISMATCH,
            "Baseline EUR; matching refundable offers rendered in USD. "
            "No cross-currency comparison was made.",
        ),
    )

    coordinator.completions[0](
        ImmediateCompletion(
            ImmediateCompletionKind.RESULT,
            result=result,
            property_name="Own Hotel",
        )
    )

    assert "currency_mismatch" in sent[-1][1]
    assert "Baseline EUR" in sent[-1][1]
    assert "rendered in USD" in sent[-1][1]
    assert result.check_id[:8] in sent[-1][1]
