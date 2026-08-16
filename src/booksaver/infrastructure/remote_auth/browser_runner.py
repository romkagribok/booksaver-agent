from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from booksaver.application.dom_incident import build_incident_draft
from booksaver.application.remote_auth import RemoteBrowserResult, RemoteBrowserWork
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomJourney,
    DomStepId,
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
from booksaver.domain.remote_auth import (
    RemoteAuthFailure,
    RemoteAuthServerVerification,
    RemoteAuthSettings,
    RemoteAuthStatus,
    SafeServerEvidence,
    ServerSessionProbeOutcome,
)
from booksaver.infrastructure.browser.playwright_adapter import new_mobile_context

from .network_session import (
    BookingServerSessionVerifier,
    CandidateSessionSnapshot,
    CandidateSnapshotStabilizer,
)

logger = logging.getLogger(__name__)

# `/connect` is deliberately not a DOM workflow.  The empty declaration keeps
# structural coverage explicit and prevents it from silently regaining one.
DOM_STEPS: tuple[DomStepId, ...] = ()

_LOGIN_URL = "https://account.booking.com/sign-in"
_BOOKING_HOST = "booking.com"
_MAX_TRANSIENT_COOKIE_FAILURES = 3


def _is_booking_navigation_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == _BOOKING_HOST or host.endswith(f".{_BOOKING_HOST}")


@dataclass(frozen=True)
class _RemoteBrowserExecution:
    result: RemoteBrowserResult
    incident_draft: IncidentDraft | None = None


ServerVerifierFactory = Callable[
    [Any, MobileWebSettings, Mapping[str, Any], RemoteBrowserWork],
    BookingServerSessionVerifier,
]
SourceUserResolver = Callable[[int], int | None]


class SystemRemoteBrowserRunner:
    """One transient headed Chromium + Xvfb/x11vnc/websockify stack.

    Authentication authority comes only from the isolated server verifier.
    The rendered page is never inspected for success and no model is available
    in this bounded context.  Child output is discarded so capability-bearing
    URLs and browser content cannot enter daemon logs.
    """

    def __init__(
        self,
        settings: RemoteAuthSettings,
        mobile_settings: MobileWebSettings,
        *,
        server_verifier_factory: ServerVerifierFactory | None = None,
        source_user_resolver: SourceUserResolver | None = None,
    ) -> None:
        self._settings = settings
        self._mobile_settings = mobile_settings
        self._server_verifier_factory = server_verifier_factory or self._default_verifier
        self._source_user_resolver = source_user_resolver

    @staticmethod
    def _default_verifier(
        browser: Any,
        mobile_settings: MobileWebSettings,
        descriptor: Mapping[str, Any],
        _work: RemoteBrowserWork,
    ) -> BookingServerSessionVerifier:
        return BookingServerSessionVerifier(browser, mobile_settings, descriptor)

    def run(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: Any,
        on_ready: Callable[[], None],
        on_finalizing: Callable[[], bool],
    ) -> RemoteBrowserResult:
        try:
            execution = self._run_browser(
                work,
                daemon_stop_event,
                on_ready,
                on_finalizing,
            )
        except Exception as exc:
            logger.warning(
                "Remote authentication verifier setup ended with %s",
                type(exc).__name__,
            )
            execution = _RemoteBrowserExecution(
                RemoteBrowserResult(
                    RemoteAuthStatus.FAILED,
                    failure=RemoteAuthFailure.SETUP_FAILED,
                )
            )

        # _run_browser closes Playwright and every display process before it
        # returns.  Only the sanitized draft crosses this boundary.
        if execution.incident_draft is None:
            return execution.result
        return replace(execution.result, incident_draft=execution.incident_draft)

    def _run_browser(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: Any,
        on_ready: Callable[[], None],
        on_finalizing: Callable[[], bool],
    ) -> _RemoteBrowserExecution:
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
                    f"{work.websocket_token}: 127.0.0.1:5900\n",
                    encoding="utf-8",
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
                    args=self._chromium_args(),
                )
                descriptor = playwright.devices[
                    self._mobile_settings.profile.playwright_device_name
                ]
                verifier = self._server_verifier_factory(
                    browser,
                    self._mobile_settings,
                    descriptor,
                    work,
                )
                baseline = verifier.establish_baseline()
                logger.info(
                    "Remote authentication server baseline ended as %s",
                    baseline.outcome.value,
                )
                if baseline.outcome is not ServerSessionProbeOutcome.SIGNED_OUT:
                    return self._failed_server_execution(work, baseline)

                context = new_mobile_context(browser, self._mobile_settings, dict(descriptor))
                context.set_default_timeout(5_000)
                self._secure_context(context)
                page = context.new_page()
                page.goto(_LOGIN_URL, timeout=45_000, wait_until="domcontentloaded")
                on_ready()

                stabilizer = CandidateSnapshotStabilizer()
                consecutive_cookie_failures = 0
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
                        snapshot = verifier.snapshot(context.cookies())
                        consecutive_cookie_failures = 0
                    except Exception as exc:
                        consecutive_cookie_failures += 1
                        logger.info(
                            "Remote authentication cookie observation ended after %s",
                            type(exc).__name__,
                        )
                        if consecutive_cookie_failures >= _MAX_TRANSIENT_COOKIE_FAILURES:
                            return _RemoteBrowserExecution(
                                RemoteBrowserResult(
                                    RemoteAuthStatus.FAILED,
                                    failure=RemoteAuthFailure.BROWSER_FAILED,
                                )
                            )
                        work.cancel_event.wait(1.0)
                        continue

                    if snapshot is not None and stabilizer.should_probe(snapshot):
                        verification = verifier.verify_candidate(
                            snapshot,
                            attempt_id=work.attempt_id,
                            telegram_user_id=work.telegram_user_id,
                        )
                        logger.info(
                            "Remote authentication server candidate ended as %s",
                            verification.outcome.value,
                        )
                        if verification.outcome is ServerSessionProbeOutcome.AUTHENTICATED:
                            return self._verified_execution(
                                verifier,
                                snapshot,
                                verification,
                                work,
                                on_finalizing,
                            )
                        if verification.outcome not in {
                            ServerSessionProbeOutcome.SIGNED_OUT,
                            ServerSessionProbeOutcome.CHALLENGE,
                        }:
                            return self._failed_server_execution(work, verification)
                        # Booking may promote an existing anonymous server
                        # session without changing its cookie bytes. Recheck
                        # the exact snapshot after a bounded quiet interval;
                        # the server contract, never cookie change, remains
                        # the authentication authority.
                        stabilizer.retry_later(snapshot)
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

    @staticmethod
    def _verified_execution(
        verifier: BookingServerSessionVerifier,
        snapshot: CandidateSessionSnapshot,
        verification: RemoteAuthServerVerification,
        work: RemoteBrowserWork,
        on_finalizing: Callable[[], bool],
    ) -> _RemoteBrowserExecution:
        receipt = verification.receipt
        if receipt is None or not verifier.consume_receipt(
            receipt,
            snapshot,
            attempt_id=work.attempt_id,
            telegram_user_id=work.telegram_user_id,
        ):
            return _RemoteBrowserExecution(
                RemoteBrowserResult(
                    RemoteAuthStatus.FAILED,
                    failure=RemoteAuthFailure.VERIFICATION_RECEIPT_REJECTED,
                )
            )
        return SystemRemoteBrowserRunner._finalized_success_execution(
            snapshot.persistence_json(),
            on_finalizing,
        )

    @staticmethod
    def _finalized_success_execution(
        cookies_json: str,
        on_finalizing: Callable[[], bool],
    ) -> _RemoteBrowserExecution:
        try:
            admitted = on_finalizing()
        except Exception as exc:
            logger.warning(
                "Remote authentication finalization admission ended with %s",
                type(exc).__name__,
            )
            return _RemoteBrowserExecution(
                RemoteBrowserResult(
                    RemoteAuthStatus.FAILED,
                    failure=RemoteAuthFailure.BROWSER_FAILED,
                )
            )
        if not admitted:
            logger.info("Remote authentication finalization cancelled before commit")
            return _RemoteBrowserExecution(RemoteBrowserResult(RemoteAuthStatus.CANCELLED))
        return _RemoteBrowserExecution(
            RemoteBrowserResult(
                RemoteAuthStatus.SUCCEEDED,
                cookies_json=cookies_json,
            )
        )

    def _failed_server_execution(
        self,
        work: RemoteBrowserWork,
        verification: RemoteAuthServerVerification,
    ) -> _RemoteBrowserExecution:
        failure = {
            ServerSessionProbeOutcome.CONTRACT_CHANGED: (
                RemoteAuthFailure.VERIFICATION_CONTRACT_CHANGED
            ),
            ServerSessionProbeOutcome.BLOCKED_REDIRECT: (RemoteAuthFailure.VERIFICATION_BLOCKED),
            ServerSessionProbeOutcome.UNAVAILABLE: RemoteAuthFailure.VERIFICATION_UNAVAILABLE,
            ServerSessionProbeOutcome.CHALLENGE: RemoteAuthFailure.VERIFICATION_UNAVAILABLE,
            ServerSessionProbeOutcome.AUTHENTICATED: (
                RemoteAuthFailure.VERIFICATION_CONTRACT_CHANGED
            ),
            ServerSessionProbeOutcome.SIGNED_OUT: RemoteAuthFailure.VERIFICATION_UNAVAILABLE,
        }[verification.outcome]
        draft = None
        if verification.outcome is ServerSessionProbeOutcome.CONTRACT_CHANGED:
            draft = self._contract_incident(work, verification.evidence)
        return _RemoteBrowserExecution(
            RemoteBrowserResult(RemoteAuthStatus.FAILED, failure=failure),
            incident_draft=draft,
        )

    def _contract_incident(
        self,
        work: RemoteBrowserWork,
        evidence: SafeServerEvidence,
    ) -> IncidentDraft | None:
        source_user_id = None
        if self._source_user_resolver is not None:
            try:
                source_user_id = self._source_user_resolver(work.telegram_user_id)
            except Exception:
                logger.warning("Remote authentication incident source resolution failed")
        diagnosis = TerminalBrowserDiagnosis(
            reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
            step_id=DomStepId.REMOTE_AUTH_SESSION_CAPTURE,
            provenance=DiagnosisProvenance.CODE_VERIFIER_DIAGNOSED,
            confidence=1.0,
            evidence=frozenset(),
            operator_action=operator_action_for_reason(
                TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED
            ),
            code_maintenance_required=True,
        )
        return build_incident_draft(
            journey=DomJourney.REMOTE_AUTH,
            diagnosis=diagnosis,
            verifier_category="remote_auth_server_contract_v2",
            structural_roles=(
                f"server_status.{evidence.status.value}",
                f"server_media.{evidence.media.value}",
                f"server_redirect.{evidence.redirect.value}",
                f"server_size.{evidence.size.value}",
            ),
            provider_state=IncidentProviderState.NOT_ATTEMPTED,
            budget_state=IncidentBudgetState.NOT_APPLICABLE,
            observed_at=datetime.now(UTC),
            source_user_ids=((source_user_id,) if source_user_id is not None else ()),
            action_outcomes=(("server_contract_changed",) if source_user_id is not None else ()),
        )

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
