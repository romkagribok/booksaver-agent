from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from booksaver.infrastructure.llm.typesafe_client import (
    TYPESAFE_ENDPOINT,
    TypeSafeClient,
    TypeSafeError,
    choice_question,
)

MODEL = "jev-1.13.0"
QUESTIONS = {
    "pick": choice_question("Which option?", {"a": "first", "b": "second"}),
    "flag": {"type": "noul", "instructions": "Is it urgent?"},
}


def _body(**overrides: object) -> bytes:
    payload: dict[str, object] = {
        "model": MODEL,
        "answers": {
            "pick": {
                "type": "choice",
                "choice": "b",
                "confidence": 0.8,
                "probabilities": {"a": 0.1, "b": 0.9},
            },
            "flag": {"type": "noul", "noul": 0.25},
        },
        "usage": {"input_tokens": 400, "output_tokens": 12},
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


class Transport:
    def __init__(self, *responses: tuple[int, bytes] | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object], Mapping[str, str]]] = []

    def __call__(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout: float
    ) -> tuple[int, Mapping[str, str], bytes]:
        self.calls.append((url, json.loads(body), headers))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        status, payload = response
        return status, {}, payload


def _client(transport: Transport, **kwargs: object) -> TypeSafeClient:
    return TypeSafeClient(
        "secret-key", model=MODEL, transport=transport, sleep=lambda _s: None, **kwargs  # type: ignore[arg-type]
    )


def test_sends_pinned_model_bearer_auth_and_parses_typed_answers() -> None:
    transport = Transport((200, _body()))
    result = _client(transport).system_one({"page": "text"}, QUESTIONS)

    url, sent, headers = transport.calls[0]
    assert url == TYPESAFE_ENDPOINT
    assert sent["model"] == MODEL and sent["state"] == {"page": "text"}
    assert set(sent["questions"]) == {"pick", "flag"}  # type: ignore[arg-type]
    assert headers["Authorization"] == "Bearer secret-key"
    assert result.choice("pick").choice == "b"
    assert result.answers["flag"].value == 0.25  # type: ignore[union-attr]
    assert (result.input_tokens, result.output_tokens, result.unresolved_attempts) == (400, 12, 0)


def test_rejects_a_choice_outside_the_offered_options() -> None:
    bad = _body(answers={
        "pick": {"type": "choice", "choice": "c", "confidence": 1.0,
                 "probabilities": {"a": 0.0, "b": 0.0, "c": 1.0}},
        "flag": {"type": "noul", "noul": 0.5},
    })
    with pytest.raises(TypeSafeError) as error:
        _client(Transport((200, bad))).system_one("s", QUESTIONS)
    assert error.value.kind == "invalid_response"
    # The unusable 200 may still be billed, so it is charged conservatively.
    assert error.value.unresolved_attempts == 1 and error.value.estimated_input_tokens > 0


def test_rejects_non_argmax_choice_and_unnormalized_probabilities() -> None:
    for probabilities, choice in (({"a": 0.7, "b": 0.3}, "b"), ({"a": 0.2, "b": 0.2}, "a")):
        bad = _body(answers={
            "pick": {"type": "choice", "choice": choice, "confidence": 0.5,
                     "probabilities": probabilities},
            "flag": {"type": "noul", "noul": 0.5},
        })
        with pytest.raises(TypeSafeError):
            _client(Transport((200, bad))).system_one("s", QUESTIONS)


def test_model_version_drift_fails_closed_but_keeps_usage_chargeable() -> None:
    with pytest.raises(TypeSafeError) as error:
        _client(Transport((200, _body(model="jev-1.14.0")))).system_one("s", QUESTIONS)
    assert error.value.kind == "model_mismatch"
    assert error.value.estimated_input_tokens == 400


def test_authentication_failure_is_not_retried() -> None:
    transport = Transport((401, b'{"detail":{"error_type":"authentication_error"}}'))
    with pytest.raises(TypeSafeError) as error:
        _client(transport).system_one("s", QUESTIONS)
    assert error.value.kind == "authentication" and len(transport.calls) == 1


def test_overload_is_retried_boundedly_then_succeeds() -> None:
    transport = Transport((529, b""), (429, b""), (200, _body()))
    result = _client(transport).system_one("s", QUESTIONS)
    assert len(transport.calls) == 3
    # Explicit rejections are not billed, so no conservative charge accrues.
    assert result.unresolved_attempts == 0 and result.estimated_input_tokens == 0


def test_transport_timeouts_are_charged_conservatively() -> None:
    transport = Transport(TimeoutError(), TimeoutError(), TimeoutError())
    with pytest.raises(TypeSafeError) as error:
        _client(transport).system_one("s", QUESTIONS)
    assert error.value.kind == "unavailable"
    assert error.value.unresolved_attempts == 3
    assert error.value.estimated_input_tokens > 0


def test_expired_deadline_sends_nothing() -> None:
    transport = Transport((200, _body()))
    client = _client(transport, clock=lambda: 100.0)
    with pytest.raises(TypeSafeError) as error:
        client.system_one("s", QUESTIONS, deadline=100.2)
    assert error.value.kind == "deadline" and transport.calls == []


def test_requires_a_key_and_hides_it_from_repr() -> None:
    with pytest.raises(ValueError):
        TypeSafeClient(" ", model=MODEL)
    assert "secret" not in repr(TypeSafeClient("secret-key", model=MODEL))


def test_omitted_zero_probability_options_are_accepted() -> None:
    sparse = _body(answers={
        "pick": {"type": "choice", "choice": "b", "confidence": 1.0, "probabilities": {"b": 1.0}},
        "flag": {"type": "noul", "noul": 0.5},
    })
    result = _client(Transport((200, sparse))).system_one("s", QUESTIONS)
    assert result.choice("pick").probabilities == {"a": 0.0, "b": 1.0}
