from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import date
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

_HOME_URL = "https://www.booking.com"
_SEARCH_RESULTS_URL = "https://www.booking.com/searchresults.html"

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
_SEL_AUTOCOMPLETE_HOTEL = (
    '[data-testid="autocomplete-result"]:has([data-testid="autocomplete-icon-hotel"])'
)
_SEL_AUTOCOMPLETE_ANY = '[data-testid="autocomplete-result"]'
# Scope to the searchbox datepicker — bare aria-label*="Next" matches homepage
# carousels and pages the wrong UI for 24 turns without ever moving the calendar.
_SEL_DATEPICKER = '[data-testid="searchbox-datepicker-calendar"]'
# Prefer datepicker-scoped arrows; fall back to exact month labels only (never
# aria-label*="Next" — that matches homepage carousels).
_SEL_CALENDAR_PREV = (
    f'{_SEL_DATEPICKER} button[aria-label="Previous month"], '
    f'{_SEL_DATEPICKER} button[aria-label="Scroll backward"], '
    'button[aria-label="Previous month"]'
)
_SEL_CALENDAR_NEXT = (
    f'{_SEL_DATEPICKER} button[aria-label="Next month"], '
    f'{_SEL_DATEPICKER} button[aria-label="Scroll forward"], '
    'button[aria-label="Next month"]'
)
_MAX_CALENDAR_NAV = 24

_MONTH_NAME_TO_NUM = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}
_CALENDAR_MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{4})\b"
)

_STEP_FAILURE_CODES = {
    JourneyStep.OPEN_HOME: FailureCode.NAVIGATION_ERROR,
    JourneyStep.LOCATE_PROPERTY: FailureCode.PROPERTY_NOT_FOUND,
}


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _month_index(d: date) -> int:
    return d.year * 12 + (d.month - 1)


def _parse_calendar_months(page_text: str) -> list[int]:
    """Month indices from calendar headers in page text (year*12 + month-1).

    Prefer `_months_from_data_dates` when day cells are present — full-page text
    can mention other months and send navigation the wrong way.
    """
    found: list[int] = []
    for match in _CALENDAR_MONTH_RE.finditer(page_text):
        month = _MONTH_NAME_TO_NUM[match.group(1)]
        year = int(match.group(2))
        found.append(_month_index(date(year, month, 1)))
    return found


def _months_from_data_dates(iso_dates: list[str]) -> list[int]:
    """Unique month indices derived from visible `[data-date]` day cells."""
    found: list[int] = []
    seen: set[int] = set()
    for raw in iso_dates:
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            continue
        idx = _month_index(d)
        if idx not in seen:
            seen.add(idx)
            found.append(idx)
    return found


def _calendar_nav_direction(target: date, visible_month_indices: list[int]) -> str:
    """Which calendar arrow brings the target month into view."""
    if not visible_month_indices:
        return "prev"  # Booking defaults near "today"+; targets are usually earlier
    target_idx = _month_index(target)
    if target_idx < min(visible_month_indices):
        return "prev"
    if target_idx > max(visible_month_indices):
        return "next"
    # Target month is already showing but the day cell is missing — do not thrash.
    raise RuntimeError(
        f"Calendar shows months covering {target.isoformat()} but that day cell "
        f"is missing (visible month indices={visible_month_indices})"
    )


def _date_label_present(text: str, d: date) -> bool:
    """Best-effort check that a stay date appears in the search form text."""
    if d.isoformat() in text:
        return True
    month_abbr = d.strftime("%b")
    month_full = d.strftime("%B")
    return bool(
        re.search(rf"\b{month_abbr}\s+0?{d.day}\b", text)
        or re.search(rf"\b{month_full}\s+0?{d.day}\b", text)
    )


def _dates_visible_in_form(text: str, check_in: date, check_out: date) -> bool:
    return _date_label_present(text, check_in) and _date_label_present(text, check_out)


def _property_already_in_form(
    text: str, search_box_values: list[str], booking: Booking
) -> bool:
    """True when the destination field already shows the target property.

    Only trust the search-box value (or an explicit 'N results found' autocomplete
    state). Never scan the full page body — Booking's homepage often mentions the
    same hotel in recommendation carousels, which falsely skipped fill_search.
    """
    wanted = _normalise(booking.property.name)
    if not wanted:
        return False
    if search_box_values:
        box = _normalise(search_box_values[0])
        if wanted in box or (box and box in wanted):
            return True
    # Autocomplete confirmation line next to the typed destination.
    if re.search(r"\d+\s+results?\s+found", text, re.I):
        # Prefer the first ~500 chars (search form region) over the whole page.
        head = _normalise(text[:800])
        return wanted in head
    return False


def _search_results_url(
    booking: Booking, *, dest_id: str | None = None, dest_type: str | None = None
) -> str:
    """searchresults URL with stay dates + occupancy (homepage Search drops dates).

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
        session_mode: SessionMode = SessionMode.AUTHENTICATED,
    ) -> None:
        self._browser = browser
        self._escalator = escalator
        self._recorder = recorder
        self._checkpoint = checkpoint  # budget wall-clock check between steps
        self._session_mode = session_mode

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

                    trigger = self._escalation_trigger(step, booking, exc)

                    escalation = self._escalator.complete_step(
                        step,
                        goal=self._step_goal(step, booking),
                        verify=_verify,
                        trigger=trigger,
                        screenshot_first=step
                        in (JourneyStep.FILL_SEARCH, JourneyStep.SUBMIT_SEARCH),
                    )
                    if escalation.ok:
                        agent_assisted = True
                        outcome = StepOutcome.success(step, escalation.detail)
                        self._record(outcome)
                        outcomes.append(outcome)
                        continue
                    if self._can_use_exact_search_fallback(step, escalation.failure_code):
                        # The agent received screenshots and had a chance to repair the
                        # homepage form. If Booking changes the calendar/occupancy UI so
                        # thoroughly that it still loops, the next scripted step remains
                        # a safe, read-only escape hatch: it opens a search-results URL
                        # built from the booking's exact dates and occupancy. This is not
                        # a checkout/reservation URL and the normal property/context
                        # verification steps still run afterward.
                        agent_assisted = True
                        detail = (
                            f"agent recovery did not complete the form ({escalation.detail}); "
                            "continuing via exact search-results URL"
                        )
                        logger.warning("Journey %s fallback: %s", step.value, detail)
                        outcome = StepOutcome.success(step, detail)
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

    @staticmethod
    def _can_use_exact_search_fallback(
        step: JourneyStep, failure_code: FailureCode | None
    ) -> bool:
        """Whether a failed agent attempt can safely defer form state to submit.

        Only ``fill_search`` has an equivalent deterministic continuation: the
        following step builds a read-only Booking.com search URL from trusted
        booking data. Guard violations remain terminal and every later journey
        postcondition still has to pass.
        """
        return step is JourneyStep.FILL_SEARCH and failure_code in {
            FailureCode.AGENT_GAVE_UP,
            FailureCode.BUDGET_EXCEEDED,
        }

    def _record(self, outcome: StepOutcome) -> None:
        if self._recorder is not None:
            self._recorder.journey_step(outcome)

    # ── escalation support (US-020) ──────────────────────────────────────────

    def _step_goal(self, step: JourneyStep, booking: Booking) -> str:
        if step is JourneyStep.FILL_SEARCH:
            return self._fill_search_goal(booking)
        goals = {
            JourneyStep.OPEN_HOME: "Get the Booking.com home page open with its "
            "accommodation search box visible.",
            JourneyStep.DISMISS_OVERLAYS: "Close any popup, banner, or overlay hiding "
            "the search form (cookie consent, sign-in nags, promos).",
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

    def _fill_search_goal(self, booking: Booking) -> str:
        text = self._safe_text()
        box_values = self._search_box_values()
        check_in = booking.stay_dates.check_in.isoformat()
        check_out = booking.stay_dates.check_out.isoformat()
        occ = booking.occupancy
        occ_suffix = ""
        if occ:
            occ_suffix = (
                f", then set occupancy to {occ.adults} adults, "
                f"{occ.children} children, {occ.rooms} room(s)"
            )
        if _property_already_in_form(text, box_values, booking):
            return (
                "The destination/property is ALREADY set — do NOT re-type or refill "
                "the search box. ONLY fix the dates: click the date display or "
                "calendar icon to open the picker, use previous/next month arrows "
                f"until the right month is visible, select check-in {check_in} then "
                f"check-out {check_out}, close the calendar (Escape or click outside)"
                f"{occ_suffix}. Both dates must appear in the search form before stopping."
            )
        occ_clause = ""
        if occ:
            occ_clause = (
                f", {occ.adults} adults, {occ.children} children, {occ.rooms} room(s)."
            )
        return (
            f"Fill the accommodation search: destination/property "
            f"{booking.property.name!r}, check-in {check_in}, check-out {check_out}"
            f"{occ_clause}"
        )

    def _escalation_trigger(
        self, step: JourneyStep, booking: Booking, exc: Exception
    ) -> str:
        trigger = str(exc)
        if step is not JourneyStep.FILL_SEARCH:
            return trigger
        text = self._safe_text()
        if not _property_already_in_form(text, self._search_box_values(), booking):
            return trigger
        return (
            f"{trigger}; property already set in search form — only fix dates "
            f"({booking.stay_dates.check_in.isoformat()} to "
            f"{booking.stay_dates.check_out.isoformat()}), do not refill destination"
        )

    def _search_box_values(self) -> list[str]:
        try:
            return self._browser.query_text(_SEL_SEARCH_BOX)
        except Exception:
            return []

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
                return _dates_visible_in_form(
                    self._safe_text(),
                    booking.stay_dates.check_in,
                    booking.stay_dates.check_out,
                )
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
        # Always (re)type + pick hotel autocomplete. A session-prefilled name alone
        # is not enough — skipping autocomplete made submit land on city pages.
        self._browser.fill(_SEL_SEARCH_BOX, booking.property.name)
        try:
            self._browser.wait_for(_SEL_AUTOCOMPLETE_ANY, timeout_ms=3000)
        except Exception:
            pass
        self._pick_destination_suggestion()

        self._browser.click(_SEL_DATES_CONTAINER)
        self._wait_for_date_picker()
        self._select_calendar_date(booking.stay_dates.check_in)
        self._select_calendar_date(booking.stay_dates.check_out)
        self._close_date_picker()

        self._browser.click(_SEL_OCCUPANCY_CONFIG)
        self._set_counter("group_adults", occ.adults)
        self._set_counter("group_children", occ.children)
        self._set_counter("no_rooms", occ.rooms)
        return (
            f"query={booking.property.name!r} dates={booking.stay_dates.check_in}"
            f"..{booking.stay_dates.check_out} occ={occ}"
        )

    def _pick_destination_suggestion(self) -> None:
        """Click the hotel autocomplete row when Booking offers one (best-effort)."""
        for selector in (_SEL_AUTOCOMPLETE_HOTEL, _SEL_AUTOCOMPLETE_ANY):
            if not self._browser.exists(selector):
                continue
            try:
                self._browser.click(selector)
                return
            except Exception:
                continue

    def _wait_for_date_picker(self) -> None:
        """Give the calendar overlay time to render after opening the date field."""
        try:
            self._browser.wait_for('[data-date]', timeout_ms=5000)
        except Exception:
            pass

    def _select_calendar_date(self, target: date) -> None:
        """Click a calendar day, paging prev/next until the target month is visible."""
        selector = f'[data-date="{target.isoformat()}"]'
        for _ in range(_MAX_CALENDAR_NAV):
            if self._browser.exists(selector):
                self._browser.click_first_visible(selector)
                return
            visible = self._visible_calendar_months()
            direction = _calendar_nav_direction(target, visible)
            self._click_calendar_nav(direction)
        raise RuntimeError(
            f"Calendar date {target.isoformat()} not found after {_MAX_CALENDAR_NAV} page turns"
        )

    def _visible_calendar_months(self) -> list[int]:
        """Months currently shown in the datepicker, from day-cell data-dates."""
        try:
            iso_dates = self._browser.query_attr("[data-date]", "data-date")
        except Exception:
            iso_dates = []
        months = _months_from_data_dates(iso_dates)
        if months:
            return months
        return _parse_calendar_months(self._safe_text())

    def _click_calendar_nav(self, direction: str) -> None:
        nav_selector = _SEL_CALENDAR_PREV if direction == "prev" else _SEL_CALENDAR_NEXT
        if not self._browser.exists(nav_selector):
            # Picker may have closed; reopen once and retry.
            try:
                self._browser.click(_SEL_DATES_CONTAINER)
                self._wait_for_date_picker()
            except Exception:
                pass
        if not self._browser.exists(nav_selector):
            raise RuntimeError(
                f"Calendar navigation control not found while paging {direction}"
            )
        self._browser.click_first_visible(nav_selector)

    def _close_date_picker(self) -> None:
        """Dismiss an open calendar overlay so Search can submit."""
        try:
            self._browser.press(_SEL_DATES_CONTAINER, "Escape")
        except Exception:
            pass

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
        self._close_date_picker()
        # Homepage Search often omits check-in/out from the request (SPA quirk under
        # automation). Load searchresults with the dates/occupancy we just set —
        # still the search journey (results list → property), not a direct hotel URL.
        url = _search_results_url(booking)
        self._browser.goto(url)
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
