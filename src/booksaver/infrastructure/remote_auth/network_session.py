"""Isolated, server-backed verification for one remote-auth cookie snapshot.

The rendered login page is only a cookie producer.  This module owns the
versioned read-only Booking server contract and never accepts a URL, response
predicate, or authentication decision from page content or a model.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin, urlsplit

from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.remote_auth import (
    REMOTE_AUTH_SERVER_CONTRACT_VERSION,
    REMOTE_AUTH_SERVER_VERIFIER,
    RemoteAuthServerReceipt,
    RemoteAuthServerVerification,
    SafeServerEvidence,
    ServerMediaClass,
    ServerRedirectClass,
    ServerSessionProbeOutcome,
    ServerSizeClass,
    ServerStatusClass,
)

SERVER_CONTRACT_VERSION = REMOTE_AUTH_SERVER_CONTRACT_VERSION
ACCOUNT_PROBE_URL = "https://secure.booking.com/myaccount.html"
_PROBE_HOST = "secure.booking.com"
_PROBE_PATH = "/myaccount.html"
_SIGNED_OUT_HOST = "account.booking.com"
_SIGNED_OUT_PATH = "/auth/oauth2"
_MAX_RESPONSE_BYTES = 2_000_000
_PROBE_TIMEOUT_MS = 15_000
_RECEIPT_TTL = timedelta(seconds=30)
_COOKIE_FIELDS = (
    "name",
    "value",
    "domain",
    "path",
    "expires",
    "httpOnly",
    "secure",
    "sameSite",
    "partitionKey",
)
_CHALLENGE_MARKERS = (
    b"cf-chl-",
    b"verify you are human",
    b"unusual traffic",
    b"px-captcha",
    b"challenge-platform",
)


def is_authenticated_account_probe_response(
    *,
    status: int,
    headers: Mapping[str, str],
    response_url: str,
    body: bytes,
) -> bool:
    """Return code-owned authentication proof for the fixed protected resource.

    This is deliberately narrower than page interpretation: it accepts only the exact successful
    server response already defined by the remote-auth contract.  Browser executors may reuse the
    predicate when deciding whether refreshed local cookies are eligible for persistence.
    """
    normalized_headers = {
        str(key).casefold(): str(value) for key, value in headers.items()
    }
    content_type = normalized_headers.get("content-type", "").split(";", 1)[0]
    try:
        parsed = urlsplit(response_url)
    except ValueError:
        return False
    return (
        status == 200
        and content_type.strip().casefold() == "text/html"
        and "location" not in normalized_headers
        and 0 < len(body) <= _MAX_RESPONSE_BYTES
        and not any(marker in body[:_MAX_RESPONSE_BYTES].lower() for marker in _CHALLENGE_MARKERS)
        and parsed.scheme == "https"
        and parsed.hostname == _PROBE_HOST
        and parsed.path == _PROBE_PATH
        and not parsed.query
        and not parsed.fragment
    )


def _is_booking_cookie_domain(domain: str) -> bool:
    normalized = domain.casefold().lstrip(".").rstrip(".")
    return normalized == "booking.com" or normalized.endswith(".booking.com")


@dataclass(frozen=True, slots=True)
class CandidateSessionSnapshot:
    """Canonical exact cookie bytes retained only for this browser attempt."""

    _serialized: bytes = field(repr=False)
    _fingerprint: bytes = field(repr=False)

    @property
    def fingerprint(self) -> bytes:
        return self._fingerprint

    def playwright_cookies(self) -> list[dict[str, Any]]:
        value = json.loads(self._serialized.decode("utf-8"))
        if not isinstance(value, list):  # pragma: no cover - constructor owns encoding
            raise ValueError("candidate cookie snapshot is malformed")
        return value

    def persistence_json(self) -> str:
        return self._serialized.decode("utf-8")


class CandidateSnapshotStabilizer:
    """Admit each unchanged candidate once without exposing its fingerprint."""

    def __init__(
        self,
        required_observations: int = 2,
        max_unstable_observations: int = 10,
        recheck_interval_seconds: float = 10.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if required_observations < 1:
            raise ValueError("candidate stabilization must require an observation")
        if max_unstable_observations < required_observations:
            raise ValueError("unstable candidate bound cannot precede stabilization")
        if recheck_interval_seconds <= 0:
            raise ValueError("candidate recheck interval must be positive")
        self._required_observations = required_observations
        self._max_unstable_observations = max_unstable_observations
        self._recheck_interval_seconds = recheck_interval_seconds
        self._clock = clock or time.monotonic
        self._last: bytes | None = None
        self._count = 0
        self._observations_since_admission = 0
        self._probed: set[bytes] = set()
        self._not_before: dict[bytes, float] = {}

    def should_probe(self, snapshot: CandidateSessionSnapshot) -> bool:
        fingerprint = snapshot.fingerprint
        self._observations_since_admission += 1
        if fingerprint != self._last:
            self._last = fingerprint
            self._count = 1
        else:
            self._count += 1
        if (
            self._count < self._required_observations
            and self._observations_since_admission < self._max_unstable_observations
        ):
            return False
        admitted = self._mark_new(fingerprint)
        self._observations_since_admission = 0
        return admitted

    def _mark_new(self, fingerprint: bytes) -> bool:
        if fingerprint in self._probed:
            if self._clock() < self._not_before.get(fingerprint, float("inf")):
                return False
            self._probed.remove(fingerprint)
            self._not_before.pop(fingerprint, None)
        self._probed.add(fingerprint)
        return True

    def retry_later(self, snapshot: CandidateSessionSnapshot) -> None:
        """Permit a bounded recheck when server state may change in place."""

        fingerprint = snapshot.fingerprint
        if fingerprint in self._probed:
            self._not_before[fingerprint] = self._clock() + self._recheck_interval_seconds
        self._last = None
        self._count = 0
        self._observations_since_admission = 0


@dataclass(frozen=True, slots=True)
class _ProbeResult:
    outcome: ServerSessionProbeOutcome
    evidence: SafeServerEvidence


class BookingServerSessionVerifier:
    """Verify a candidate against a fixed protected Booking resource."""

    def __init__(
        self,
        browser: Any,
        mobile_settings: MobileWebSettings,
        device_descriptor: Mapping[str, Any],
        *,
        clock: Callable[[], datetime] | None = None,
        hmac_key: bytes | None = None,
        max_transport_attempts: int = 2,
    ) -> None:
        self._validate_contract_literal()
        if max_transport_attempts < 1 or max_transport_attempts > 3:
            raise ValueError("remote-auth transport retries must be between one and three")
        options = mobile_settings.context_options(dict(device_descriptor))
        options["service_workers"] = "block"
        self._context_factory: Callable[[], Any] = lambda: browser.new_context(**options)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._hmac_key = hmac_key or secrets.token_bytes(32)
        if len(self._hmac_key) < 32:
            raise ValueError("remote-auth verifier HMAC key is too short")
        self._max_transport_attempts = max_transport_attempts
        self._baseline_established = False
        self._issued_receipt: RemoteAuthServerReceipt | None = None
        self._receipt_consumed = False

    @staticmethod
    def _validate_contract_literal() -> None:
        parsed = urlsplit(ACCOUNT_PROBE_URL)
        if (
            parsed.scheme != "https"
            or parsed.hostname != _PROBE_HOST
            or parsed.path != _PROBE_PATH
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError("remote-auth server contract literal is unsafe")

    def snapshot(self, raw_cookies: Sequence[Mapping[str, Any]]) -> CandidateSessionSnapshot | None:
        canonical: list[dict[str, Any]] = []
        for raw in raw_cookies:
            domain = raw.get("domain")
            name = raw.get("name")
            value = raw.get("value")
            if not isinstance(domain, str) or not _is_booking_cookie_domain(domain):
                continue
            if not isinstance(name, str) or not name or not isinstance(value, str):
                continue
            cookie = {field: raw[field] for field in _COOKIE_FIELDS if field in raw}
            canonical.append(cookie)
        if not canonical:
            return None
        canonical.sort(
            key=lambda item: (
                str(item.get("domain", "")).casefold(),
                str(item.get("path", "/")),
                str(item.get("name", "")),
                str(item.get("value", "")),
            )
        )
        serialized = json.dumps(
            canonical,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        fingerprint = hmac.new(
            self._hmac_key,
            b"candidate\0" + serialized,
            hashlib.sha256,
        ).digest()
        return CandidateSessionSnapshot(serialized, fingerprint)

    def establish_baseline(self) -> RemoteAuthServerVerification:
        result = self._probe_with_retry(None)
        if result.outcome is ServerSessionProbeOutcome.SIGNED_OUT:
            self._baseline_established = True
            return RemoteAuthServerVerification(result.outcome, result.evidence)
        outcome = result.outcome
        if outcome is ServerSessionProbeOutcome.AUTHENTICATED:
            outcome = ServerSessionProbeOutcome.CONTRACT_CHANGED
        return RemoteAuthServerVerification(outcome, result.evidence)

    def verify_candidate(
        self,
        snapshot: CandidateSessionSnapshot,
        *,
        attempt_id: str,
        telegram_user_id: int,
    ) -> RemoteAuthServerVerification:
        if not self._baseline_established:
            raise RuntimeError("remote-auth negative baseline was not established")
        first = self._probe_with_retry(snapshot)
        if first.outcome is not ServerSessionProbeOutcome.AUTHENTICATED:
            return RemoteAuthServerVerification(first.outcome, first.evidence)
        second = self._probe_with_retry(snapshot)
        if second.outcome is not ServerSessionProbeOutcome.AUTHENTICATED:
            return RemoteAuthServerVerification(second.outcome, second.evidence)
        verified_at = self._clock()
        digest = self._snapshot_hmac(snapshot)
        receipt = RemoteAuthServerReceipt(
            attempt_id=attempt_id,
            telegram_user_id=telegram_user_id,
            contract_version=SERVER_CONTRACT_VERSION,
            verified_at=verified_at,
            expires_at=verified_at + _RECEIPT_TTL,
            verifier=REMOTE_AUTH_SERVER_VERIFIER,
            _snapshot_hmac=digest,
            _nonce=secrets.token_bytes(32),
        )
        self._issued_receipt = receipt
        self._receipt_consumed = False
        return RemoteAuthServerVerification(
            ServerSessionProbeOutcome.AUTHENTICATED,
            second.evidence,
            receipt,
        )

    def consume_receipt(
        self,
        receipt: RemoteAuthServerReceipt,
        snapshot: CandidateSessionSnapshot,
        *,
        attempt_id: str,
        telegram_user_id: int,
    ) -> bool:
        now = self._clock()
        valid = (
            receipt is self._issued_receipt
            and not self._receipt_consumed
            and receipt.attempt_id == attempt_id
            and receipt.telegram_user_id == telegram_user_id
            and receipt.contract_version == SERVER_CONTRACT_VERSION
            and receipt.verified_at <= now < receipt.expires_at
            and receipt.matches_snapshot_hmac(self._snapshot_hmac(snapshot))
        )
        if not valid:
            return False
        self._receipt_consumed = True
        return True

    def _snapshot_hmac(self, snapshot: CandidateSessionSnapshot) -> bytes:
        return hmac.new(
            self._hmac_key,
            b"receipt\0" + snapshot._serialized,  # noqa: SLF001 - same bounded context
            hashlib.sha256,
        ).digest()

    def _probe_with_retry(
        self,
        snapshot: CandidateSessionSnapshot | None,
    ) -> _ProbeResult:
        result: _ProbeResult | None = None
        for _ in range(self._max_transport_attempts):
            result = self._probe_once(snapshot)
            if result.outcome is not ServerSessionProbeOutcome.UNAVAILABLE:
                return result
        assert result is not None
        return result

    def _probe_once(self, snapshot: CandidateSessionSnapshot | None) -> _ProbeResult:
        context: Any = None
        try:
            context = self._context_factory()
            if snapshot is not None:
                context.add_cookies(snapshot.playwright_cookies())
            response = context.request.get(
                ACCOUNT_PROBE_URL,
                max_redirects=0,
                fail_on_status_code=False,
                timeout=_PROBE_TIMEOUT_MS,
            )
            return self._classify_response(response)
        except Exception:
            return _ProbeResult(
                ServerSessionProbeOutcome.UNAVAILABLE,
                self._evidence(
                    status=ServerStatusClass.UNAVAILABLE,
                    media=ServerMediaClass.MISSING,
                    redirect=ServerRedirectClass.INVALID,
                    size=ServerSizeClass.UNKNOWN,
                ),
            )
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass

    def _classify_response(self, response: Any) -> _ProbeResult:
        try:
            status = int(response.status)
            headers = {str(key).casefold(): str(value) for key, value in response.headers.items()}
            response_url = str(response.url)
        except Exception:
            return _ProbeResult(
                ServerSessionProbeOutcome.UNAVAILABLE,
                self._evidence(
                    status=ServerStatusClass.UNAVAILABLE,
                    media=ServerMediaClass.MISSING,
                    redirect=ServerRedirectClass.INVALID,
                    size=ServerSizeClass.UNKNOWN,
                ),
            )

        status_class = self._status_class(status)
        media = self._media_class(headers.get("content-type"))
        redirect = self._redirect_class(headers.get("location"))
        size = self._declared_size_class(headers.get("content-length"))
        evidence = self._evidence(
            status=status_class,
            media=media,
            redirect=redirect,
            size=size,
        )

        if redirect is ServerRedirectClass.EXTERNAL:
            return _ProbeResult(ServerSessionProbeOutcome.BLOCKED_REDIRECT, evidence)
        if (
            status == 302
            and media is ServerMediaClass.HTML
            and redirect is ServerRedirectClass.BOOKING_OAUTH
        ):
            return _ProbeResult(ServerSessionProbeOutcome.SIGNED_OUT, evidence)
        if status == 429:
            return _ProbeResult(ServerSessionProbeOutcome.CHALLENGE, evidence)
        if status >= 500:
            return _ProbeResult(ServerSessionProbeOutcome.UNAVAILABLE, evidence)
        if size is ServerSizeClass.OVERSIZED:
            return _ProbeResult(ServerSessionProbeOutcome.CONTRACT_CHANGED, evidence)
        try:
            body = bytes(response.body())
        except Exception:
            return _ProbeResult(
                ServerSessionProbeOutcome.UNAVAILABLE,
                self._evidence(
                    status=status_class,
                    media=media,
                    redirect=redirect,
                    size=ServerSizeClass.UNKNOWN,
                ),
            )
        size = (
            ServerSizeClass.EMPTY
            if not body
            else ServerSizeClass.OVERSIZED
            if len(body) > _MAX_RESPONSE_BYTES
            else ServerSizeClass.BOUNDED
        )
        evidence = self._evidence(
            status=status_class,
            media=media,
            redirect=redirect,
            size=size,
        )
        if self._has_challenge_marker(body):
            return _ProbeResult(ServerSessionProbeOutcome.CHALLENGE, evidence)
        parsed_response = urlsplit(response_url)
        exact_probe_url = (
            parsed_response.scheme == "https"
            and parsed_response.hostname == _PROBE_HOST
            and parsed_response.path == _PROBE_PATH
            and not parsed_response.query
            and not parsed_response.fragment
        )
        if (
            status == 202
            and media is ServerMediaClass.HTML
            and redirect is ServerRedirectClass.NONE
            and size is ServerSizeClass.EMPTY
            and exact_probe_url
        ):
            return _ProbeResult(ServerSessionProbeOutcome.SIGNED_OUT, evidence)
        if is_authenticated_account_probe_response(
            status=status,
            headers=headers,
            response_url=response_url,
            body=body,
        ):
            return _ProbeResult(ServerSessionProbeOutcome.AUTHENTICATED, evidence)
        return _ProbeResult(ServerSessionProbeOutcome.CONTRACT_CHANGED, evidence)

    @staticmethod
    def _has_challenge_marker(body: bytes) -> bool:
        lowered = body[:_MAX_RESPONSE_BYTES].lower()
        return any(marker in lowered for marker in _CHALLENGE_MARKERS)

    @staticmethod
    def _declared_size_class(content_length: str | None) -> ServerSizeClass:
        if content_length is None:
            return ServerSizeClass.UNKNOWN
        try:
            size = int(content_length)
        except ValueError:
            return ServerSizeClass.UNKNOWN
        if size < 0:
            return ServerSizeClass.UNKNOWN
        if size == 0:
            return ServerSizeClass.EMPTY
        if size > _MAX_RESPONSE_BYTES:
            return ServerSizeClass.OVERSIZED
        return ServerSizeClass.BOUNDED

    @staticmethod
    def _status_class(status: int) -> ServerStatusClass:
        if 200 <= status < 300:
            return ServerStatusClass.SUCCESS
        if 300 <= status < 400:
            return ServerStatusClass.REDIRECTION
        if 400 <= status < 500:
            return ServerStatusClass.CLIENT_ERROR
        if 500 <= status < 600:
            return ServerStatusClass.SERVER_ERROR
        return ServerStatusClass.UNAVAILABLE

    @staticmethod
    def _media_class(content_type: str | None) -> ServerMediaClass:
        if content_type is None:
            return ServerMediaClass.MISSING
        media = content_type.split(";", 1)[0].strip().casefold()
        return ServerMediaClass.HTML if media == "text/html" else ServerMediaClass.OTHER

    @staticmethod
    def _redirect_class(location: str | None) -> ServerRedirectClass:
        if location is None:
            return ServerRedirectClass.NONE
        try:
            parsed = urlsplit(urljoin(ACCOUNT_PROBE_URL, location))
        except ValueError:
            return ServerRedirectClass.INVALID
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme != "https" or not (host == "booking.com" or host.endswith(".booking.com")):
            return ServerRedirectClass.EXTERNAL
        if host == _SIGNED_OUT_HOST and parsed.path == _SIGNED_OUT_PATH:
            return ServerRedirectClass.BOOKING_OAUTH
        return ServerRedirectClass.OTHER_BOOKING

    @staticmethod
    def _evidence(
        *,
        status: ServerStatusClass,
        media: ServerMediaClass,
        redirect: ServerRedirectClass,
        size: ServerSizeClass,
    ) -> SafeServerEvidence:
        return SafeServerEvidence(
            contract_version=SERVER_CONTRACT_VERSION,
            status=status,
            media=media,
            redirect=redirect,
            size=size,
        )
