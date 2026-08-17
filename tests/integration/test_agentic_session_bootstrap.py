from __future__ import annotations

import asyncio
import json

from booksaver.infrastructure.browser.agentic_executor import LocalStagehandRuntime


def test_cookie_injection_readback_and_transient_browser_destruction() -> None:
    async def exercise() -> None:
        from playwright.async_api import async_playwright

        runtime = LocalStagehandRuntime()
        runtime.restore_session(
            json.dumps(
                [
                    {
                        "name": "booksaver_test_session",
                        "value": "ephemeral-secret",
                        "domain": ".booking.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "Lax",
                    }
                ]
            ).encode()
        )
        try:
            await runtime.launch()
            cdp_url = runtime._cdp_url  # noqa: SLF001 - integration custody assertion
            assert cdp_url is not None and cdp_url.startswith("http://127.0.0.1:")
            await runtime.apply_session()
            await runtime.attach("dummy-not-sent")
            assert runtime._telemetry is not None  # noqa: SLF001 - egress assertion
            assert runtime._telemetry.endpoint.startswith(  # noqa: SLF001
                "http://127.0.0.1:"
            )

            playwright = await async_playwright().start()
            try:
                browser = await playwright.chromium.connect_over_cdp(cdp_url)
                cookies = await browser.contexts[0].cookies("https://www.booking.com/")
                assert [cookie["value"] for cookie in cookies] == ["ephemeral-secret"]
            finally:
                await playwright.stop()
        finally:
            await runtime.close()
        assert runtime._browser is None  # noqa: SLF001 - cleanup postcondition
        assert runtime._page is None  # noqa: SLF001 - cleanup postcondition

    asyncio.run(exercise())
