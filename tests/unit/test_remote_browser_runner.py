from __future__ import annotations

from typing import Any

from booksaver.infrastructure.remote_auth.browser_runner import SystemRemoteBrowserRunner


class FakeFrame:
    def __init__(self, parent: object | None) -> None:
        self.parent_frame = parent


class FakeRequest:
    def __init__(
        self,
        url: str,
        *,
        navigation: bool = True,
        parent: object | None = None,
    ) -> None:
        self.url = url
        self._navigation = navigation
        self.frame = FakeFrame(parent)
        self.resource_type = "document" if navigation else "script"

    def is_navigation_request(self) -> bool:
        return self._navigation


class FakeRoute:
    def __init__(self, request: FakeRequest) -> None:
        self.request = request
        self.outcome: str | None = None

    def abort(self, error: str) -> None:
        self.outcome = f"abort:{error}"

    def continue_(self) -> None:
        self.outcome = "continue"


class FakeContext:
    def __init__(self) -> None:
        self.route_handler: Any = None
        self.page_handler: Any = None

    def route(self, pattern: str, handler: Any) -> None:
        assert pattern == "**/*"
        self.route_handler = handler

    def on(self, event: str, handler: Any) -> None:
        assert event == "page"
        self.page_handler = handler


def _route(context: FakeContext, request: FakeRequest) -> str | None:
    route = FakeRoute(request)
    context.route_handler(route)
    return route.outcome


def test_remote_browser_allows_booking_and_identity_provider_navigation_only() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001

    assert _route(context, FakeRequest("https://account.booking.com/sign-in")) == "continue"
    assert _route(context, FakeRequest("https://www.booking.com/index.html")) == "continue"
    assert (
        _route(context, FakeRequest("https://accounts.google.com/o/oauth2/v2/auth"))
        == "continue"
    )
    assert _route(context, FakeRequest("https://appleid.apple.com/auth/authorize")) == "continue"
    assert _route(context, FakeRequest("https://booking.com.attacker.example/phish")) == (
        "abort:blockedbyclient"
    )
    assert _route(context, FakeRequest("https://evilbooking.com/phish")) == (
        "abort:blockedbyclient"
    )


def test_remote_browser_allows_cross_origin_subresources_but_blocks_top_level_escape() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001

    assert _route(
        context,
        FakeRequest("https://cdn.example.test/script.js", navigation=False),
    ) == "continue"
    assert _route(
        context,
        FakeRequest("https://attacker.example/frame", parent=object()),
    ) == "continue"
    assert _route(context, FakeRequest("https://attacker.example/top")) == (
        "abort:blockedbyclient"
    )


def test_remote_browser_cancels_downloads_on_every_page() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001
    handlers: dict[str, Any] = {}

    class Page:
        def on(self, event: str, handler: Any) -> None:
            handlers[event] = handler

    cancelled: list[bool] = []

    class Download:
        def cancel(self) -> None:
            cancelled.append(True)

    context.page_handler(Page())
    handlers["download"](Download())
    assert cancelled == [True]
