from __future__ import annotations

import pytest

from booksaver.domain.browser_guard import (
    BrowserActionGuard,
    BrowserActionProposal,
    BrowserActionType,
    CoordinateHitTest,
    DestinationSnapshot,
    ExecutorEgressKind,
    GuardRejection,
    classify_executor_egress,
    is_booking_destination,
)


def _page(url: str = "https://www.booking.com/hotel/example.html") -> DestinationSnapshot:
    return DestinationSnapshot(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.booking.com/hotel/example.html",
        "https://booking.com:444/hotel/example.html",
        "https://booking.com@example.org/hotel/example.html",
        "https://booking.com.example.org/hotel/example.html",
        "javascript:alert(1)",
        "data:text/html,unsafe",
    ],
)
def test_destination_allowlist_rejects_lookalikes_and_non_https(url: str) -> None:
    assert not is_booking_destination(url)


def test_destination_allowlist_accepts_apex_and_subdomains() -> None:
    assert is_booking_destination("https://booking.com/searchresults.html")
    assert is_booking_destination("https://www.booking.com/hotel/example.html")


@pytest.mark.parametrize(
    ("label", "destination", "rejection"),
    [
        ("Reserve now", None, GuardRejection.UNSAFE_LABEL),
        ("Cancel reservation", None, GuardRejection.UNSAFE_LABEL),
        ("Accept all cookies", None, GuardRejection.UNSAFE_LABEL),
        (
            "Open account",
            "https://secure.booking.com/myaccount.html",
            GuardRejection.UNSAFE_PATH,
        ),
        ("Open details", "https://evil.example/hotel", GuardRejection.INVALID_DESTINATION),
        (
            "Open details",
            "https://www.booking.com/checkout/start",
            GuardRejection.UNSAFE_PATH,
        ),
    ],
)
def test_semantic_click_guard_fails_closed(
    label: str, destination: str | None, rejection: GuardRejection
) -> None:
    decision = BrowserActionGuard().evaluate(
        BrowserActionProposal(
            BrowserActionType.CLICK,
            _page(),
            label=label,
            role="link",
            destination=destination,
        )
    )
    assert not decision.allowed
    assert decision.rejection is rejection


def test_coordinate_click_requires_visible_enabled_hit_test() -> None:
    hit = CoordinateHitTest(
        20,
        30,
        1280,
        800,
        label="See availability",
        role="button",
        visible=True,
        enabled=True,
    )
    decision = BrowserActionGuard().evaluate(
        BrowserActionProposal(
            BrowserActionType.CLICK,
            _page(),
            x=20,
            y=30,
            hit_test=hit,
        )
    )
    assert decision.allowed

    disabled = BrowserActionGuard().evaluate(
        BrowserActionProposal(
            BrowserActionType.CLICK,
            _page(),
            x=20,
            y=30,
            hit_test=CoordinateHitTest(20, 30, 1280, 800, enabled=False),
        )
    )
    assert disabled.rejection is GuardRejection.TARGET_NOT_ACTIONABLE


@pytest.mark.parametrize(
    "proposal",
    [
        BrowserActionProposal(BrowserActionType.SCROLL, _page(), delta_x=1, delta_y=400),
        BrowserActionProposal(BrowserActionType.SCROLL, _page(), delta_y=1_201),
        BrowserActionProposal(BrowserActionType.TYPE, _page(), role="textbox", value="password"),
        BrowserActionProposal(BrowserActionType.KEY, _page(), value="Control+L"),
        BrowserActionProposal(BrowserActionType.WAIT, _page(), wait_ms=5_001),
        BrowserActionProposal(
            BrowserActionType.ZOOM,
            _page(),
            zoom_region=(0, 0, 2_000, 2_000),
            viewport_width=1280,
            viewport_height=800,
        ),
    ],
)
def test_unsafe_visual_actions_are_rejected(proposal: BrowserActionProposal) -> None:
    assert not BrowserActionGuard().evaluate(proposal).allowed


def test_post_action_popup_or_destination_change_is_rejected() -> None:
    guard = BrowserActionGuard()
    assert guard.validate_destination(_page(), DestinationSnapshot(_page().url, 1)).rejection is (
        GuardRejection.UNEXPECTED_POPUP
    )
    assert guard.validate_destination(
        _page(), DestinationSnapshot("https://accounts.example/signin")
    ).rejection is GuardRejection.INVALID_DESTINATION


def test_zoom_accepts_only_a_bounded_screen_region() -> None:
    decision = BrowserActionGuard().evaluate(
        BrowserActionProposal(
            BrowserActionType.ZOOM,
            _page(),
            zoom_region=(100, 100, 500, 400),
            viewport_width=1280,
            viewport_height=800,
        )
    )
    assert decision.allowed


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("https://www.booking.com/searchresults.html", ExecutorEgressKind.BOOKING),
        ("https://api.anthropic.com/v1/messages", ExecutorEgressKind.ANTHROPIC),
        ("http://127.0.0.1:4318/v1/traces", ExecutorEgressKind.LOOPBACK),
        ("ws://localhost:9222/devtools/browser/example", ExecutorEgressKind.LOOPBACK),
    ],
)
def test_authenticated_executor_egress_allowlist(url: str, kind: ExecutorEgressKind) -> None:
    assert classify_executor_egress(url) is kind


@pytest.mark.parametrize(
    "url",
    [
        "https://browserbase.com/session",
        "https://api.openai.com/v1/responses",
        "https://telemetry.stagehand.dev/v1/traces",
        "https://api.anthropic.com.evil.example/v1/messages",
        "http://api.anthropic.com/v1/messages",
        "https://localhost.evil.example/",
    ],
)
def test_authenticated_executor_egress_rejects_every_other_destination(url: str) -> None:
    assert classify_executor_egress(url) is None
