from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from booksaver.domain.session_maintenance import SessionMaintenanceCleanupError
from booksaver.domain.session_maintenance import SessionVerificationOutcome as Outcome
from booksaver.infrastructure.browser import session_maintenance as adapter

URL = "https://secure.booking.com/myaccount.html"
NOW = datetime.now(UTC)


def cookie(value="original", *, expires=-1):
    return {"name": "auth", "value": value, "domain": ".booking.com", "path": "/",
            "expires": expires, "httpOnly": True, "secure": True, "sameSite": "Lax"}


def material(*cookies):
    return json.dumps(cookies).encode()


@pytest.mark.parametrize("status,headers,body,url,expected", [
    (200, {"content-type": "text/html"}, b"account", URL, Outcome.AUTHENTICATED),
    (202, {"content-type": "text/html"}, b"", URL, Outcome.RETRY_LATER),
    (202, {"content-type": "text/html"}, b"account", URL, Outcome.RETRY_LATER),
    (429, {"content-type": "text/html"}, b"", URL, Outcome.RETRY_LATER),
    (503, {"content-type": "text/html"}, b"", URL, Outcome.RETRY_LATER),
    (200, {"content-type": "text/html"}, b"Verify you are human", URL, Outcome.RETRY_LATER),
    (200, {"content-type": "text/html"}, b"", URL, Outcome.RETRY_LATER),
    (200, {"content-type": "application/json"}, b"account", URL, Outcome.RETRY_LATER),
    (200, {"content-type": "text/html"}, b"account", URL + "?next=1", Outcome.RETRY_LATER),
    (200, {"content-type": "text/html"}, b"account", "https://secure.booking.com:443/myaccount.html",
     Outcome.RETRY_LATER),
    (302, {"content-type": "text/html",
           "location": "https://account.booking.com/auth/oauth2?state=private"},
     b"redirect", URL, Outcome.SIGNED_OUT),
    (302, {"content-type": "text/html",
           "location": "https://account.booking.com/auth/oauth2?state=private"},
     b"px-captcha", URL, Outcome.RETRY_LATER),
    (302, {"content-type": "text/html", "location": "https://account.booking.com/sign-in"},
     b"redirect", URL, Outcome.RETRY_LATER),
    (302, {"content-type": "text/html", "location": "https://outside.example/auth/oauth2"},
     b"redirect", URL, Outcome.RETRY_LATER),
    (302, {"content-type": "text/html",
           "location": "https://user:secret@account.booking.com/auth/oauth2"},
     b"redirect", URL, Outcome.RETRY_LATER),
])
def test_response_classification_never_infers_signout_from_uncertainty(
    status, headers, body, url, expected,
):
    assert adapter.classify_account_response(
        status=status, headers=headers, response_url=url, body=body,
    ) is expected


def test_expired_cookie_filter_keeps_provider_values_and_session_cookies():
    surviving = [cookie("future", expires=NOW.timestamp() + 100), cookie("session")]
    encoded = material(cookie("past", expires=NOW.timestamp() - 1),
                       cookie("now", expires=NOW.timestamp()), *surviving)
    assert json.loads(adapter.unexpired_cookie_material(encoded, now=NOW)) == surviving


@pytest.mark.parametrize("expiry", [True, "yesterday", float("inf"), float("nan")])
def test_malformed_cookie_expiry_is_rejected(expiry):
    with pytest.raises(ValueError):
        adapter.unexpired_cookie_material(material(cookie(expires=expiry)))


class Response:
    def __init__(self, status=200, *, body=b"protected account", headers=None, rotated=None):
        self.status = status
        self.headers = headers or {"content-type": "text/html"}
        self.url = URL
        self.body = AsyncMock(return_value=body)
        self.dispose = AsyncMock()
        self.rotated = rotated


def negative():
    return Response(302, headers={"content-type": "text/html",
                                "location": "https://account.booking.com/auth/oauth2?state=x"})


class Browser:
    def __init__(self, responses):
        self.responses = list(responses)
        self.contexts = []
        self.calls = []

    async def new_context(self, **options):
        browser = self

        class Context:
            def __init__(self):
                self.material = []
                self.response = None
                self.closed = False
                self.request = SimpleNamespace(get=self.get)

            async def add_cookies(self, cookies):
                self.material = cookies

            async def get(self, url, **kwargs):
                browser.calls.append((url, kwargs, list(self.material)))
                value = browser.responses.pop(0)
                if isinstance(value, Exception):
                    raise value
                self.response = value
                return value

            async def cookies(self):
                return self.response.rotated if self.response.rotated is not None else self.material

            async def close(self):
                self.closed = True

        context = Context()
        self.contexts.append(context)
        return context


def run(browser, cookies=None, *, deadline=None):
    return asyncio.run(adapter.verify_saved_snapshot(
        browser, {}, cookies or material(cookie()), deadline or time.monotonic() + 60,
    ))


def test_authentication_requires_negative_control_and_two_independent_exact_snapshots():
    browser = Browser([negative(), Response(), Response()])
    result = run(browser)
    assert result.outcome is Outcome.AUTHENTICATED
    assert json.loads(result.cookies) == [cookie()]
    assert [call[2] for call in browser.calls] == [[], [cookie()], [cookie()]]
    assert len(browser.contexts) == 3 and all(c.closed for c in browser.contexts)
    assert all(url == URL and kw["max_redirects"] == 0 for url, kw, _ in browser.calls)
    assert all(0 < kw["timeout"] <= 15000 for _, kw, _ in browser.calls)


def test_renewed_bytes_get_full_second_verification_and_later_rotations_are_not_persisted():
    renewed = cookie("renewed")
    browser = Browser([
        negative(), Response(rotated=[cookie("first")]), Response(rotated=[renewed]),
        negative(), Response(rotated=[cookie("unverified-third")]),
        Response(rotated=[cookie("unverified-fourth")]),
    ])
    result = run(browser)
    assert result.outcome is Outcome.AUTHENTICATED
    assert json.loads(result.cookies) == [renewed]
    assert [call[2] for call in browser.calls] == [
        [], [cookie()], [cookie()], [], [renewed], [renewed],
    ]


def test_rotation_that_does_not_pass_second_attempt_is_not_exported():
    browser = Browser([
        negative(), Response(), Response(rotated=[cookie("renewed")]),
        negative(), Response(202, body=b""),
    ])
    result = run(browser)
    assert result.outcome is Outcome.RETRY_LATER and result.cookies is None
    assert len(browser.calls) == 5


def test_public_or_drifted_endpoint_cannot_authenticate_saved_cookies():
    browser = Browser([Response(), Response()])
    result = run(browser)
    assert result.outcome is Outcome.RETRY_LATER and result.cookies is None
    assert len(browser.calls) == 2
    assert all(call[2] == [] for call in browser.calls)


def test_exact_pending_tuple_qualifies_negative_control_but_never_a_positive():
    browser = Browser([Response(202, body=b""), Response(202, body=b""),
                       Response(202, body=b""), Response(202, body=b"")])
    assert run(browser).outcome is Outcome.RETRY_LATER
    assert len(browser.calls) == 4


@pytest.mark.parametrize("response", [Response(429), Response(503),
                                     Response(body=b"Verify you are human"), TimeoutError()])
def test_temporary_candidate_failure_is_retryable_with_no_inner_retry(response):
    browser = Browser([negative(), response, negative(), response])
    result = run(browser)
    assert result.outcome is Outcome.RETRY_LATER and result.cookies is None
    assert len(browser.calls) == 4


def test_confirmed_oauth_redirect_is_signed_out_only_after_negative_baseline():
    browser = Browser([negative(), negative()])
    result = run(browser)
    assert result.outcome is Outcome.SIGNED_OUT and result.cookies is None
    assert len(browser.calls) == 2


def test_deadline_and_all_expired_cookies_make_no_request():
    browser = Browser([])
    assert run(browser, deadline=time.monotonic() - 1).outcome is Outcome.RETRY_LATER
    assert run(browser, material(cookie(expires=1))).outcome is Outcome.RETRY_LATER
    assert browser.calls == []


def test_expired_external_deadline_does_not_start_an_event_loop():
    service = adapter.BrowserSessionMaintenance()
    result = service.verify(material(cookie()), datetime.now(UTC) - timedelta(seconds=1))
    assert result.outcome is Outcome.RETRY_LATER
    assert not hasattr(service, "_runner")


@pytest.mark.parametrize("failure", ["startup", "close", None])
def test_supervisor_always_confirms_cleanup_before_return_and_uses_private_pipe(
    monkeypatch, failure,
):
    service = adapter.BrowserSessionMaintenance()
    monkeypatch.setattr(service, "is_supported", lambda: True)
    process = SimpleNamespace(pid=401, poll=lambda: None)
    launches = []
    monkeypatch.setattr(adapter.subprocess, "Popen",
                        lambda args, **kwargs: launches.append((args, kwargs)) or process)
    monkeypatch.setattr(adapter, "_process_identity", lambda pid: (1, 987, "S"))
    result = adapter.SessionVerificationResult(Outcome.AUTHENTICATED, b"verified", NOW)
    replies = ["ready", result]

    def receive(channel, deadline):
        if failure == "startup" or failure == "close" and len(replies) == 1:
            raise TimeoutError
        return replies.pop(0)

    sent = []
    cleanup = []
    monkeypatch.setattr(adapter, "_receive_message", receive)
    monkeypatch.setattr(adapter, "_send_message",
                        lambda channel, value, deadline: sent.append(value))
    monkeypatch.setattr(adapter, "_terminate_owned_worker",
                        lambda *args: cleanup.append(args) or True)
    monkeypatch.setenv("BOOKSAVER_SECRET_KEY", "not-for-worker")
    observed = service.verify(b"private-cookie-material", datetime.now(UTC) + timedelta(seconds=60))
    assert observed.outcome is (Outcome.AUTHENTICATED if failure is None else Outcome.RETRY_LATER)
    assert len(cleanup) == 1
    args, options = launches[0]
    assert "private-cookie-material" not in repr(args)
    assert "BOOKSAVER_SECRET_KEY" not in options["env"]
    assert options["start_new_session"] is True
    assert options["stdout"] is subprocess.DEVNULL
    if failure != "startup":
        assert sent[0][0] == b"private-cookie-material"


def test_unconfirmed_cleanup_is_fatal_not_a_retry(monkeypatch):
    service = adapter.BrowserSessionMaintenance()
    monkeypatch.setattr(service, "is_supported", lambda: True)
    monkeypatch.setattr(adapter.subprocess, "Popen",
                        lambda *args, **kwargs: SimpleNamespace(pid=401, poll=lambda: None))
    monkeypatch.setattr(adapter, "_process_identity", lambda pid: (1, 987, "S"))
    monkeypatch.setattr(adapter, "_receive_message", lambda *args: "ready")
    monkeypatch.setattr(adapter, "_send_message", lambda *args: None)
    monkeypatch.setattr(adapter, "_terminate_owned_worker", lambda *args: False)
    with pytest.raises(SessionMaintenanceCleanupError):
        service.verify(b"secret", datetime.now(UTC) + timedelta(seconds=60))


def test_supervisor_deadline_includes_slow_startup(monkeypatch):
    service = adapter.BrowserSessionMaintenance()
    monkeypatch.setattr(service, "is_supported", lambda: True)
    elapsed = [100.0]
    monkeypatch.setattr(adapter.time, "monotonic", lambda: elapsed[0])

    def launch(*args, **kwargs):
        elapsed[0] += 30
        return SimpleNamespace(pid=401, poll=lambda: None)

    monkeypatch.setattr(adapter.subprocess, "Popen", launch)
    monkeypatch.setattr(adapter, "_process_identity", lambda pid: (1, 987, "S"))
    deadlines = []

    def timeout(channel, deadline):
        deadlines.append(deadline)
        raise TimeoutError

    monkeypatch.setattr(adapter, "_receive_message", timeout)
    monkeypatch.setattr(adapter, "_terminate_owned_worker",
                        lambda p, i, d: deadlines.append(d) or True)
    service.verify(b"secret", datetime.now(UTC) + timedelta(seconds=60))
    assert 154 < deadlines[0] <= 155
    assert 159 < deadlines[1] <= 160


def test_pid_reuse_never_signals_unrelated_process(monkeypatch):
    monkeypatch.setattr(adapter, "_process_identity", lambda pid: (1, 999, "S"))
    signals = []
    monkeypatch.setattr(adapter.os, "pidfd_open", lambda pid: 9001, raising=False)
    monkeypatch.setattr(adapter.os, "close", lambda fd: None)
    monkeypatch.setattr(adapter.signal, "pidfd_send_signal",
                        lambda *args: signals.append(args), raising=False)
    adapter._signal_exact(401, (1, 987, "S"), signal.SIGKILL)
    assert signals == []


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper qualification")
def test_owned_subreaper_cleanup_kills_detached_orphan_and_worker():
    # A grandchild creates another process group, then loses its immediate parent.
    # Subreaper ownership must retain it; killing only the worker group would miss it.
    script = '''
import ctypes, subprocess, sys, time
assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0
subprocess.run([sys.executable, "-c", "import subprocess; "
    "p=subprocess.Popen(['sleep','120'], start_new_session=True); "
    "print(p.pid, flush=True)"], check=True)
time.sleep(120)
'''
    process = subprocess.Popen([sys.executable, "-c", script], start_new_session=True,
                               stdout=subprocess.PIPE)
    try:
        assert process.stdout is not None
        child_pid = int(process.stdout.readline())
        identity = adapter._process_identity(process.pid)
        assert identity is not None
        assert os.getpgid(child_pid) != os.getpgid(process.pid)
        assert adapter._terminate_owned_worker(process, identity, time.monotonic() + 5)
        child = adapter._process_identity(child_pid)
        assert child is None or child[2] == "Z"
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
