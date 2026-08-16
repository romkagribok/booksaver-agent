from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.remote_auth import (
    REMOTE_AUTH_SERVER_CONTRACT_VERSION,
    REMOTE_AUTH_SERVER_VERIFIER,
    RemoteAuthServerReceipt,
    SafeServerEvidence,
    ServerMediaClass,
    ServerRedirectClass,
    ServerSessionProbeOutcome,
    ServerSizeClass,
    ServerStatusClass,
)
from booksaver.infrastructure.remote_auth.network_session import (
    ACCOUNT_PROBE_URL,
    BookingServerSessionVerifier,
    CandidateSnapshotStabilizer,
)

NOW = datetime(2026, 8, 15, 22, 0, tzinfo=UTC)
DESCRIPTOR = {
    "user_agent": "Mozilla/5.0 (Linux; Android 13) Chrome Mobile",
    "viewport": {"width": 480, "height": 960},
    "is_mobile": True,
    "has_touch": True,
    "device_scale_factor": 1,
}


class Response:
    def __init__(
        self,
        status: int,
        *,
        url: str = ACCOUNT_PROBE_URL,
        headers: dict[str, str] | None = None,
        body: bytes = b"protected account resource",
    ) -> None:
        self.status = status
        self.url = url
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}
        self._body = body

    def body(self) -> bytes:
        return self._body


class RequestContext:
    def __init__(self, response: Response | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> Response:
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class Context:
    def __init__(self, response: Response | Exception) -> None:
        self.request = RequestContext(response)
        self.cookies: list[dict[str, Any]] = []
        self.closed = False

    def add_cookies(self, cookies: list[dict[str, Any]]) -> None:
        self.cookies = cookies

    def close(self) -> None:
        self.closed = True


class Browser:
    def __init__(self, responses: list[Response | Exception]) -> None:
        self.responses = responses
        self.contexts: list[Context] = []
        self.options: list[dict[str, Any]] = []

    def new_context(self, **options: Any) -> Context:
        self.options.append(options)
        context = Context(self.responses.pop(0))
        self.contexts.append(context)
        return context


def signed_out() -> Response:
    return Response(
        302,
        headers={
            "content-type": "text/html",
            "location": "https://account.booking.com/auth/oauth2?state=sensitive",
        },
        body=b"redirect",
    )


def authenticated() -> Response:
    return Response(200)


def edge_pending() -> Response:
    return Response(
        202,
        headers={"content-type": "text/html; charset=UTF-8"},
        body=b"",
    )


def verifier(
    responses: list[Response | Exception],
    *,
    now: list[datetime] | None = None,
) -> tuple[BookingServerSessionVerifier, Browser]:
    browser = Browser(responses)
    current = now or [NOW]
    return (
        BookingServerSessionVerifier(
            browser,
            MobileWebSettings(),
            DESCRIPTOR,
            clock=lambda: current[0],
            hmac_key=b"k" * 32,
        ),
        browser,
    )


def snapshot(value: BookingServerSessionVerifier, secret: str = "secret") -> Any:
    result = value.snapshot(
        [
            {
                "name": "session",
                "value": secret,
                "domain": ".booking.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax",
            },
            {
                "name": "unrelated",
                "value": "must-not-copy",
                "domain": ".attacker.example",
                "path": "/",
            },
        ]
    )
    assert result is not None
    return result


def test_negative_baseline_and_two_isolated_positive_probes_issue_receipt() -> None:
    value, browser = verifier([signed_out(), authenticated(), authenticated()])
    candidate = snapshot(value)

    baseline = value.establish_baseline()
    result = value.verify_candidate(
        candidate,
        attempt_id="attempt-1",
        telegram_user_id=42,
    )

    assert baseline.outcome is ServerSessionProbeOutcome.SIGNED_OUT
    assert result.outcome is ServerSessionProbeOutcome.AUTHENTICATED
    assert result.receipt is not None
    assert len(browser.contexts) == 3
    assert browser.contexts[0].cookies == []
    assert all(context.closed for context in browser.contexts)
    assert all(options["service_workers"] == "block" for options in browser.options)
    for context in browser.contexts:
        call_url, kwargs = context.request.calls[0]
        assert call_url == ACCOUNT_PROBE_URL
        assert kwargs == {
            "max_redirects": 0,
            "fail_on_status_code": False,
            "timeout": 15_000,
        }
    for context in browser.contexts[1:]:
        assert len(context.cookies) == 1
        assert context.cookies[0]["domain"] == ".booking.com"
        assert context.cookies[0]["value"] == "secret"


def test_anonymous_candidate_is_predictable_and_has_no_receipt() -> None:
    value, _browser = verifier([signed_out(), signed_out()])
    value.establish_baseline()

    result = value.verify_candidate(
        snapshot(value),
        attempt_id="attempt-1",
        telegram_user_id=42,
    )

    assert result.outcome is ServerSessionProbeOutcome.SIGNED_OUT
    assert result.receipt is None


def test_exact_edge_pending_response_is_negative_for_baseline_and_candidate() -> None:
    value, _browser = verifier([edge_pending(), edge_pending()])

    baseline = value.establish_baseline()
    result = value.verify_candidate(
        snapshot(value),
        attempt_id="attempt-1",
        telegram_user_id=42,
    )

    assert baseline.outcome is ServerSessionProbeOutcome.SIGNED_OUT
    assert result.outcome is ServerSessionProbeOutcome.SIGNED_OUT
    assert result.receipt is None
    assert baseline.evidence.status.value == "success"
    assert baseline.evidence.media.value == "html"
    assert baseline.evidence.redirect.value == "none"
    assert baseline.evidence.size.value == "empty"


def test_edge_pending_baseline_still_requires_two_exact_positive_probes() -> None:
    value, _browser = verifier([edge_pending(), authenticated(), authenticated()])
    value.establish_baseline()

    result = value.verify_candidate(
        snapshot(value),
        attempt_id="attempt-1",
        telegram_user_id=42,
    )

    assert result.outcome is ServerSessionProbeOutcome.AUTHENTICATED
    assert result.receipt is not None
    assert result.receipt.contract_version == REMOTE_AUTH_SERVER_CONTRACT_VERSION
    assert result.receipt.verifier == REMOTE_AUTH_SERVER_VERIFIER


def test_previous_server_contract_cannot_cross_the_v2_boundary() -> None:
    with pytest.raises(ValueError, match="unsupported remote-auth server contract version"):
        SafeServerEvidence(
            contract_version="booking-account-session-v1",
            status=ServerStatusClass.SUCCESS,
            media=ServerMediaClass.HTML,
            redirect=ServerRedirectClass.NONE,
            size=ServerSizeClass.EMPTY,
        )

    with pytest.raises(ValueError, match="unsupported remote-auth receipt contract"):
        RemoteAuthServerReceipt(
            attempt_id="attempt-1",
            telegram_user_id=42,
            contract_version="booking-account-session-v1",
            verified_at=NOW,
            expires_at=NOW + timedelta(seconds=30),
            verifier="booking_server_session_v1",
            _snapshot_hmac=b"x" * 32,
            _nonce=b"y" * 32,
        )


def test_edge_pending_second_probe_prevents_receipt() -> None:
    value, _browser = verifier([signed_out(), authenticated(), edge_pending()])
    value.establish_baseline()

    result = value.verify_candidate(
        snapshot(value),
        attempt_id="attempt-1",
        telegram_user_id=42,
    )

    assert result.outcome is ServerSessionProbeOutcome.SIGNED_OUT
    assert result.receipt is None


@pytest.mark.parametrize(
    "response",
    [
        Response(202, body=b"not empty"),
        Response(202, headers={"content-type": "application/json"}, body=b""),
        Response(202, url=f"{ACCOUNT_PROBE_URL}?variant=1", body=b""),
        Response(202, url=f"{ACCOUNT_PROBE_URL}#fragment", body=b""),
        Response(202, url="https://secure.booking.com/other", body=b""),
        Response(
            202,
            headers={
                "content-type": "text/html",
                "content-length": "2000001",
            },
            body=b"",
        ),
        Response(202, body=b"x" * 2_000_001),
        Response(
            202,
            headers={
                "content-type": "text/html",
                "location": "https://secure.booking.com/other",
            },
            body=b"",
        ),
        Response(202, body=b"verify you are human"),
    ],
)
def test_malformed_edge_pending_variants_never_authenticate(response: Response) -> None:
    value, _browser = verifier([signed_out(), response])
    value.establish_baseline()

    result = value.verify_candidate(
        snapshot(value),
        attempt_id="attempt-1",
        telegram_user_id=42,
    )

    assert result.outcome is not ServerSessionProbeOutcome.AUTHENTICATED
    assert result.receipt is None


@pytest.mark.parametrize(
    ("response", "outcome"),
    [
        (Response(200, headers={"content-type": "application/json"}), "contract_changed"),
        (Response(200, body=b"verify you are human"), "challenge"),
        (Response(429), "challenge"),
        (Response(503), "unavailable"),
        (
            Response(
                302,
                headers={
                    "content-type": "text/html",
                    "location": "https://attacker.example/sign-in",
                },
            ),
            "blocked_redirect",
        ),
        (Response(200, body=b"x" * 2_000_001), "contract_changed"),
    ],
)
def test_candidate_contract_fails_closed(response: Response, outcome: str) -> None:
    # Unavailable is retried by policy, so provide a second identical response.
    responses = [signed_out(), response]
    if outcome == "unavailable":
        responses.append(response)
    value, _browser = verifier(responses)
    value.establish_baseline()

    result = value.verify_candidate(
        snapshot(value),
        attempt_id="attempt-1",
        telegram_user_id=42,
    )

    assert result.outcome.value == outcome
    assert result.receipt is None


def test_baseline_must_be_exact_signed_out_contract() -> None:
    value, _browser = verifier([authenticated()])
    baseline = value.establish_baseline()

    assert baseline.outcome is ServerSessionProbeOutcome.CONTRACT_CHANGED
    with pytest.raises(RuntimeError, match="negative baseline"):
        value.verify_candidate(
            snapshot(value),
            attempt_id="attempt-1",
            telegram_user_id=42,
        )


def test_wrong_oauth_path_is_contract_change_not_signed_out() -> None:
    value, _browser = verifier(
        [
            Response(
                302,
                headers={
                    "content-type": "text/html",
                    "location": "https://account.booking.com/other",
                },
            )
        ]
    )
    result = value.establish_baseline()

    assert result.outcome is ServerSessionProbeOutcome.CONTRACT_CHANGED
    assert result.evidence.redirect is ServerRedirectClass.OTHER_BOOKING


def test_receipt_is_bound_to_exact_snapshot_caller_attempt_and_one_use() -> None:
    value, _browser = verifier([signed_out(), authenticated(), authenticated()])
    candidate = snapshot(value, "first-secret")
    different = snapshot(value, "second-secret")
    value.establish_baseline()
    result = value.verify_candidate(
        candidate,
        attempt_id="attempt-1",
        telegram_user_id=42,
    )
    assert result.receipt is not None

    assert not value.consume_receipt(
        result.receipt,
        different,
        attempt_id="attempt-1",
        telegram_user_id=42,
    )
    assert not value.consume_receipt(
        replace(result.receipt, attempt_id="other"),
        candidate,
        attempt_id="other",
        telegram_user_id=42,
    )
    assert value.consume_receipt(
        result.receipt,
        candidate,
        attempt_id="attempt-1",
        telegram_user_id=42,
    )
    assert not value.consume_receipt(
        result.receipt,
        candidate,
        attempt_id="attempt-1",
        telegram_user_id=42,
    )


def test_expired_receipt_is_rejected() -> None:
    current = [NOW]
    value, _browser = verifier(
        [signed_out(), authenticated(), authenticated()],
        now=current,
    )
    candidate = snapshot(value)
    value.establish_baseline()
    result = value.verify_candidate(
        candidate,
        attempt_id="attempt-1",
        telegram_user_id=42,
    )
    assert result.receipt is not None
    current[0] += timedelta(seconds=31)

    assert not value.consume_receipt(
        result.receipt,
        candidate,
        attempt_id="attempt-1",
        telegram_user_id=42,
    )


def test_candidate_requires_booking_cookie_and_repr_hides_secrets() -> None:
    value, _browser = verifier([])
    assert value.snapshot([{"name": "x", "value": "secret", "domain": ".attacker.example"}]) is None
    candidate = snapshot(value, "super-secret")

    assert "super-secret" not in repr(candidate)
    assert "must-not-copy" not in candidate.persistence_json()


def test_stabilizer_admits_each_exact_snapshot_once() -> None:
    value, _browser = verifier([])
    first = snapshot(value, "first")
    second = snapshot(value, "second")
    stabilizer = CandidateSnapshotStabilizer(required_observations=2)

    assert not stabilizer.should_probe(first)
    assert stabilizer.should_probe(first)
    assert not stabilizer.should_probe(first)
    assert not stabilizer.should_probe(second)
    assert stabilizer.should_probe(second)
    assert not stabilizer.should_probe(first)


def test_stabilizer_eventually_probes_latest_snapshot_during_cookie_churn() -> None:
    value, _browser = verifier([])
    stabilizer = CandidateSnapshotStabilizer(
        required_observations=2,
        max_unstable_observations=3,
    )

    assert not stabilizer.should_probe(snapshot(value, "first"))
    assert not stabilizer.should_probe(snapshot(value, "second"))
    assert stabilizer.should_probe(snapshot(value, "third"))


def test_signed_out_snapshot_can_be_rechecked_after_server_side_upgrade_delay() -> None:
    value, _browser = verifier([])
    candidate = snapshot(value, "unchanged-server-session")
    current = [10.0]
    stabilizer = CandidateSnapshotStabilizer(
        required_observations=2,
        recheck_interval_seconds=5.0,
        clock=lambda: current[0],
    )

    assert not stabilizer.should_probe(candidate)
    assert stabilizer.should_probe(candidate)
    stabilizer.retry_later(candidate)
    assert not stabilizer.should_probe(candidate)
    current[0] += 5.0
    assert stabilizer.should_probe(candidate)
