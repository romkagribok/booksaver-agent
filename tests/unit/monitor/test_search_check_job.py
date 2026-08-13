from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import booksaver.monitor.search_check_job as search_check_job
from booksaver.application.dom_incident import is_dom_incident_eligible
from booksaver.domain.agent import AgentAction, AgentActionType, ElementInfo
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomStepId,
    OperatorAction,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
)
from booksaver.domain.check_result import CheckOutcome, ExtractionMethod, FailureCode
from booksaver.domain.journey import JourneyResult, JourneyStep, StepOutcome
from booksaver.domain.model_policy import (
    AdaptiveModelPortfolio,
    ModelRole,
    ModelStopReason,
)
from booksaver.domain.offer import OfferCandidate
from booksaver.domain.savings import SavingsOpportunity, detect_savings
from booksaver.domain.user_session import UserSessionMetadata, UserSessionSnapshot
from booksaver.domain.value_objects import Money, Platform
from booksaver.infrastructure.llm.adaptive_execution import AdaptiveModelStopped
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_check_job import BookingComSearchMonitor
from booksaver.monitor.session_manager import SessionManager

from .fakes import (
    FakeAgentBrain,
    FakeBookingRepository,
    FakeCheckHistoryRepository,
    FakeInteractiveBrowser,
    FakeLLMExtractor,
    FakeSessionRepository,
    make_booking,
    make_session,
)

_PROPERTY_URL = (
    "https://www.booking.com/hotel/test.html"
    "?checkin=2026-09-01&checkout=2026-09-05&group_adults=2"
)

_ROOM_TABLE = """\
Standard Double
€ 350.00
Free cancellation before 30 August 2026
Deluxe Suite
€ 520.00
Non-refundable
"""


def _happy_browser() -> FakeInteractiveBrowser:
    browser = FakeInteractiveBrowser(titles=["Hotel Test"], page_text=_ROOM_TABLE)
    browser.property_url = _PROPERTY_URL
    return browser


def _user_snapshot(cookies: bytes = b'[{"name":"session"}]') -> UserSessionSnapshot:
    return UserSessionSnapshot(
        metadata=UserSessionMetadata.imported(
            owner_user_id=7,
            platform=Platform.BOOKING_COM,
            imported_at=datetime.now(UTC),
            expires_at=None,
        ),
        cookies=cookies,
    )


def _monitor(
    browser: FakeInteractiveBrowser,
    bookings: list | None = None,
    llm: FakeLLMExtractor | None = None,
    session: FakeSessionRepository | None = None,
    brain: FakeAgentBrain | None = None,
) -> tuple[BookingComSearchMonitor, FakeCheckHistoryRepository]:
    history = FakeCheckHistoryRepository()
    monitor = BookingComSearchMonitor(
        browser=browser,
        session_manager=SessionManager(session or FakeSessionRepository(make_session())),
        check_history=history,
        booking_repo=FakeBookingRepository(bookings if bookings is not None else []),
        failure_tracker=FailureTracker(history),
        llm=llm,
        brain=brain,
    )
    return monitor, history


class TestOccupancyGuard:
    def test_missing_occupancy_fails_without_browser(self):
        browser = _happy_browser()
        monitor, _ = _monitor(browser)
        result = monitor.run_check(make_booking(occupancy=None))
        assert result.outcome is CheckOutcome.FAILURE
        assert result.failure_reason.code is FailureCode.OCCUPANCY_MISSING
        assert "set-occupancy" in result.failure_reason.detail
        assert browser.actions == []  # no navigation happened


class TestScriptedHappyPath:
    def test_assisted_journey_diagnosis_reaches_successful_check_result(
        self, monkeypatch
    ):
        diagnosis = TerminalBrowserDiagnosis(
            reason=TerminalBrowserReason.POSTCONDITION_SATISFIED,
            step_id=DomStepId.PRICE_SEARCH_QUERY_SUBMISSION,
            provenance=DiagnosisProvenance.OPUS_RECOVERED,
            confidence=0.9,
            evidence=frozenset(),
            operator_action=OperatorAction.NONE,
        )

        class AssistedJourney:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, booking):
                return JourneyResult(
                    outcomes=(
                        StepOutcome.success(
                            JourneyStep.SUBMIT_SEARCH, "recovered changed DOM"
                        ),
                    ),
                    agent_assisted=True,
                    assisted_diagnoses=(diagnosis,),
                )

        monkeypatch.setattr(search_check_job, "SearchJourney", AssistedJourney)
        monitor, _ = _monitor(_happy_browser())

        result = monitor.run_check(make_booking())

        assert result.outcome is CheckOutcome.SUCCESS
        assert result.assisted_diagnoses == (diagnosis,)

    def test_dom_exact_match_success_without_llm(self):
        monitor, _ = _monitor(_happy_browser())
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.SUCCESS
        assert result.extraction_method is ExtractionMethod.DOM
        assert result.assisted_diagnoses == ()
        assert result.live_price == Money(amount=Decimal("350.00"), currency="EUR")
        assert result.refund_indicators.is_refundable is True

    def test_success_feeds_existing_savings_detection(self):
        booking = make_booking()  # baseline 400.00 EUR
        monitor, _ = _monitor(_happy_browser())
        result = monitor.run_check(booking)
        detection = detect_savings(booking, result)
        assert isinstance(detection, SavingsOpportunity)
        assert detection.amount_saved.amount == Decimal("50.00")

    def test_extracted_fields_carry_verified_booking_context(self):
        booking = make_booking()
        monitor, _ = _monitor(_happy_browser())
        result = monitor.run_check(booking)
        fields = result.extracted_fields
        assert fields.property_name == booking.property.name
        assert fields.check_in == booking.stay_dates.check_in
        assert fields.check_out == booking.stay_dates.check_out
        assert fields.room_label == "Standard Double"  # exact match is echoed


class TestAuthenticatedMobileWeb:
    def test_authenticated_check_restores_owner_cookies_and_records_genius_source(self):
        browser = _happy_browser()
        browser.page_text += "\nGenius Level 2 discount applied"
        monitor, history = _monitor(browser)
        snapshot = _user_snapshot()

        result = monitor.run_authenticated(make_booking(), snapshot)

        assert result.outcome is CheckOutcome.SUCCESS
        assert browser.restored_cookies == [snapshot.cookies]
        assert history.results == [result]
        assert result.price_source is not None
        assert result.price_source.session_revision_id == snapshot.metadata.revision_id
        assert result.price_source.genius_evidence.value == "applied_or_present"
        assert result.price_source.profile_id.value == "android-chromium"

    def test_authenticated_check_accepts_rate_when_genius_is_not_observed(self):
        monitor, _ = _monitor(_happy_browser())

        result = monitor.run_authenticated(make_booking(), _user_snapshot())

        assert result.outcome is CheckOutcome.SUCCESS
        assert result.price_source is not None
        assert result.price_source.genius_evidence.value == "not_observed"

    def test_authenticated_check_runs_code_owned_account_probe_before_search(self):
        browser = _happy_browser()
        probes: list[bool] = []
        browser.verify_authenticated_account = lambda: (probes.append(True) or True)  # type: ignore[attr-defined]
        monitor, _ = _monitor(browser)

        result = monitor.run_authenticated(make_booking(), _user_snapshot())

        assert result.outcome is CheckOutcome.SUCCESS
        assert probes == [True]

    def test_failed_account_probe_never_runs_the_price_search(self):
        browser = _happy_browser()
        browser.verify_authenticated_account = lambda: False  # type: ignore[attr-defined]
        monitor, history = _monitor(browser)

        result = monitor.run_authenticated(make_booking(), _user_snapshot())

        assert result.failure_reason is not None
        assert result.failure_reason.code is FailureCode.AUTH_REQUIRED
        assert browser.actions == []
        assert history.results == [result]

    def test_signed_out_render_fails_closed_without_an_accepted_price(self):
        browser = _happy_browser()
        browser.authenticated = False
        monitor, history = _monitor(browser)

        result = monitor.run_authenticated(make_booking(), _user_snapshot())

        assert result.failure_reason is not None
        assert result.failure_reason.code is FailureCode.AUTH_REQUIRED
        assert result.live_price is None
        assert result.price_source is None
        assert history.results == [result]
        assert "No public-price fallback" in result.failure_reason.detail

    def test_cookie_restore_error_is_redacted_and_recorded(self):
        class RestoreFailureBrowser(FakeInteractiveBrowser):
            def restore_cookies(self, data: bytes) -> None:
                raise RuntimeError(f"secret-cookie={data!r}")

        browser = RestoreFailureBrowser(titles=["Hotel Test"], page_text=_ROOM_TABLE)
        monitor, history = _monitor(browser)

        result = monitor.run_authenticated(make_booking(), _user_snapshot(b"secret"))

        assert result.failure_reason is not None
        assert result.failure_reason.code is FailureCode.AUTH_REQUIRED
        assert "secret" not in result.failure_reason.detail
        assert history.results == [result]


class TestLLMFallback:
    def test_drift_match_uses_llm_and_omits_room_label(self):
        browser = _happy_browser()
        browser.page_text = "Cosy Double Room\n€ 340.00\nFree cancellation until check-in"
        drift_offer = OfferCandidate(
            room_label="Cosy Double Room",
            total=Money(amount=Decimal("340.00"), currency="EUR"),
            is_refundable=True,
            cancellation_text="Free cancellation until check-in",
            matches_room=True,
            match_confidence=0.8,
        )
        llm = FakeLLMExtractor(offers=[drift_offer])
        booking = make_booking()
        monitor, _ = _monitor(browser, llm=llm)
        result = monitor.run_check(booking)
        assert result.outcome is CheckOutcome.SUCCESS
        assert result.extraction_method is ExtractionMethod.LLM
        assert len(llm.offer_calls) == 1
        assert monitor.last_llm_calls_used == 1
        # Drift-matched label must not contradict the booking downstream
        assert result.extracted_fields.room_label is None
        detection = detect_savings(booking, result)
        assert isinstance(detection, SavingsOpportunity)

    def test_adaptive_runtime_supplies_both_search_roles_once(self):
        browser = _happy_browser()
        runtime_calls: list[str] = []

        class Runtime:
            def extractor(self):
                runtime_calls.append("extractor")
                return FakeLLMExtractor()

            def agent_brain(self):
                runtime_calls.append("agent")
                return None

            def page_state_resolver(self):
                runtime_calls.append("resolver")
                return None

        history = FakeCheckHistoryRepository()
        monitor = BookingComSearchMonitor(
            browser=browser,
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            adaptive_runtime_factory=lambda booking: Runtime(),  # type: ignore[arg-type,return-value]
        )

        result = monitor.run_check(make_booking())

        assert result.outcome is CheckOutcome.SUCCESS
        assert runtime_calls == ["extractor", "agent", "resolver"]

    def test_adaptive_extractor_stop_preserves_exact_terminal_diagnosis(self):
        browser = _happy_browser()
        browser.page_text = "Nothing that looks like a rate table"

        class StoppedExtractor(FakeLLMExtractor):
            def extract_offers(self, page_text, booking):
                raise AdaptiveModelStopped(ModelStopReason.PROVIDER_RATE_LIMIT)

        class Runtime:
            def extractor(self):
                return StoppedExtractor()

            def agent_brain(self):
                return None

            def page_state_resolver(self):
                return None

        history = FakeCheckHistoryRepository()
        monitor = BookingComSearchMonitor(
            browser=browser,
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            adaptive_runtime_factory=lambda booking: Runtime(),  # type: ignore[arg-type,return-value]
        )

        result = monitor.run_check(make_booking())

        assert result.failure_reason is not None
        assert result.failure_reason.code is FailureCode.PROVIDER_RATE_LIMIT
        assert result.terminal_diagnosis is not None
        assert result.terminal_diagnosis.reason.value == "provider_rate_limit"
        assert (
            result.terminal_diagnosis.model_stop_reason
            is ModelStopReason.PROVIDER_RATE_LIMIT
        )

    def test_sonnet_extraction_success_records_recovery_receipt(self):
        browser = _happy_browser()
        browser.page_text = "Nothing that looks like a rate table"
        recovered = OfferCandidate(
            room_label="Standard Double",
            total=Money(amount=Decimal("345.00"), currency="EUR"),
            is_refundable=True,
            cancellation_text="Free cancellation",
            matches_room=True,
            match_confidence=1.0,
        )
        profile = AdaptiveModelPortfolio().primary(
            ModelRole.EXTRACTION, "booking-offer-extraction-v1"
        )

        class AdaptiveExtractor:
            last_profile = profile

            def extract_offers(self, page_text, booking):
                return [recovered]

        class Runtime:
            def extractor(self):
                return AdaptiveExtractor()

            def agent_brain(self):
                return None

            def page_state_resolver(self):
                return None

        history = FakeCheckHistoryRepository()
        monitor = BookingComSearchMonitor(
            browser=browser,
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            adaptive_runtime_factory=lambda booking: Runtime(),  # type: ignore[arg-type,return-value]
        )

        result = monitor.run_check(make_booking())

        assert result.outcome is CheckOutcome.SUCCESS
        assert result.live_price == recovered.total
        assert len(result.assisted_diagnoses) == 1
        assert result.assisted_diagnoses[0].step_id is DomStepId.PRICE_OFFER_EXTRACTION
        assert (
            result.assisted_diagnoses[0].provenance
            is DiagnosisProvenance.SONNET_RECOVERED
        )

    def test_empty_sonnet_extraction_uses_one_opus_quality_escalation(self):
        browser = _happy_browser()
        browser.page_text = "Nothing that looks like a rate table"
        calls: list[str] = []
        recovered = OfferCandidate(
            room_label="Standard Double",
            total=Money(amount=Decimal("345.00"), currency="EUR"),
            is_refundable=True,
            cancellation_text="Free cancellation",
            matches_room=True,
            match_confidence=1.0,
        )
        portfolio = AdaptiveModelPortfolio()

        class AdaptiveExtractor:
            last_profile = None

            def extract_offers(self, page_text, booking):
                calls.append("sonnet")
                self.last_profile = portfolio.primary(
                    ModelRole.EXTRACTION, "booking-offer-extraction-v1"
                )
                return []

            def extract_offers_with_escalation(self, page_text, booking, trigger):
                calls.append(f"opus:{trigger.value}")
                self.last_profile = portfolio.escalation(
                    ModelRole.EXTRACTION, "booking-offer-extraction-v1"
                )
                return [recovered]

        class Runtime:
            def extractor(self):
                return AdaptiveExtractor()

            def agent_brain(self):
                return None

            def page_state_resolver(self):
                return None

        history = FakeCheckHistoryRepository()
        monitor = BookingComSearchMonitor(
            browser=browser,
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            adaptive_runtime_factory=lambda booking: Runtime(),  # type: ignore[arg-type,return-value]
        )

        result = monitor.run_check(make_booking())

        assert result.outcome is CheckOutcome.SUCCESS
        assert result.live_price == recovered.total
        assert calls == ["sonnet", "opus:unresolved_low_confidence"]
        assert len(result.assisted_diagnoses) == 1
        assert result.assisted_diagnoses[0].step_id is DomStepId.PRICE_OFFER_EXTRACTION
        assert (
            result.assisted_diagnoses[0].provenance
            is DiagnosisProvenance.OPUS_RECOVERED
        )

    def test_no_candidates_at_all_remains_typed_ambiguity(self):
        browser = _happy_browser()
        browser.page_text = "Nothing that looks like a rate table"
        monitor, _ = _monitor(browser, llm=FakeLLMExtractor(offers=[]))
        result = monitor.run_check(make_booking())
        assert result.failure_reason.code is FailureCode.DOM_AMBIGUITY
        assert result.terminal_diagnosis is not None
        assert result.terminal_diagnosis.step_id.value == "price_search.offer_extraction"

    def test_empty_sonnet_and_opus_extraction_is_incident_eligible_ambiguity(self):
        browser = _happy_browser()
        browser.page_text = "Nothing that looks like a rate table"
        calls: list[str] = []
        portfolio = AdaptiveModelPortfolio()

        class AdaptiveExtractor:
            last_profile = None

            def extract_offers(self, page_text, booking):
                calls.append("sonnet")
                self.last_profile = portfolio.primary(
                    ModelRole.EXTRACTION, "booking-offer-extraction-v1"
                )
                return []

            def extract_offers_with_escalation(self, page_text, booking, trigger):
                calls.append(f"opus:{trigger.value}")
                self.last_profile = portfolio.escalation(
                    ModelRole.EXTRACTION, "booking-offer-extraction-v1"
                )
                return []

        class Runtime:
            def extractor(self):
                return AdaptiveExtractor()

            def agent_brain(self):
                return None

            def page_state_resolver(self):
                return None

        history = FakeCheckHistoryRepository()
        monitor = BookingComSearchMonitor(
            browser=browser,
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            adaptive_runtime_factory=lambda booking: Runtime(),  # type: ignore[arg-type,return-value]
        )

        result = monitor.run_check(make_booking())

        assert calls == ["sonnet", "opus:unresolved_low_confidence"]
        assert result.failure_reason is not None
        assert result.failure_reason.code is FailureCode.DOM_AMBIGUITY
        diagnosis = result.terminal_diagnosis
        assert diagnosis is not None
        assert diagnosis.reason is TerminalBrowserReason.UNRESOLVED_AMBIGUITY
        assert diagnosis.step_id is DomStepId.PRICE_OFFER_EXTRACTION
        assert diagnosis.provenance is DiagnosisProvenance.OPUS_DIAGNOSED
        assert diagnosis.model_stop_reason is ModelStopReason.OPUS_EXHAUSTED
        assert is_dom_incident_eligible(diagnosis)

    def test_grounded_llm_candidates_rejected_by_code_remain_no_equivalent(self):
        browser = _happy_browser()
        browser.page_text = "Nothing that looks like a rate table"
        excluded = OfferCandidate(
            room_label="Standard Double",
            total=Money(amount=Decimal("345.00"), currency="EUR"),
            is_refundable=False,
            cancellation_text="Non-refundable",
            matches_room=True,
            match_confidence=1.0,
        )
        profile = AdaptiveModelPortfolio().primary(
            ModelRole.EXTRACTION, "booking-offer-extraction-v1"
        )

        class AdaptiveExtractor:
            last_profile = profile

            def extract_offers(self, page_text, booking):
                return [excluded]

        class Runtime:
            def extractor(self):
                return AdaptiveExtractor()

            def agent_brain(self):
                return None

            def page_state_resolver(self):
                return None

        history = FakeCheckHistoryRepository()
        monitor = BookingComSearchMonitor(
            browser=browser,
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            adaptive_runtime_factory=lambda booking: Runtime(),  # type: ignore[arg-type,return-value]
        )

        result = monitor.run_check(make_booking())

        assert result.failure_reason is not None
        assert result.failure_reason.code is FailureCode.NO_EQUIVALENT_OFFER
        assert result.terminal_diagnosis is None

    def test_candidates_but_none_equivalent_is_no_equivalent_offer(self):
        browser = _happy_browser()
        browser.page_text = "Deluxe Suite\n€ 520.00\nNon-refundable"
        monitor, _ = _monitor(browser)
        result = monitor.run_check(make_booking())
        assert result.failure_reason.code is FailureCode.NO_EQUIVALENT_OFFER
        assert "not_refundable" in result.failure_reason.detail

    def test_llm_error_degrades_to_dom_candidates(self):
        browser = _happy_browser()
        browser.page_text = "Deluxe Suite\n€ 520.00\nNon-refundable"
        monitor, _ = _monitor(browser, llm=FakeLLMExtractor(raise_error=True))
        result = monitor.run_check(make_booking())
        # DOM found a candidate; it just isn't equivalent
        assert result.failure_reason.code is FailureCode.NO_EQUIVALENT_OFFER

    def test_dom_only_mode_never_resolves_or_calls_llm(self):
        browser = _happy_browser()
        browser.page_text = "Nothing that looks like a rate table"
        llm = FakeLLMExtractor(offers=[])
        monitor, _ = _monitor(browser, llm=llm)
        monitor.set_llm_enabled(False)

        result = monitor.run_check(make_booking())

        assert result.failure_reason.code is FailureCode.DOM_AMBIGUITY
        assert llm.offer_calls == []
        assert monitor.last_llm_calls_used == 0


class TestCurrencyAlignmentRecovery:
    @staticmethod
    def _usd_browser(**overrides) -> FakeInteractiveBrowser:
        browser = FakeInteractiveBrowser(
            titles=["Hotel Test"],
            page_text="Standard Double\nUSD 350.00\nFree cancellation",
            currency_label="USD",
            **overrides,
        )
        browser.property_url = _PROPERTY_URL
        return browser

    def test_scripted_alignment_reloads_once_and_recovers_same_currency(self):
        browser = self._usd_browser()
        result_searches = 0

        def _refresh_in_eur(b: FakeInteractiveBrowser, url: str) -> None:
            nonlocal result_searches
            if "/searchresults.html" in url:
                result_searches += 1
                if result_searches == 2:
                    b.page_text = (
                        "Standard Double\nEUR 330.00\nFree cancellation"
                    )

        browser.on_goto = _refresh_in_eur
        monitor, _ = _monitor(browser)

        result = monitor.run_check(make_booking())

        assert result.outcome is CheckOutcome.SUCCESS
        assert result.live_price == Money(Decimal("330.00"), "EUR")
        assert result.extraction_method is ExtractionMethod.DOM
        assert result_searches == 2
        assert monitor.last_llm_calls_used == 0

    def test_persistent_mismatch_fails_closed_after_one_refresh(self):
        browser = self._usd_browser()
        monitor, _ = _monitor(browser)

        result = monitor.run_check(make_booking())

        assert result.failure_reason.code is FailureCode.CURRENCY_MISMATCH
        assert "Baseline EUR" in result.failure_reason.detail
        assert "rendered in USD" in result.failure_reason.detail
        assert "No cross-currency comparison" in result.failure_reason.detail
        searches = [
            url
            for action, url in browser.actions
            if action == "goto" and "/searchresults.html" in url
        ]
        assert len(searches) == 2

    def test_agent_fallback_is_guarded_and_marks_recovered_result(self):
        browser = self._usd_browser(
            fail_click_selectors={
                "header-currency-picker-trigger",
                'aria-label*="currency"',
            }
        )
        browser.elements = (
            ElementInfo(ref="e0", role="button", label="Currency: USD"),
            ElementInfo(ref="e1", role="button", label="EUR Euro"),
        )
        result_searches = 0

        def _refresh_in_eur(b: FakeInteractiveBrowser, url: str) -> None:
            nonlocal result_searches
            if "/searchresults.html" in url:
                result_searches += 1
                if result_searches == 2:
                    b.page_text = "Standard Double\nEUR 325.00\nFree cancellation"

        def _select_eur(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            if action.ref == "e1":
                b.currency_label = "EUR"

        browser.on_goto = _refresh_in_eur
        browser.on_act = _select_eur
        brain = FakeAgentBrain(
            [AgentAction(type=AgentActionType.CLICK, ref="e1")]
        )
        monitor, _ = _monitor(browser, brain=brain)

        result = monitor.run_check(make_booking())

        assert result.outcome is CheckOutcome.SUCCESS
        assert result.live_price == Money(Decimal("325.00"), "EUR")
        assert result.extraction_method is ExtractionMethod.AGENT
        assert monitor.last_llm_calls_used == 1
        assert len(brain.decisions) == 1

    def test_no_agent_reports_actionable_currency_failure(self):
        browser = self._usd_browser(
            fail_click_selectors={
                "header-currency-picker-trigger",
                'aria-label*="currency"',
            }
        )
        monitor, _ = _monitor(browser, brain=None)

        result = monitor.run_check(make_booking())

        assert result.failure_reason.code is FailureCode.CURRENCY_MISMATCH
        assert "no browser agent was configured" in result.failure_reason.detail
        assert monitor.last_llm_calls_used == 0
        searches = [
            url
            for action, url in browser.actions
            if action == "goto" and "/searchresults.html" in url
        ]
        assert len(searches) == 1


class TestJourneyFailureMapping:
    def test_unrecognized_result_titles_land_as_ambiguous_step_failure(self):
        browser = _happy_browser()
        browser.titles = ["Wrong Hotel"]
        monitor, _ = _monitor(browser)
        result = monitor.run_check(make_booking())
        assert result.failure_reason.code is FailureCode.DOM_AMBIGUITY
        assert "step=locate_property" in result.failure_reason.detail

    def test_auth_required_detail_points_at_cookie_import(self):
        # US-035: a session existed (AUTHENTICATED) but the journey still
        # landed on a signed-out page — the failure detail must point at the
        # VPS-compatible fix, not just silently degrade.
        browser = FakeInteractiveBrowser(
            titles=["Hotel Test"],
            page_text="Log in to your account to continue",
            fail_selectors={"property-card"},
        )
        monitor, _ = _monitor(browser, session=FakeSessionRepository(make_session()))
        result = monitor.run_check(make_booking())
        assert result.failure_reason.code is FailureCode.AUTH_REQUIRED
        assert "booksaver auth import" in result.failure_reason.detail


class TestRunAllActive:
    def test_no_session_runs_logged_out_instead_of_failing(self):
        bookings = [make_booking("b-1"), make_booking("b-2")]
        browser = _happy_browser()
        monitor, history = _monitor(
            browser, bookings=bookings, session=FakeSessionRepository(None)
        )
        results = monitor.run_all_active()
        assert len(results) == 2
        assert all(r.outcome is CheckOutcome.SUCCESS for r in results)
        assert len(history.results) == 2
        # No session existed, so nothing was restored and nothing was saved.
        assert browser.restored_cookies == []

    def test_checks_recorded_and_cookies_refreshed(self):
        session_repo = FakeSessionRepository(make_session())
        bookings = [make_booking("b-1")]
        monitor, history = _monitor(
            _happy_browser(), bookings=bookings, session=session_repo
        )
        results = monitor.run_all_active()
        assert len(results) == 1
        assert results[0].outcome is CheckOutcome.SUCCESS
        assert history.results[0].check_id == results[0].check_id
        assert session_repo.saved  # refreshed cookies persisted

    def test_auth_required_marks_reauth_without_refreshing_cookies(self):
        session_repo = FakeSessionRepository(make_session(b"original-session"))
        browser = _happy_browser()
        browser.page_text = "Log in to your account to continue"
        browser.fail_selectors.add("property-card")
        monitor, _ = _monitor(
            browser,
            bookings=[make_booking("b-1")],
            session=session_repo,
        )

        results = monitor.run_all_active()

        assert results[0].failure_reason is not None
        assert results[0].failure_reason.code is FailureCode.AUTH_REQUIRED
        assert session_repo.saved[-1].status.value == "requires_reauth"
        assert all(item.cookies != b'[{"name": "fresh"}]' for item in session_repo.saved)

    def test_mixed_bookings_one_missing_occupancy(self):
        bookings = [make_booking("b-1", occupancy=None), make_booking("b-2")]
        monitor, _ = _monitor(_happy_browser(), bookings=bookings)
        results = monitor.run_all_active()
        codes = {
            r.booking_id: r.failure_reason.code if r.failure_reason else None
            for r in results
        }
        assert codes["b-1"] is FailureCode.OCCUPANCY_MISSING
        assert codes["b-2"] is None  # succeeded


class _FakeLLMClientFactory:
    """Fakes the US-027 hybrid-billing seam: raises on `for_booking` to
    simulate a booking owner's invalid/undecryptable personal key."""

    def __init__(self, raise_error: bool = True) -> None:
        self._raise_error = raise_error
        self.calls: list[str] = []

    def for_booking(self, booking):
        self.calls.append(booking.booking_id if booking else "none")
        if self._raise_error:
            from booksaver.domain.errors import UserKeyInvalidError

            raise UserKeyInvalidError(user_id=7, detail="stub")
        return None

    def agent_brain_for_booking(self, booking):
        return None


class TestHybridBillingIntegration:
    """US-027: a per-booking LLMClientFactory that raises UserKeyInvalidError
    fails only that booking's check with FailureCode.USER_KEY_INVALID —
    every other constructor-injected-llm test above is unaffected because
    `llm_factory` defaults to None."""

    def test_invalid_user_key_fails_the_check_with_user_key_invalid(self):
        history = FakeCheckHistoryRepository()
        factory = _FakeLLMClientFactory(raise_error=True)
        monitor = BookingComSearchMonitor(
            browser=_happy_browser(),
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            llm_factory=factory,
        )
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.FAILURE
        assert result.failure_reason.code is FailureCode.USER_KEY_INVALID
        assert factory.calls == ["b-1"]

    def test_no_user_key_error_uses_the_factory_resolved_clients(self):
        history = FakeCheckHistoryRepository()
        factory = _FakeLLMClientFactory(raise_error=False)
        monitor = BookingComSearchMonitor(
            browser=_happy_browser(),
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            llm_factory=factory,
        )
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.SUCCESS
        assert factory.calls == ["b-1"]
