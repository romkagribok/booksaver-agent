from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from booksaver.application.remote_auth import RemoteBrowserResult, RemoteBrowserWork
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomStepId,
    EvidenceCategory,
    OperatorAction,
    PageState,
    PageStateClassification,
    PageStateResolution,
    PageStateSource,
    TerminalBrowserReason,
)
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.model_policy import ModelStopReason
from booksaver.domain.remote_auth import RemoteAuthSettings, RemoteAuthStatus
from booksaver.infrastructure.remote_auth.browser_runner import (
    RemoteAuthPageStateCapability,
    SystemRemoteBrowserRunner,
    _AmbiguousStateDebouncer,
    _RemoteBrowserExecution,
)


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


def test_remote_browser_allows_booking_owned_top_level_navigation() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001

    assert _route(context, FakeRequest("https://account.booking.com/sign-in")) == "continue"
    assert _route(context, FakeRequest("https://www.booking.com/index.html")) == "continue"
    assert _route(context, FakeRequest("https://BOOKING.COM/sign-in")) == "continue"


def test_remote_browser_blocks_provider_arbitrary_and_lookalike_top_level_hosts() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001

    blocked_urls = (
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://appleid.apple.com/auth/authorize",
        "https://login.microsoftonline.com/common/oauth2/authorize",
        "https://www.facebook.com/login.php",
        "https://arbitrary.example/sign-in",
        "https://booking.com.attacker.example/phish",
        "https://evilbooking.com/phish",
        "https://booking.com./sign-in",
    )
    for url in blocked_urls:
        assert _route(context, FakeRequest(url)) == "abort:blockedbyclient"


def test_remote_browser_context_policy_covers_popup_top_level_navigation() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001

    # A popup has its own main frame, so its document navigation has no parent.
    assert (
        _route(
            context,
            FakeRequest("https://accounts.google.com/o/oauth2/v2/auth", parent=None),
        )
        == "abort:blockedbyclient"
    )
    assert _route(context, FakeRequest("https://booking.com.attacker.example/phish")) == (
        "abort:blockedbyclient"
    )


def test_remote_browser_allows_subresources_but_blocks_external_frame_navigation() -> None:
    context = FakeContext()
    SystemRemoteBrowserRunner._secure_context(context)  # noqa: SLF001

    assert (
        _route(
            context,
            FakeRequest("https://cdn.example.test/script.js", navigation=False),
        )
        == "continue"
    )
    assert (
        _route(
            context,
            FakeRequest("https://attacker.example/frame", parent=object()),
        )
        == "abort:blockedbyclient"
    )
    assert (
        _route(
            context,
            FakeRequest("https://account.booking.com/frame", parent=object()),
        )
        == "continue"
    )
    assert _route(context, FakeRequest("https://attacker.example/top")) == ("abort:blockedbyclient")


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
    else:
        raise AssertionError("Missing noVNC input module was accepted")


def test_remote_browser_probe_requires_strong_inventory_evidence() -> None:
    class Locator:
        def __init__(self, visible: bool, text: str = "") -> None:
            self.visible = visible
            self.text = text

        def count(self) -> int:
            return int(self.visible)

        def nth(self, _index: int) -> Locator:
            return self

        def is_visible(self) -> bool:
            return self.visible

        def inner_text(self, timeout: int | None = None) -> str:
            assert timeout == 5_000
            return self.text

    class Page:
        def __init__(self, *, inventory_visible: bool) -> None:
            self.url = "https://www.booking.com/"
            self.inventory_visible = inventory_visible
            self.goto_urls: list[str] = []

        def goto(self, url: str, **_kwargs: Any) -> None:
            self.goto_urls.append(url)
            self.url = url

        def locator(self, selector: str) -> Locator:
            if selector == "body":
                return Locator(True, "Genius Level 2 — Upcoming reservations")
            return Locator(self.inventory_visible and selector == '[data-testid="bookings-list"]')

    weak_only = Page(inventory_visible=False)
    strong = Page(inventory_visible=True)

    assert not SystemRemoteBrowserRunner._probe_authenticated_inventory(  # noqa: SLF001
        weak_only
    )
    assert SystemRemoteBrowserRunner._probe_authenticated_inventory(strong)  # noqa: SLF001
    assert weak_only.goto_urls == ["https://secure.booking.com/myreservations.html"]
    assert strong.goto_urls == ["https://secure.booking.com/myreservations.html"]


class _ObservedControl:
    def is_visible(self) -> bool:
        return True

    def evaluate(self, _script: str) -> str:
        return "button"

    def get_attribute(self, name: str) -> str | None:
        return "Continue" if name == "aria-label" else None

    def inner_text(self) -> str:
        return "Continue"


class _ObservedControls:
    def count(self) -> int:
        return 1

    def nth(self, _index: int) -> _ObservedControl:
        return _ObservedControl()


class _ObservedPage:
    url = "https://account.booking.com/new-flow"

    def locator(self, _selector: str) -> _ObservedControls:
        return _ObservedControls()

    def title(self) -> str:
        return "Booking account"


class _CountingResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[DomStepId, object]] = []

    def resolve(self, step_id: DomStepId, observation: object) -> PageStateResolution:
        self.calls.append((step_id, observation))
        return PageStateResolution(
            classification=PageStateClassification(
                state=PageState.AUTHENTICATED_CANDIDATE,
                confidence=0.95,
                evidence=frozenset({EvidenceCategory.WEAK_ACCOUNT_CHROME}),
                evidence_references=(),
                operator_action=OperatorAction.NONE,
                source=PageStateSource.SONNET,
                observation_id="remote-auth-test",
            ),
            terminal_reason=TerminalBrowserReason.CODE_VERIFICATION_REQUIRED,
        )


def test_remote_browser_classifies_only_stable_unchanged_ambiguity() -> None:
    runner = SystemRemoteBrowserRunner(RemoteAuthSettings(), MobileWebSettings())
    resolver = _CountingResolver()
    capability = RemoteAuthPageStateCapability(resolver=resolver)
    debouncer = _AmbiguousStateDebouncer()
    page = _ObservedPage()

    assert (
        runner._resolve_ambiguous_state(  # noqa: SLF001
            page, "Unknown account page", PageState.AMBIGUOUS, capability, debouncer
        )
        is None
    )
    assert (
        runner._resolve_ambiguous_state(  # noqa: SLF001
            page, "Unknown account page", PageState.AMBIGUOUS, capability, debouncer
        )
        is not None
    )
    assert (
        runner._resolve_ambiguous_state(  # noqa: SLF001
            page, "Unknown account page", PageState.AMBIGUOUS, capability, debouncer
        )
        is None
    )
    assert len(resolver.calls) == 1
    assert resolver.calls[0][0] is DomStepId.REMOTE_AUTH_SESSION_CAPTURE

    # A changed state must itself stabilize before the one allowed call.
    assert (
        runner._resolve_ambiguous_state(  # noqa: SLF001
            page, "Changed account page", PageState.AMBIGUOUS, capability, debouncer
        )
        is None
    )
    assert (
        runner._resolve_ambiguous_state(  # noqa: SLF001
            page, "Changed account page", PageState.AMBIGUOUS, capability, debouncer
        )
        is not None
    )
    assert len(resolver.calls) == 2


@pytest.mark.parametrize(
    "state",
    [
        PageState.AUTHENTICATION_REQUIRED,
        PageState.MFA_REQUIRED,
        PageState.CAPTCHA,
        PageState.BOT_WALL,
    ],
)
def test_remote_browser_protected_interactive_states_never_call_model(
    state: PageState,
) -> None:
    runner = SystemRemoteBrowserRunner(RemoteAuthSettings(), MobileWebSettings())
    resolver = _CountingResolver()
    capability = RemoteAuthPageStateCapability(resolver=resolver)
    debouncer = _AmbiguousStateDebouncer()

    for _ in range(3):
        assert (
            runner._resolve_ambiguous_state(  # noqa: SLF001
                _ObservedPage(), "Protected state", state, capability, debouncer
            )
            is None
        )
    assert resolver.calls == []


@pytest.mark.parametrize(
    ("model_stop", "terminal_reason", "provenance"),
    [
        (
            ModelStopReason.PROVIDER_RATE_LIMIT,
            TerminalBrowserReason.PROVIDER_RATE_LIMIT,
            DiagnosisProvenance.PROVIDER_STOP,
        ),
        (
            ModelStopReason.JOB_COST_LIMIT,
            TerminalBrowserReason.JOB_COST_LIMIT,
            DiagnosisProvenance.BUDGET_STOP,
        ),
        (
            ModelStopReason.DAILY_COST_LIMIT,
            TerminalBrowserReason.DAILY_COST_LIMIT,
            DiagnosisProvenance.BUDGET_STOP,
        ),
    ],
)
def test_remote_browser_preserves_exact_model_stop_without_claiming_dom_drift(
    model_stop: ModelStopReason,
    terminal_reason: TerminalBrowserReason,
    provenance: DiagnosisProvenance,
) -> None:
    runner = SystemRemoteBrowserRunner(RemoteAuthSettings(), MobileWebSettings())
    execution = runner._resolution_execution(  # noqa: SLF001
        _ObservedPage(),
        PageStateResolution(
            classification=None,
            terminal_reason=terminal_reason,
            model_stop_reason=model_stop,
        ),
        runner._observe_page(_ObservedPage(), "Unknown account page"),  # noqa: SLF001
        RemoteAuthPageStateCapability(),
    )

    assert execution is not None
    diagnosis = execution.result.terminal_diagnosis
    assert diagnosis is not None
    assert diagnosis.reason is terminal_reason
    assert diagnosis.provenance is provenance
    assert diagnosis.model_stop_reason is model_stop
    assert not diagnosis.code_maintenance_required
    assert execution.incident_draft is None


def test_remote_browser_model_candidate_only_runs_fixed_inventory_probe() -> None:
    class Page(_ObservedPage):
        def __init__(self) -> None:
            self.goto_urls: list[str] = []

        def goto(self, url: str, **_kwargs: object) -> None:
            self.goto_urls.append(url)

        def locator(self, selector: str) -> object:
            if selector == "body":
                return type(
                    "Body",
                    (),
                    {"inner_text": lambda self, timeout=None: "Unknown account page"},
                )()
            return _ObservedControls()

    page = Page()
    runner = SystemRemoteBrowserRunner(RemoteAuthSettings(), MobileWebSettings())
    observation = runner._observe_page(page, "Unknown account page")  # noqa: SLF001
    resolution = _CountingResolver().resolve(
        DomStepId.REMOTE_AUTH_SESSION_CAPTURE,
        observation,
    )

    execution = runner._resolution_execution(  # noqa: SLF001
        page,
        resolution,
        observation,
        RemoteAuthPageStateCapability(),
    )

    assert execution is None
    assert page.goto_urls == ["https://secure.booking.com/myreservations.html"]


def test_remote_browser_opus_exhaustion_is_ambiguous_incident_diagnosis() -> None:
    classification = PageStateClassification(
        state=PageState.AMBIGUOUS,
        confidence=0.0,
        evidence=frozenset({EvidenceCategory.UNSUPPORTED_PAGE_STRUCTURE}),
        evidence_references=(),
        operator_action=OperatorAction.NONE,
        source=PageStateSource.DETERMINISTIC,
        observation_id="remote-auth-opus-exhausted",
    )
    diagnosis = SystemRemoteBrowserRunner._diagnosis_for_resolution(  # noqa: SLF001
        PageStateResolution(
            classification=classification,
            terminal_reason=TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
            model_stop_reason=ModelStopReason.OPUS_EXHAUSTED,
        )
    )

    assert diagnosis.reason is TerminalBrowserReason.UNRESOLVED_AMBIGUITY
    assert diagnosis.provenance is DiagnosisProvenance.OPUS_DIAGNOSED
    assert diagnosis.confidence == 0.0
    assert not diagnosis.code_maintenance_required


def test_remote_browser_unexpected_resolver_error_is_typed_infrastructure_stop() -> None:
    class BrokenResolver:
        def resolve(self, _step_id: object, _observation: object) -> object:
            raise RuntimeError("provider payload must not escape")

    runner = SystemRemoteBrowserRunner(RemoteAuthSettings(), MobileWebSettings())
    capability = RemoteAuthPageStateCapability(
        resolver=BrokenResolver(),  # type: ignore[arg-type]
    )
    debouncer = _AmbiguousStateDebouncer()

    assert (
        runner._resolve_ambiguous_state(  # noqa: SLF001
            _ObservedPage(),
            "Unknown account page",
            PageState.AMBIGUOUS,
            capability,
            debouncer,
        )
        is None
    )
    resolved = runner._resolve_ambiguous_state(  # noqa: SLF001
        _ObservedPage(),
        "Unknown account page",
        PageState.AMBIGUOUS,
        capability,
        debouncer,
    )

    assert resolved is not None
    assert resolved[0].terminal_reason is TerminalBrowserReason.INFRASTRUCTURE_FAILURE
    assert resolved[0].model_stop_reason is None


def test_remote_browser_records_incident_only_after_browser_execution_cleanup() -> None:
    browser_active = True
    recorded: list[object] = []
    draft = object()

    class Runner(SystemRemoteBrowserRunner):
        def _run_browser(self, *_args: object, **_kwargs: object) -> _RemoteBrowserExecution:
            nonlocal browser_active
            browser_active = False
            return _RemoteBrowserExecution(
                RemoteBrowserResult(RemoteAuthStatus.CANCELLED),
                incident_draft=draft,  # type: ignore[arg-type]
            )

    def _sink(value: object) -> None:
        assert not browser_active
        recorded.append(value)

    runner = Runner(
        RemoteAuthSettings(),
        MobileWebSettings(),
        incident_sink=_sink,  # type: ignore[arg-type]
    )
    work = RemoteBrowserWork(
        attempt_id="attempt-1",
        telegram_user_id=1,
        websocket_token="token",
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
        cancel_event=threading.Event(),
    )

    result = runner.run(work, threading.Event(), lambda: None)

    assert result.status is RemoteAuthStatus.CANCELLED
    assert recorded == [draft]
