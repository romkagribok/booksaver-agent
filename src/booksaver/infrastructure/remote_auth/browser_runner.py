from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from booksaver.application.remote_auth import RemoteBrowserResult, RemoteBrowserWork
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.remote_auth import RemoteAuthFailure, RemoteAuthSettings, RemoteAuthStatus
from booksaver.infrastructure.browser.playwright_adapter import (
    has_authenticated_account_context,
    new_mobile_context,
)

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://account.booking.com/sign-in"
_ALLOWED_TOP_LEVEL_HOSTS = (
    "booking.com",
    "accounts.google.com",
    "appleid.apple.com",
)


def _allowed_top_level(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(
        host == allowed or host.endswith(f".{allowed}")
        for allowed in _ALLOWED_TOP_LEVEL_HOSTS
    )


class SystemRemoteBrowserRunner:
    """One transient headed Chromium + Xvfb/x11vnc/websockify stack.

    Child output is discarded so capability-bearing URLs and browser content
    cannot enter daemon logs. Cleanup is idempotent and runs for every result.
    """

    def __init__(
        self,
        settings: RemoteAuthSettings,
        mobile_settings: MobileWebSettings,
    ) -> None:
        self._settings = settings
        self._mobile_settings = mobile_settings

    def run(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: Any,
        on_ready: Callable[[], None],
    ) -> RemoteBrowserResult:
        processes: list[subprocess.Popen[bytes]] = []
        playwright: Any = None
        browser: Any = None
        context: Any = None
        try:
            self._require_tools()
            with tempfile.TemporaryDirectory(prefix="booksaver-auth-") as temp_raw:
                temp_dir = Path(temp_raw)
                temp_dir.chmod(0o700)
                token_file = temp_dir / "websockify.tokens"
                token_file.write_text(
                    f"{work.websocket_token}: 127.0.0.1:5900\n", encoding="utf-8"
                )
                token_file.chmod(0o600)

                processes.append(
                    self._spawn(
                        [
                            "Xvfb",
                            self._settings.display,
                            "-screen",
                            "0",
                            "480x960x24",
                            "-nolisten",
                            "tcp",
                            "-noreset",
                        ]
                    )
                )
                self._wait_started(processes[-1])
                processes.append(
                    self._spawn(
                        [
                            "x11vnc",
                            "-display",
                            self._settings.display,
                            "-rfbport",
                            "5900",
                            "-localhost",
                            "-nopw",
                            "-forever",
                            "-shared",
                            "-noxdamage",
                            "-quiet",
                        ]
                    )
                )
                self._wait_started(processes[-1])
                processes.append(
                    self._spawn(
                        [
                            "websockify",
                            "--token-plugin",
                            "TokenFile",
                            "--token-source",
                            str(token_file),
                            f"0.0.0.0:{self._settings.websocket_port}",
                        ]
                    )
                )
                self._wait_started(processes[-1])

                from playwright.sync_api import sync_playwright

                playwright = sync_playwright().start()
                browser_env = dict(os.environ)
                browser_env["DISPLAY"] = self._settings.display
                browser = playwright.chromium.launch(
                    headless=False,
                    env=browser_env,
                    args=[
                        "--window-position=0,0",
                        "--window-size=480,960",
                        "--disable-session-crashed-bubble",
                        "--disable-features=Translate",
                        "--no-first-run",
                    ],
                )
                descriptor = playwright.devices[
                    self._mobile_settings.profile.playwright_device_name
                ]
                context = new_mobile_context(browser, self._mobile_settings, descriptor)
                context.set_default_timeout(5_000)
                self._secure_context(context)
                page = context.new_page()
                page.goto(_LOGIN_URL, timeout=45_000, wait_until="domcontentloaded")
                on_ready()

                while True:
                    if daemon_stop_event.is_set() or work.cancel_event.is_set():
                        return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
                    if datetime.now(UTC) >= work.expires_at:
                        return RemoteBrowserResult(RemoteAuthStatus.EXPIRED)
                    if any(process.poll() is not None for process in processes):
                        return RemoteBrowserResult(
                            RemoteAuthStatus.FAILED,
                            failure=RemoteAuthFailure.BROWSER_FAILED,
                        )
                    try:
                        text = page.locator("body").inner_text(timeout=2_000)
                        if has_authenticated_account_context(page, text):
                            cookies = json.dumps(
                                context.cookies(), separators=(",", ":")
                            )
                            return RemoteBrowserResult(
                                RemoteAuthStatus.SUCCEEDED,
                                cookies_json=cookies,
                            )
                    except Exception:
                        # Navigation/login transitions can temporarily detach the body.
                        pass
                    work.cancel_event.wait(1.0)
        except Exception as exc:
            logger.warning(
                "Remote authentication browser ended with %s", type(exc).__name__
            )
            return RemoteBrowserResult(
                RemoteAuthStatus.FAILED,
                failure=RemoteAuthFailure.SETUP_FAILED,
            )
        finally:
            for resource in (context, browser):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception:
                    pass
            self._terminate(processes)

    @staticmethod
    def _secure_context(context: Any) -> None:
        def _route(route: Any) -> None:
            request = route.request
            try:
                top_level = request.is_navigation_request() and request.frame.parent_frame is None
            except Exception:
                top_level = request.resource_type == "document"
            if top_level and not _allowed_top_level(request.url):
                route.abort("blockedbyclient")
                return
            route.continue_()

        # Context-level routing also covers sign-in popups and avoids installing
        # duplicate handlers on the initial page.
        context.route("**/*", _route)
        context.on(
            "page",
            lambda page: page.on("download", lambda download: download.cancel()),
        )

    @staticmethod
    def _spawn(command: list[str]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(  # noqa: S603 - fixed executable/arguments only
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    @staticmethod
    def _wait_started(process: subprocess.Popen[bytes]) -> None:
        time.sleep(0.2)
        if process.poll() is not None:
            raise RuntimeError("Remote display component did not start")

    @staticmethod
    def _terminate(processes: list[subprocess.Popen[bytes]]) -> None:
        for process in reversed(processes):
            if process.poll() is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
        for process in reversed(processes):
            if process.poll() is None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
        processes.clear()

    @staticmethod
    def _require_tools() -> None:
        missing = [name for name in ("Xvfb", "x11vnc", "websockify") if shutil.which(name) is None]
        if missing:
            raise RuntimeError("Remote display components are unavailable")
