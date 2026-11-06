"""Code-owned Booking.com cookie bootstrap for one transient local browser."""

from __future__ import annotations

import json
from typing import Any, cast


class CodeOwnedSessionBootstrap:
    """Holds opaque cookie bytes only until a code-owned Playwright CDP injection."""

    def __init__(self) -> None:
        self._material: bytes | None = None

    def restore_session(self, data: bytes) -> None:
        if self._material is not None:
            raise ValueError("session bootstrap is single use")
        self._material = bytes(data)

    async def apply(self, cdp_url: str) -> None:
        material = self._material
        self._material = None
        if material is None:
            raise ValueError("session lease was not restored")
        try:
            cookies = self._decode_cookies(material)
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()
            browser: Any | None = None
            try:
                browser = await playwright.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                if len(contexts) != 1:
                    raise RuntimeError("transient browser must contain exactly one context")
                await contexts[0].add_cookies(cast(Any, cookies))
            finally:
                # Stopping Playwright disconnects its CDP client without terminating Chromium.
                await playwright.stop()
                del browser
        finally:
            material = b""

    @staticmethod
    def _decode_cookies(material: bytes) -> list[dict[str, Any]]:
        try:
            raw = json.loads(material.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("session material is not a cookie list") from exc
        if not isinstance(raw, list) or not raw:
            raise ValueError("session material must contain cookies")
        cookies: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("session cookie must be an object")
            domain = item.get("domain")
            if not isinstance(domain, str):
                raise ValueError("session cookie domain is required")
            normalized = domain.lstrip(".").casefold()
            if normalized != "booking.com" and not normalized.endswith(".booking.com"):
                raise ValueError("session cookie is outside Booking.com")
            cookies.append(dict(item))
        return cookies

