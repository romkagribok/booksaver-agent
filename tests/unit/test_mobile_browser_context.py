from typing import Any

from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.infrastructure.browser.playwright_adapter import (
    has_authenticated_account_context,
    new_mobile_context,
)

PIXEL_7 = {
    "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 7) Chrome/149 Mobile Safari/537.36",
    "viewport": {"width": 412, "height": 839},
    "device_scale_factor": 2.625,
    "is_mobile": True,
    "has_touch": True,
    "default_browser_type": "chromium",
}


class FakeBrowser:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def new_context(self, **options: Any) -> object:
        self.calls.append(options)
        return object()


class FakePage:
    def __init__(
        self,
        selectors: set[str] | None = None,
        *,
        url: str = "https://secure.booking.com/myreservations.html",
    ) -> None:
        self._selectors = selectors or set()
        self.url = url

    def locator(self, selector: str) -> Any:
        count = 1 if selector in self._selectors else 0

        class Locator:
            def count(self) -> int:
                return count

            def nth(self, _index: int) -> Any:
                return self

            def is_visible(self) -> bool:
                return True

        return Locator()


def test_each_mobile_context_is_fresh_and_uses_complete_profile() -> None:
    browser = FakeBrowser()
    settings = MobileWebSettings.from_values(
        "android-chromium", "en-US", "America/Indiana/Indianapolis"
    )

    first = new_mobile_context(browser, settings, PIXEL_7)
    second = new_mobile_context(browser, settings, PIXEL_7)

    assert first is not second
    assert len(browser.calls) == 2
    assert browser.calls[0] == browser.calls[1]
    assert browser.calls[0]["is_mobile"] is True
    assert browser.calls[0]["has_touch"] is True
    assert browser.calls[0]["timezone_id"] == "America/Indiana/Indianapolis"
    assert "storage_state" not in browser.calls[0]


def test_rendered_authentication_requires_positive_account_evidence() -> None:
    assert not has_authenticated_account_context(FakePage(), "Genius Level 2")
    assert not has_authenticated_account_context(
        FakePage({'[data-testid="header-profile"]'}), "Welcome"
    )
    assert not has_authenticated_account_context(FakePage(), "Welcome")
    assert not has_authenticated_account_context(
        FakePage({'[data-testid="header-profile"]'}),
        "Sign in or register — Genius Level 2",
    )
    assert has_authenticated_account_context(
        FakePage({'[data-testid="bookings-list"]'}),
        "Upcoming reservations",
    )


def test_protected_authentication_evidence_outranks_inventory_chrome() -> None:
    page = FakePage(
        {
            '[data-testid="bookings-list"]',
            '[data-testid="header-profile"]',
            "input[autocomplete='one-time-code']",
        }
    )

    assert not has_authenticated_account_context(
        page,
        "Enter the verification code — Genius Level 2",
    )
