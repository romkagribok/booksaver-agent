from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from booksaver.application.savings_pipeline import (
    NotificationDispatcher,
    SavingsPipeline,
    render_alert,
)
from booksaver.domain.check_result import (
    CheckResult,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
)
from booksaver.domain.mobile_web import (
    GeniusEvidence,
    MobileProfileId,
    PriceSourceProvenance,
)
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.session import SessionMode
from booksaver.domain.value_objects import Money

from ..monitor.fakes import FakeBookingRepository, make_booking


class FakeNotifier:
    def __init__(self, name: str, fail: bool = False) -> None:
        self._name = name
        self._fail = fail
        self.sent: list[tuple[str, str]] = []

    @property
    def channel_name(self) -> str:
        return self._name

    def send(self, subject: str, body: str) -> None:
        if self._fail:
            raise ConnectionError(f"{self._name} unreachable")
        self.sent.append((subject, body))


class FakeSavingsRepository:
    def __init__(self) -> None:
        self.added: list[SavingsOpportunity] = []
        self.notified: list[str] = []

    def add(self, opportunity: SavingsOpportunity) -> None:
        self.added.append(opportunity)

    def get(self, opportunity_id: str) -> SavingsOpportunity | None:
        return next((o for o in self.added if o.opportunity_id == opportunity_id), None)

    def list_for_booking(self, booking_id: str) -> list[SavingsOpportunity]:
        return [o for o in self.added if o.booking_id == booking_id]

    def list_all(self) -> list[SavingsOpportunity]:
        return list(self.added)

    def list_all_for_user(self, user_id: int) -> list[SavingsOpportunity]:
        return list(self.added)

    def mark_notified(self, opportunity_id: str, at: datetime) -> None:
        self.notified.append(opportunity_id)


def _success_check(
    booking_id: str = "b-1",
    amount: str = "350.00",
    session_mode: SessionMode | None = None,
    price_source: PriceSourceProvenance | None = None,
) -> CheckResult:
    return CheckResult.success(
        booking_id=booking_id,
        checked_at=datetime.now(UTC),
        live_price=Money(amount=Decimal(amount), currency="EUR"),
        extraction_method=ExtractionMethod.DOM,
        refund_indicators=RefundIndicators(is_refundable=True),
        session_mode=session_mode,
        price_source=price_source,
    )


def _price_source(genius: GeniusEvidence) -> PriceSourceProvenance:
    return PriceSourceProvenance(
        profile_id=MobileProfileId.ANDROID_CHROMIUM,
        session_revision_id="revision-7",
        genius_evidence=genius,
        observed_at=datetime.now(UTC),
    )


def _make_pipeline(
    notifiers: list[FakeNotifier],
    bookings: list | None = None,
) -> tuple[SavingsPipeline, FakeSavingsRepository]:
    repo = FakeSavingsRepository()
    pipeline = SavingsPipeline(
        booking_repo=FakeBookingRepository(bookings if bookings is not None else [make_booking()]),
        savings_repo=repo,
        dispatcher=NotificationDispatcher(list(notifiers)),
    )
    return pipeline, repo


# ── dispatcher (US-009) ───────────────────────────────────────────────────────

def test_both_channels_receive_alert() -> None:
    email, telegram = FakeNotifier("email"), FakeNotifier("telegram")
    pipeline, _ = _make_pipeline([email, telegram])

    pipeline.process([_success_check()])

    assert len(email.sent) == 1
    assert len(telegram.sent) == 1


def test_one_channel_failing_does_not_block_the_other() -> None:
    email = FakeNotifier("email", fail=True)
    telegram = FakeNotifier("telegram")
    pipeline, repo = _make_pipeline([email, telegram])

    pipeline.process([_success_check()])

    assert len(telegram.sent) == 1        # telegram still delivered
    assert repo.notified                   # partial success still marks notified


def test_all_channels_failing_leaves_unnotified() -> None:
    pipeline, repo = _make_pipeline(
        [FakeNotifier("email", fail=True), FakeNotifier("telegram", fail=True)]
    )

    pipeline.process([_success_check()])

    assert len(repo.added) == 1   # opportunity still persisted
    assert repo.notified == []    # but not marked notified


def test_no_channels_configured_still_persists() -> None:
    pipeline, repo = _make_pipeline([])
    pipeline.process([_success_check()])
    assert len(repo.added) == 1
    assert repo.notified == []


# ── alert content (US-009) ────────────────────────────────────────────────────

def test_alert_contains_core_facts_and_rebook_pointer() -> None:
    email = FakeNotifier("email")
    pipeline, repo = _make_pipeline([email])

    pipeline.process([_success_check()])

    subject, body = email.sent[0]
    opportunity = repo.added[0]
    assert "50.00 EUR" in subject or "50.00" in body          # amount saved
    assert "12.50" in subject + body                          # percent saved
    assert "400.00" in body                                    # baseline
    assert "350.00" in body                                    # live price
    assert "CONF-b-1" in body                                  # confirmation id
    assert f"booksaver rebook {opportunity.opportunity_id}" in body


def test_render_alert_mentions_confirmation_gate() -> None:
    booking = make_booking()
    opportunity = SavingsOpportunity(
        opportunity_id="opp-1",
        booking_id=booking.booking_id,
        check_id="chk-1",
        baseline_price=Money(amount=Decimal("400"), currency="EUR"),
        live_price=Money(amount=Decimal("300"), currency="EUR"),
        amount_saved=Money(amount=Decimal("100"), currency="EUR"),
        percent_saved=Decimal("25.00"),
        validated_at=datetime.now(UTC),
    )
    _, body = render_alert(opportunity, booking)
    assert "explicit confirmation" in body  # no autonomous cancel/purchase promise


def test_render_alert_labels_logged_out_price_as_public_rate() -> None:
    booking = make_booking()
    opportunity = SavingsOpportunity(
        opportunity_id="opp-1",
        booking_id=booking.booking_id,
        check_id="chk-1",
        baseline_price=Money(amount=Decimal("400"), currency="EUR"),
        live_price=Money(amount=Decimal("300"), currency="EUR"),
        amount_saved=Money(amount=Decimal("100"), currency="EUR"),
        percent_saved=Decimal("25.00"),
        validated_at=datetime.now(UTC),
    )
    _, body = render_alert(opportunity, booking, session_mode=SessionMode.LOGGED_OUT)
    assert "public rate" in body
    assert "member deals may be cheaper" in body


def test_render_alert_omits_public_rate_label_when_authenticated() -> None:
    booking = make_booking()
    opportunity = SavingsOpportunity(
        opportunity_id="opp-1",
        booking_id=booking.booking_id,
        check_id="chk-1",
        baseline_price=Money(amount=Decimal("400"), currency="EUR"),
        live_price=Money(amount=Decimal("300"), currency="EUR"),
        amount_saved=Money(amount=Decimal("100"), currency="EUR"),
        percent_saved=Decimal("25.00"),
        validated_at=datetime.now(UTC),
    )
    _, body = render_alert(opportunity, booking, session_mode=SessionMode.AUTHENTICATED)
    assert "public rate" not in body


def test_render_alert_omits_public_rate_label_when_session_mode_unknown() -> None:
    """Every pre-US-035 caller (session_mode defaulted/omitted) keeps the
    exact prior body — no regression for existing callers."""
    booking = make_booking()
    opportunity = SavingsOpportunity(
        opportunity_id="opp-1",
        booking_id=booking.booking_id,
        check_id="chk-1",
        baseline_price=Money(amount=Decimal("400"), currency="EUR"),
        live_price=Money(amount=Decimal("300"), currency="EUR"),
        amount_saved=Money(amount=Decimal("100"), currency="EUR"),
        percent_saved=Decimal("25.00"),
        validated_at=datetime.now(UTC),
    )
    _, body = render_alert(opportunity, booking)
    assert "public rate" not in body


def test_pipeline_dispatches_public_rate_label_through_end_to_end() -> None:
    email = FakeNotifier("email")
    pipeline, _ = _make_pipeline([email])

    pipeline.process([_success_check(session_mode=SessionMode.LOGGED_OUT)])

    _, body = email.sent[0]
    assert "public rate" in body


def test_pipeline_alert_identifies_authenticated_mobile_genius_observed() -> None:
    email = FakeNotifier("email")
    pipeline, _ = _make_pipeline([email])

    pipeline.process(
        [_success_check(price_source=_price_source(GeniusEvidence.APPLIED_OR_PRESENT))]
    )

    _, body = email.sent[0]
    assert "authenticated mobile web (android-chromium)" in body
    assert "Genius       : evidence observed/present on the rendered page" in body


def test_pipeline_alert_identifies_authenticated_mobile_without_genius() -> None:
    email = FakeNotifier("email")
    pipeline, _ = _make_pipeline([email])

    pipeline.process(
        [_success_check(price_source=_price_source(GeniusEvidence.NOT_OBSERVED))]
    )

    _, body = email.sent[0]
    assert "authenticated mobile web (android-chromium)" in body
    assert "Genius       : not observed on the rendered page" in body


# ── pipeline flow ─────────────────────────────────────────────────────────────

def test_failed_checks_are_skipped() -> None:
    email = FakeNotifier("email")
    pipeline, repo = _make_pipeline([email])
    failed = CheckResult.failure(
        "b-1", datetime.now(UTC), FailureReason(code=FailureCode.TIMEOUT, detail="x")
    )

    opportunities = pipeline.process([failed])

    assert opportunities == []
    assert repo.added == []
    assert email.sent == []


def test_rejected_offers_produce_no_alert() -> None:
    email = FakeNotifier("email")
    pipeline, repo = _make_pipeline([email])

    # Higher than baseline — gate passes but price rule rejects
    opportunities = pipeline.process([_success_check(amount="450.00")])

    assert opportunities == []
    assert repo.added == []
    assert email.sent == []


def test_unknown_booking_skipped() -> None:
    email = FakeNotifier("email")
    pipeline, repo = _make_pipeline([email], bookings=[])

    opportunities = pipeline.process([_success_check(booking_id="ghost")])

    assert opportunities == []
    assert repo.added == []


def test_multiple_results_processed_independently() -> None:
    email = FakeNotifier("email")
    bookings = [make_booking("b-1"), make_booking("b-2")]
    pipeline, repo = _make_pipeline([email], bookings=bookings)

    opportunities = pipeline.process(
        [
            _success_check("b-1", amount="350.00"),   # savings
            _success_check("b-2", amount="450.00"),   # no savings
        ]
    )

    assert len(opportunities) == 1
    assert opportunities[0].booking_id == "b-1"
    assert len(email.sent) == 1
