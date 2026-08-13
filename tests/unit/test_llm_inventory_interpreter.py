"""Strict positive-only inventory interpretation at the provider boundary."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from anthropic.types import TextBlock

from booksaver.domain.account_sync import ReservationLifecycle
from booksaver.domain.agent import LLMUsage
from booksaver.infrastructure.llm.anthropic_adapter import (
    AnthropicInventoryInterpreter,
    LLMFailureKind,
    LLMProviderError,
    has_non_authoritative_inventory_negative_claims,
    parse_inventory_response,
)

SOURCE_URL = "https://secure.booking.com/myreservations?token=secret#private"
OBSERVED_AT = datetime(2026, 8, 2, 18, 30, tzinfo=UTC)


def _item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "remote_id": "reservation-123",
        "lifecycle": "upcoming",
        "confirmation_id": "CONF-123",
        "property_name": "Example Hotel",
        "property_ref": "/hotel/example",
        "check_in": "2026-09-01",
        "check_out": "2026-09-03",
        "room_type": "King Room",
        "booked_total": {"amount": "245.50", "currency": "USD"},
        "refundable": True,
        "refund_note": "Free cancellation",
        "refund_deadline": "2026-08-28",
        "occupancy": {"adults": 2, "children": 0, "rooms": 1},
    }
    item.update(overrides)
    return item


def _parse(*items: object, source_url: str = SOURCE_URL):
    return parse_inventory_response(
        json.dumps(items), source_url, observed_at=OBSERVED_AT
    )


def test_parses_complete_positive_observation_and_marks_provenance() -> None:
    observations = _parse(_item())

    assert len(observations) == 1
    observation = observations[0]
    assert observation.remote_id == "reservation-123"
    assert observation.lifecycle is ReservationLifecycle.UPCOMING
    assert observation.booked_total is not None
    assert str(observation.booked_total.amount) == "245.50"
    assert observation.occupancy is not None
    assert observation.occupancy.adults == 2
    assert observation.extraction_method == "llm_inventory"
    assert observation.observed_at == OBSERVED_AT
    assert observation.source_url == "https://secure.booking.com/myreservations"


@pytest.mark.parametrize(
    "overrides",
    [
        {"remote_id": None},
        {"remote_id": "  "},
        {"lifecycle": "invented"},
        {"lifecycle": "absent"},
        {"check_in": "not-a-date"},
        {"check_out": "2026-08-30"},
        {"booked_total": {"amount": "NaN", "currency": "USD"}},
        {"booked_total": {"amount": "1", "currency": "dollars"}},
        {"occupancy": {"adults": 0, "children": 0, "rooms": 1}},
        {"occupancy": {"adults": True, "children": 0, "rooms": 1}},
        {"refundable": "yes"},
        {"property_ref": "javascript:alert(1)"},
        {"property_ref": "https://evil.example/hotel/example"},
    ],
)
def test_malformed_or_non_positive_item_fails_closed(overrides: dict[str, object]) -> None:
    assert _parse(_item(**overrides)) == ()


def test_one_malformed_item_rejects_whole_model_reply() -> None:
    assert _parse(_item(), _item(remote_id="reservation-2", lifecycle="absent")) == ()


@pytest.mark.parametrize("lifecycle", ["completed", "cancelled"])
def test_seen_negative_lifecycle_is_explicitly_non_authoritative(lifecycle: str) -> None:
    observations = _parse(_item(lifecycle=lifecycle))

    assert len(observations) == 1
    assert has_non_authoritative_inventory_negative_claims(observations[0])


def test_non_refundable_model_claim_is_explicitly_non_authoritative() -> None:
    observations = _parse(_item(refundable=False))

    assert len(observations) == 1
    assert has_non_authoritative_inventory_negative_claims(observations[0])


def test_duplicate_remote_identity_is_ambiguous() -> None:
    assert _parse(_item(), _item()) == ()


@pytest.mark.parametrize(
    "source_url",
    [
        "http://www.booking.com/mytrips",
        "https://booking.com.evil.example/mytrips",
        "https://evil.example/mytrips",
        "not a url",
    ],
)
def test_non_booking_or_non_https_provenance_is_rejected(source_url: str) -> None:
    assert _parse(_item(), source_url=source_url) == ()


@pytest.mark.parametrize("raw", ["not json", "{}", '[{"remote_id":'])
def test_malformed_provider_output_is_empty(raw: str) -> None:
    assert parse_inventory_response(raw, SOURCE_URL, observed_at=OBSERVED_AT) == ()


def test_empty_array_is_valid_positive_evidence_but_not_completeness() -> None:
    assert parse_inventory_response("[]", SOURCE_URL, observed_at=OBSERVED_AT) == ()


def test_interpreter_uses_bounded_versioned_positive_only_prompt() -> None:
    calls: list[dict[str, object]] = []

    class _Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                content=[TextBlock(type="text", text=json.dumps([_item()]))],
                usage=SimpleNamespace(input_tokens=321, output_tokens=87),
            )

    interpreter = AnthropicInventoryInterpreter.__new__(AnthropicInventoryInterpreter)
    interpreter._client = SimpleNamespace(messages=_Messages())  # noqa: SLF001
    interpreter._model = "test-model"  # noqa: SLF001

    observations = interpreter.interpret("visible booking facts", SOURCE_URL)

    assert len(observations) == 1
    prompt = calls[0]["messages"][0]["content"]  # type: ignore[index]
    assert "booking-inventory-interpretation-v1" in prompt
    assert "Never report absence" in prompt
    assert "inventory completeness" in prompt
    assert "visible booking facts" in prompt
    assert "complete" not in _item()
    assert interpreter.last_usage == LLMUsage(input_tokens=321, output_tokens=87)


def test_interpreter_resets_usage_when_provider_omits_it() -> None:
    class _Messages:
        def create(self, **kwargs):
            return SimpleNamespace(
                content=[TextBlock(type="text", text="[]")],
            )

    interpreter = AnthropicInventoryInterpreter.__new__(AnthropicInventoryInterpreter)
    interpreter._client = SimpleNamespace(messages=_Messages())  # noqa: SLF001
    interpreter._model = "test-model"  # noqa: SLF001
    interpreter.last_usage = LLMUsage(99, 99)

    assert interpreter.interpret("visible booking facts", SOURCE_URL) == ()
    assert interpreter.last_usage is None


def test_inventory_provider_exception_fails_closed() -> None:
    class _Messages:
        def create(self, **kwargs):
            raise TimeoutError("sensitive provider detail")

    interpreter = AnthropicInventoryInterpreter.__new__(AnthropicInventoryInterpreter)
    interpreter._client = SimpleNamespace(messages=_Messages())  # noqa: SLF001
    interpreter._model = "test-model"  # noqa: SLF001
    interpreter.last_usage = LLMUsage(99, 99)

    with pytest.raises(LLMProviderError) as raised:
        interpreter.interpret("visible booking facts", SOURCE_URL)

    assert str(raised.value) == "inventory interpreter provider call failed"
    assert raised.value.kind is LLMFailureKind.TRANSPORT
    assert "sensitive provider detail" not in str(raised.value)
    assert interpreter.last_usage is None
