from __future__ import annotations

from typing import Any

import pytest

from booksaver.domain.agent import AgentAction, AgentActionType, blocked_url_reason
from booksaver.domain.browser_resilience import DomStepId, PopupRefusalReason
from booksaver.infrastructure.browser.playwright_adapter import (
    PlaywrightInteractiveBrowser,
)


class _Popup:
    def __init__(self, url: str, text: str = "Hotel Test") -> None:
        self.url = url
        self.text = text
        self.closed = False
        self.default_timeout: int | None = None

    def close(self) -> None:
        self.closed = True

    def wait_for_load_state(self, _state: str, timeout: int) -> None:
        assert timeout > 0

    def set_default_timeout(self, timeout: int) -> None:
        self.default_timeout = timeout

    def inner_text(self, _selector: str) -> str:
        return self.text


class _Button:
    def __init__(self, on_click: Any, href: str | None = None) -> None:
        self._on_click = on_click
        self._href = href

    def is_visible(self) -> bool:
        return True

    def evaluate(self, _script: str) -> str:
        return "a" if self._href is not None else "button"

    def get_attribute(self, name: str) -> str | None:
        if name == "aria-label":
            return "Hotel Test"
        return self._href if name == "href" else None

    def inner_text(self) -> str:
        return "Hotel Test"

    def click(self) -> None:
        self._on_click()


class _Locator:
    def __init__(self, button: _Button | None) -> None:
        self._button = button

    def count(self) -> int:
        return int(self._button is not None)

    def nth(self, _index: int) -> _Button:
        assert self._button is not None
        return self._button


class _Page(_Popup):
    def __init__(
        self,
        url: str,
        *,
        scroll_y: object = 0,
        on_click: Any | None = None,
        href: str | None = None,
    ) -> None:
        super().__init__(url)
        self._scroll_y = scroll_y
        self._button = _Button(on_click, href) if on_click is not None else None

    def locator(self, _selector: str) -> _Locator:
        return _Locator(self._button)

    def title(self) -> str:
        return "Search results"

    def inner_text(self, _selector: str) -> str:
        return "Hotel Test"

    def evaluate(self, script: str) -> object:
        assert "scrollY" in script
        return self._scroll_y


class _Context:
    def __init__(self, pages: list[_Popup]) -> None:
        self.pages = pages
        self.closed = False

    def close(self) -> None:
        self.closed = True
        for page in self.pages:
            page.close()


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _Stoppable:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def _browser(page: _Page, context: _Context) -> PlaywrightInteractiveBrowser:
    browser = PlaywrightInteractiveBrowser()
    browser._page = page
    browser._context = context
    return browser


def test_click_reports_sanitized_popup_without_adopting_it() -> None:
    popup = _Popup(
        "https://www.booking.com/hotel/test.html"
        "?checkin=2026-09-01&checkout=2026-09-05&aid=secret-value"
    )
    pages: list[_Popup] = []
    page = _Page(
        "https://www.booking.com/searchresults.html?ss=Hotel+Test",
        scroll_y=480.8,
        on_click=lambda: pages.append(popup),
    )
    pages.append(page)
    context = _Context(pages)
    browser = _browser(page, context)

    before = browser.observe()
    browser.act(AgentAction(type=AgentActionType.CLICK, ref="e0"))
    after = browser.observe()

    assert before.popup_count == 0
    assert after.popup_count == 1
    assert after.popup_urls == (
        "https://www.booking.com/hotel/test.html",
    )
    assert after.scroll_y == 480
    assert "secret-value" not in after.describe()
    assert browser._page is page
    assert browser.snapshot().url == page.url


def test_adopts_exactly_one_new_step_relevant_property_popup() -> None:
    popup = _Popup(
        "https://www.booking.com/hotel/test.html?aid=secret-value"
    )
    pages: list[_Popup] = []
    page = _Page(
        "https://www.booking.com/searchresults.html",
        on_click=lambda: pages.append(popup),
    )
    pages.append(page)
    browser = _browser(page, _Context(pages))

    browser.observe()
    browser.act(AgentAction(type=AgentActionType.CLICK, ref="e0"))
    result = browser.adopt_read_only_popup(DomStepId.PRICE_PROPERTY_OPEN)

    assert result.is_adopted
    assert result.receipt is not None
    assert result.receipt.step_id is DomStepId.PRICE_PROPERTY_OPEN
    assert browser._page is popup
    assert popup.default_timeout is not None
    assert page.closed


def test_adopts_approved_inventory_detail_popup() -> None:
    popup = _Popup(
        "https://secure.booking.com/confirmation/CONF-PRIVATE?trip_id=secret"
    )
    pages: list[_Popup] = []
    page = _Page(
        "https://secure.booking.com/myreservations.html",
        on_click=lambda: pages.append(popup),
    )
    pages.append(page)
    browser = _browser(page, _Context(pages))

    browser.observe()
    browser.act(AgentAction(type=AgentActionType.CLICK, ref="e0"))
    result = browser.adopt_read_only_popup(DomStepId.INVENTORY_DETAIL)

    assert result.is_adopted
    assert browser._page is popup


@pytest.mark.parametrize(
    ("popup", "step_id", "reason"),
    [
        (
            _Popup("https://evil.example/phish"),
            DomStepId.PRICE_PROPERTY_OPEN,
            PopupRefusalReason.EXTERNAL_ORIGIN,
        ),
        (
            _Popup("https://secure.booking.com/checkout"),
            DomStepId.PRICE_PROPERTY_OPEN,
            PopupRefusalReason.MUTATING_DESTINATION,
        ),
        (
            _Popup("https://www.booking.com/searchresults.html"),
            DomStepId.PRICE_PROPERTY_OPEN,
            PopupRefusalReason.UNSUPPORTED_ROUTE,
        ),
        (
            _Popup(
                "https://www.booking.com/hotel/test.html",
                text="Sign in to manage your booking",
            ),
            DomStepId.PRICE_PROPERTY_OPEN,
            PopupRefusalReason.PROTECTED_DESTINATION,
        ),
    ],
)
def test_popup_adoption_refuses_unsafe_or_irrelevant_destination(
    popup: _Popup,
    step_id: DomStepId,
    reason: PopupRefusalReason,
) -> None:
    pages: list[_Popup] = []
    page = _Page(
        "https://www.booking.com/searchresults.html",
        on_click=lambda: pages.append(popup),
    )
    pages.append(page)
    browser = _browser(page, _Context(pages))

    browser.observe()
    browser.act(AgentAction(type=AgentActionType.CLICK, ref="e0"))
    result = browser.adopt_read_only_popup(step_id)

    assert result.refusal_reason is reason
    assert popup.closed
    assert browser._page is page


def test_popup_adoption_refuses_multiple_new_children() -> None:
    popups = [
        _Popup("https://www.booking.com/hotel/one.html"),
        _Popup("https://www.booking.com/hotel/two.html"),
    ]
    pages: list[_Popup] = []
    page = _Page(
        "https://www.booking.com/searchresults.html",
        on_click=lambda: pages.extend(popups),
    )
    pages.append(page)
    browser = _browser(page, _Context(pages))

    browser.observe()
    browser.act(AgentAction(type=AgentActionType.CLICK, ref="e0"))
    result = browser.adopt_read_only_popup(DomStepId.PRICE_PROPERTY_OPEN)

    assert result.refusal_reason is PopupRefusalReason.MULTIPLE_OPENED
    assert all(popup.closed for popup in popups)
    assert browser._page is page


def test_every_popup_destination_remains_inspectable_and_value_free() -> None:
    page = _Page("https://www.booking.com/searchresults.html")
    popups = [
        _Popup("https://evil.example/phish?token=very-secret"),
        _Popup("https://secure.booking.com/book.html?stage=1&session=hidden"),
        _Popup(
            "https://secure.booking.com/confirmation/"
            "CONF-12345?reservation=CONF-SECRET&scope=past"
        ),
    ]
    browser = _browser(page, _Context([page, *popups]))

    observation = browser.observe()

    assert observation.popup_count == 3
    assert observation.popup_urls == (
        "https://evil.example/phish",
        "https://secure.booking.com/book.html",
        "https://secure.booking.com/confirmation/{id}",
    )
    assert "very-secret" not in observation.describe()
    assert "CONF-SECRET" not in observation.describe()
    assert blocked_url_reason(observation.popup_urls[1]) is not None
    assert "evil.example" in observation.popup_urls[0]


def test_controllable_url_and_link_href_are_safe_for_model_observation() -> None:
    page = _Page(
        "https://account:password@www.booking.com/hotel/test.html"
        "?aid=private&confirmation=CONF-PRIVATE#payment",
        on_click=lambda: None,
        href=(
            "https://user:secret@secure.booking.com/confirmation/"
            "CONFIDENTIALSESSION123456?reservation=PRIVATE#details"
        ),
    )
    browser = _browser(page, _Context([page]))

    observation = browser.observe()

    assert observation.url == "https://www.booking.com/hotel/test.html"
    assert observation.elements[0].href == (
        "https://secure.booking.com/confirmation/{id}"
    )
    rendered = observation.describe()
    for secret in (
        "password",
        "CONF-PRIVATE",
        "CONFIDENTIALSESSION123456",
        "reservation=PRIVATE",
        "#details",
    ):
        assert secret not in rendered


def test_popup_metadata_overflow_is_explicit_and_bounded() -> None:
    page = _Page("https://www.booking.com/searchresults.html")
    popups = [_Popup(f"https://popup-{index}.example/path") for index in range(20)]
    browser = _browser(page, _Context([page, *popups]))

    observation = browser.observe()

    assert observation.popup_count == 20
    assert len(observation.popup_urls) == 16
    assert observation.popup_urls[-1] == "unavailable:popup-metadata-overflow"


def test_overlong_popup_destination_fails_closed_instead_of_truncating() -> None:
    page = _Page("https://www.booking.com/searchresults.html")
    popup = _Popup(f"https://www.booking.com/{'x/' * 300}book.html")
    browser = _browser(page, _Context([page, popup]))

    assert browser.observe().popup_urls == ("unavailable:popup-url-too-long",)


def test_observation_tolerates_unreadable_scroll_position() -> None:
    page = _Page("https://www.booking.com/searchresults.html", scroll_y="not-a-number")
    browser = _browser(page, _Context([page]))

    assert browser.observe().scroll_y == 0


def test_action_boundary_rechecks_destination_after_observation() -> None:
    clicked = {"value": False}
    page = _Page(
        "https://www.booking.com/searchresults.html",
        on_click=lambda: clicked.update(value=True),
    )
    browser = _browser(page, _Context([page]))
    browser.observe()

    # Simulate an asynchronous redirect while the provider is deciding.
    page.url = "https://secure.booking.com/checkout?session=private"
    try:
        browser.act(AgentAction(type=AgentActionType.CLICK, ref="e0"))
    except RuntimeError as exc:
        assert "reservation-mutating destination" in str(exc)
    else:
        raise AssertionError("expected action from checkout state to be refused")

    assert not clicked["value"]


def test_close_tears_down_controllable_page_and_every_popup() -> None:
    page = _Page("https://www.booking.com/searchresults.html")
    popup = _Popup("https://www.booking.com/hotel/test.html")
    context = _Context([page, popup])
    chromium = _Closable()
    playwright = _Stoppable()
    browser = _browser(page, context)
    browser._browser = chromium
    browser._playwright = playwright

    browser.close()

    assert page.closed
    assert popup.closed
    assert context.closed
    assert chromium.closed
    assert playwright.stopped
    assert browser._page is None
    assert browser._context is None
    assert browser._browser is None
    assert browser._playwright is None
