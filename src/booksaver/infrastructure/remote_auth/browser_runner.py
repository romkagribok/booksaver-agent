from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from booksaver.application.dom_incident import build_incident_draft
from booksaver.application.remote_auth import RemoteBrowserResult, RemoteBrowserWork
from booksaver.domain.agent import ElementInfo, Observation
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomJourney,
    DomStepId,
    EvidenceCategory,
    PageState,
    PageStateResolution,
    PageStateSource,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
    operator_action_for_reason,
)
from booksaver.domain.dom_incident import (
    IncidentBudgetState,
    IncidentDraft,
    IncidentProviderState,
)
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.model_policy import ModelStopReason
from booksaver.domain.remote_auth import RemoteAuthFailure, RemoteAuthSettings, RemoteAuthStatus
from booksaver.infrastructure.browser.page_state import (
    assess_page_state,
    assessment_proves_authenticated,
)
from booksaver.infrastructure.browser.playwright_adapter import new_mobile_context

if TYPE_CHECKING:
    from booksaver.application.model_policy import BrowserJobCostBudget
    from booksaver.application.ports import RegisteredPageStateResolver

logger = logging.getLogger(__name__)

# Structural coverage declaration for the production remote-auth capture seam.
DOM_STEPS: tuple[DomStepId, ...] = (DomStepId.REMOTE_AUTH_SESSION_CAPTURE,)

_LOGIN_URL = "https://account.booking.com/sign-in"
_INVENTORY_PROBE_URL = "https://secure.booking.com/myreservations.html"
_BOOKING_HOST = "booking.com"
_MAX_OBSERVATION_TEXT = 30_000
_MAX_OBSERVATION_CONTROLS = 80
_INTERACTIVE_SELECTOR = "a, button, input, select, textarea, [role='button']"


@dataclass(frozen=True)
class RemoteAuthPageStateCapability:
    """One caller-scoped resolver lease kept alive for a browser attempt."""

    resolver: RegisteredPageStateResolver | None = None
    source_user_id: int | None = None
    budget: BrowserJobCostBudget | None = None


PageStateCapabilityFactory = Callable[
    [RemoteBrowserWork], AbstractContextManager[RemoteAuthPageStateCapability]
]
IncidentSink = Callable[[IncidentDraft], None]


@dataclass(frozen=True)
class _RemoteBrowserExecution:
    result: RemoteBrowserResult
    incident_draft: IncidentDraft | None = None


@dataclass
class _AmbiguousStateDebouncer:
    fingerprint: str | None = None
    stable_observations: int = 0
    classified_fingerprint: str | None = None

    def should_classify(self, fingerprint: str) -> bool:
        if fingerprint != self.fingerprint:
            self.fingerprint = fingerprint
            self.stable_observations = 1
            self.classified_fingerprint = None
            return False
        self.stable_observations += 1
        if self.stable_observations < 2 or self.classified_fingerprint == fingerprint:
            return False
        self.classified_fingerprint = fingerprint
        return True

    def reset(self) -> None:
        self.fingerprint = None
        self.stable_observations = 0
        self.classified_fingerprint = None


def _is_booking_navigation_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == _BOOKING_HOST or host.endswith(f".{_BOOKING_HOST}")


class SystemRemoteBrowserRunner:
    """One transient headed Chromium + Xvfb/x11vnc/websockify stack.

    Child output is discarded so capability-bearing URLs and browser content
    cannot enter daemon logs. Cleanup is idempotent and runs for every result.
    """

    def __init__(
        self,
        settings: RemoteAuthSettings,
        mobile_settings: MobileWebSettings,
        *,
        page_state_capability_factory: PageStateCapabilityFactory | None = None,
        incident_sink: IncidentSink | None = None,
    ) -> None:
        self._settings = settings
        self._mobile_settings = mobile_settings
        self._page_state_capability_factory = page_state_capability_factory
        self._incident_sink = incident_sink

    def run(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: Any,
        on_ready: Callable[[], None],
    ) -> RemoteBrowserResult:
        capability_context = (
            self._page_state_capability_factory(work)
            if self._page_state_capability_factory is not None
            else nullcontext(RemoteAuthPageStateCapability())
        )
        try:
            with capability_context as capability:
                execution = self._run_browser(
                    work,
                    daemon_stop_event,
                    on_ready,
                    capability,
                )
        except Exception as exc:
            logger.warning(
                "Remote authentication capability setup ended with %s",
                type(exc).__name__,
            )
            execution = _RemoteBrowserExecution(
                RemoteBrowserResult(
                    RemoteAuthStatus.FAILED,
                    failure=RemoteAuthFailure.SETUP_FAILED,
                )
            )

        # _run_browser closes Playwright and every display process before it
        # returns. Incident persistence therefore cannot overlap the browser
        # or retain live page authority.
        if execution.incident_draft is not None and self._incident_sink is not None:
            try:
                self._incident_sink(execution.incident_draft)
            except Exception:
                logger.warning("Remote authentication incident recording failed")
        return execution.result

    def _run_browser(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: Any,
        on_ready: Callable[[], None],
        capability: RemoteAuthPageStateCapability,
    ) -> _RemoteBrowserExecution:
        processes: list[subprocess.Popen[bytes]] = []
        playwright: Any = None
        browser: Any = None
        context: Any = None
        debouncer = _AmbiguousStateDebouncer()
        try:
            self._require_tools()
            with tempfile.TemporaryDirectory(prefix="booksaver-auth-") as temp_raw:
                temp_dir = Path(temp_raw)
                temp_dir.chmod(0o700)
                token_file = temp_dir / "websockify.tokens"
                token_file.write_text(f"{work.websocket_token}: 127.0.0.1:5900\n", encoding="utf-8")
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
                    args=self._chromium_args(),
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
                        return _RemoteBrowserExecution(
                            RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
                        )
                    if datetime.now(UTC) >= work.expires_at:
                        return _RemoteBrowserExecution(
                            RemoteBrowserResult(RemoteAuthStatus.EXPIRED)
                        )
                    if any(process.poll() is not None for process in processes):
                        return _RemoteBrowserExecution(
                            RemoteBrowserResult(
                                RemoteAuthStatus.FAILED,
                                failure=RemoteAuthFailure.BROWSER_FAILED,
                            )
                        )
                    try:
                        text = page.locator("body").inner_text(timeout=2_000)
                        assessment = assess_page_state(page, text)
                        verified = assessment_proves_authenticated(assessment)
                        if not verified and (
                            assessment.state is PageState.AUTHENTICATED_CANDIDATE
                            or (
                                assessment.state is PageState.AMBIGUOUS
                                and EvidenceCategory.WEAK_ACCOUNT_CHROME in assessment.evidence
                            )
                        ):
                            verified = self._probe_authenticated_inventory(page)
                            if not verified:
                                # The fixed probe changed page state. Observe it
                                # afresh on the next tick before classification.
                                debouncer.reset()
                                work.cancel_event.wait(1.0)
                                continue
                        if verified:
                            cookies = json.dumps(context.cookies(), separators=(",", ":"))
                            return _RemoteBrowserExecution(
                                RemoteBrowserResult(
                                    RemoteAuthStatus.SUCCEEDED,
                                    cookies_json=cookies,
                                )
                            )
                        resolved = self._resolve_ambiguous_state(
                            page,
                            text,
                            assessment.state,
                            capability,
                            debouncer,
                        )
                        if resolved is not None:
                            resolution, observation = resolved
                            terminal = self._resolution_execution(
                                page,
                                resolution,
                                observation,
                                capability,
                            )
                            if terminal is not None:
                                if terminal.result.status is RemoteAuthStatus.SUCCEEDED:
                                    cookies = json.dumps(context.cookies(), separators=(",", ":"))
                                    return _RemoteBrowserExecution(
                                        RemoteBrowserResult(
                                            RemoteAuthStatus.SUCCEEDED,
                                            cookies_json=cookies,
                                        )
                                    )
                                return terminal
                    except Exception:
                        # Navigation/login transitions can temporarily detach the body.
                        pass
                    work.cancel_event.wait(1.0)
        except Exception as exc:
            logger.warning("Remote authentication browser ended with %s", type(exc).__name__)
            return _RemoteBrowserExecution(
                RemoteBrowserResult(
                    RemoteAuthStatus.FAILED,
                    failure=RemoteAuthFailure.SETUP_FAILED,
                )
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

    def _resolve_ambiguous_state(
        self,
        page: Any,
        text: str,
        state: PageState,
        capability: RemoteAuthPageStateCapability,
        debouncer: _AmbiguousStateDebouncer,
    ) -> tuple[PageStateResolution, Observation] | None:
        if state is not PageState.AMBIGUOUS:
            # Login, MFA, and bot challenges are expected parts of an
            # interactive connection and never spend.
            debouncer.reset()
            return None
        if capability.resolver is None:
            return None
        observation = self._observe_page(page, text)
        fingerprint = self._observation_fingerprint(observation)
        if not debouncer.should_classify(fingerprint):
            return None
        try:
            resolution = capability.resolver.resolve(
                DomStepId.REMOTE_AUTH_SESSION_CAPTURE,
                observation,
            )
        except Exception:
            # Provider adapters return exact provider/budget stops themselves.
            # An unexpected resolver defect is infrastructure, not DOM drift.
            resolution = PageStateResolution(
                classification=None,
                terminal_reason=TerminalBrowserReason.INFRASTRUCTURE_FAILURE,
            )
        return resolution, observation

    def _resolution_execution(
        self,
        page: Any,
        resolution: PageStateResolution,
        observation: Observation,
        capability: RemoteAuthPageStateCapability,
    ) -> _RemoteBrowserExecution | None:
        reason = resolution.terminal_reason
        if reason in {
            TerminalBrowserReason.AUTHENTICATION_REQUIRED,
            TerminalBrowserReason.MFA_REQUIRED,
            TerminalBrowserReason.BOT_WALL,
        }:
            return None
        if reason in {
            TerminalBrowserReason.CODE_VERIFICATION_REQUIRED,
            TerminalBrowserReason.POSTCONDITION_SATISFIED,
        }:
            if self._probe_authenticated_inventory(page):
                # The caller captures cookies only after this fresh code-owned
                # proof; the model merely selected the fixed verification probe.
                return _RemoteBrowserExecution(
                    RemoteBrowserResult(
                        RemoteAuthStatus.SUCCEEDED,
                        cookies_json="pending-code-owned-capture",
                    )
                )
            # A candidate remains untrusted. The fixed probe changed the page;
            # its next fresh deterministic assessment decides whether to keep
            # waiting, classify a new ambiguity, or capture cookies.
            return None

        diagnosis = self._diagnosis_for_resolution(resolution)
        return self._failed_execution(
            diagnosis,
            observation,
            capability,
            action_outcome="page_state_diagnosed",
        )

    @staticmethod
    def _diagnosis_for_resolution(
        resolution: PageStateResolution,
    ) -> TerminalBrowserDiagnosis:
        reason = resolution.terminal_reason
        classification = resolution.classification
        if resolution.model_stop_reason is ModelStopReason.OPUS_EXHAUSTED:
            # Both approved classifiers inspected the stable state and could
            # not resolve it. This is an ambiguous incident observation (not a
            # conclusive DOM-drift claim) and becomes owner-visible only under
            # the incident correlation policy.
            provenance = DiagnosisProvenance.OPUS_DIAGNOSED
            confidence = classification.confidence if classification is not None else 0.0
        elif resolution.model_stop_reason is not None:
            if reason in {
                TerminalBrowserReason.PROVIDER_AUTHENTICATION,
                TerminalBrowserReason.PROVIDER_UNAVAILABLE,
                TerminalBrowserReason.PROVIDER_RATE_LIMIT,
            }:
                provenance = DiagnosisProvenance.PROVIDER_STOP
            elif reason in {
                TerminalBrowserReason.TIME_LIMIT,
                TerminalBrowserReason.JOB_COST_LIMIT,
                TerminalBrowserReason.DAILY_COST_LIMIT,
                TerminalBrowserReason.MODEL_PRICING_UNAVAILABLE,
                TerminalBrowserReason.COST_ACCOUNTING_ERROR,
                TerminalBrowserReason.CLOCK_ROLLBACK,
            }:
                provenance = DiagnosisProvenance.BUDGET_STOP
            else:
                provenance = DiagnosisProvenance.POLICY_STOP
            confidence = 1.0
        else:
            provenance = {
                PageStateSource.DETERMINISTIC: DiagnosisProvenance.DETERMINISTIC,
                PageStateSource.SONNET: DiagnosisProvenance.SONNET_DIAGNOSED,
                PageStateSource.OPUS: DiagnosisProvenance.OPUS_DIAGNOSED,
                None: DiagnosisProvenance.INFRASTRUCTURE_STOP,
            }[classification.source if classification is not None else None]
            confidence = classification.confidence if classification is not None else 1.0
        evidence = classification.evidence if classification is not None else frozenset()
        return TerminalBrowserDiagnosis(
            reason=reason,
            step_id=DomStepId.REMOTE_AUTH_SESSION_CAPTURE,
            provenance=provenance,
            confidence=confidence,
            evidence=evidence,
            operator_action=operator_action_for_reason(reason),
            code_maintenance_required=(reason is TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED),
            model_stop_reason=resolution.model_stop_reason,
        )

    @staticmethod
    def _failed_execution(
        diagnosis: TerminalBrowserDiagnosis,
        observation: Observation,
        capability: RemoteAuthPageStateCapability,
        *,
        action_outcome: str,
    ) -> _RemoteBrowserExecution:
        attempts = capability.budget.ordered_attempts() if capability.budget is not None else ()
        draft = None
        if attempts:
            draft = build_incident_draft(
                journey=DomJourney.REMOTE_AUTH,
                diagnosis=diagnosis,
                verifier_category="remote_auth_session_capture",
                structural_roles=tuple(item.role for item in observation.elements) or ("page",),
                provider_state=IncidentProviderState.COMPLETED,
                budget_state=IncidentBudgetState.WITHIN_LIMIT,
                observed_at=datetime.now(UTC),
                model_attempts=attempts,
                source_user_ids=(
                    (capability.source_user_id,) if capability.source_user_id is not None else ()
                ),
                action_outcomes=(
                    (action_outcome,) if capability.source_user_id is not None else ()
                ),
            )
        return _RemoteBrowserExecution(
            RemoteBrowserResult(
                RemoteAuthStatus.FAILED,
                failure=RemoteAuthFailure.BROWSER_FAILED,
                terminal_diagnosis=diagnosis,
            ),
            incident_draft=draft,
        )

    @staticmethod
    def _observe_page(page: Any, text: str) -> Observation:
        elements: list[ElementInfo] = []
        locator = page.locator(_INTERACTIVE_SELECTOR)
        for index in range(min(locator.count(), _MAX_OBSERVATION_CONTROLS * 3)):
            if len(elements) >= _MAX_OBSERVATION_CONTROLS:
                break
            handle = locator.nth(index)
            try:
                if not handle.is_visible():
                    continue
                tag = str(handle.evaluate("el => el.tagName.toLowerCase()"))
                role_attr = handle.get_attribute("role") or ""
                role = (
                    "checkbox"
                    if role_attr == "checkbox"
                    else {
                        "a": "link",
                        "input": "input",
                        "select": "select",
                        "textarea": "input",
                    }.get(tag, "button")
                )
                label = (
                    handle.get_attribute("aria-label")
                    or handle.inner_text()
                    or handle.get_attribute("placeholder")
                    or ""
                ).strip()[:256]
            except Exception:
                continue
            elements.append(ElementInfo(ref=f"e{len(elements)}", role=role, label=label))
        return Observation(
            url=str(page.url),
            title=str(page.title()),
            text=text[:_MAX_OBSERVATION_TEXT],
            elements=tuple(elements),
        )

    @staticmethod
    def _observation_fingerprint(observation: Observation) -> str:
        parsed = urlparse(observation.url)
        normalized = "\n".join(
            (
                parsed.scheme.casefold(),
                (parsed.hostname or "").casefold(),
                parsed.path,
                " ".join(observation.title.split()),
                " ".join(observation.text.split()),
                *(f"{item.role}:{' '.join(item.label.split())}" for item in observation.elements),
            )
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _probe_authenticated_inventory(page: Any) -> bool:
        """Verify a weak signed-in candidate through one fixed read-only page.

        This is code-owned navigation to a fixed Booking.com inventory URL. A
        model classification alone never reaches cookie capture.
        """

        try:
            page.goto(
                _INVENTORY_PROBE_URL,
                timeout=15_000,
                wait_until="domcontentloaded",
            )
            text = page.locator("body").inner_text(timeout=5_000)
            return assessment_proves_authenticated(assess_page_state(page, text))
        except Exception:
            return False

    @staticmethod
    def _secure_context(context: Any) -> None:
        def _route(route: Any) -> None:
            request = route.request
            try:
                navigation = request.is_navigation_request()
            except Exception:
                navigation = request.resource_type == "document"
            if navigation and not _is_booking_navigation_url(request.url):
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

    def _require_tools(self) -> None:
        missing = [name for name in ("Xvfb", "x11vnc", "websockify") if shutil.which(name) is None]
        if missing:
            raise RuntimeError("Remote display components are unavailable")
        self._require_viewer_modules()

    def _require_viewer_modules(self) -> None:
        required = (
            "core/rfb.js",
            "core/input/keyboard.js",
            "core/input/keysym.js",
            "core/input/keysymdef.js",
        )
        if any(not (self._settings.novnc_root / relative).is_file() for relative in required):
            raise RuntimeError("Required noVNC viewer modules are unavailable")

    @staticmethod
    def _chromium_args() -> list[str]:
        return [
            "--kiosk",
            "--window-position=0,0",
            "--window-size=480,960",
            "--disable-session-crashed-bubble",
            "--disable-features=Translate",
            "--no-first-run",
        ]
