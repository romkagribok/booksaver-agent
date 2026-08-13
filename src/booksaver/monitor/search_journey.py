from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from booksaver.application.browser_resilience import DOM_STEP_REGISTRY
from booksaver.application.ports import InteractiveBrowser
from booksaver.domain.agent import AgentStopReason, BudgetExceeded
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomStepId,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
    operator_action_for_reason,
)
from booksaver.domain.check_result import FailureCode, failure_code_for_terminal
from booksaver.domain.journey import JourneyResult, JourneyStep, StepOutcome
from booksaver.domain.model_policy import ModelStopReason
from booksaver.domain.models import Booking
from booksaver.domain.session import SessionMode

if TYPE_CHECKING:
    from .browser_agent import BrowserAgent
    from .trace import TraceRecorder

logger = logging.getLogger(__name__)

# Production search-navigation DOM seams.  Legacy homepage open/fill steps are
# intentionally absent: production enters through the trusted direct results
# query before locating and verifying the registered property.
DOM_STEPS: tuple[DomStepId, ...] = (
    DomStepId.PRICE_SEARCH_QUERY_SUBMISSION,
    DomStepId.PRICE_SEARCH_RESULTS,
    DomStepId.PRICE_CONSENT_OVERLAY,
    DomStepId.PRICE_PROPERTY_LOCATE,
    DomStepId.PRICE_PROPERTY_OPEN,
    DomStepId.PRICE_CONTEXT_VERIFY,
    DomStepId.PRICE_ROOM_RATE_READINESS,
)

# Failures the agent cannot fix: captchas and logged-out sessions need the human
# (booksaver auth) — escalating would only burn budget.
_NON_ESCALATABLE = frozenset(
    {
        FailureCode.BOT_WALL,
        FailureCode.AUTH_REQUIRED,
        FailureCode.NO_EQUIVALENT_OFFER,
    }
)

_SEARCH_RESULTS_URL = "https://www.booking.com/searchresults.html"
_CURRENCY_QUERY_PARAM = "selected_currency"

_CAPTCHA_MARKERS = re.compile(
    r"(are you a human|verify you are human|hcaptcha|px-captcha|unusual traffic)", re.I
)
_SIGN_IN_MARKERS = re.compile(
    r"(sign in to manage|log in to your account|create an account)", re.I
)
_NO_AVAILABILITY_MARKERS = re.compile(
    r"(not available for (?:your|these) dates|no availability|no rooms? available|"
    r"sold out|unavailable on our site|we have no availability)",
    re.I,
)
_RATE_PRICE_MARKERS = re.compile(
    r"(?:US\$|C\$|A\$|\$|€|£|¥|USD|EUR|GBP|CAD|AUD)\s*[\d,.]+|"
    r"[\d,.]+\s*(?:USD|EUR|GBP|CAD|AUD)\b",
    re.I,
)
_RATE_CONTEXT_MARKERS = re.compile(
    r"\b(room|suite|studio|apartment|double|twin|single|king|queen|"
    r"free cancellation|refundable|non-?refundable)\b",
    re.I,
)

# Known-good selectors as of bolt 006. Drift here is expected: a missing selector
# fails its named step, where bolt 007's guarded LLM agent can take over.
_SEL_PROPERTY_CARD = '[data-testid="property-card"]'
_SEL_PROPERTY_TITLE = '[data-testid="property-card"] [data-testid="title"]'
_SEL_ROOM_TABLE_ANCHORS = ("#hprt-table", '[data-testid="rt-room-table"]')
_CONSENT_DISMISS_SELECTORS = (
    'button:text-is("Decline")',
    'button[aria-label="Decline"]',
    "#onetrust-reject-all-handler",
    'button:text-is("Reject all")',
    'button:text-is("Accept")',
    'button[aria-label="Accept"]',
    "#onetrust-accept-btn-handler",
)
_CURRENCY_TRIGGER_SELECTORS = (
    '[data-testid="header-currency-picker-trigger"]',
    'button[aria-label*="currency" i]',
)
_CURRENCY_NAMES = {
    "USD": ("US Dollar", "U.S. Dollar"),
    "EUR": ("Euro",),
    "GBP": ("British Pound", "Pound Sterling"),
    "CAD": ("Canadian Dollar",),
    "AUD": ("Australian Dollar",),
}


class _KnownJourneyFailure(RuntimeError):
    """A code-proven terminal outcome that must not consume a model call."""

    def __init__(self, code: FailureCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code


class _AmbiguousDomFailure(RuntimeError):
    """A DOM-dependent miss that may be recoverable from fresh page evidence."""


_STEP_FAILURE_CODES = {
    JourneyStep.SUBMIT_SEARCH: FailureCode.NAVIGATION_ERROR,
}

_PROPERTY_IDENTITY_SELECTORS = (
    'h1[data-testid="property-name"]',
    '[data-testid="property-name"]',
    "main h1",
    "h1",
)

_DOM_STEP_BY_JOURNEY_STEP = {
    JourneyStep.SUBMIT_SEARCH: DomStepId.PRICE_SEARCH_QUERY_SUBMISSION,
    JourneyStep.LOCATE_PROPERTY: DomStepId.PRICE_PROPERTY_LOCATE,
    JourneyStep.OPEN_PROPERTY: DomStepId.PRICE_PROPERTY_OPEN,
    JourneyStep.VERIFY_CONTEXT: DomStepId.PRICE_CONTEXT_VERIFY,
    JourneyStep.READ_ROOM_TABLE: DomStepId.PRICE_ROOM_RATE_READINESS,
    JourneyStep.ALIGN_CURRENCY: DomStepId.PRICE_CURRENCY_ALIGN,
}


def _provenance_for_terminal(reason: TerminalBrowserReason) -> DiagnosisProvenance:
    if reason in {
        TerminalBrowserReason.PROVIDER_AUTHENTICATION,
        TerminalBrowserReason.PROVIDER_UNAVAILABLE,
        TerminalBrowserReason.PROVIDER_RATE_LIMIT,
    }:
        return DiagnosisProvenance.PROVIDER_STOP
    if reason in {
        TerminalBrowserReason.TIME_LIMIT,
        TerminalBrowserReason.JOB_COST_LIMIT,
        TerminalBrowserReason.DAILY_COST_LIMIT,
        TerminalBrowserReason.MODEL_PRICING_UNAVAILABLE,
        TerminalBrowserReason.COST_ACCOUNTING_ERROR,
        TerminalBrowserReason.CLOCK_ROLLBACK,
    }:
        return DiagnosisProvenance.BUDGET_STOP
    if reason in {
        TerminalBrowserReason.AUTHENTICATION_REQUIRED,
        TerminalBrowserReason.MFA_REQUIRED,
        TerminalBrowserReason.BOT_WALL,
        TerminalBrowserReason.BLOCKED_DESTINATION,
        TerminalBrowserReason.PROHIBITED_ACTION,
        TerminalBrowserReason.EXPLICIT_UNAVAILABLE,
    }:
        return DiagnosisProvenance.DETERMINISTIC
    return DiagnosisProvenance.POLICY_STOP


def _terminal_diagnosis_from_escalation(
    step: JourneyStep,
    *,
    diagnosis: TerminalBrowserDiagnosis | None,
    model_stop_reason: ModelStopReason | None,
    agent_stop_reason: AgentStopReason | None,
) -> TerminalBrowserDiagnosis:
    if diagnosis is not None:
        return diagnosis
    step_id = _DOM_STEP_BY_JOURNEY_STEP[step]
    if model_stop_reason is not None:
        reason = DOM_STEP_REGISTRY.definition(step_id).reason_for_model_stop(
            model_stop_reason
        )
    else:
        reason = {
            AgentStopReason.AUTHENTICATION_REQUIRED: (
                TerminalBrowserReason.AUTHENTICATION_REQUIRED
            ),
            AgentStopReason.CAPTCHA: TerminalBrowserReason.BOT_WALL,
            AgentStopReason.EXPLICIT_UNAVAILABLE: (
                TerminalBrowserReason.EXPLICIT_UNAVAILABLE
            ),
            AgentStopReason.UNSAFE_ACTION: TerminalBrowserReason.PROHIBITED_ACTION,
            AgentStopReason.MISSING_BROWSER_CAPABILITY: (
                TerminalBrowserReason.OBSERVATION_UNAVAILABLE
            ),
            AgentStopReason.NO_PROGRESS: TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
            AgentStopReason.PROVIDER_ERROR: TerminalBrowserReason.PROVIDER_UNAVAILABLE,
            AgentStopReason.BUDGET_EXHAUSTED: TerminalBrowserReason.JOB_COST_LIMIT,
            AgentStopReason.UNKNOWN: TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
            None: TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
        }[agent_stop_reason]
    return TerminalBrowserDiagnosis(
        reason=reason,
        step_id=step_id,
        provenance=_provenance_for_terminal(reason),
        confidence=1.0,
        evidence=frozenset(),
        operator_action=operator_action_for_reason(reason),
        model_stop_reason=model_stop_reason,
    )


def _deterministic_diagnosis(
    step: JourneyStep,
    code: FailureCode,
) -> TerminalBrowserDiagnosis:
    reason = {
        FailureCode.AUTH_REQUIRED: TerminalBrowserReason.AUTHENTICATION_REQUIRED,
        FailureCode.BOT_WALL: TerminalBrowserReason.BOT_WALL,
        FailureCode.NO_EQUIVALENT_OFFER: TerminalBrowserReason.EXPLICIT_UNAVAILABLE,
        FailureCode.BLOCKED_ACTION: TerminalBrowserReason.PROHIBITED_ACTION,
        FailureCode.NAVIGATION_ERROR: TerminalBrowserReason.OBSERVATION_UNAVAILABLE,
        FailureCode.STEP_FAILED: TerminalBrowserReason.DETERMINISTIC_REJECTION,
        FailureCode.BUDGET_EXCEEDED: TerminalBrowserReason.TIME_LIMIT,
    }.get(code, TerminalBrowserReason.DETERMINISTIC_REJECTION)
    provenance = (
        DiagnosisProvenance.INFRASTRUCTURE_STOP
        if reason is TerminalBrowserReason.OBSERVATION_UNAVAILABLE
        else DiagnosisProvenance.BUDGET_STOP
        if reason is TerminalBrowserReason.TIME_LIMIT
        else DiagnosisProvenance.DETERMINISTIC
    )
    return TerminalBrowserDiagnosis(
        reason=reason,
        step_id=_DOM_STEP_BY_JOURNEY_STEP[step],
        provenance=provenance,
        confidence=1.0,
        evidence=frozenset(),
        operator_action=operator_action_for_reason(reason),
    )


def _ambiguous_diagnosis(step: JourneyStep) -> TerminalBrowserDiagnosis:
    reason = TerminalBrowserReason.UNRESOLVED_AMBIGUITY
    return TerminalBrowserDiagnosis(
        reason=reason,
        step_id=_DOM_STEP_BY_JOURNEY_STEP[step],
        provenance=DiagnosisProvenance.POLICY_STOP,
        confidence=1.0,
        evidence=frozenset(),
        operator_action=operator_action_for_reason(reason),
    )


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _search_results_url(
    booking: Booking, *, dest_id: str | None = None, dest_type: str | None = None
) -> str:
    """Booking.com results URL built only from persisted search context.

    `src=searchresults` keeps query params; `src=index` often redirects to a city
    landing page with no property cards.
    """
    occ = booking.occupancy
    assert occ is not None
    params = {
        "ss": booking.property.name,
        "checkin": booking.stay_dates.check_in.isoformat(),
        "checkout": booking.stay_dates.check_out.isoformat(),
        "group_adults": str(occ.adults),
        "group_children": str(occ.children),
        "no_rooms": str(occ.rooms),
        _CURRENCY_QUERY_PARAM: booking.baseline_price.currency,
        "sb": "1",
        "src": "searchresults",
    }
    if dest_id and dest_type:
        params["dest_id"] = dest_id
        params["dest_type"] = dest_type
    return f"{_SEARCH_RESULTS_URL}?{urlencode(params)}"


def _is_booking_property_url(url: str) -> bool:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    return (hostname == "booking.com" or hostname.endswith(".booking.com")) and (
        "/hotel/" in parsed.path
    )


def _property_url_with_context(href: str, booking: Booking) -> str:
    """Merge trusted search context into the fresh result-card property href."""
    absolute = urljoin(_SEARCH_RESULTS_URL, href)
    if not _is_booking_property_url(absolute):
        raise RuntimeError(f"Unsafe or non-property Booking.com result href: {absolute}")
    occ = booking.occupancy
    assert occ is not None
    parsed = urlsplit(absolute)
    trusted = {
        "checkin": booking.stay_dates.check_in.isoformat(),
        "checkout": booking.stay_dates.check_out.isoformat(),
        "group_adults": str(occ.adults),
        "group_children": str(occ.children),
        "no_rooms": str(occ.rooms),
        _CURRENCY_QUERY_PARAM: booking.baseline_price.currency,
    }
    # Preserve opaque result-card parameters exactly, including duplicates, while
    # ensuring stale search context can never override the persisted booking.
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in trusted
    ]
    query.extend(trusted.items())
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


class SearchJourney:
    """Verified search journey: results query → exact property → room table.

    The results query is built from persisted booking data (US-041); the visible
    homepage form is not an automation dependency. Extraction from the room table
    happens upstream in the monitor.
    """

    def __init__(
        self,
        browser: InteractiveBrowser,
        escalator: BrowserAgent | None = None,
        recorder: TraceRecorder | None = None,
        checkpoint: Callable[[], None] | None = None,
        session_mode: SessionMode = SessionMode.AUTHENTICATED,
    ) -> None:
        self._browser = browser
        self._escalator = escalator
        self._recorder = recorder
        self._checkpoint = checkpoint  # budget wall-clock check between steps
        self._session_mode = session_mode
        self._verified_property_paths: set[str] = set()

    def run(self, booking: Booking) -> JourneyResult:
        self._verified_property_paths.clear()
        steps: list[tuple[JourneyStep, Callable[[Booking], str]]] = [
            (JourneyStep.SUBMIT_SEARCH, self._submit_search),
            (JourneyStep.LOCATE_PROPERTY, self._locate_property),
            (JourneyStep.OPEN_PROPERTY, self._open_property),
            (JourneyStep.VERIFY_CONTEXT, self._verify_context),
            (JourneyStep.READ_ROOM_TABLE, self._await_room_table),
        ]
        outcomes: list[StepOutcome] = []
        agent_assisted = False
        assisted_diagnoses: list[TerminalBrowserDiagnosis] = []
        for step, action in steps:
            try:
                if self._checkpoint is not None:
                    self._checkpoint()
                detail = action(booking)
            except BudgetExceeded as exc:
                outcome = StepOutcome.failed(step, str(exc))
                self._record(outcome)
                outcomes.append(outcome)
                return JourneyResult(
                    outcomes=tuple(outcomes),
                    failure_code=FailureCode.BUDGET_EXCEEDED,
                    agent_assisted=agent_assisted,
                    terminal_diagnosis=_deterministic_diagnosis(
                        step, FailureCode.BUDGET_EXCEEDED
                    ),
                    assisted_diagnoses=tuple(assisted_diagnoses),
                )
            except _KnownJourneyFailure as exc:
                outcome = StepOutcome.failed(step, str(exc))
                self._record(outcome)
                outcomes.append(outcome)
                return JourneyResult(
                    outcomes=tuple(outcomes),
                    failure_code=exc.code,
                    agent_assisted=agent_assisted,
                    terminal_diagnosis=_deterministic_diagnosis(step, exc.code),
                    assisted_diagnoses=tuple(assisted_diagnoses),
                )
            except Exception as exc:
                code = self._classify_failure(step)
                if self._escalator is not None and code not in _NON_ESCALATABLE:
                    def _verify(s: JourneyStep = step, b: Booking = booking) -> bool:
                        return self._step_verified(s, b)

                    trigger = self._escalation_trigger(step, booking, exc)

                    escalation = self._escalator.complete_step(
                        step,
                        goal=self._step_goal(step, booking),
                        verify=_verify,
                        trigger=trigger,
                        screenshot_first=step
                        in (JourneyStep.SUBMIT_SEARCH, JourneyStep.READ_ROOM_TABLE),
                    )
                    if escalation.ok:
                        agent_assisted = True
                        if escalation.diagnosis is not None:
                            assisted_diagnoses.append(escalation.diagnosis)
                        outcome = StepOutcome.success(step, escalation.detail)
                        self._record(outcome)
                        outcomes.append(outcome)
                        continue
                    final_code = self._classify_failure(step)
                    if final_code in _NON_ESCALATABLE:
                        detail = str(exc)
                        if final_code is FailureCode.NO_EQUIVALENT_OFFER:
                            detail = (
                                "Booking.com reports no availability for the requested stay"
                            )
                        outcome = StepOutcome.failed(step, detail)
                        self._record(outcome)
                        outcomes.append(outcome)
                        return JourneyResult(
                            outcomes=tuple(outcomes),
                            failure_code=final_code,
                            agent_assisted=True,
                            terminal_diagnosis=_deterministic_diagnosis(
                                step, final_code
                            ),
                            assisted_diagnoses=tuple(assisted_diagnoses),
                        )
                    outcome = StepOutcome.failed(step, escalation.detail)
                    self._record(outcome)
                    outcomes.append(outcome)
                    diagnosis = _terminal_diagnosis_from_escalation(
                        step,
                        diagnosis=escalation.diagnosis,
                        model_stop_reason=escalation.model_stop_reason,
                        agent_stop_reason=escalation.stop_reason,
                    )
                    return JourneyResult(
                        outcomes=tuple(outcomes),
                        failure_code=failure_code_for_terminal(diagnosis.reason),
                        agent_assisted=True,
                        terminal_diagnosis=diagnosis,
                        assisted_diagnoses=tuple(assisted_diagnoses),
                    )
                outcome = StepOutcome.failed(step, str(exc))
                self._record(outcome)
                outcomes.append(outcome)
                logger.warning("Journey step %s failed (%s): %s", step.value, code.value, exc)
                return JourneyResult(
                    outcomes=tuple(outcomes),
                    failure_code=code,
                    agent_assisted=agent_assisted,
                    terminal_diagnosis=(
                        _deterministic_diagnosis(step, code)
                        if code in _NON_ESCALATABLE
                        else _ambiguous_diagnosis(step)
                        if isinstance(exc, _AmbiguousDomFailure)
                        else _deterministic_diagnosis(step, code)
                    ),
                    assisted_diagnoses=tuple(assisted_diagnoses),
                )
            outcome = StepOutcome.success(step, detail)
            self._record(outcome)
            outcomes.append(outcome)
        return JourneyResult(
            outcomes=tuple(outcomes),
            agent_assisted=agent_assisted,
            assisted_diagnoses=tuple(assisted_diagnoses),
        )

    def _record(self, outcome: StepOutcome) -> None:
        if self._recorder is not None:
            self._recorder.journey_step(outcome)

    # ── escalation support (US-020) ──────────────────────────────────────────

    def _step_goal(self, step: JourneyStep, booking: Booking) -> str:
        goals = {
            JourneyStep.SUBMIT_SEARCH: "Load Booking.com search results for the exact "
            "persisted property, dates, and occupancy.",
            JourneyStep.LOCATE_PROPERTY: f"Find the property {booking.property.name!r} "
            "in the search results list.",
            JourneyStep.OPEN_PROPERTY: f"Open the property page for "
            f"{booking.property.name!r} with the trusted dates and occupancy preserved.",
            JourneyStep.VERIFY_CONTEXT: "Ensure the property page shows prices for "
            f"check-in {booking.stay_dates.check_in.isoformat()} to check-out "
            f"{booking.stay_dates.check_out.isoformat()} with the right party size.",
            JourneyStep.READ_ROOM_TABLE: "Reveal room/rate content with prices and "
            "cancellation policies. Dismiss any consent panel, scroll toward availability, "
            "and click a read-only 'Check available dates' control if shown. If the page "
            "explicitly says the stay is unavailable or sold out, give up with that reason.",
        }
        return goals[step]

    def _escalation_trigger(
        self, step: JourneyStep, booking: Booking, exc: Exception
    ) -> str:
        return str(exc)

    def _step_verified(self, step: JourneyStep, booking: Booking) -> bool:
        """Postcondition check so agent success is verified, not assumed."""
        try:
            if step is JourneyStep.SUBMIT_SEARCH:
                return self._browser.exists(
                    _SEL_PROPERTY_CARD
                ) or self._accessible_property_result_verified(booking)
            if step is JourneyStep.LOCATE_PROPERTY:
                wanted = _normalise(booking.property.name)
                return self._accessible_property_result_verified(booking) or any(
                    _normalise(t) == wanted
                    for t in self._browser.query_text(_SEL_PROPERTY_TITLE)
                )
            if step is JourneyStep.OPEN_PROPERTY:
                return self._property_identity_verified(booking)
            if step is JourneyStep.VERIFY_CONTEXT:
                self._verify_context(booking)
                return True
            if step is JourneyStep.READ_ROOM_TABLE:
                return self._room_content_ready()
        except Exception:
            return False
        return False

    def _accessible_property_result_verified(self, booking: Booking) -> bool:
        """Verify an exact visible result link without relying on legacy selectors."""
        observation = self._browser.observe()
        page = urlsplit(observation.url)
        if page.path != "/searchresults.html":
            return False
        wanted = _normalise(booking.property.name)
        for element in observation.elements:
            if element.role != "link" or _normalise(element.label) != wanted:
                continue
            if not element.href:
                continue
            destination = urljoin(observation.url, element.href)
            if not _is_booking_property_url(destination):
                continue
            self._verified_property_paths.add(
                urlsplit(destination).path.rstrip("/")
            )
            return True
        return False

    def _classify_failure(self, step: JourneyStep) -> FailureCode:
        page_text = self._safe_text()
        if _CAPTCHA_MARKERS.search(page_text):
            return FailureCode.BOT_WALL
        if step is JourneyStep.READ_ROOM_TABLE and _NO_AVAILABILITY_MARKERS.search(
            page_text
        ):
            return FailureCode.NO_EQUIVALENT_OFFER
        # AUTH_REQUIRED means "your saved session dropped" — it presupposes a
        # session existed. In logged-out mode there is nothing to drop (US-035,
        # FR-8): a "sign in" banner just reflects the anonymous journey and must
        # not be misreported as an auth failure, so fall through to the
        # step-specific code instead.
        if self._session_mode is SessionMode.AUTHENTICATED and _SIGN_IN_MARKERS.search(
            page_text
        ):
            return FailureCode.AUTH_REQUIRED
        return _STEP_FAILURE_CODES.get(step, FailureCode.STEP_FAILED)

    def _property_identity_verified(
        self,
        booking: Booking,
        *,
        expected_url: str | None = None,
    ) -> bool:
        """Prove the requested property, never merely a generic hotel route.

        The exact path from the matched result-card href is code-owned evidence.
        A visible exact property heading is accepted as an independent fallback
        for guarded recovery where the model opened the property without exposing
        the original selector.  Neither the model nor a bare ``/hotel/`` URL can
        assert identity by itself.
        """
        snapshot = self._browser.snapshot()
        if not _is_booking_property_url(snapshot.url):
            return False
        current_path = urlsplit(snapshot.url).path.rstrip("/")
        registered_ref = booking.property.booking_com_ref
        if _is_booking_property_url(registered_ref):
            self._verified_property_paths.add(urlsplit(registered_ref).path.rstrip("/"))
        if current_path in self._verified_property_paths:
            return True
        if expected_url is not None:
            expected = urlsplit(expected_url)
            current = urlsplit(snapshot.url)
            if (
                (expected.hostname or "").lower() == (current.hostname or "").lower()
                and expected.path.rstrip("/") == current.path.rstrip("/")
            ):
                return True

        wanted = _normalise(booking.property.name)
        visible_names: list[str] = []
        for selector in _PROPERTY_IDENTITY_SELECTORS:
            try:
                visible_names.extend(self._browser.query_text(selector))
            except Exception:
                continue
        if snapshot.title:
            visible_names.append(snapshot.title)
        return any(_normalise(name) == wanted for name in visible_names)

    def _safe_text(self) -> str:
        try:
            return self._browser.snapshot().text
        except Exception:
            return ""

    def _dismiss_consent(self) -> str | None:
        """Best-effort consent dismissal, preferring privacy-preserving rejection."""
        for selector in _CONSENT_DISMISS_SELECTORS:
            try:
                if not self._browser.exists(selector):
                    continue
                self._browser.click(selector)
                return selector
            except Exception:
                continue
        return None

    def currency_preference_visible(self, currency: str) -> bool:
        """Verify the current header control, never a requested URL parameter."""
        markers = (currency, *_CURRENCY_NAMES.get(currency, ()))
        normalised_markers = tuple(
            re.sub(r"[^A-Z]", "", marker.upper()) for marker in markers
        )
        for selector in _CURRENCY_TRIGGER_SELECTORS:
            values: list[str] = []
            try:
                values.extend(self._browser.query_text(selector))
                values.extend(self._browser.query_attr(selector, "aria-label"))
                values.extend(self._browser.query_attr(selector, "title"))
            except Exception:
                continue
            for value in values:
                normalised = re.sub(r"[^A-Z]", "", value.upper())
                if any(marker and marker in normalised for marker in normalised_markers):
                    return True
        return False

    def align_currency(self, booking: Booking) -> str:
        """Operate Booking.com's visible currency preference deterministically.

        The caller must still reload the trusted journey and verify currencies on
        rendered room offers. Header state is only a recovery postcondition, never
        permission to compare unlike amounts.
        """
        currency = booking.baseline_price.currency
        self._dismiss_consent()
        trigger_used: str | None = None
        trigger_errors: list[str] = []
        for selector in _CURRENCY_TRIGGER_SELECTORS:
            try:
                self._browser.click_first_visible(selector)
                trigger_used = selector
                break
            except Exception as exc:
                trigger_errors.append(str(exc))
        if trigger_used is None:
            raise RuntimeError(
                "Currency preference control not found: " + "; ".join(trigger_errors)
            )

        option_errors: list[str] = []
        option_used: str | None = None
        option_markers = (currency, *_CURRENCY_NAMES.get(currency, ()))
        for marker in option_markers:
            selectors = (
                f'[role="dialog"] [data-testid="selection-item"]:has-text("{marker}")',
                f'[role="dialog"] button:has-text("{marker}")',
                f'button:has-text("{marker}")',
            )
            for selector in selectors:
                try:
                    self._browser.click_first_visible(selector)
                    option_used = selector
                    break
                except Exception as exc:
                    option_errors.append(str(exc))
            if option_used is not None:
                break
        if option_used is None:
            raise RuntimeError(
                f"Currency option {currency} not found: " + "; ".join(option_errors)
            )
        if not self.currency_preference_visible(currency):
            raise RuntimeError(
                f"Currency control did not confirm {currency} after selecting it"
            )
        return (
            f"requested={currency}; trigger={trigger_used}; option={option_used}; "
            "header preference verified"
        )

    def _room_content_ready(self) -> bool:
        text = self._safe_text()
        if _CAPTCHA_MARKERS.search(text) or _NO_AVAILABILITY_MARKERS.search(text):
            return False
        if any(self._browser.exists(anchor) for anchor in _SEL_ROOM_TABLE_ANCHORS):
            return True
        return bool(_RATE_PRICE_MARKERS.search(text) and _RATE_CONTEXT_MARKERS.search(text))

    # ── steps ────────────────────────────────────────────────────────────────

    def _submit_search(self, booking: Booking) -> str:
        # Enter through Booking.com's read-only results query. This remains the
        # customer search journey (results → fresh property link → verified room
        # table), not a registered-property or checkout deep link.
        url = _search_results_url(booking)
        try:
            self._browser.goto(url)
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise _KnownJourneyFailure(
                FailureCode.NAVIGATION_ERROR,
                f"Booking.com search navigation failed ({type(exc).__name__})",
            ) from exc
        dismissed = self._dismiss_consent()
        if _CAPTCHA_MARKERS.search(self._safe_text()):
            raise _KnownJourneyFailure(
                FailureCode.BOT_WALL,
                "Bot-detection interstitial on the search-results page",
            )
        try:
            self._browser.wait_for(_SEL_PROPERTY_CARD)
        except Exception as exc:
            raise _AmbiguousDomFailure(
                "Search results loaded, but the property-card structure could not "
                "be recognized"
            ) from exc
        suffix = f"; consent dismissed via {dismissed}" if dismissed else ""
        return f"results loaded ({url}){suffix}"

    def _locate_property(self, booking: Booking) -> str:
        titles = self._browser.query_text(_SEL_PROPERTY_TITLE)
        wanted = _normalise(booking.property.name)
        for index, title in enumerate(titles):
            if _normalise(title) == wanted:
                try:
                    hrefs = self._browser.query_attr(
                        '[data-testid="title-link"]', "href"
                    )
                    if index < len(hrefs) and _is_booking_property_url(
                        urljoin(_SEARCH_RESULTS_URL, hrefs[index])
                    ):
                        self._verified_property_paths.add(
                            urlsplit(
                                urljoin(_SEARCH_RESULTS_URL, hrefs[index])
                            ).path.rstrip("/")
                        )
                except Exception:
                    pass
                return f"index={index} title={title!r}"
        raise _AmbiguousDomFailure(
            f"Could not verify {booking.property.name!r} in the current search-results "
            f"structure ({len(titles)} recognized titles)"
        )

    def _open_property(self, booking: Booking) -> str:
        # Re-derive the matched card index so the step is self-contained.
        titles = self._browser.query_text(_SEL_PROPERTY_TITLE)
        wanted = _normalise(booking.property.name)
        try:
            index = next(i for i, t in enumerate(titles) if _normalise(t) == wanted)
        except StopIteration as exc:
            raise _AmbiguousDomFailure(
                f"The matched property {booking.property.name!r} could not be re-verified "
                "before opening it"
            ) from exc
        # Property cards open target=_blank; clicking leaves the journey on the
        # results page. Navigate the same tab via the title-link href instead.
        hrefs = self._browser.query_attr('[data-testid="title-link"]', "href")
        if index >= len(hrefs) or not hrefs[index]:
            raise _AmbiguousDomFailure(
                f"No title-link href for property {booking.property.name!r} at index {index}"
            )
        try:
            url = _property_url_with_context(hrefs[index], booking)
        except RuntimeError as exc:
            raise _KnownJourneyFailure(FailureCode.BLOCKED_ACTION, str(exc)) from exc
        try:
            self._browser.goto(url)
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise _KnownJourneyFailure(
                FailureCode.NAVIGATION_ERROR,
                f"Booking.com property navigation failed ({type(exc).__name__})",
            ) from exc
        dismissed = self._dismiss_consent()
        snapshot = self._browser.snapshot()
        if _CAPTCHA_MARKERS.search(snapshot.text):
            raise _KnownJourneyFailure(
                FailureCode.BOT_WALL,
                "Bot-detection interstitial on the property page",
            )
        if not _is_booking_property_url(snapshot.url):
            raise _KnownJourneyFailure(
                FailureCode.BLOCKED_ACTION,
                "Property navigation left the approved Booking.com property origin",
            )
        if not self._property_identity_verified(booking, expected_url=url):
            raise _AmbiguousDomFailure(
                f"Property navigation did not prove the requested identity "
                f"{booking.property.name!r}"
            )
        suffix = f"; consent dismissed via {dismissed}" if dismissed else ""
        return f"property loaded ({snapshot.url}){suffix}"

    def _verify_context(self, booking: Booking) -> str:
        occ = booking.occupancy
        assert occ is not None
        url = self._browser.snapshot().url
        query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
        checks = {
            "checkin": booking.stay_dates.check_in.isoformat(),
            "checkout": booking.stay_dates.check_out.isoformat(),
            "group_adults": str(occ.adults),
            "group_children": str(occ.children),
            "no_rooms": str(occ.rooms),
        }
        mismatches = [
            f"{param}={expected} missing from property URL"
            for param, expected in checks.items()
            if query.get(param) != expected
        ]
        if mismatches:
            raise _KnownJourneyFailure(FailureCode.STEP_FAILED, "; ".join(mismatches))
        return "dates and occupancy verified in property URL"

    def _await_room_table(self, booking: Booking) -> str:
        self._dismiss_consent()
        text = self._safe_text()
        if _CAPTCHA_MARKERS.search(text):
            raise _KnownJourneyFailure(
                FailureCode.BOT_WALL,
                "Bot-detection interstitial on the property page",
            )
        if _NO_AVAILABILITY_MARKERS.search(text):
            raise _KnownJourneyFailure(
                FailureCode.NO_EQUIVALENT_OFFER,
                "Booking.com reports no availability for the requested stay",
            )
        if _RATE_PRICE_MARKERS.search(text) and _RATE_CONTEXT_MARKERS.search(text):
            return "semantic room/rate content present without a legacy table anchor"
        for anchor in _SEL_ROOM_TABLE_ANCHORS:
            try:
                self._browser.wait_for(anchor, timeout_ms=5_000)
                return f"room table anchor: {anchor}"
            except Exception:
                continue
        # Content may have loaded while the selector waits elapsed.
        if self._room_content_ready():
            return "semantic room/rate content present without a legacy table anchor"
        raise _AmbiguousDomFailure(
            "No room/rate content or explicit availability outcome found on property page"
        )
