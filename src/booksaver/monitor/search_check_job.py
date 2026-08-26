from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from booksaver.application.browser_executor import (
    OwnerBoundAgenticPriceCheck,
    PriceExecutionOutcome,
)
from booksaver.application.browser_resilience import DOM_STEP_REGISTRY
from booksaver.application.model_policy import AdaptiveModelStopped
from booksaver.application.ports import (
    AgentBrain,
    BookingRepository,
    CheckHistoryRepository,
    CheckTraceRepository,
    InteractiveBrowser,
    LLMClientFactory,
    LLMExtractor,
    RegisteredPageStateResolver,
)
from booksaver.domain.agent import AgentBudget, AgentSettings, BudgetExceeded
from booksaver.domain.browser_executor import (
    ExecutionLimits,
    PriceExecutionStatus,
    RoutingDecision,
    ValidationRejection,
)
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomStepId,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
    operator_action_for_reason,
)
from booksaver.domain.check_result import (
    CheckResult,
    ExtractedBookingFields,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
    failure_code_for_terminal,
)
from booksaver.domain.errors import UserKeyInvalidError
from booksaver.domain.journey import JourneyResult, JourneyStep
from booksaver.domain.mobile_web import (
    GeniusEvidence,
    MobileProfileId,
    PriceSourceProvenance,
)
from booksaver.domain.model_policy import EscalationTrigger, ModelStopReason, ModelTier
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate, OfferSelection, select_offer
from booksaver.domain.session import SessionMode
from booksaver.domain.user_session import UserSessionSnapshot
from booksaver.monitor import room_table
from booksaver.monitor.browser_agent import BrowserAgent
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_journey import SearchJourney
from booksaver.monitor.session_manager import SessionManager
from booksaver.monitor.trace import SnapshotWriter, TraceRecorder

if TYPE_CHECKING:
    from booksaver.infrastructure.llm.adaptive_execution import (
        AdaptiveAnthropicRuntimeFactory,
    )

logger = logging.getLogger(__name__)

# Production price-evaluation DOM seams owned after search navigation succeeds.
DOM_STEPS: tuple[DomStepId, ...] = (
    DomStepId.PRICE_CURRENCY_ALIGN,
    DomStepId.PRICE_SNAPSHOT,
    DomStepId.PRICE_OFFER_EXTRACTION,
)

_GENIUS_EVIDENCE = re.compile(r"\bGenius(?:\s+(?:Level|discount|deal|rate))?\b", re.I)


def _model_stop_diagnosis(step_id: DomStepId, reason: ModelStopReason) -> TerminalBrowserDiagnosis:
    terminal = DOM_STEP_REGISTRY.definition(step_id).reason_for_model_stop(reason)
    provenance = (
        DiagnosisProvenance.PROVIDER_STOP
        if terminal
        in {
            TerminalBrowserReason.PROVIDER_AUTHENTICATION,
            TerminalBrowserReason.PROVIDER_UNAVAILABLE,
            TerminalBrowserReason.PROVIDER_RATE_LIMIT,
        }
        else DiagnosisProvenance.BUDGET_STOP
        if terminal
        in {
            TerminalBrowserReason.TIME_LIMIT,
            TerminalBrowserReason.JOB_COST_LIMIT,
            TerminalBrowserReason.DAILY_COST_LIMIT,
            TerminalBrowserReason.MODEL_PRICING_UNAVAILABLE,
            TerminalBrowserReason.COST_ACCOUNTING_ERROR,
            TerminalBrowserReason.CLOCK_ROLLBACK,
        }
        else DiagnosisProvenance.POLICY_STOP
    )
    return TerminalBrowserDiagnosis(
        reason=terminal,
        step_id=step_id,
        provenance=provenance,
        confidence=1.0,
        evidence=frozenset(),
        operator_action=operator_action_for_reason(terminal),
        model_stop_reason=reason,
    )


class BookingComSearchMonitor:
    """Search-flow price monitor (ADR-013): replaces the manage-page monitor as
    the sole producer of live prices. Same never-raise contract and session
    handling as bolt 003's BookingComMonitor.
    """

    def __init__(
        self,
        browser: InteractiveBrowser,
        session_manager: SessionManager,
        check_history: CheckHistoryRepository,
        booking_repo: BookingRepository,
        failure_tracker: FailureTracker,
        llm: LLMExtractor | None = None,
        brain: AgentBrain | None = None,
        llm_factory: LLMClientFactory | None = None,
        adaptive_runtime_factory: (
            Callable[[Booking], AdaptiveAnthropicRuntimeFactory | None] | None
        ) = None,
        agent_settings: AgentSettings | None = None,
        trace_repo: CheckTraceRepository | None = None,
        snapshot_writer: SnapshotWriter | None = None,
        clock: Callable[[], float] = time.monotonic,
        mobile_profile_id: MobileProfileId = MobileProfileId.ANDROID_CHROMIUM,
        agentic_price_check: OwnerBoundAgenticPriceCheck | None = None,
        agentic_owner_user_id: int | None = None,
        agentic_route: RoutingDecision | None = None,
        agentic_execution_limits: ExecutionLimits | None = None,
        room_equivalence_policy: (Callable[[str, Booking], tuple[bool, float]] | None) = None,
    ) -> None:
        self._browser = browser
        self._sessions = session_manager
        self._history = check_history
        self._bookings = booking_repo
        self._failures = failure_tracker
        self._llm = llm
        self._brain = brain
        # US-027 hybrid billing: when set, `_run_check_inner` re-resolves
        # `self._llm`/`self._brain` per booking (owner key or the booking
        # owner's personal key) instead of using the constructor-injected
        # `llm`/`brain` for every booking. `llm`/`brain` above remain the
        # values used when no factory is supplied (every existing caller/test
        # is unaffected).
        self._llm_factory = llm_factory
        # The coordinator owns caller/key resolution and constructs one shared
        # job budget. This lazy seam supplies the already-bound adaptive runtime
        # only when an ambiguous search actually needs model assistance.
        self._adaptive_runtime_factory = adaptive_runtime_factory
        self._agent_settings = agent_settings or AgentSettings()
        self._trace_repo = trace_repo
        self._snapshots = snapshot_writer
        self._clock = clock
        self._last_escalator: BrowserAgent | None = None
        self._page_state_resolver: RegisteredPageStateResolver | None = None
        self._active_budget: AgentBudget | None = None
        self._last_llm_calls_used = 0
        self._llm_enabled = True
        self._mobile_profile_id = mobile_profile_id
        self._agentic_price_check = agentic_price_check
        self._agentic_owner_user_id = agentic_owner_user_id
        self._agentic_route = agentic_route
        self._agentic_execution_limits = agentic_execution_limits
        self._room_equivalence_policy = room_equivalence_policy or self._exact_room_equivalence
        self._last_agentic_outcome: PriceExecutionOutcome | None = None

    @property
    def last_llm_calls_used(self) -> int:
        """Actual LLM calls consumed by the most recent ``run_check``."""
        return self._last_llm_calls_used

    @property
    def last_agentic_outcome(self) -> PriceExecutionOutcome | None:
        """Ephemeral outcome for the coordinator's content-free canary projection."""
        return self._last_agentic_outcome

    @property
    def last_agent_steps_used(self) -> int:
        """Code-metered legacy-agent actions used by the most recent price check."""
        return self._active_budget.steps_used if self._active_budget is not None else 0

    def set_llm_enabled(self, enabled: bool) -> None:
        """Disable both extractor and agent resolution for a DOM-only check."""
        self._llm_enabled = enabled

    def run_all_active(self, bookings: list[Booking] | None = None) -> list[CheckResult]:
        """Scheduler job entry point: check every active booking, never raise.

        `bookings` defaults to every active booking (`self._bookings.list_active()`,
        pre-US-031 behavior). A caller doing per-user fair scheduling / daily
        check caps (US-031) instead computes its own ordered subset (e.g. via
        `monitor.user_limits.build_check_plan`) and passes it here.
        """
        results: list[CheckResult] = []
        bookings = self._bookings.list_active() if bookings is None else bookings
        if not bookings:
            logger.info("No active bookings to check")
            return results

        session = self._sessions.ensure_active()
        if session is None:
            # No usable session on this deployment (typical on a display-less
            # VPS, where headed `booksaver auth` cannot run): fall back to
            # logged-out mode rather than failing every booking (US-035,
            # FR-8). The search journey works unauthenticated and returns
            # real public bookable totals.
            mode = SessionMode.LOGGED_OUT
            logger.info(
                "No active Booking.com session — running %d booking(s) logged out (public prices).",
                len(bookings),
            )
        else:
            mode = SessionMode.AUTHENTICATED
            try:
                self._browser.restore_cookies(session.cookies)
            except Exception as exc:
                logger.error("Failed to restore session cookies: %s", exc)
                self._sessions.mark_reauth_required(session)
                return results

        reauth_flagged = False
        for booking in bookings:
            result = self.run_check(booking, session_mode=mode)
            self._record(result)
            results.append(result)
            if (
                session is not None
                and not reauth_flagged
                and result.failure_reason is not None
                and result.failure_reason.code is FailureCode.AUTH_REQUIRED
            ):
                self._sessions.mark_reauth_required(session)
                reauth_flagged = True

        if session is not None and not reauth_flagged and self._browser.is_authenticated():
            try:
                self._sessions.save_refreshed(session, self._browser.get_cookies())
            except Exception as exc:
                logger.warning("Could not save refreshed cookies: %s", exc)

        return results

    def run_authenticated(self, booking: Booking, snapshot: UserSessionSnapshot) -> CheckResult:
        """Run one fail-closed owner-bound check and persist its result."""
        if self._agentic_route is not None and self._agentic_route.use_agentic:
            result = self._run_agentic_authenticated(booking, snapshot)
            self._record(result)
            return result
        try:
            self._browser.restore_cookies(snapshot.cookies)
        except Exception:
            logger.warning(
                "Could not restore encrypted Booking.com session for user %s",
                snapshot.metadata.owner_user_id,
                exc_info=True,
            )
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(
                    code=FailureCode.AUTH_REQUIRED,
                    detail=(
                        "Could not restore this user's encrypted Booking.com session. "
                        "Import fresh cookies; no public-price fallback was used."
                    ),
                ),
            )
            recorder = TraceRecorder(booking.booking_id)
            self._persist_trace(recorder, result, None)
            self._record(result)
            return result

        verify_account = getattr(self._browser, "verify_authenticated_account", None)
        if callable(verify_account) and not verify_account():
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(
                    code=FailureCode.AUTH_REQUIRED,
                    detail=(
                        "Booking.com did not render a verifiable signed-in account "
                        "context; send /connect and retry. No public-price fallback "
                        "was used."
                    ),
                ),
            )
            recorder = TraceRecorder(booking.booking_id)
            self._persist_trace(recorder, result, None)
            self._record(result)
            return result

        result = self.run_check(
            booking,
            session_mode=SessionMode.AUTHENTICATED,
            session_revision_id=snapshot.metadata.revision_id,
        )
        self._record(result)
        return result

    def _run_agentic_authenticated(
        self,
        booking: Booking,
        snapshot: UserSessionSnapshot,
    ) -> CheckResult:
        recorder = TraceRecorder(booking.booking_id)
        self._last_llm_calls_used = 0
        self._last_agentic_outcome = None
        if self._agentic_price_check is None or self._agentic_owner_user_id is None:
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(
                    FailureCode.PROVIDER_AUTHENTICATION,
                    "Agentic routing is selected but its local Anthropic executor is unavailable.",
                ),
            )
            self._persist_trace(recorder, result, None)
            return result
        try:
            outcome = self._agentic_price_check.execute(
                owner_user_id=self._agentic_owner_user_id,
                booking=booking,
                session_material=snapshot.cookies,
                limits=self._agentic_execution_limits,
            )
            self._last_agentic_outcome = outcome
            self._last_llm_calls_used = outcome.result.usage.model_calls
            result = self._agentic_check_result(
                booking,
                outcome,
                snapshot.metadata.revision_id,
            )
        except Exception as exc:
            logger.error(
                "Unexpected agentic execution error for booking %s failure_type=%s",
                booking.booking_id,
                type(exc).__name__,
            )
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(
                    FailureCode.INFRASTRUCTURE_FAILURE,
                    f"Agentic browser check stopped after {type(exc).__name__}.",
                ),
            )
        self._persist_trace(recorder, result, None)
        return result

    def _agentic_check_result(
        self,
        booking: Booking,
        outcome: PriceExecutionOutcome,
        session_revision_id: str,
    ) -> CheckResult:
        now = datetime.now(UTC)
        if not outcome.validation.accepted:
            code = self._agentic_failure_code(
                outcome.result.status,
                outcome.validation.rejection,
            )
            rejection = (
                outcome.validation.rejection.value
                if outcome.validation.rejection is not None
                else outcome.result.status.value
            )
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code,
                    f"Agentic price observation rejected by BookSaver ({rejection}).",
                ),
            )

        candidates: list[OfferCandidate] = []
        for offer in outcome.validation.accepted_offers:
            matches, confidence = self._room_equivalence_policy(
                offer.room_label,
                booking,
            )
            candidates.append(
                OfferCandidate(
                    room_label=offer.room_label,
                    total=offer.total,
                    is_refundable=True,
                    cancellation_text=offer.cancellation_text,
                    matches_room=matches,
                    match_confidence=confidence,
                )
            )
        selection = select_offer(candidates, booking)
        if selection.chosen is None:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    FailureCode.NO_EQUIVALENT_OFFER,
                    "No BookSaver-qualified equivalent refundable offer was observed.",
                ),
            )
        facts = outcome.result.query_facts
        genius = (
            GeniusEvidence.APPLIED_OR_PRESENT
            if facts is not None and facts.genius is True
            else GeniusEvidence.NOT_OBSERVED
        )
        return self._to_success(
            booking,
            selection.chosen,
            (ExtractionMethod.AGENT if outcome.result.fallback_used else ExtractionMethod.LLM),
            now,
            session_mode=SessionMode.AUTHENTICATED,
            session_revision_id=session_revision_id,
            genius_evidence=genius,
        )

    @staticmethod
    def _exact_room_equivalence(
        observed_room_label: str,
        booking: Booking,
    ) -> tuple[bool, float]:
        exact = " ".join(observed_room_label.casefold().split()) == " ".join(
            booking.room_type.label.casefold().split()
        )
        return exact, 1.0 if exact else 0.0

    @staticmethod
    def _agentic_failure_code(
        status: PriceExecutionStatus,
        rejection: ValidationRejection | None,
    ) -> FailureCode:
        rejection_codes = {
            ValidationRejection.PROPERTY_MISMATCH: FailureCode.PROPERTY_NOT_FOUND,
            ValidationRejection.DATE_MISMATCH: FailureCode.STEP_FAILED,
            ValidationRejection.OCCUPANCY_MISMATCH: FailureCode.OCCUPANCY_MISSING,
            ValidationRejection.AUTHENTICATION_REQUIRED: FailureCode.AUTH_REQUIRED,
            ValidationRejection.CURRENCY_MISMATCH: FailureCode.CURRENCY_MISMATCH,
            ValidationRejection.NO_COMPLETE_REFUNDABLE_ALL_IN_OFFER: (
                FailureCode.NO_EQUIVALENT_OFFER
            ),
            ValidationRejection.EXECUTION_LIMIT_BREACH: FailureCode.BUDGET_EXCEEDED,
            ValidationRejection.QUERY_EVIDENCE_INCOMPLETE: FailureCode.EXTRACTION_FAILED,
        }
        if rejection in rejection_codes:
            return rejection_codes[rejection]
        return {
            PriceExecutionStatus.SESSION_UNAVAILABLE: FailureCode.AUTH_REQUIRED,
            PriceExecutionStatus.SIGNED_OUT: FailureCode.AUTH_REQUIRED,
            PriceExecutionStatus.MFA_REQUIRED: FailureCode.AUTH_REQUIRED,
            PriceExecutionStatus.CAPTCHA: FailureCode.BOT_WALL,
            PriceExecutionStatus.BOT_WALL: FailureCode.BOT_WALL,
            PriceExecutionStatus.UNAVAILABLE: FailureCode.NO_EQUIVALENT_OFFER,
            PriceExecutionStatus.UNSAFE_ACTION: FailureCode.BLOCKED_ACTION,
            PriceExecutionStatus.PROVIDER_FAILURE: FailureCode.PROVIDER_UNAVAILABLE,
            PriceExecutionStatus.BUDGET_EXHAUSTED: FailureCode.BUDGET_EXCEEDED,
            PriceExecutionStatus.TIMEOUT: FailureCode.TIMEOUT,
            PriceExecutionStatus.NO_VALID_OBSERVATION: FailureCode.EXTRACTION_FAILED,
        }.get(status, FailureCode.EXTRACTION_FAILED)

    def run_check(
        self,
        booking: Booking,
        session_mode: SessionMode = SessionMode.AUTHENTICATED,
        session_revision_id: str | None = None,
    ) -> CheckResult:
        """Check one booking via the search journey. Always returns; never raises."""
        recorder = TraceRecorder(booking.booking_id)
        escalator: BrowserAgent | None = None
        self._active_budget = None
        self._last_llm_calls_used = 0
        try:
            result = self._run_check_inner(booking, recorder, session_mode, session_revision_id)
        except Exception as exc:  # belt and braces: the never-raise contract
            logger.exception("Unexpected error checking booking %s", booking.booking_id)
            diagnosis = TerminalBrowserDiagnosis(
                reason=TerminalBrowserReason.INFRASTRUCTURE_FAILURE,
                step_id=DomStepId.PRICE_SNAPSHOT,
                provenance=DiagnosisProvenance.INFRASTRUCTURE_STOP,
                confidence=1.0,
                evidence=frozenset(),
                operator_action=operator_action_for_reason(
                    TerminalBrowserReason.INFRASTRUCTURE_FAILURE
                ),
            )
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(
                    code=FailureCode.INFRASTRUCTURE_FAILURE,
                    detail=f"Browser check stopped after {type(exc).__name__}.",
                ),
                terminal_diagnosis=diagnosis,
            )
        else:
            escalator = self._last_escalator
        if self._active_budget is not None:
            self._last_llm_calls_used = self._active_budget.llm_calls_used
        self._persist_trace(recorder, result, escalator)
        return result

    def _run_check_inner(
        self,
        booking: Booking,
        recorder: TraceRecorder,
        session_mode: SessionMode,
        session_revision_id: str | None,
    ) -> CheckResult:
        now = datetime.now(UTC)
        self._last_escalator = None
        self._page_state_resolver = None

        if self._adaptive_runtime_factory is not None and self._llm_enabled:
            try:
                runtime = self._adaptive_runtime_factory(booking)
                self._llm = runtime.extractor() if runtime is not None else None
                self._brain = runtime.agent_brain() if runtime is not None else None
                self._page_state_resolver = (
                    runtime.page_state_resolver() if runtime is not None else None
                )
            except UserKeyInvalidError as exc:
                return CheckResult.failure(
                    booking.booking_id,
                    now,
                    FailureReason(code=FailureCode.USER_KEY_INVALID, detail=str(exc)),
                )
        elif self._llm_factory is not None and self._llm_enabled:
            try:
                self._llm = self._llm_factory.for_booking(booking)
                self._brain = self._llm_factory.agent_brain_for_booking(booking)
            except UserKeyInvalidError as exc:
                return CheckResult.failure(
                    booking.booking_id,
                    now,
                    FailureReason(code=FailureCode.USER_KEY_INVALID, detail=str(exc)),
                )
        elif not self._llm_enabled:
            self._llm = None
            self._brain = None

        if booking.occupancy is None:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.OCCUPANCY_MISSING,
                    detail=(
                        "Booking predates the occupancy field. Run: booksaver bookings "
                        f"set-occupancy {booking.booking_id} --adults N"
                    ),
                ),
            )

        budget = AgentBudget(self._agent_settings, clock=self._clock)
        self._active_budget = budget
        escalator: BrowserAgent | None = None
        if self._brain is not None:
            escalator = BrowserAgent(
                self._browser,
                self._brain,
                budget,
                recorder,
                recovery_policy=self._agent_settings.recovery_policy,
                page_state_resolver=self._page_state_resolver,
            )
            self._last_escalator = escalator

        search_journey = SearchJourney(
            self._browser,
            escalator=escalator,
            recorder=recorder,
            checkpoint=budget.check_time,
            session_mode=session_mode,
        )
        journey = search_journey.run(booking)

        if session_revision_id is not None and not self._browser.is_authenticated():
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.AUTH_REQUIRED,
                    detail=(
                        "Booking.com did not render a verifiable signed-in account context; "
                        "re-import this user's cookies. No public-price fallback was used."
                    ),
                ),
            )

        if not journey.ok:
            return self._journey_failure(booking, journey, now)

        try:
            page_text = self._browser.snapshot().text
        except Exception:
            diagnosis = TerminalBrowserDiagnosis(
                reason=TerminalBrowserReason.OBSERVATION_UNAVAILABLE,
                step_id=DomStepId.PRICE_SNAPSHOT,
                provenance=DiagnosisProvenance.INFRASTRUCTURE_STOP,
                confidence=1.0,
                evidence=frozenset(),
                operator_action=operator_action_for_reason(
                    TerminalBrowserReason.OBSERVATION_UNAVAILABLE
                ),
            )
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.OBSERVATION_UNAVAILABLE,
                    detail="A fresh property-page observation was unavailable.",
                ),
                terminal_diagnosis=diagnosis,
            )

        try:
            candidates, method, extraction_diagnosis = self._extract_candidates(
                page_text, booking, budget
            )
        except BudgetExceeded as exc:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(code=FailureCode.BUDGET_EXCEEDED, detail=str(exc)),
            )
        except Exception as exc:
            if isinstance(exc, AdaptiveModelStopped):
                diagnosis = _model_stop_diagnosis(DomStepId.PRICE_OFFER_EXTRACTION, exc.reason)
                return CheckResult.failure(
                    booking.booking_id,
                    now,
                    FailureReason(
                        code=failure_code_for_terminal(diagnosis.reason),
                        detail=(
                            "Offer extraction stopped under adaptive model policy: "
                            f"{diagnosis.reason.value}"
                        ),
                    ),
                    terminal_diagnosis=diagnosis,
                )
            raise

        if journey.agent_assisted:
            method = ExtractionMethod.AGENT  # US-020: scripted vs agent-assisted marker

        if not candidates:
            diagnosis = self._unresolved_extraction_diagnosis()
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=failure_code_for_terminal(diagnosis.reason),
                    detail=(
                        "Offer extraction remained ambiguous after every configured "
                        "DOM/model evidence adapter returned no grounded offers."
                    ),
                ),
                terminal_diagnosis=diagnosis,
            )

        selection = select_offer(candidates, booking)
        if selection.chosen is None and selection.currency_mismatches:
            return self._recover_currency(
                booking=booking,
                initial_selection=selection,
                search_journey=search_journey,
                escalator=escalator,
                budget=budget,
                recorder=recorder,
                now=now,
                session_mode=session_mode,
                initial_agent_assisted=journey.agent_assisted,
                initial_assisted_diagnoses=(
                    *journey.assisted_diagnoses,
                    *((extraction_diagnosis,) if extraction_diagnosis is not None else ()),
                ),
                session_revision_id=session_revision_id,
            )
        if selection.chosen is None:
            return self._no_equivalent_failure(booking, candidates, selection, now)

        if session_mode is SessionMode.LOGGED_OUT:
            # US-035: not persisted to check_history (schema owned elsewhere,
            # see CheckResult.session_mode's docstring) — but it does survive
            # in-memory to SavingsPipeline within this tick, so a savings
            # alert built from it can label the price a public rate.
            logger.info(
                "Check for booking %s used a public (logged-out) rate.",
                booking.booking_id,
            )
        return self._to_success(
            booking,
            selection.chosen,
            method,
            now,
            session_mode,
            session_revision_id,
            page_text,
            (
                *journey.assisted_diagnoses,
                *((extraction_diagnosis,) if extraction_diagnosis is not None else ()),
            ),
        )

    def _recover_currency(
        self,
        *,
        booking: Booking,
        initial_selection: OfferSelection,
        search_journey: SearchJourney,
        escalator: BrowserAgent | None,
        budget: AgentBudget,
        recorder: TraceRecorder,
        now: datetime,
        session_mode: SessionMode,
        initial_agent_assisted: bool,
        initial_assisted_diagnoses: tuple[TerminalBrowserDiagnosis, ...],
        session_revision_id: str | None,
    ) -> CheckResult:
        desired = booking.baseline_price.currency
        observed = self._observed_currencies(initial_selection)
        recorder.currency_alignment(
            f"requested={desired}; observed={','.join(observed)}; recovery started"
        )

        recovery_detail: str
        alignment_agent_assisted = False
        alignment_diagnosis: TerminalBrowserDiagnosis | None = None
        try:
            budget.check_time()
            recovery_detail = search_journey.align_currency(booking)
            recorder.currency_alignment(f"method=scripted; {recovery_detail}")
        except BudgetExceeded as exc:
            recorder.currency_alignment(f"method=scripted; budget exceeded: {exc}")
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(code=FailureCode.BUDGET_EXCEEDED, detail=str(exc)),
            )
        except Exception as exc:
            scripted_detail = str(exc)
            recorder.currency_alignment(f"method=scripted; unavailable: {scripted_detail}")
            if escalator is None:
                return self._currency_failure(
                    booking,
                    observed,
                    "scripted preference was unavailable and no browser agent was configured",
                    now,
                )
            escalation = escalator.complete_step(
                JourneyStep.ALIGN_CURRENCY,
                goal=(
                    f"Set Booking.com's displayed currency to {desired}. Use only the "
                    "visible header currency control and choose the exact requested currency; "
                    "do not change property, dates, occupancy, or enter any booking flow."
                ),
                verify=lambda: search_journey.currency_preference_visible(desired),
                trigger=(
                    f"Rendered equivalent refundable offers use {','.join(observed)} while "
                    f"the booking baseline uses {desired}; scripted selector failed: "
                    f"{scripted_detail}"
                ),
            )
            alignment_agent_assisted = True
            alignment_diagnosis = escalation.diagnosis if escalation.ok else None
            recovery_detail = escalation.detail
            recorder.currency_alignment(
                f"method=agent; result={'ok' if escalation.ok else 'failed'}; "
                f"detail={escalation.detail}"
            )
            if not escalation.ok:
                if escalation.failure_code is FailureCode.BUDGET_EXCEEDED:
                    return CheckResult.failure(
                        booking.booking_id,
                        now,
                        FailureReason(
                            code=FailureCode.BUDGET_EXCEEDED,
                            detail=escalation.detail,
                        ),
                    )
                return self._currency_failure(
                    booking,
                    observed,
                    f"scripted and agent recovery failed ({escalation.detail})",
                    now,
                )

        retry_journey = SearchJourney(
            self._browser,
            escalator=escalator,
            recorder=recorder,
            checkpoint=budget.check_time,
            session_mode=session_mode,
        ).run(booking)
        if not retry_journey.ok:
            return self._journey_failure(booking, retry_journey, now)

        try:
            page_text = self._browser.snapshot().text
        except Exception:
            diagnosis = TerminalBrowserDiagnosis(
                reason=TerminalBrowserReason.OBSERVATION_UNAVAILABLE,
                step_id=DomStepId.PRICE_SNAPSHOT,
                provenance=DiagnosisProvenance.INFRASTRUCTURE_STOP,
                confidence=1.0,
                evidence=frozenset(),
                operator_action=operator_action_for_reason(
                    TerminalBrowserReason.OBSERVATION_UNAVAILABLE
                ),
            )
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.OBSERVATION_UNAVAILABLE,
                    detail="A fresh property-page observation was unavailable.",
                ),
                terminal_diagnosis=diagnosis,
            )
        try:
            candidates, method, extraction_diagnosis = self._extract_candidates(
                page_text, booking, budget
            )
        except BudgetExceeded as exc:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(code=FailureCode.BUDGET_EXCEEDED, detail=str(exc)),
            )
        except Exception as exc:
            if isinstance(exc, AdaptiveModelStopped):
                diagnosis = _model_stop_diagnosis(DomStepId.PRICE_OFFER_EXTRACTION, exc.reason)
                return CheckResult.failure(
                    booking.booking_id,
                    now,
                    FailureReason(
                        code=failure_code_for_terminal(diagnosis.reason),
                        detail=(
                            "Offer extraction stopped under adaptive model policy: "
                            f"{diagnosis.reason.value}"
                        ),
                    ),
                    terminal_diagnosis=diagnosis,
                )
            raise
        if retry_journey.agent_assisted or alignment_agent_assisted or initial_agent_assisted:
            method = ExtractionMethod.AGENT

        if not candidates:
            diagnosis = self._unresolved_extraction_diagnosis()
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=failure_code_for_terminal(diagnosis.reason),
                    detail=(
                        "Offer extraction remained ambiguous after currency alignment; "
                        "no grounded offers were accepted."
                    ),
                ),
                terminal_diagnosis=diagnosis,
            )
        selection = select_offer(candidates, booking)
        if selection.chosen is not None:
            recorder.currency_alignment(
                f"verification=success; rendered={selection.chosen.total.currency}; "
                f"recovery={recovery_detail}"
            )
            return self._to_success(
                booking,
                selection.chosen,
                method,
                now,
                session_mode,
                session_revision_id,
                page_text,
                (
                    *initial_assisted_diagnoses,
                    *((alignment_diagnosis,) if alignment_diagnosis is not None else ()),
                    *retry_journey.assisted_diagnoses,
                    *((extraction_diagnosis,) if extraction_diagnosis is not None else ()),
                ),
            )
        if selection.currency_mismatches:
            final_observed = self._observed_currencies(selection)
            recorder.currency_alignment(
                f"verification=failed; requested={desired}; observed={','.join(final_observed)}"
            )
            return self._currency_failure(
                booking,
                final_observed,
                "Booking.com still rendered another currency after one bounded recovery",
                now,
            )
        return self._no_equivalent_failure(booking, candidates, selection, now)

    def _extract_candidates(
        self, page_text: str, booking: Booking, budget: AgentBudget
    ) -> tuple[
        list[OfferCandidate],
        ExtractionMethod,
        TerminalBrowserDiagnosis | None,
    ]:
        candidates = room_table.parse_candidates(page_text, booking)
        method = ExtractionMethod.DOM
        assisted_diagnosis = None
        if not room_table.has_confident_exact_match(candidates, booking):
            llm_candidates = self._try_llm_offers(page_text, booking, budget)
            if llm_candidates is not None:
                candidates = llm_candidates
                method = ExtractionMethod.LLM
                if candidates:
                    assisted_diagnosis = self._extraction_recovery_diagnosis()
        return candidates, method, assisted_diagnosis

    def _extraction_recovery_diagnosis(self) -> TerminalBrowserDiagnosis | None:
        """Receipt a grounded adaptive extraction under its actual model tier."""

        profile = getattr(self._llm, "last_profile", None)
        tier = getattr(profile, "tier", None)
        if not isinstance(tier, ModelTier):
            return None
        provenance = {
            ModelTier.SONNET: DiagnosisProvenance.SONNET_RECOVERED,
            ModelTier.OPUS: DiagnosisProvenance.OPUS_RECOVERED,
        }[tier]
        return TerminalBrowserDiagnosis(
            reason=TerminalBrowserReason.POSTCONDITION_SATISFIED,
            step_id=DomStepId.PRICE_OFFER_EXTRACTION,
            provenance=provenance,
            confidence=1.0,
            evidence=frozenset(),
            operator_action=operator_action_for_reason(
                TerminalBrowserReason.POSTCONDITION_SATISFIED
            ),
        )

    def _unresolved_extraction_diagnosis(self) -> TerminalBrowserDiagnosis:
        """Type exhausted adaptive extraction without claiming business absence."""

        profile = getattr(self._llm, "last_profile", None)
        tier = getattr(profile, "tier", None)
        if isinstance(tier, ModelTier):
            provenance = {
                ModelTier.SONNET: DiagnosisProvenance.SONNET_DIAGNOSED,
                ModelTier.OPUS: DiagnosisProvenance.OPUS_DIAGNOSED,
            }[tier]
            model_stop_reason = ModelStopReason.OPUS_EXHAUSTED if tier is ModelTier.OPUS else None
            confidence = 0.0
        else:
            provenance = DiagnosisProvenance.POLICY_STOP
            model_stop_reason = None
            confidence = 1.0
        reason = TerminalBrowserReason.UNRESOLVED_AMBIGUITY
        return TerminalBrowserDiagnosis(
            reason=reason,
            step_id=DomStepId.PRICE_OFFER_EXTRACTION,
            provenance=provenance,
            confidence=confidence,
            evidence=frozenset(),
            operator_action=operator_action_for_reason(reason),
            model_stop_reason=model_stop_reason,
        )

    @staticmethod
    def _observed_currencies(selection: OfferSelection) -> tuple[str, ...]:
        return tuple(sorted({c.total.currency for c in selection.currency_mismatches}))

    @staticmethod
    def _currency_failure(
        booking: Booking,
        observed: tuple[str, ...],
        recovery: str,
        now: datetime,
    ) -> CheckResult:
        desired = booking.baseline_price.currency
        observed_label = ", ".join(observed) or "unknown"
        return CheckResult.failure(
            booking.booking_id,
            now,
            FailureReason(
                code=FailureCode.CURRENCY_MISMATCH,
                detail=(
                    f"Baseline {desired}; matching refundable offers rendered in "
                    f"{observed_label}. {recovery}. No cross-currency comparison was made."
                ),
            ),
        )

    @staticmethod
    def _no_equivalent_failure(
        booking: Booking,
        candidates: list[OfferCandidate],
        selection: OfferSelection,
        now: datetime,
    ) -> CheckResult:
        return CheckResult.failure(
            booking.booking_id,
            now,
            FailureReason(
                code=FailureCode.NO_EQUIVALENT_OFFER,
                detail=(
                    f"{len(candidates)} offers parsed, none equivalent+refundable "
                    f"(excluded: {selection.exclusion_summary()})"
                ),
            ),
        )

    @staticmethod
    def _journey_failure(booking: Booking, journey: JourneyResult, now: datetime) -> CheckResult:
        failed = journey.failed_step
        assert failed is not None and journey.failure_code is not None
        detail = f"step={failed.step.value}: {failed.detail}"
        if journey.failure_code is FailureCode.AUTH_REQUIRED:
            detail += (
                " (fix: run `booksaver auth import <file>` with a fresh cookie "
                "export — see the runbook's cookie-import section; works on a "
                "display-less VPS, unlike `booksaver auth`)"
            )
        return CheckResult.failure(
            booking.booking_id,
            now,
            FailureReason(
                code=(
                    failure_code_for_terminal(journey.terminal_diagnosis.reason)
                    if journey.terminal_diagnosis is not None
                    else journey.failure_code
                ),
                detail=detail,
            ),
            terminal_diagnosis=journey.terminal_diagnosis,
        )

    def _persist_trace(
        self,
        recorder: TraceRecorder,
        result: CheckResult,
        escalator: BrowserAgent | None,
    ) -> None:
        if self._trace_repo is not None:
            try:
                self._trace_repo.add(recorder.finish(result))
            except Exception as exc:
                logger.warning("Could not persist check trace: %s", exc)
        if self._snapshots is not None and result.failure_reason is not None:
            page_text = ""
            try:
                page_text = self._browser.snapshot().text
            except Exception:
                pass
            screenshot = escalator.last_screenshot if escalator else None
            self._snapshots.write_failure(result.check_id, page_text, screenshot)

    def _to_success(
        self,
        booking: Booking,
        chosen: OfferCandidate,
        method: ExtractionMethod,
        now: datetime,
        session_mode: SessionMode = SessionMode.AUTHENTICATED,
        session_revision_id: str | None = None,
        page_text: str = "",
        assisted_diagnoses: tuple[TerminalBrowserDiagnosis, ...] = (),
        genius_evidence: GeniusEvidence | None = None,
    ) -> CheckResult:
        """Map the chosen candidate to the downstream CheckResult contract.

        Property and dates were verified by the journey, so they are reported as
        the booking's own (verified-equal) values. A drift-matched room label is
        reported as None — absence passes the US-008 gate, whereas echoing the
        differing label would wrongly reject the already-judged equivalence.
        """
        if not chosen.exact_label_match(booking):
            logger.info(
                "Room match via judgment (confidence %.2f): booked %r ~ offered %r",
                chosen.match_confidence,
                booking.room_type.label,
                chosen.room_label,
            )
        price_source = None
        if session_revision_id is not None:
            genius = genius_evidence or (
                GeniusEvidence.APPLIED_OR_PRESENT
                if _GENIUS_EVIDENCE.search(page_text)
                else GeniusEvidence.NOT_OBSERVED
            )
            price_source = PriceSourceProvenance(
                profile_id=self._mobile_profile_id,
                session_revision_id=session_revision_id,
                genius_evidence=genius,
                observed_at=now,
            )
        return CheckResult.success(
            booking_id=booking.booking_id,
            checked_at=now,
            live_price=chosen.total,
            extraction_method=method,
            refund_indicators=RefundIndicators(
                is_refundable=chosen.is_refundable,
                raw_text=chosen.cancellation_text,
            ),
            extracted_fields=ExtractedBookingFields(
                property_name=booking.property.name,
                room_label=chosen.room_label if chosen.exact_label_match(booking) else None,
                check_in=booking.stay_dates.check_in,
                check_out=booking.stay_dates.check_out,
            ),
            session_mode=session_mode,
            price_source=price_source,
            assisted_diagnoses=assisted_diagnoses,
        )

    def _try_llm_offers(
        self, page_text: str, booking: Booking, budget: AgentBudget
    ) -> list[OfferCandidate] | None:
        if self._llm is None:
            logger.info("LLM extractor not configured; DOM-only offer parsing")
            return None
        budget.consume_llm_call()  # extraction draws from the same pool (ADR-017)
        try:
            offers = self._llm.extract_offers(page_text, booking)
            if offers:
                return offers
            escalate = getattr(self._llm, "extract_offers_with_escalation", None)
            if callable(escalate):
                budget.consume_llm_call()
                return cast(
                    list[OfferCandidate],
                    escalate(
                        page_text,
                        booking,
                        EscalationTrigger.UNRESOLVED_LOW_CONFIDENCE,
                    ),
                )
            return offers
        except Exception as exc:
            if isinstance(exc, AdaptiveModelStopped):
                raise
            logger.error("LLM offer extraction failed for booking %s: %s", booking.booking_id, exc)
            return None

    def _record(self, result: CheckResult) -> None:
        self._history.add(result)
        self._failures.after_check(result.booking_id, succeeded=result.outcome.value == "success")
