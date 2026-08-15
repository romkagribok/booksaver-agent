from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

from booksaver.domain.dom_incident import IncidentDraft
from booksaver.domain.remote_auth import (
    AttemptLaunch,
    RemoteAuthFailure,
    RemoteAuthSettings,
    RemoteAuthStatus,
    ViewerGrant,
    ViewerState,
)

if TYPE_CHECKING:
    from booksaver.domain.browser_resilience import TerminalBrowserDiagnosis


logger = logging.getLogger(__name__)


class RemoteAuthError(RuntimeError):
    """Safe-to-display remote-auth application error."""


class RemoteAuthBusy(RemoteAuthError):
    pass


class RemoteAuthUnavailable(RemoteAuthError):
    pass


class RemoteAuthDenied(RemoteAuthError):
    pass


@dataclass(frozen=True)
class RemoteBrowserWork:
    attempt_id: str
    telegram_user_id: int
    websocket_token: str
    expires_at: datetime
    cancel_event: threading.Event


@dataclass(frozen=True)
class RemoteBrowserResult:
    status: RemoteAuthStatus
    cookies_json: str | None = None
    failure: RemoteAuthFailure | None = None
    terminal_diagnosis: TerminalBrowserDiagnosis | None = None
    incident_draft: IncidentDraft | None = None

    def __post_init__(self) -> None:
        if not self.status.is_terminal:
            raise ValueError("Remote browser result must be terminal")
        if self.status is RemoteAuthStatus.SUCCEEDED and self.cookies_json is None:
            raise ValueError("Successful remote browser result requires cookies")
        if self.status is not RemoteAuthStatus.SUCCEEDED and self.cookies_json is not None:
            raise ValueError("Only successful remote browser results may contain cookies")
        if self.status is not RemoteAuthStatus.FAILED and self.terminal_diagnosis is not None:
            raise ValueError("Only failed remote browser results may carry a terminal diagnosis")
        if self.incident_draft is not None and self.status not in {
            RemoteAuthStatus.SUCCEEDED,
            RemoteAuthStatus.FAILED,
        }:
            raise ValueError("Only successful or failed results may carry an incident draft")


class RemoteBrowserRunner(Protocol):
    def run(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: threading.Event,
        on_ready: Callable[[], None],
        on_finalizing: Callable[[], bool],
    ) -> RemoteBrowserResult: ...


CaptureSession = Callable[[int, str], Any]
NotifyUser = Callable[[int, str], None]
SuccessfulConnection = Callable[[int], None]
IncidentSink = Callable[[IncidentDraft], None]
Clock = Callable[[], datetime]
_FINALIZATION_RESULT_RETENTION = timedelta(seconds=30)


class _FailureIncidentPolicy(Enum):
    PUBLISH = "publish"
    SUPPRESS_PRIVACY_ERASURE = "suppress_privacy_erasure"
    SUPPRESS_SHUTDOWN = "suppress_shutdown"


@dataclass
class _Attempt:
    attempt_id: str
    telegram_user_id: int
    chat_id: int
    launch_digest: bytes
    websocket_token: str
    created_at: datetime
    expires_at: datetime
    status: RemoteAuthStatus = RemoteAuthStatus.STARTING
    viewer_digest: bytes | None = None
    failure: RemoteAuthFailure | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    worker: threading.Thread | None = None
    suppress_cancel_notification: bool = False
    failure_incident_policy: _FailureIncidentPolicy = _FailureIncidentPolicy.PUBLISH


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


class RemoteAuthenticationManager:
    """In-memory, single-browser remote-auth aggregate coordinator.

    Launch/viewer/WebSocket capabilities are never persisted. Only SHA-256
    digests of HTTP capabilities are retained after they are handed to the
    caller; the WebSocket token remains in memory only while the browser is
    active because noVNC must present it to websockify.
    """

    def __init__(
        self,
        settings: RemoteAuthSettings,
        runner: RemoteBrowserRunner,
        daemon_stop_event: threading.Event,
        capture_session: CaptureSession,
        notify_user: NotifyUser,
        *,
        on_success: SuccessfulConnection | None = None,
        clock: Clock | None = None,
        browser_gate: threading.Lock | None = None,
        replacement_join_timeout: float = 5.0,
        incident_sink: IncidentSink | None = None,
    ) -> None:
        self._settings = settings
        self._runner = runner
        self._daemon_stop_event = daemon_stop_event
        self._capture_session = capture_session
        self._notify_user = notify_user
        self._on_success = on_success or (lambda _user_id: None)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._browser_gate = browser_gate or threading.Lock()
        self._replacement_join_timeout = max(0.0, replacement_join_timeout)
        self._incident_sink = incident_sink
        self._create_lock = threading.Lock()
        self._lock = threading.RLock()
        self._attempts: dict[str, _Attempt] = {}
        self._launch_index: dict[bytes, str] = {}
        self._viewer_index: dict[bytes, str] = {}
        self._active_attempt_id: str | None = None
        self._replacement_attempt_id: str | None = None

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def create(self, telegram_user_id: int, chat_id: int) -> AttemptLaunch:
        if not self._settings.enabled:
            raise RemoteAuthUnavailable("Booking.com connection is not configured yet.")
        if self._daemon_stop_event.is_set():
            raise RemoteAuthUnavailable("BookSaver is shutting down; try again after restart.")
        with self._create_lock:
            return self._create_serialized(telegram_user_id, chat_id)

    def _create_serialized(self, telegram_user_id: int, chat_id: int) -> AttemptLaunch:
        replacement_id: str | None = None
        replacement_worker: threading.Thread | None = None
        with self._lock:
            if self._daemon_stop_event.is_set():
                raise RemoteAuthUnavailable("BookSaver is shutting down; try again after restart.")
            now = self._clock()
            self._expire_locked(now)
            if self._active_attempt_id is not None:
                active = self._attempts[self._active_attempt_id]
                if active.telegram_user_id != telegram_user_id:
                    raise RemoteAuthBusy(
                        "Another Booking.com login is currently active. Try again in a few minutes."
                    )
                if active.status is RemoteAuthStatus.FINALIZING:
                    raise RemoteAuthBusy(
                        "Your Booking.com login is being saved. Return to the open "
                        "connection window for the result."
                    )
                replacement_id = active.attempt_id
                replacement_worker = active.worker
                self._replacement_attempt_id = active.attempt_id
                active.suppress_cancel_notification = True
                if not active.status.is_terminal:
                    active.status = RemoteAuthStatus.CANCELLED
                    active.cancel_event.set()
            else:
                return self._start_attempt_locked(telegram_user_id, chat_id, now)

        if replacement_worker is not None:
            replacement_worker.join(timeout=self._replacement_join_timeout)

        with self._lock:
            assert replacement_id is not None
            if self._active_attempt_id == replacement_id:
                if self._replacement_attempt_id == replacement_id:
                    # The old worker still owns the gate and will release it.
                    self._replacement_attempt_id = None
                raise RemoteAuthBusy(
                    "Your previous Booking.com login is still closing. "
                    "Send /connect again in a few seconds."
                )

            gate_reserved = self._replacement_attempt_id == replacement_id
            if gate_reserved:
                self._replacement_attempt_id = None
            if self._daemon_stop_event.is_set():
                if gate_reserved:
                    self._browser_gate.release()
                raise RemoteAuthUnavailable("BookSaver is shutting down; try again after restart.")
            return self._start_attempt_locked(
                telegram_user_id,
                chat_id,
                self._clock(),
                gate_already_acquired=gate_reserved,
            )

    def _start_attempt_locked(
        self,
        telegram_user_id: int,
        chat_id: int,
        now: datetime,
        *,
        gate_already_acquired: bool = False,
    ) -> AttemptLaunch:
        if not gate_already_acquired and not self._browser_gate.acquire(blocking=False):
            raise RemoteAuthBusy(
                "A price check or Booking.com login is already running. Try again shortly."
            )
        launch_token = secrets.token_urlsafe(32)
        websocket_token = secrets.token_urlsafe(32)
        attempt = _Attempt(
            attempt_id=str(uuid.uuid4()),
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            launch_digest=_digest(launch_token),
            websocket_token=websocket_token,
            created_at=now,
            expires_at=now + timedelta(seconds=self._settings.session_timeout_seconds),
        )
        self._attempts[attempt.attempt_id] = attempt
        self._launch_index[attempt.launch_digest] = attempt.attempt_id
        self._active_attempt_id = attempt.attempt_id
        worker = threading.Thread(
            target=self._run_attempt,
            args=(attempt.attempt_id,),
            name=f"booksaver-auth-{attempt.attempt_id[:8]}",
            daemon=True,
        )
        attempt.worker = worker
        try:
            worker.start()
        except Exception:
            self._active_attempt_id = None
            self._attempts.pop(attempt.attempt_id, None)
            self._launch_index.pop(attempt.launch_digest, None)
            self._browser_gate.release()
            raise
        return AttemptLaunch(
            url=f"{self._settings.base_url}/connect/{launch_token}",
            expires_at=attempt.expires_at,
        )

    def expected_telegram_user(self, launch_token: str) -> int:
        now = self._clock()
        with self._lock:
            attempt = self._attempt_for_launch_locked(launch_token, now)
            return attempt.telegram_user_id

    def exchange(self, launch_token: str, telegram_user_id: int) -> ViewerGrant:
        now = self._clock()
        with self._lock:
            attempt = self._attempt_for_launch_locked(launch_token, now)
            if attempt.telegram_user_id != telegram_user_id:
                raise RemoteAuthDenied("This connection link is not available.")
            viewer_token = secrets.token_urlsafe(32)
            viewer_digest = _digest(viewer_token)
            attempt.viewer_digest = viewer_digest
            self._viewer_index[viewer_digest] = attempt.attempt_id
            self._launch_index.pop(attempt.launch_digest, None)
            attempt.launch_digest = b""
            return ViewerGrant(viewer_token, attempt.expires_at)

    def viewer_state(self, session_token: str) -> ViewerState:
        now = self._clock()
        with self._lock:
            attempt = self._attempt_for_viewer_locked(session_token, now)
            websocket_token: str | None = None
            websocket_path: str | None = None
            if attempt.status in {RemoteAuthStatus.READY, RemoteAuthStatus.CONNECTED}:
                attempt.status = RemoteAuthStatus.CONNECTED
                websocket_token = attempt.websocket_token
                websocket_path = "/websockify"
            return ViewerState(
                status=attempt.status,
                expires_at=attempt.expires_at,
                websocket_path=websocket_path,
                websocket_token=websocket_token,
                message=self._viewer_message(attempt),
            )

    def cancel(self, session_token: str) -> bool:
        now = self._clock()
        with self._lock:
            attempt = self._attempt_for_viewer_locked(session_token, now)
            if attempt.status.is_terminal or attempt.status is RemoteAuthStatus.FINALIZING:
                return False
            attempt.status = RemoteAuthStatus.CANCELLED
            attempt.cancel_event.set()
            return True

    def cancel_for_telegram_user(self, telegram_user_id: int) -> bool:
        """Cancel a user's active login without requiring its viewer capability.

        The manager lock also guards successful session capture. A confirmed
        purge can therefore establish cancellation before capture, or observe
        that capture already completed and delete the resulting session next.
        Browser teardown remains the worker's responsibility.
        """
        with self._lock:
            cancelled = False
            for attempt in self._attempts.values():
                if attempt.telegram_user_id == telegram_user_id and not attempt.status.is_terminal:
                    attempt.failure_incident_policy = (
                        _FailureIncidentPolicy.SUPPRESS_PRIVACY_ERASURE
                    )
                    attempt.status = RemoteAuthStatus.CANCELLED
                    attempt.cancel_event.set()
                    cancelled = True
            return cancelled

    def stop_all(self, join_timeout: float = 10.0) -> None:
        with self._create_lock:
            with self._lock:
                workers = []
                for attempt in self._attempts.values():
                    if not attempt.status.is_terminal:
                        if attempt.failure_incident_policy is _FailureIncidentPolicy.PUBLISH:
                            attempt.failure_incident_policy = (
                                _FailureIncidentPolicy.SUPPRESS_SHUTDOWN
                            )
                        attempt.status = RemoteAuthStatus.CANCELLED
                        attempt.cancel_event.set()
                    if attempt.worker is not None and attempt.worker.is_alive():
                        workers.append(attempt.worker)
            for worker in workers:
                worker.join(timeout=join_timeout)

    def _run_attempt(self, attempt_id: str) -> None:
        with self._lock:
            attempt = self._attempts[attempt_id]
            work = RemoteBrowserWork(
                attempt_id=attempt.attempt_id,
                telegram_user_id=attempt.telegram_user_id,
                websocket_token=attempt.websocket_token,
                expires_at=attempt.expires_at,
                cancel_event=attempt.cancel_event,
            )

        def _ready() -> None:
            with self._lock:
                current = self._attempts.get(attempt_id)
                if current is not None and current.status is RemoteAuthStatus.STARTING:
                    current.status = RemoteAuthStatus.READY

        def _finalizing() -> bool:
            with self._lock:
                current = self._attempts.get(attempt_id)
                if current is None or current.status not in {
                    RemoteAuthStatus.READY,
                    RemoteAuthStatus.CONNECTED,
                }:
                    return False
                if (
                    current.cancel_event.is_set()
                    or self._daemon_stop_event.is_set()
                    or self._clock() >= current.expires_at
                ):
                    return False
                current.status = RemoteAuthStatus.FINALIZING
                logger.info("Remote authentication finalization started")
                return True

        try:
            result = self._runner.run(
                work,
                self._daemon_stop_event,
                _ready,
                _finalizing,
            )
        except Exception as exc:
            logger.warning(
                "Remote authentication runner ended with %s",
                type(exc).__name__,
            )
            result = RemoteBrowserResult(
                RemoteAuthStatus.FAILED,
                failure=RemoteAuthFailure.BROWSER_FAILED,
            )

        with self._lock:
            attempt = self._attempts[attempt_id]
            if (
                self._daemon_stop_event.is_set()
                and attempt.failure_incident_policy is _FailureIncidentPolicy.PUBLISH
            ):
                attempt.failure_incident_policy = _FailureIncidentPolicy.SUPPRESS_SHUTDOWN
            if not attempt.status.is_terminal:
                if result.status is RemoteAuthStatus.SUCCEEDED:
                    cookies_json = result.cookies_json
                    assert cookies_json is not None
                    if attempt.status is not RemoteAuthStatus.FINALIZING:
                        result = RemoteBrowserResult(
                            RemoteAuthStatus.FAILED,
                            failure=RemoteAuthFailure.BROWSER_FAILED,
                        )
                    else:
                        try:
                            # Persistence and the terminal transition are one critical
                            # section. A concurrent cancel can therefore either win
                            # before capture (and prevent it) or observe success after
                            # capture, but can never produce cancelled-and-persisted.
                            self._capture_session(work.telegram_user_id, cookies_json)
                        except Exception as exc:  # redact message and values
                            logger.warning(
                                "Remote authentication finalization capture rejected with %s",
                                type(exc).__name__,
                            )
                            result = RemoteBrowserResult(
                                RemoteAuthStatus.FAILED,
                                failure=RemoteAuthFailure.CAPTURE_REJECTED,
                            )
                        else:
                            self._safe_record_incident(result.incident_draft)
                            logger.info("Remote authentication finalization succeeded")
                if result.status.is_terminal:
                    attempt.expires_at = max(
                        attempt.expires_at,
                        self._clock() + _FINALIZATION_RESULT_RETENTION,
                    )
                attempt.status = result.status
                attempt.failure = result.failure
            # A failure draft was prepared while the browser page still existed. Preserve it
            # after ordinary viewer/expiry races, but never recreate evidence after privacy
            # erasure or during daemon shutdown. This remains under the lifecycle lock so purge
            # either suppresses publication first or deletes an occurrence published first.
            if (
                result.status is RemoteAuthStatus.FAILED
                and attempt.failure_incident_policy is _FailureIncidentPolicy.PUBLISH
            ):
                self._safe_record_incident(result.incident_draft)
            self._release_active_locked(attempt)
            telegram_user_id = attempt.telegram_user_id
            chat_id = attempt.chat_id
            status = attempt.status

        if status is RemoteAuthStatus.SUCCEEDED:
            self._on_success(telegram_user_id)
            self._safe_notify(
                chat_id,
                "Booking.com connected successfully. Future checks will use your "
                "authenticated mobile-web prices.",
            )
        elif status is RemoteAuthStatus.EXPIRED:
            self._safe_notify(
                chat_id,
                "Booking.com connection timed out. Send /connect when you're ready to try again.",
            )
        elif status is RemoteAuthStatus.FAILED:
            if attempt.failure is RemoteAuthFailure.CAPTURE_REJECTED:
                self._safe_notify(
                    chat_id,
                    "Booking.com authentication was verified, but BookSaver could not save "
                    "the session. No session was replaced. Send /connect to retry.",
                )
            else:
                self._safe_notify(
                    chat_id,
                    "Booking.com connection failed and no session was saved. "
                    "Send /connect to retry.",
                )
        elif (
            status is RemoteAuthStatus.CANCELLED
            and not attempt.suppress_cancel_notification
            and not self._daemon_stop_event.is_set()
        ):
            self._safe_notify(chat_id, "Booking.com connection cancelled.")

    def _attempt_for_launch_locked(self, token: str, now: datetime) -> _Attempt:
        self._expire_locked(now)
        digest = _digest(token)
        attempt_id = self._launch_index.get(digest)
        if attempt_id is None:
            raise RemoteAuthDenied("This connection link is invalid or expired.")
        attempt = self._attempts[attempt_id]
        if attempt.status.is_terminal or now >= attempt.expires_at:
            raise RemoteAuthDenied("This connection link is invalid or expired.")
        return attempt

    def _attempt_for_viewer_locked(self, token: str, now: datetime) -> _Attempt:
        self._expire_locked(now)
        digest = _digest(token)
        attempt_id = self._viewer_index.get(digest)
        if attempt_id is None:
            raise RemoteAuthDenied("This connection session is invalid or expired.")
        attempt = self._attempts[attempt_id]
        if not hmac.compare_digest(attempt.viewer_digest or b"", digest):
            raise RemoteAuthDenied("This connection session is invalid or expired.")
        return attempt

    def _expire_locked(self, now: datetime) -> None:
        stale: list[str] = []
        for attempt_id, attempt in self._attempts.items():
            if (
                not attempt.status.is_terminal
                and attempt.status is not RemoteAuthStatus.FINALIZING
                and now >= attempt.expires_at
            ):
                attempt.status = RemoteAuthStatus.EXPIRED
                attempt.cancel_event.set()
                continue
            if (
                attempt.status.is_terminal
                and now >= attempt.expires_at
                and self._active_attempt_id != attempt_id
                and (attempt.worker is None or not attempt.worker.is_alive())
            ):
                stale.append(attempt_id)
        for attempt_id in stale:
            attempt = self._attempts.pop(attempt_id)
            self._launch_index.pop(attempt.launch_digest, None)
            if attempt.viewer_digest is not None:
                self._viewer_index.pop(attempt.viewer_digest, None)

    def _release_active_locked(self, attempt: _Attempt) -> None:
        if self._active_attempt_id == attempt.attempt_id:
            self._active_attempt_id = None
            if self._replacement_attempt_id != attempt.attempt_id:
                self._browser_gate.release()
        if attempt.status.is_terminal:
            attempt.websocket_token = ""
            self._launch_index.pop(attempt.launch_digest, None)

    @staticmethod
    def _viewer_message(attempt: _Attempt) -> str:
        if attempt.status is RemoteAuthStatus.STARTING:
            return "Starting the secure Booking.com browser…"
        if attempt.status in {RemoteAuthStatus.READY, RemoteAuthStatus.CONNECTED}:
            return (
                "Sign in below with your Booking.com email and password. Google, Apple, "
                "and other external providers are disabled. This window closes after "
                "authentication."
            )
        if attempt.status is RemoteAuthStatus.FINALIZING:
            return "Authentication verified; saving the Booking.com session…"
        if attempt.status is RemoteAuthStatus.SUCCEEDED:
            return "Connected. You can return to Telegram."
        if attempt.status is RemoteAuthStatus.EXPIRED:
            return "This connection timed out. Return to Telegram and send /connect again."
        if attempt.status is RemoteAuthStatus.CANCELLED:
            return "This connection was cancelled."
        if attempt.failure is RemoteAuthFailure.CAPTURE_REJECTED:
            return (
                "Authentication was verified, but BookSaver could not save the session. "
                "Return to Telegram and send /connect to retry."
            )
        return "Connection failed. No Booking.com session was saved."

    def _safe_record_incident(self, draft: IncidentDraft | None) -> None:
        if draft is None or self._incident_sink is None:
            return
        try:
            self._incident_sink(draft)
        except Exception:
            logger.warning("Remote authentication finalization incident recording failed")

    def _safe_notify(self, chat_id: int, message: str) -> None:
        try:
            self._notify_user(chat_id, message)
        except Exception:
            pass
