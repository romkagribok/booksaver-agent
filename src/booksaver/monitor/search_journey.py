from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from booksaver.application.ports import InteractiveBrowser
from booksaver.domain.agent import BudgetExceeded
from booksaver.domain.check_result import FailureCode
from booksaver.domain.journey import JourneyResult, JourneyStep, StepOutcome
from booksaver.domain.models import Booking

if TYPE_CHECKING:
    from .browser_agent import BrowserAgent
    from .trace import TraceRecorder

logger = logging.getLogger(__name__)

# Failures the agent cannot fix: captchas and logged-out sessions need the human
# (booksaver auth) — escalating would only burn budget.
_NON_ESCALATABLE = frozenset({FailureCode.BOT_WALL, FailureCode.AUTH_REQUIRED})

_HOME_URL = "https://www.booking.com"

_CAPTCHA_MARKERS = re.compile(
    r"(are you a human|verify you are human|hcaptcha|px-captcha|unusual traffic)", re.I
)
_SIGN_IN_MARKERS = re.compile(
    r"(sign in to manage|log in to your account|create an account)", re.I
)

# Known-good selectors as of bolt 006. Drift here is EXPECTED and acceptable:
# a missing selector fails the step with its name, which is the seam where
# bolt 007's LLM agent takes over (ADR-013).
_SEL_SEARCH_BOX = 'input[name="ss"]'
_SEL_CONSENT_ACCEPT = "#onetrust-accept-btn-handler"
_SEL_DATES_CONTAINER = '[data-testid="searchbox-dates-container"]'
_SEL_OCCUPANCY_CONFIG = '[data-testid="occupancy-config"]'
_SEL_SUBMIT = 'button[type="submit"]'
_SEL_PROPERTY_CARD = '[data-testid="property-card"]'
_SEL_PROPERTY_TITLE = '[data-testid="property-card"] [data-testid="title"]'
_SEL_ROOM_TABLE_ANCHORS = ("#hprt-table", '[data-testid="rt-room-table"]')

_STEP_FAILURE_CODES = {
    JourneyStep.OPEN_HOME: FailureCode.NAVIGATION_ERROR,
    JourneyStep.LOCATE_PROPERTY: FailureCode.PROPERTY_NOT_FOUND,
}


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


class SearchJourney:
    """Scripted full search journey (US-018): home → search → results →
    verified property page. Extraction from the room table happens upstream in
    the monitor; this class only gets the browser onto the right page.
    """

    def __init__(
        self,
        browser: InteractiveBrowser,
        escalator: BrowserAgent | None = None,
        recorder: TraceRecorder | None = None,
        checkpoint: Callable[[], None] | None = None,
    ) -> None:
        self._browser = browser
        self._escalator = escalator
        self._recorder = recorder
        self._checkpoint = checkpoint  # budget wall-clock check between steps

    def run(self, booking: Booking) -> JourneyResult:
        steps: list[tuple[JourneyStep, Callable[[Booking], str]]] = [
            (JourneyStep.OPEN_HOME, self._open_home),
            (JourneyStep.DISMISS_OVERLAYS, self._dismiss_overlays),
            (JourneyStep.FILL_SEARCH, self._fill_search),
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

                    escalation = self._escalator.complete_step(
                        step,
                        goal=self._step_goal(step, booking),
                        verify=_verify,
                        trigger=str(exc),
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
        occ = booking.occupancy
        goals = {
            JourneyStep.OPEN_HOME: "Get the Booking.com home page open with its "
            "accommodation search box visible.",
            JourneyStep.DISMISS_OVERLAYS: "Close any popup, banner, or overlay hiding "
            "the search form (cookie consent, sign-in nags, promos).",
            JourneyStep.FILL_SEARCH: (
                f"Fill the accommodation search: destination/property "
                f"{booking.property.name!r}, check-in "
                f"{booking.stay_dates.check_in.isoformat()}, check-out "
                f"{booking.stay_dates.check_out.isoformat()}"
                + (f", {occ.adults} adults, {occ.children} children, {occ.rooms} room(s)."
                   if occ else ".")
            ),
            JourneyStep.SUBMIT_SEARCH: "Submit the search so property results are shown.",
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

    def _step_verified(self, step: JourneyStep, booking: Booking) -> bool:
        """Postcondition check so agent success is verified, not assumed."""
        try:
            if step is JourneyStep.OPEN_HOME:
                return self._browser.exists(_SEL_SEARCH_BOX)
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
            if step in (JourneyStep.DISMISS_OVERLAYS, JourneyStep.READ_ROOM_TABLE):
                return not _CAPTCHA_MARKERS.search(self._safe_text())
            if step is JourneyStep.FILL_SEARCH:
                return True  # no reliable postcondition; submit_search verifies next
        except Exception:
            return False
        return False

    def _classify_failure(self, step: JourneyStep) -> FailureCode:
        page_text = self._safe_text()
        if _CAPTCHA_MARKERS.search(page_text):
            return FailureCode.BOT_WALL
        if _SIGN_IN_MARKERS.search(page_text):
            return FailureCode.AUTH_REQUIRED
        return _STEP_FAILURE_CODES.get(step, FailureCode.STEP_FAILED)

    def _safe_text(self) -> str:
        try:
            return self._browser.snapshot().text
        except Exception:
            return ""

    # ── steps ────────────────────────────────────────────────────────────────

    def _open_home(self, booking: Booking) -> str:
        self._browser.goto(_HOME_URL)
        self._browser.wait_for(_SEL_SEARCH_BOX)
        return _HOME_URL

    def _dismiss_overlays(self, booking: Booking) -> str:
        text = self._safe_text()
        if _CAPTCHA_MARKERS.search(text):
            raise RuntimeError("Bot-detection interstitial on the home page")
        dismissed = []
        for selector in (_SEL_CONSENT_ACCEPT, '[aria-label*="Dismiss"]'):
            if self._browser.exists(selector):
                try:
                    self._browser.click(selector)
                    dismissed.append(selector)
                except Exception:
                    pass  # overlays are best-effort; absence or a flaky close is fine
        return f"dismissed: {dismissed or 'none'}"

    def _fill_search(self, booking: Booking) -> str:
        occ = booking.occupancy
        assert occ is not None  # monitor guards OCCUPANCY_MISSING before the journey
        self._browser.fill(_SEL_SEARCH_BOX, booking.property.name)

        self._browser.click(_SEL_DATES_CONTAINER)
        self._browser.click(f'[data-date="{booking.stay_dates.check_in.isoformat()}"]')
        self._browser.click(f'[data-date="{booking.stay_dates.check_out.isoformat()}"]')

        self._browser.click(_SEL_OCCUPANCY_CONFIG)
        self._set_counter("group_adults", occ.adults)
        self._set_counter("group_children", occ.children)
        self._set_counter("no_rooms", occ.rooms)
        return (
            f"query={booking.property.name!r} dates={booking.stay_dates.check_in}"
            f"..{booking.stay_dates.check_out} occ={occ}"
        )

    def _set_counter(self, input_id: str, target: int) -> None:
        """Booking.com occupancy counters are +/- steppers around a numeric input."""
        texts = self._browser.query_text(f"input#{input_id}")
        current = int(texts[0]) if texts and texts[0].strip().isdigit() else None
        if current is None:
            raise RuntimeError(f"Occupancy counter '{input_id}' not readable")
        plus = f'button[aria-describedby="{input_id}_desc"]:has-text("+"), ' \
               f'input#{input_id} ~ button:last-of-type'
        minus = f'input#{input_id} ~ button:first-of-type'
        for _ in range(current, target):
            self._browser.click(plus)
        for _ in range(target, current):
            self._browser.click(minus)

    def _submit_search(self, booking: Booking) -> str:
        self._browser.click(_SEL_SUBMIT)
        self._browser.wait_for(_SEL_PROPERTY_CARD)
        return "results loaded"

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
        self._browser.click(f"{_SEL_PROPERTY_TITLE} >> nth={index}")
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
