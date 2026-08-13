from __future__ import annotations

from typing import Any

from booksaver.domain.browser_resilience import PageState
from booksaver.infrastructure.browser.page_state import (
    assess_page_state,
    assessment_proves_authenticated,
)


class _Locator:
    def __init__(self, visible: bool) -> None:
        self._visible = visible

    def count(self) -> int:
        return int(self._visible)

    def nth(self, _index: int) -> _Locator:
        return self

    def is_visible(self) -> bool:
        return self._visible


class _Page:
    def __init__(
        self,
        *,
        url: str = "https://secure.booking.com/myreservations.html",
        selectors: set[str] | None = None,
    ) -> None:
        self.url = url
        self._selectors = selectors or set()

    def locator(self, selector: str) -> Any:
        return _Locator(selector in self._selectors)


def test_login_controls_outrank_weak_account_and_inventory_chrome() -> None:
    page = _Page(
        selectors={
            '[data-testid="header-profile"]',
            '[data-testid="bookings-list"]',
            "input[type='password']",
        }
    )

    assessment = assess_page_state(page, "Sign in to manage — Genius Level 2")

    assert assessment.state is PageState.AUTHENTICATION_REQUIRED
    assert not assessment_proves_authenticated(assessment)


def test_mfa_and_captcha_outrank_supported_inventory() -> None:
    supported = {'[data-testid="bookings-list"]'}

    mfa = assess_page_state(
        _Page(selectors=supported | {"input[autocomplete='one-time-code']"}),
        "Enter the verification code",
    )
    captcha = assess_page_state(
        _Page(selectors=supported | {"iframe[src*='captcha']"}),
        "Verify you are human",
    )

    assert mfa.state is PageState.MFA_REQUIRED
    assert captcha.state is PageState.CAPTCHA
    assert not assessment_proves_authenticated(mfa)
    assert not assessment_proves_authenticated(captcha)


def test_weak_account_chrome_alone_is_ambiguous_not_authenticated() -> None:
    assessment = assess_page_state(
        _Page(selectors={'a[href*="myreservations"]'}),
        "Genius Level 2",
    )

    assert assessment.state is PageState.AMBIGUOUS
    assert not assessment_proves_authenticated(assessment)


def test_strong_supported_inventory_is_code_verified() -> None:
    assessment = assess_page_state(
        _Page(selectors={'[data-testid="reservation-card"]'}),
        "Upcoming reservations",
    )

    assert assessment.state is PageState.INVENTORY
    assert assessment_proves_authenticated(assessment)


def test_external_or_mutating_destination_precedes_page_chrome() -> None:
    external = assess_page_state(
        _Page(
            url="https://booking.com.attacker.example/login",
            selectors={'[data-testid="bookings-list"]'},
        ),
        "Upcoming reservations",
    )
    mutating = assess_page_state(
        _Page(
            url="https://secure.booking.com/checkout",
            selectors={'[data-testid="bookings-list"]'},
        ),
        "Upcoming reservations",
    )

    assert external.state is PageState.EXTERNAL
    assert mutating.state is PageState.PROHIBITED


def test_property_newsletter_email_field_does_not_imply_login() -> None:
    assessment = assess_page_state(
        _Page(
            url="https://www.booking.com/hotel/us/example.html",
            selectors={"input[type='email']"},
        ),
        "Get travel deals in your inbox",
    )

    assert assessment.state is PageState.AMBIGUOUS


def test_email_field_on_account_sign_in_destination_is_credential_evidence() -> None:
    assessment = assess_page_state(
        _Page(
            url="https://account.booking.com/sign-in",
            selectors={"input[type='email']"},
        ),
        "Continue",
    )

    assert assessment.state is PageState.AUTHENTICATION_REQUIRED
