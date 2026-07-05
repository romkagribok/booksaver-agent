from __future__ import annotations

import json
import logging
import re
from typing import Any

from booksaver.application.ports import PageContent

logger = logging.getLogger(__name__)

_SIGN_IN_MARKERS = re.compile(r"(sign in to manage|log in to your account|create an account)", re.I)

_PAGE_TIMEOUT_MS = 45_000


class PlaywrightBrowserSession:
    """BrowserSession adapter over Playwright's sync API (ADR-007/008).

    Playwright is imported lazily so the rest of the application (and its tests)
    work without the package installed; only actually opening a browser needs it.
    """

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._authenticated = False

    def _ensure_context(self) -> Any:
        if self._context is not None:
            return self._context
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._context = self._browser.new_context()
        return self._context

    def open_page(self, url: str) -> PageContent:
        context = self._ensure_context()
        page = context.new_page()
        try:
            page.goto(url, timeout=_PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=_PAGE_TIMEOUT_MS)
            html = page.content()
            text = page.inner_text("body")
            self._authenticated = not _SIGN_IN_MARKERS.search(text)
            return PageContent(url=page.url, html=html, text=text)
        finally:
            page.close()

    def get_cookies(self) -> bytes:
        context = self._ensure_context()
        return json.dumps(context.cookies()).encode("utf-8")

    def restore_cookies(self, data: bytes) -> None:
        context = self._ensure_context()
        cookies = json.loads(data.decode("utf-8"))
        context.add_cookies(cookies)

    def is_authenticated(self) -> bool:
        return self._authenticated

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> PlaywrightBrowserSession:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def interactive_login(login_url: str = "https://account.booking.com/sign-in") -> bytes:
    """Open a headed browser for manual login; return cookies once the user finishes.

    Blocks until the user closes the browser window (or 10 minutes pass).
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url)
        print("A browser window has opened. Log in to Booking.com, then close the window.")
        try:
            page.wait_for_event("close", timeout=600_000)
        except Exception:
            logger.info("Login window wait ended (timeout or navigation); capturing cookies")
        cookies = json.dumps(context.cookies()).encode("utf-8")
        browser.close()
        return cookies
