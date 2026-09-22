"""Code-owned, bounded verification of saved mobile Booking.com sessions."""

from __future__ import annotations

import asyncio
import ctypes
import json
import math
import os
import pickle
import signal
import socket
import struct
import subprocess
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.session_maintenance import (
    SessionMaintenanceCleanupError,
    SessionVerificationOutcome,
    SessionVerificationResult,
)
from booksaver.infrastructure.browser.agentic_executor import CodeOwnedSessionBootstrap
from booksaver.infrastructure.remote_auth.network_session import (
    ACCOUNT_PROBE_URL,
    is_authenticated_account_probe_response,
)

_CHALLENGE_MARKERS = (
    b"cf-chl-", b"verify you are human", b"unusual traffic", b"px-captcha",
    b"challenge-platform",
)
_MAX_RESPONSE_BYTES = 2_000_000


def classify_account_response(
    *, status: int, headers: Mapping[str, str], response_url: str, body: bytes,
) -> SessionVerificationOutcome:
    """Only the fixed server contract proves authentication or confirmed sign-out."""
    retry = SessionVerificationOutcome.RETRY_LATER
    normalized = {key.casefold(): value for key, value in headers.items()}
    try:
        source = urlsplit(response_url)
        if (source.scheme != "https" or source.hostname != "secure.booking.com"
            or source.path != "/myaccount.html" or source.query or source.fragment
            or source.username is not None or source.password is not None
            or source.port is not None):
            return retry
    except ValueError:
        return retry
    if len(body) > _MAX_RESPONSE_BYTES or any(
        marker in body.lower() for marker in _CHALLENGE_MARKERS
    ):
        return retry
    media = normalized.get("content-type", "").split(";", 1)[0].strip().casefold()
    if status == 302 and media == "text/html":
        try:
            target = urlsplit(urljoin(ACCOUNT_PROBE_URL, normalized.get("location", "")))
            if (target.scheme == "https" and target.hostname == "account.booking.com"
                and target.path == "/auth/oauth2" and target.username is None
                and target.password is None and target.port is None and not target.fragment):
                return SessionVerificationOutcome.SIGNED_OUT
        except ValueError:
            return retry
    if is_authenticated_account_probe_response(
        status=status, headers=normalized, response_url=response_url, body=body,
    ):
        return SessionVerificationOutcome.AUTHENTICATED
    # In particular, the anonymous 202 edge-pending tuple does not prove revocation.
    return retry


def unexpired_cookie_material(data: bytes, *, now: datetime | None = None) -> bytes:
    """Drop expired individual cookies without rewriting any provider expiry value."""
    instant = (now or datetime.now(UTC)).timestamp()
    cookies = CodeOwnedSessionBootstrap._decode_cookies(data)
    retained = []
    for cookie in cookies:
        expiry = cookie.get("expires", -1)
        if isinstance(expiry, bool) or not isinstance(expiry, (int, float)):
            raise ValueError("session cookie expiry must be numeric")
        if not math.isfinite(expiry):
            raise ValueError("session cookie expiry must be finite")
        if expiry == -1 or expiry > instant:
            retained.append(cookie)
    return json.dumps(retained, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def _canonical_material(cookies: list[dict[str, Any]]) -> bytes:
    ordered = sorted(cookies, key=lambda item: (
        str(item.get("domain", "")), str(item.get("path", "/")),
        str(item.get("name", "")), str(item.get("partitionKey", "")),
    ))
    return json.dumps(ordered, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


async def _probe_context(
    browser: Any, options: dict[str, Any], material: bytes | None, deadline: float,
) -> tuple[SessionVerificationOutcome, bool, bytes | None]:
    """One fixed GET in a new context; return only closed evidence and local cookie bytes."""
    context = await browser.new_context(**options)
    try:
        if material is not None:
            await context.add_cookies(json.loads(material))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        response = await context.request.get(
            ACCOUNT_PROBE_URL, max_redirects=0, fail_on_status_code=False,
            timeout=min(15_000, max(1, int(remaining * 1_000))),
        )
        try:
            headers = {str(k).casefold(): str(v) for k, v in response.headers.items()}
            declared_size = headers.get("content-length")
            if declared_size is not None and int(declared_size) > _MAX_RESPONSE_BYTES:
                return SessionVerificationOutcome.RETRY_LATER, False, None
            body = await response.body()
            outcome = classify_account_response(
                status=response.status, headers=headers, response_url=response.url, body=body,
            )
            pending_negative = (
                response.status == 202 and not body and response.url == ACCOUNT_PROBE_URL
                and headers.get("content-type", "").split(";", 1)[0].strip().casefold()
                == "text/html" and "location" not in headers
            )
            captured = (
                _canonical_material(await context.cookies())
                if outcome is SessionVerificationOutcome.AUTHENTICATED else None
            )
            return outcome, pending_negative, captured
        finally:
            await response.dispose()
    except Exception:
        return SessionVerificationOutcome.RETRY_LATER, False, None
    finally:
        await asyncio.wait_for(context.close(), timeout=max(0.1, min(
            1.0, deadline - time.monotonic(),
        )))


async def verify_saved_snapshot(
    browser: Any, options: dict[str, Any], material: bytes, deadline: float,
) -> SessionVerificationResult:
    """At most two attempts, each one negative control and two immutable positive probes."""
    candidate = _canonical_material(json.loads(unexpired_cookie_material(material)))
    if candidate == b"[]":
        return SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)
    for attempt in range(2):
        negative, pending, _ = await _probe_context(browser, options, None, deadline)
        if negative is not SessionVerificationOutcome.SIGNED_OUT and not pending:
            continue
        last_cookies: bytes | None = None
        for _ in range(2):
            outcome, _, last_cookies = await _probe_context(browser, options, candidate, deadline)
            if outcome is SessionVerificationOutcome.SIGNED_OUT:
                return SessionVerificationResult(outcome)
            if outcome is not SessionVerificationOutcome.AUTHENTICATED:
                break
        else:
            # Persist only exact bytes that passed both independent probes. A renewed
            # candidate needs the second complete attempt; later rotations are ignored.
            if attempt == 0 and last_cookies is not None and last_cookies != candidate:
                candidate = _canonical_material(json.loads(unexpired_cookie_material(last_cookies)))
                if candidate == b"[]":
                    return SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)
                continue
            return SessionVerificationResult(
                SessionVerificationOutcome.AUTHENTICATED,
                cookies=candidate, verified_at=datetime.now(UTC),
            )
    return SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)


def _process_identity(pid: int) -> tuple[int, int, str] | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[1]), int(fields[19]), fields[0]
    except (OSError, ValueError, IndexError):
        return None


def _descendants(root: int) -> dict[int, tuple[int, int, str]]:
    processes = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            info = _process_identity(int(entry.name))
            if info is not None:
                processes[int(entry.name)] = info
    selected = {root}
    while True:
        discovered = {pid for pid, info in processes.items() if info[0] in selected}
        expanded = selected | discovered
        if expanded == selected:
            return {pid: processes[pid] for pid in selected if pid in processes}
        selected = expanded


def _signal_exact(pid: int, identity: tuple[int, int, str], action: int) -> None:
    try:
        descriptor = int(getattr(os, "pidfd_open")(pid))
    except ProcessLookupError:
        return
    try:
        current = _process_identity(pid)
        if current is not None and current[1] == identity[1] and current[2] != "Z":
            # pidfd prevents reuse between checking start ticks and delivering the signal.
            try:
                getattr(signal, "pidfd_send_signal")(descriptor, action)
            except ProcessLookupError:
                pass
    finally:
        os.close(descriptor)


def _terminate_owned_worker(
    process: subprocess.Popen[bytes], identity: tuple[int, int, str], deadline: float,
) -> bool:
    """Freeze a subreaper's exact tree before killing it, including detached groups."""
    current = _process_identity(process.pid)
    if current is None or current[1] != identity[1] or current[2] == "Z":
        # The subreaper must remain alive until supervision completes. Its unexpected
        # death makes descendant ownership uncertain; the coordinator stops admission.
        return False
    known = {process.pid: identity}
    _signal_exact(process.pid, identity, signal.SIGSTOP)
    while time.monotonic() < deadline:
        descendants = _descendants(process.pid)
        known.update(descendants)
        for pid, info in known.items():
            _signal_exact(pid, info, signal.SIGSTOP)
        time.sleep(0.01)
        fresh = _descendants(process.pid)
        if set(fresh) <= set(known) and all(
            info[2] in {"T", "t", "Z"} for info in fresh.values()
        ):
            break
    else:
        return False
    # Children cannot fork while stopped, and their orphaned descendants remain
    # attached to the still-living subreaper. Match start ticks before each signal.
    for pid, info in known.items():
        if pid != process.pid:
            _signal_exact(pid, info, signal.SIGKILL)
    _signal_exact(process.pid, identity, signal.SIGKILL)
    try:
        process.wait(timeout=max(0.01, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        return False
    while time.monotonic() < deadline:
        if all(
            (current := _process_identity(pid)) is None
            or current[1] != info[1] or current[2] == "Z"
            for pid, info in known.items()
        ):
            return True
        time.sleep(0.01)
    return False


def _send_message(channel: socket.socket, value: Any, deadline: float) -> None:
    data = pickle.dumps(value, protocol=5)
    if len(data) > 2_000_000:
        raise ValueError("maintenance message exceeds bound")
    channel.settimeout(max(0.001, deadline - time.monotonic()))
    channel.sendall(struct.pack("!I", len(data)) + data)


def _receive_message(channel: socket.socket, deadline: float) -> Any:
    def receive(size: int) -> bytes:
        value = bytearray()
        while len(value) < size:
            channel.settimeout(max(0.001, deadline - time.monotonic()))
            part = channel.recv(size - len(value))
            if not part:
                raise EOFError
            value.extend(part)
        return bytes(value)
    length = struct.unpack("!I", receive(4))[0]
    if length > 2_000_000:
        raise ValueError("maintenance message exceeds bound")
    # This socket connects only this process and its owned local worker.
    return pickle.loads(receive(length))


async def _verify_in_worker(
    cookies: bytes, settings: MobileWebSettings, deadline: float,
) -> SessionVerificationResult:
    from playwright.async_api import async_playwright

    playwright: Any = None
    browser: Any = None
    try:
        async with asyncio.timeout(max(0.001, deadline - time.monotonic())):
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            descriptor = playwright.devices[settings.profile.playwright_device_name]
            options = settings.context_options(descriptor)
            options.update(accept_downloads=False, service_workers="block")
            return await verify_saved_snapshot(browser, options, cookies, deadline)
    finally:
        # The supervisor retains the gate while this runs. A stuck close is killed
        # along with the exact owned process tree before any result can return.
        try:
            if browser is not None:
                await browser.close()
        finally:
            if playwright is not None:
                await playwright.stop()


def _worker_main(fd: int) -> None:
    with socket.socket(fileno=fd) as channel:
        try:
            # PR_SET_CHILD_SUBREAPER: detached grandchildren stay owned if their
            # intermediary exits, so cleanup never relies only on a process group.
            if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
                raise OSError("subreaper unavailable")
            _send_message(channel, "ready", time.monotonic() + 60)
            cookies, settings, deadline = _receive_message(channel, time.monotonic() + 60)
            try:
                result = asyncio.run(_verify_in_worker(cookies, settings, deadline))
            except BaseException:
                result = SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)
            _send_message(channel, result, deadline)
        except BaseException:
            pass
        # Remain the descendant owner until the supervisor terminates the tree.
        # Even startup/probe/cleanup exceptions cannot orphan browser processes.
        channel.settimeout(None)
        try:
            channel.recv(1)
        except OSError:
            pass


class BrowserSessionMaintenance:
    """One supervised Linux worker, no persistent thread, and no model calls."""

    def __init__(self, mobile_settings: MobileWebSettings | None = None) -> None:
        self._settings = mobile_settings or MobileWebSettings()

    @staticmethod
    def is_supported() -> bool:
        if (sys.platform != "linux" or not Path("/proc/self/stat").is_file()
            or not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal")):
            return False
        try:
            descriptor = int(getattr(os, "pidfd_open")(os.getpid()))
            os.close(descriptor)
            return True
        except OSError:
            return False

    def verify(self, cookies: bytes, deadline: datetime) -> SessionVerificationResult:
        retry = SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)
        stop_at = time.monotonic() + min(60.0, (deadline - datetime.now(UTC)).total_seconds())
        work_deadline = stop_at - 5.0
        if not self.is_supported() or work_deadline <= time.monotonic():
            return retry
        parent, child = socket.socketpair()
        process: subprocess.Popen[bytes] | None = None
        identity: tuple[int, int, str] | None = None
        admitted = False
        try:
            environment = {key: os.environ[key] for key in (
                "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "PLAYWRIGHT_BROWSERS_PATH",
            ) if key in os.environ}
            environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[3])
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            process = subprocess.Popen(
                [sys.executable, "-m", __name__, "--worker", str(child.fileno())],
                pass_fds=(child.fileno(),), start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=environment,
            )
            identity = _process_identity(process.pid)
            child.close()
            if identity is None:
                raise SessionMaintenanceCleanupError("maintenance ownership unavailable")
            if _receive_message(parent, work_deadline) != "ready":
                return retry
            admitted = True
            _send_message(parent, (cookies, self._settings, work_deadline), work_deadline)
            result = _receive_message(parent, work_deadline)
            return result if isinstance(result, SessionVerificationResult) else retry
        except SessionMaintenanceCleanupError:
            raise
        except Exception:
            return retry
        finally:
            try:
                if process is not None and not admitted and process.poll() is not None:
                    # The worker cannot start a browser until it receives our input.
                    process.wait()
                elif process is not None:
                    try:
                        confirmed = identity is not None and _terminate_owned_worker(
                            process, identity, stop_at,
                        )
                    except Exception:
                        confirmed = False
                    if not confirmed:
                        raise SessionMaintenanceCleanupError("maintenance cleanup unconfirmed")
            finally:
                parent.close()
                child.close()

    def close(self) -> None:
        """No persistent worker or event-loop thread is retained between calls."""


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        _worker_main(int(sys.argv[2]))
