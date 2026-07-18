from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from booksaver.application.ports import InteractiveBrowser
from booksaver.domain.agent import BudgetExceeded
from booksaver.domain.check_result import FailureCode
from booksaver.domain.journey import JourneyResult, JourneyStep, StepOutcome
from booksaver.domain.models import Booking
from booksaver.domain.session import SessionMode

if TYPE_CHECKING:
    from .browser_agent import BrowserAgent
    from .trace import TraceRecorder

logger = logging.getLogger(__name__)

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

_STEP_FAILURE_CODES = {
    JourneyStep.SUBMIT_SEARCH: FailureCode.NAVIGATION_ERROR,
    JourneyStep.LOCATE_PROPERTY: FailureCode.PROPERTY_NOT_FOUND,
}


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

    def run(self, booking: Booking) -> JourneyResult:
        steps: list[tuple[JourneyStep, Callable[[Booking], str]]] = [
            (JourneyStep.SUBMIT_SEARCH, self._submit_search),
            (JourneyStep.LOCATE_PROPERTY, self._locate_property),
            (JourneyStep.OPEN_PROPERTY, self._open_property),
            (JourneyStep.VERIFY_CONTEXT, self._verify_context),
            (JourneyStep.READ_ROOM_TABLE, self._await_room_table),
        ]
        outcomes: list[StepOutcome] = []
        agent_assisted = False
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
                        outcome = StepOutcome.success(step, escalation.detail)
                        self._record(outcome)
                        outcomes.append(outcome)
                        continue
                    final_code = self._classify_failure(step)
                    if final_code in _NON_ESCALATABLE:
                        detail = str(exc)
                        if final_code is FailureCode.NO_EQUIVALENT_OFFER:
                            detail = "Booking.com reports no availability for the requested stay"
                        outcome = StepOutcome.failed(step, detail)
                        self._record(outcome)
                        outcomes.append(outcome)
                        return JourneyResult(
                            outcomes=tuple(outcomes),
                            failure_code=final_code,
                            agent_assisted=True,
                        )
                    outcome = StepOutcome.failed(step, escalation.detail)
                    self._record(outcome)
                    outcomes.append(outcome)
                    assert escalation.failure_code is not None
                    return JourneyResult(
                        outcomes=tuple(outcomes),
                        failure_code=escalation.failure_code,
                        agent_assisted=True,
                    )
                outcome = StepOutcome.failed(step, str(exc))
                self._record(outcome)
                outcomes.append(outcome)
                logger.warning("Journey step %s failed (%s): %s", step.value, code.value, exc)
                return JourneyResult(
                    outcomes=tuple(outcomes),
                    failure_code=code,
                    agent_assisted=agent_assisted,
                )
            outcome = StepOutcome.success(step, detail)
            self._record(outcome)
            outcomes.append(outcome)
        return JourneyResult(outcomes=tuple(outcomes), agent_assisted=agent_assisted)

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
                return self._browser.exists(_SEL_PROPERTY_CARD)
            if step is JourneyStep.LOCATE_PROPERTY:
                wanted = _normalise(booking.property.name)
                return any(
                    _normalise(t) == wanted
                    for t in self._browser.query_text(_SEL_PROPERTY_TITLE)
                )
            if step is JourneyStep.OPEN_PROPERTY:
                return _is_booking_property_url(self._browser.snapshot().url)
            if step is JourneyStep.VERIFY_CONTEXT:
                self._verify_context(booking)
                return True
            if step is JourneyStep.READ_ROOM_TABLE:
                return self._room_content_ready()
        except Exception:
            return False
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
        self._browser.goto(url)
        dismissed = self._dismiss_consent()
        if _CAPTCHA_MARKERS.search(self._safe_text()):
            raise RuntimeError("Bot-detection interstitial on the search-results page")
        self._browser.wait_for(_SEL_PROPERTY_CARD)
        suffix = f"; consent dismissed via {dismissed}" if dismissed else ""
        return f"results loaded ({url}){suffix}"

    def _locate_property(self, booking: Booking) -> str:
        titles = self._browser.query_text(_SEL_PROPERTY_TITLE)
        wanted = _normalise(booking.property.name)
        for index, title in enumerate(titles):
            if _normalise(title) == wanted:
                return f"index={index} title={title!r}"
        raise RuntimeError(
            f"Property {booking.property.name!r} not found among {len(titles)} results"
        )

    def _open_property(self, booking: Booking) -> str:
        # Re-derive the matched card index so the step is self-contained.
        titles = self._browser.query_text(_SEL_PROPERTY_TITLE)
        wanted = _normalise(booking.property.name)
        index = next(i for i, t in enumerate(titles) if _normalise(t) == wanted)
        # Property cards open target=_blank; clicking leaves the journey on the
        # results page. Navigate the same tab via the title-link href instead.
        hrefs = self._browser.query_attr('[data-testid="title-link"]', "href")
        if index >= len(hrefs) or not hrefs[index]:
            raise RuntimeError(
                f"No title-link href for property {booking.property.name!r} at index {index}"
            )
        url = _property_url_with_context(hrefs[index], booking)
        self._browser.goto(url)
        dismissed = self._dismiss_consent()
        snapshot = self._browser.snapshot()
        if _CAPTCHA_MARKERS.search(snapshot.text):
            raise RuntimeError("Bot-detection interstitial on the property page")
        if not _is_booking_property_url(snapshot.url):
            raise RuntimeError(f"Property navigation landed on unexpected URL: {snapshot.url}")
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
            raise RuntimeError("; ".join(mismatches))
        return "dates and occupancy verified in property URL"

    def _await_room_table(self, booking: Booking) -> str:
        self._dismiss_consent()
        text = self._safe_text()
        if _CAPTCHA_MARKERS.search(text):
            raise RuntimeError("Bot-detection interstitial on the property page")
        if _NO_AVAILABILITY_MARKERS.search(text):
            raise RuntimeError("Booking.com reports no availability for the requested stay")
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
        raise RuntimeError(
            "No room/rate content or explicit availability outcome found on property page"
        )
