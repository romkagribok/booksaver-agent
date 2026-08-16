from __future__ import annotations

import inspect
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from booksaver.application.remote_auth import RemoteBrowserWork
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.remote_auth import (
    RemoteAuthFailure,
    RemoteAuthServerReceipt,
    RemoteAuthServerVerification,
    RemoteAuthSettings,
    RemoteAuthStatus,
    SafeServerEvidence,
    ServerMediaClass,
    ServerRedirectClass,
    ServerSessionProbeOutcome,
    ServerSizeClass,
    ServerStatusClass,
)
from booksaver.infrastructure.remote_auth.browser_runner import (
    SystemRemoteBrowserRunner,
)
from booksaver.infrastructure.remote_auth.network_session import (
    BookingServerSessionVerifier,
    CandidateSessionSnapshot,
)

NOW = datetime(2026, 8, 15, 22, 0, tzinfo=UTC)
DESCRIPTOR = {
    "user_agent": "Mozilla/5.0 (Linux; Android 13) Chrome Mobile",
    "viewport": {"width": 480, "height": 960},
    "is_mobile": True,
    "has_touch": True,
    "device_scale_factor": 1,
}


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


def test_remote_browser_allows_only_booking_owned_navigation() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001

    assert _route(context, FakeRequest("https://account.booking.com/sign-in")) == "continue"
    assert _route(context, FakeRequest("https://www.booking.com/index.html")) == "continue"
    for url in (
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://appleid.apple.com/auth/authorize",
        "https://arbitrary.example/sign-in",
        "https://booking.com.attacker.example/phish",
        "https://evilbooking.com/phish",
        "https://booking.com./sign-in",
    ):
        assert _route(context, FakeRequest(url)) == "abort:blockedbyclient"

    assert (
        _route(
            context,
            FakeRequest("https://cdn.example.test/script.js", navigation=False),
        )
        == "continue"
    )


def test_remote_browser_context_policy_covers_popups_and_downloads() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001
    assert (
        _route(
            context,
            FakeRequest("https://accounts.google.com/o/oauth2/v2/auth", parent=None),
        )
        == "abort:blockedbyclient"
    )

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


def test_remote_browser_uses_chrome_free_kiosk_presentation() -> None:
    args = SystemRemoteBrowserRunner._chromium_args()  # noqa: SLF001

    assert "--kiosk" in args
    assert "--window-position=0,0" in args
    assert "--window-size=480,960" in args
    assert not any(argument.startswith("--app=") for argument in args)


def test_remote_browser_requires_all_viewer_modules(tmp_path: Any) -> None:
    settings = RemoteAuthSettings(
        enabled=True,
        public_url="https://connect.example.test",
        novnc_root=tmp_path,
    )
    runner = SystemRemoteBrowserRunner(settings, MobileWebSettings())
    required = (
        "core/rfb.js",
        "core/input/keyboard.js",
        "core/input/keysym.js",
        "core/input/keysymdef.js",
    )
    for relative in required:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("export default {}")

    runner._require_viewer_modules()  # noqa: SLF001
    (tmp_path / "core/input/keyboard.js").unlink()

    try:
        runner._require_viewer_modules()  # noqa: SLF001
    except RuntimeError as exc:
        assert str(exc) == "Required noVNC viewer modules are unavailable"
    else:  # pragma: no cover - assertion branch
        raise AssertionError("Missing noVNC input module was accepted")


class FakeResponse:
    def __init__(
        self,
        status: int,
        *,
        url: str = "https://secure.booking.com/myaccount.html",
        headers: dict[str, str] | None = None,
        body: bytes = b"account",
    ) -> None:
        self.status = status
        self.url = url
        self.headers = headers or {"content-type": "text/html"}
        self._body = body

    def body(self) -> bytes:
        return self._body


class FakeRequestContext:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(self, _url: str, **_kwargs: Any) -> FakeResponse:
        return self.response


class ProbeContext:
    def __init__(self, response: FakeResponse) -> None:
        self.request = FakeRequestContext(response)
        self.cookies: list[dict[str, Any]] = []
        self.closed = False

    def add_cookies(self, cookies: list[dict[str, Any]]) -> None:
        self.cookies = cookies

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.contexts: list[ProbeContext] = []

    def new_context(self, **_kwargs: Any) -> ProbeContext:
        context = ProbeContext(self.responses.pop(0))
        self.contexts.append(context)
        return context


def _verified_fixture() -> tuple[
    BookingServerSessionVerifier,
    CandidateSessionSnapshot,
    RemoteAuthServerVerification,
]:
    browser = FakeBrowser(
        [
            FakeResponse(
                302,
                headers={
                    "content-type": "text/html",
                    "location": "https://account.booking.com/auth/oauth2?state=redacted",
                },
            ),
            FakeResponse(200),
            FakeResponse(200),
        ]
    )
    verifier = BookingServerSessionVerifier(
        browser,
        MobileWebSettings(),
        DESCRIPTOR,
        clock=lambda: NOW,
        hmac_key=b"k" * 32,
    )
    assert verifier.establish_baseline().outcome is ServerSessionProbeOutcome.SIGNED_OUT
    snapshot = verifier.snapshot(
        [
            {
                "name": "session",
                "value": "secret-value",
                "domain": ".booking.com",
                "path": "/",
                "secure": True,
            }
        ]
    )
    assert snapshot is not None
    verification = verifier.verify_candidate(
        snapshot,
        attempt_id="attempt-1",
        telegram_user_id=42,
    )
    return verifier, snapshot, verification


def test_verified_server_receipt_finalizes_exact_snapshot() -> None:
    verifier, snapshot, verification = _verified_fixture()
    work = RemoteBrowserWork(
        attempt_id="attempt-1",
        telegram_user_id=42,
        websocket_token="ws",
        expires_at=NOW + timedelta(minutes=5),
        cancel_event=threading.Event(),
    )
    execution = SystemRemoteBrowserRunner._verified_execution(  # noqa: SLF001
        verifier,
        snapshot,
        verification,
        work,
        lambda: True,
    )

    assert execution.result.status is RemoteAuthStatus.SUCCEEDED
    assert execution.result.cookies_json is not None
    assert "secret-value" in execution.result.cookies_json
    assert "pending-code-owned-capture" not in execution.result.cookies_json


def test_server_receipt_cannot_be_reused_for_finalization() -> None:
    verifier, snapshot, verification = _verified_fixture()
    work = RemoteBrowserWork(
        attempt_id="attempt-1",
        telegram_user_id=42,
        websocket_token="ws",
        expires_at=NOW + timedelta(minutes=5),
        cancel_event=threading.Event(),
    )
    first = SystemRemoteBrowserRunner._verified_execution(  # noqa: SLF001
        verifier,
        snapshot,
        verification,
        work,
        lambda: True,
    )
    second = SystemRemoteBrowserRunner._verified_execution(  # noqa: SLF001
        verifier,
        snapshot,
        verification,
        work,
        lambda: True,
    )

    assert first.result.status is RemoteAuthStatus.SUCCEEDED
    assert second.result.failure is RemoteAuthFailure.VERIFICATION_RECEIPT_REJECTED


def _safe_evidence() -> SafeServerEvidence:
    return SafeServerEvidence(
        contract_version="booking-account-session-v2",
        status=ServerStatusClass.SUCCESS,
        media=ServerMediaClass.OTHER,
        redirect=ServerRedirectClass.NONE,
        size=ServerSizeClass.BOUNDED,
    )


def test_contract_change_builds_model_free_content_safe_incident() -> None:
    work = RemoteBrowserWork(
        attempt_id="attempt-1",
        telegram_user_id=42,
        websocket_token="ws-secret",
        expires_at=NOW + timedelta(minutes=5),
        cancel_event=threading.Event(),
    )
    runner = SystemRemoteBrowserRunner(
        RemoteAuthSettings(),
        MobileWebSettings(),
        source_user_resolver=lambda _telegram_user_id: 7,
    )
    execution = runner._failed_server_execution(  # noqa: SLF001
        work,
        RemoteAuthServerVerification(
            ServerSessionProbeOutcome.CONTRACT_CHANGED,
            _safe_evidence(),
        ),
    )

    assert execution.result.failure is RemoteAuthFailure.VERIFICATION_CONTRACT_CHANGED
    assert execution.incident_draft is not None
    occurrence = execution.incident_draft.occurrence
    assert occurrence.model_roles == ()
    assert occurrence.provider_state.value == "not_attempted"
    bundle = execution.incident_draft.diagnostic_bundle
    assert bundle is not None
    assert bundle.source_user_ids == (7,)
    rendered = repr(execution.incident_draft)
    assert "ws-secret" not in rendered
    assert "attempt-1" not in rendered


def test_predictable_server_failures_do_not_create_maintenance_incident() -> None:
    work = RemoteBrowserWork(
        attempt_id="attempt-1",
        telegram_user_id=42,
        websocket_token="ws",
        expires_at=NOW + timedelta(minutes=5),
        cancel_event=threading.Event(),
    )
    runner = SystemRemoteBrowserRunner(RemoteAuthSettings(), MobileWebSettings())

    for outcome, failure in (
        (ServerSessionProbeOutcome.UNAVAILABLE, RemoteAuthFailure.VERIFICATION_UNAVAILABLE),
        (ServerSessionProbeOutcome.BLOCKED_REDIRECT, RemoteAuthFailure.VERIFICATION_BLOCKED),
    ):
        execution = runner._failed_server_execution(  # noqa: SLF001
            work,
            RemoteAuthServerVerification(outcome, _safe_evidence()),
        )
        assert execution.result.failure is failure
        assert execution.incident_draft is None


def test_remote_auth_declares_no_dom_steps() -> None:
    from booksaver.infrastructure.remote_auth import browser_runner

    assert browser_runner.DOM_STEPS == ()
    source = inspect.getsource(SystemRemoteBrowserRunner._run_browser)  # noqa: SLF001
    assert ".locator(" not in source
    assert "page_state" not in source
    assert "model" not in source
    assert "myreservations" not in source


def test_remote_auth_runtime_has_no_adaptive_model_admission() -> None:
    from booksaver.infrastructure.remote_auth.runtime import build_remote_auth_runtime

    signature = inspect.signature(build_remote_auth_runtime)
    source = inspect.getsource(build_remote_auth_runtime)
    assert "adaptive_runtime_scope" not in signature.parameters
    assert "BrowserJobKind.REMOTE_AUTH" not in source
    assert "page_state_resolver" not in source


class _RunnerProcess:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: int) -> None:
        assert timeout == 3


class _RunnerPage:
    def __init__(self) -> None:
        self.goto_calls: list[tuple[str, dict[str, Any]]] = []

    def goto(self, url: str, **kwargs: Any) -> None:
        self.goto_calls.append((url, kwargs))


class _RunnerContext(FakeContext):
    def __init__(self, cookie_states: list[str]) -> None:
        super().__init__()
        self.cookie_states = cookie_states
        self.page = _RunnerPage()
        self.closed = False
        self.default_timeout: int | None = None

    def set_default_timeout(self, value: int) -> None:
        self.default_timeout = value

    def new_page(self) -> _RunnerPage:
        return self.page

    def cookies(self) -> list[dict[str, str]]:
        state = self.cookie_states.pop(0)
        return [{"state": state}]

    def close(self) -> None:
        self.closed = True


class _RunnerBrowser:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _RunnerChromium:
    def __init__(self, browser: _RunnerBrowser) -> None:
        self.browser = browser

    def launch(self, **_kwargs: Any) -> _RunnerBrowser:
        return self.browser


class _RunnerPlaywright:
    def __init__(self, browser: _RunnerBrowser) -> None:
        self.chromium = _RunnerChromium(browser)
        self.devices = {"Pixel 7": DESCRIPTOR}
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _RunnerPlaywrightStarter:
    def __init__(self, playwright: _RunnerPlaywright) -> None:
        self.playwright = playwright

    def start(self) -> _RunnerPlaywright:
        return self.playwright


class _NoWaitEvent:
    def is_set(self) -> bool:
        return False

    def wait(self, _timeout: float) -> bool:
        return False


class _RunnerVerifier:
    def __init__(self, baseline: ServerSessionProbeOutcome) -> None:
        self.baseline = baseline
        self.verified_states: list[str] = []
        self.consumed = False

    def establish_baseline(self) -> RemoteAuthServerVerification:
        return RemoteAuthServerVerification(self.baseline, _safe_evidence())

    def snapshot(self, cookies: list[dict[str, str]]) -> CandidateSessionSnapshot:
        state = cookies[0]["state"]
        return CandidateSessionSnapshot(
            f'{{"state":"{state}"}}'.encode(),
            state.encode().ljust(32, b"0"),
        )

    def verify_candidate(
        self,
        snapshot: CandidateSessionSnapshot,
        *,
        attempt_id: str,
        telegram_user_id: int,
    ) -> RemoteAuthServerVerification:
        state = snapshot.persistence_json()
        self.verified_states.append(state)
        if "anonymous" in state:
            return RemoteAuthServerVerification(
                ServerSessionProbeOutcome.SIGNED_OUT,
                _safe_evidence(),
            )
        receipt = RemoteAuthServerReceipt(
            attempt_id=attempt_id,
            telegram_user_id=telegram_user_id,
            contract_version="booking-account-session-v2",
            verified_at=NOW,
            expires_at=NOW + timedelta(seconds=30),
            verifier="booking_server_session_v2",
            _snapshot_hmac=b"h" * 32,
            _nonce=b"n" * 32,
        )
        return RemoteAuthServerVerification(
            ServerSessionProbeOutcome.AUTHENTICATED,
            _safe_evidence(),
            receipt,
        )

    def consume_receipt(self, *_args: Any, **_kwargs: Any) -> bool:
        self.consumed = True
        return True


def test_runner_uses_server_evidence_without_page_inspection_or_reload(
    monkeypatch: Any,
) -> None:
    from playwright import sync_api

    from booksaver.infrastructure.remote_auth import browser_runner

    browser = _RunnerBrowser()
    playwright = _RunnerPlaywright(browser)
    context = _RunnerContext(["anonymous", "anonymous", "authenticated", "authenticated"])
    verifier = _RunnerVerifier(ServerSessionProbeOutcome.SIGNED_OUT)
    processes: list[_RunnerProcess] = []

    def spawn(_command: list[str]) -> _RunnerProcess:
        process = _RunnerProcess()
        processes.append(process)
        return process

    monkeypatch.setattr(sync_api, "sync_playwright", lambda: _RunnerPlaywrightStarter(playwright))
    monkeypatch.setattr(browser_runner, "new_mobile_context", lambda *_args: context)
    monkeypatch.setattr(SystemRemoteBrowserRunner, "_require_tools", lambda _self: None)
    monkeypatch.setattr(SystemRemoteBrowserRunner, "_spawn", staticmethod(spawn))
    monkeypatch.setattr(SystemRemoteBrowserRunner, "_wait_started", staticmethod(lambda _p: None))
    monkeypatch.setattr(
        SystemRemoteBrowserRunner,
        "_terminate",
        staticmethod(lambda items: [item.terminate() for item in items]),
    )
    ready: list[bool] = []
    finalizing: list[bool] = []
    runner = SystemRemoteBrowserRunner(
        RemoteAuthSettings(),
        MobileWebSettings(),
        server_verifier_factory=lambda *_args: verifier,  # type: ignore[arg-type]
    )
    work = RemoteBrowserWork(
        attempt_id="attempt-1",
        telegram_user_id=42,
        websocket_token="ws",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        cancel_event=_NoWaitEvent(),  # type: ignore[arg-type]
    )

    result = runner.run(
        work,
        _NoWaitEvent(),
        lambda: ready.append(True),
        lambda: finalizing.append(True) or True,
    )

    assert result.status is RemoteAuthStatus.SUCCEEDED
    assert result.cookies_json == '{"state":"authenticated"}'
    assert ready == [True]
    assert finalizing == [True]
    assert verifier.verified_states == [
        '{"state":"anonymous"}',
        '{"state":"authenticated"}',
    ]
    assert verifier.consumed
    assert context.page.goto_calls == [
        (
            "https://account.booking.com/sign-in",
            {"timeout": 45_000, "wait_until": "domcontentloaded"},
        )
    ]
    assert context.closed and browser.closed and playwright.stopped
    assert all(process.terminated for process in processes)


def test_runner_refuses_to_admit_viewer_when_negative_baseline_changes(
    monkeypatch: Any,
) -> None:
    from playwright import sync_api

    from booksaver.infrastructure.remote_auth import browser_runner

    browser = _RunnerBrowser()
    playwright = _RunnerPlaywright(browser)
    context = _RunnerContext(["unused"])
    verifier = _RunnerVerifier(ServerSessionProbeOutcome.CONTRACT_CHANGED)
    monkeypatch.setattr(sync_api, "sync_playwright", lambda: _RunnerPlaywrightStarter(playwright))
    monkeypatch.setattr(browser_runner, "new_mobile_context", lambda *_args: context)
    monkeypatch.setattr(SystemRemoteBrowserRunner, "_require_tools", lambda _self: None)
    monkeypatch.setattr(
        SystemRemoteBrowserRunner, "_spawn", staticmethod(lambda _cmd: _RunnerProcess())
    )
    monkeypatch.setattr(SystemRemoteBrowserRunner, "_wait_started", staticmethod(lambda _p: None))
    runner = SystemRemoteBrowserRunner(
        RemoteAuthSettings(),
        MobileWebSettings(),
        server_verifier_factory=lambda *_args: verifier,  # type: ignore[arg-type]
    )
    ready: list[bool] = []

    result = runner.run(
        RemoteBrowserWork(
            attempt_id="attempt-1",
            telegram_user_id=42,
            websocket_token="ws",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            cancel_event=_NoWaitEvent(),  # type: ignore[arg-type]
        ),
        _NoWaitEvent(),
        lambda: ready.append(True),
        lambda: True,
    )

    assert result.failure is RemoteAuthFailure.VERIFICATION_CONTRACT_CHANGED
    assert ready == []
    assert context.page.goto_calls == []
    assert browser.closed and playwright.stopped
