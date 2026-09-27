"""Bounded stdlib client for TypeSafe's System One API (Jev).

Jev answers typed questions (Choice / Noul) about a text ``state``; it never generates text.
Every response is untrusted: answers are validated against the exact offered options, the
pinned model version, and finite probability bounds before any caller may act on them.
"""

from __future__ import annotations

import http.client
import json
import logging
import math
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

TYPESAFE_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504, 529})
# 4xx rejections happen before inference; a missing response after the request was sent may
# still have been billed, so those attempts are charged conservatively by the caller.
_UNRESOLVED_STATUSES = frozenset({500, 502, 503, 504})
_MAX_REQUEST_BYTES = 400_000
_MAX_RESPONSE_BYTES = 1_000_000


class TypeSafeError(RuntimeError):
    """Content-free failure; ``kind`` is a bounded category safe to log."""

    def __init__(
        self,
        kind: str,
        *,
        status: int | None = None,
        unresolved_attempts: int = 0,
        estimated_input_tokens: int = 0,
    ) -> None:
        self.kind = kind
        self.status = status
        self.unresolved_attempts = unresolved_attempts
        self.estimated_input_tokens = estimated_input_tokens
        super().__init__(f"typesafe_{kind}")


@dataclass(frozen=True, slots=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class NoulAnswer:
    value: float


@dataclass(frozen=True, slots=True)
class SystemOneResult:
    model: str
    answers: Mapping[str, ChoiceAnswer | NoulAnswer]
    input_tokens: int
    output_tokens: int
    # Earlier attempts in this call that may have been billed without returning usage.
    unresolved_attempts: int = 0
    estimated_input_tokens: int = 0
    request_id: str | None = field(default=None, repr=False)

    def choice(self, question_id: str) -> ChoiceAnswer:
        answer = self.answers[question_id]
        if not isinstance(answer, ChoiceAnswer):
            raise TypeSafeError("invalid_response")
        return answer


class HttpTransport(Protocol):
    def __call__(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout: float
    ) -> tuple[int, Mapping[str, str], bytes]: ...


def urllib_transport(
    url: str, body: bytes, headers: Mapping[str, str], timeout: float
) -> tuple[int, Mapping[str, str], bytes]:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return (
                int(response.status),
                {key.casefold(): value for key, value in response.headers.items()},
                response.read(_MAX_RESPONSE_BYTES + 1),
            )
    except urllib.error.HTTPError as exc:
        payload = exc.read(_MAX_RESPONSE_BYTES + 1) if exc.fp is not None else b""
        headers_out = (
            {key.casefold(): value for key, value in exc.headers.items()}
            if exc.headers is not None
            else {}
        )
        return int(exc.code), headers_out, payload


def choice_question(instructions: object, criteria: Mapping[str, object]) -> dict[str, object]:
    if not 2 <= len(criteria) <= 255:
        raise ValueError("a Jev choice needs 2-255 options")
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


class TypeSafeClient:
    """One pinned-model System One caller with bounded retries and strict answer validation."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        timeout_seconds: float = 15.0,
        max_attempts: int = 3,
        transport: HttpTransport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key.strip():
            raise ValueError("BOOKSAVER_TYPESAFE_API_KEY is required for Jev execution")
        if not 1 <= max_attempts <= 4:
            raise ValueError("max_attempts must be between 1 and 4")
        self._api_key = api_key.strip()
        self._model = model
        self._timeout = timeout_seconds
        self._max_attempts = max_attempts
        self._transport = transport
        self._sleep = sleep
        self._clock = clock

    def __repr__(self) -> str:
        return f"<TypeSafeClient model={self._model}>"

    def system_one(
        self,
        state: object,
        questions: Mapping[str, Mapping[str, object]],
        *,
        deadline: float | None = None,
    ) -> SystemOneResult:
        if not questions:
            raise ValueError("at least one question is required")
        body = json.dumps(
            {"state": state, "model": self._model, "questions": questions},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > _MAX_REQUEST_BYTES:
            raise TypeSafeError("request_too_large")
        # Conservative estimate for attempts whose usage never returned: ~3 bytes per token.
        estimate = math.ceil(len(body) / 3)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "booksaver-jev/1",
        }
        unresolved = 0
        last_status: int | None = None
        for attempt in range(self._max_attempts):
            timeout = self._timeout
            if deadline is not None:
                timeout = min(timeout, deadline - self._clock())
                if timeout <= 0.5:
                    raise TypeSafeError(
                        "deadline",
                        status=last_status,
                        unresolved_attempts=unresolved,
                        estimated_input_tokens=estimate * unresolved,
                    )
            try:
                status, response_headers, payload = self._transport(
                    TYPESAFE_ENDPOINT, body, headers, timeout
                )
            except (TimeoutError, OSError, http.client.HTTPException):
                unresolved += 1
                status, response_headers, payload = 0, {}, b""
            last_status = status or None
            if status == 200:
                return self._parse(
                    payload,
                    questions,
                    unresolved_attempts=unresolved,
                    per_attempt_estimate=estimate,
                    request_id=response_headers.get("x-typesafe-request-id"),
                )
            if status in _UNRESOLVED_STATUSES:
                unresolved += 1
            if status in {401, 403}:
                raise TypeSafeError("authentication", status=status,
                                    unresolved_attempts=unresolved,
                                    estimated_input_tokens=estimate * unresolved)
            if status != 0 and status not in _RETRYABLE_STATUSES:
                raise TypeSafeError("rejected", status=status,
                                    unresolved_attempts=unresolved,
                                    estimated_input_tokens=estimate * unresolved)
            if attempt + 1 < self._max_attempts:
                self._sleep(self._retry_delay(attempt, response_headers))
        raise TypeSafeError(
            "overloaded" if last_status in {429, 529} else "unavailable",
            status=last_status,
            unresolved_attempts=unresolved,
            estimated_input_tokens=estimate * unresolved,
        )

    @staticmethod
    def _retry_delay(attempt: int, headers: Mapping[str, str]) -> float:
        delay: float = 0.5 * (2**attempt)
        try:
            if "retry-after-ms" in headers:
                delay = float(headers["retry-after-ms"]) / 1_000
            elif "retry-after" in headers:
                delay = float(headers["retry-after"])
        except ValueError:
            pass
        return max(0.1, min(delay, 4.0))

    def _parse(
        self,
        payload: bytes,
        questions: Mapping[str, Mapping[str, object]],
        *,
        unresolved_attempts: int,
        per_attempt_estimate: int,
        request_id: str | None,
    ) -> SystemOneResult:
        estimated_input_tokens = per_attempt_estimate * unresolved_attempts

        def invalid() -> TypeSafeError:
            # The unusable 200 response may still have been billed; charge its estimate too.
            return TypeSafeError(
                "invalid_response",
                status=200,
                unresolved_attempts=unresolved_attempts + 1,
                estimated_input_tokens=estimated_input_tokens + per_attempt_estimate,
            )

        if len(payload) > _MAX_RESPONSE_BYTES:
            raise invalid()
        try:
            raw: Any = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            raise invalid() from None
        if not isinstance(raw, dict):
            raise invalid()
        usage = raw.get("usage")
        answers = raw.get("answers")
        model = raw.get("model")
        if not isinstance(usage, dict) or not isinstance(answers, dict):
            raise invalid()
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens", 0)
        if (
            not isinstance(input_tokens, int)
            or isinstance(input_tokens, bool)
            or input_tokens < 0
            or not isinstance(output_tokens, int)
            or isinstance(output_tokens, bool)
            or output_tokens < 0
        ):
            raise invalid()
        if model != self._model:
            # A moving or unexpected version invalidates the frozen experiment cohort. The call
            # still returned usage, so the caller charges it before failing closed.
            raise TypeSafeError(
                "model_mismatch",
                status=200,
                unresolved_attempts=unresolved_attempts,
                estimated_input_tokens=estimated_input_tokens + input_tokens,
            )
        parsed: dict[str, ChoiceAnswer | NoulAnswer] = {}
        for question_id, question in questions.items():
            answer = answers.get(question_id)
            if not isinstance(answer, dict):
                raise invalid()
            kind = question.get("type")
            if kind == "choice":
                criteria = question.get("criteria")
                assert isinstance(criteria, Mapping)
                parsed_choice = _validated_choice(answer, frozenset(str(key) for key in criteria))
                if parsed_choice is None:
                    raise invalid()
                parsed[question_id] = parsed_choice
            elif kind == "noul":
                value = answer.get("noul")
                if (
                    answer.get("type") != "noul"
                    or not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                    or not 0.0 <= float(value) <= 1.0
                ):
                    raise invalid()
                parsed[question_id] = NoulAnswer(float(value))
            else:
                raise ValueError("unsupported question type")
        return SystemOneResult(
            model=str(model),
            answers=parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            unresolved_attempts=unresolved_attempts,
            estimated_input_tokens=estimated_input_tokens,
            request_id=request_id,
        )


def _validated_choice(answer: Mapping[str, object], offered: frozenset[str]) -> ChoiceAnswer | None:
    choice = answer.get("choice")
    confidence = answer.get("confidence")
    probabilities = answer.get("probabilities")
    if answer.get("type") != "choice" or not isinstance(choice, str) or choice not in offered:
        return None
    # Omitted options are read as zero probability; unknown options are rejected.
    if not isinstance(probabilities, dict) or not set(probabilities) <= offered:
        return None
    values: dict[str, float] = dict.fromkeys(offered, 0.0)
    for key, value in probabilities.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        number = float(value)
        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
            return None
        values[str(key)] = number
    if abs(sum(values.values()) - 1.0) > 0.02:
        return None
    if values[choice] < max(values.values()) - 1e-9:
        return None
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        return None
    confidence_value = float(confidence)
    if not math.isfinite(confidence_value) or not 0.0 <= confidence_value <= 1.0:
        return None
    return ChoiceAnswer(choice, confidence_value, values)
