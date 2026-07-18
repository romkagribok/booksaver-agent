from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING
from urllib.parse import urlencode

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
_NON_ESCALATABLE = frozenset({FailureCode.BOT_WALL, FailureCode.AUTH_REQUIRED})

_SEARCH_RESULTS_URL = "https://www.booking.com/searchresults.html"

_CAPTCHA_MARKERS = re.compile(
    r"(are you a human|verify you are human|hcaptcha|px-captcha|unusual traffic)", re.I
)
_SIGN_IN_MARKERS = re.compile(
    r"(sign in to manage|log in to your account|create an account)", re.I
)

# Known-good selectors as of bolt 006. Drift here is expected: a missing selector
# fails its named step, where bolt 007's guarded LLM agent can take over.
_SEL_PROPERTY_CARD = '[data-testid="property-card"]'
_SEL_PROPERTY_TITLE = '[data-testid="property-card"] [data-testid="title"]'
_SEL_ROOM_TABLE_ANCHORS = ("#hprt-table", '[data-testid="rt-room-table"]')

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
                        screenshot_first=step is JourneyStep.SUBMIT_SEARCH,
                    )
                    if escalation.ok:
                        agent_assisted = True
                        outcome = StepOutcome.success(step, escalation.detail)
                        self._record(outcome)
                        outcomes.append(outcome)
                        continue
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
            f"{booking.property.name!r} so its room/rate table is visible.",
            JourneyStep.VERIFY_CONTEXT: "Ensure the property page shows prices for "
            f"check-in {booking.stay_dates.check_in.isoformat()} to check-out "
            f"{booking.stay_dates.check_out.isoformat()} with the right party size.",
            JourneyStep.READ_ROOM_TABLE: "Make the room/rate table with prices and "
            "cancellation policies fully visible.",
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
                return any(self._browser.exists(a) for a in _SEL_ROOM_TABLE_ANCHORS)
            if step is JourneyStep.VERIFY_CONTEXT:
                self._verify_context(booking)
                return True
            if step is JourneyStep.READ_ROOM_TABLE:
                return not _CAPTCHA_MARKERS.search(self._safe_text())
        except Exception:
            return False
        return False

    def _classify_failure(self, step: JourneyStep) -> FailureCode:
        page_text = self._safe_text()
        if _CAPTCHA_MARKERS.search(page_text):
            return FailureCode.BOT_WALL
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

    # ── steps ────────────────────────────────────────────────────────────────

    def _submit_search(self, booking: Booking) -> str:
        # Enter through Booking.com's read-only results query. This remains the
        # customer search journey (results → fresh property link → verified room
        # table), not a registered-property or checkout deep link.
        url = _search_results_url(booking)
        self._browser.goto(url)
        if _CAPTCHA_MARKERS.search(self._safe_text()):
            raise RuntimeError("Bot-detection interstitial on the search-results page")
        self._browser.wait_for(_SEL_PROPERTY_CARD)
        return f"results loaded ({url})"

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
        self._browser.goto(hrefs[index])
        last_error: Exception | None = None
        for anchor in _SEL_ROOM_TABLE_ANCHORS:
            try:
                self._browser.wait_for(anchor, timeout_ms=15_000)
                return f"room table anchor: {anchor}"
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"No room table anchor found: {last_error}")

    def _verify_context(self, booking: Booking) -> str:
        occ = booking.occupancy
        assert occ is not None
        snapshot = self._browser.snapshot()
        url = snapshot.url
        checks = {
            "checkin": booking.stay_dates.check_in.isoformat(),
            "checkout": booking.stay_dates.check_out.isoformat(),
            "group_adults": str(occ.adults),
        }
        mismatches = [
            f"{param}={expected} not in page URL"
            for param, expected in checks.items()
            if f"{param}={expected}" not in url
        ]
        if mismatches:
            raise RuntimeError("; ".join(mismatches))
        return "dates and occupancy verified in property URL"

    def _await_room_table(self, booking: Booking) -> str:
        # The page is already on the room table (open_property waited for its
        # anchor); this step exists as the named escalation seam for extraction
        # oddities and re-checks the wall/auth markers before extraction runs.
        text = self._safe_text()
        if _CAPTCHA_MARKERS.search(text):
            raise RuntimeError("Bot-detection interstitial on the property page")
        return "room table present"
