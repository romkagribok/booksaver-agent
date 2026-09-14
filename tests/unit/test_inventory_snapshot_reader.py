from __future__ import annotations

import asyncio
import json
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

import booksaver.infrastructure.browser.grouped_inventory_reader as adapter

ROOT = "https://secure.booking.com/mytrips.html"
TRIP = ROOT + "?trip_id=private-trip"
DETAIL = "https://secure.booking.com/confirmation.en-us.html?auth_key=private-auth"
HOTEL = "https://www.booking.com/hotel/nl/example.en-gb.html"


def _snapshot(**changes: Any) -> dict[str, Any]:
    return {
        "url": DETAIL,
        "text": "Private Hotel\nCheck-in\nFri, Sep 11, 2026",
        "links": [{"url": HOTEL, "text": "Private Hotel"}],
        "hotels": [{"url": HOTEL, "text": "Private Hotel"}],
        **changes,
    }


def _session(
    *, value: object | None = None, raw: object | None = None,
    race: str | None = None, stage: str = "evaluate",
) -> tuple[Any, list[dict[str, Any]]]:
    session = SimpleNamespace(agent_focus_target_id="private-target", url=DETAIL, targets=1)
    calls: list[dict[str, Any]] = []

    def mutate(point: str) -> None:
        if point != stage:
            return
        if race == "source":
            session.url = TRIP
        elif race == "focus":
            session.agent_focus_target_id = "other-target"
        elif race == "tabs":
            session.targets = 2

    async def url() -> str:
        return session.url

    async def pooled_session(target_id: str, *, focus: bool) -> Any:
        session.pool_calls.append((target_id, focus))
        mutate("pool")
        return session.pooled

    async def evaluate(**kwargs: Any) -> object:
        calls.append(kwargs)
        mutate("evaluate")
        return raw if raw is not None else {
            "result": {"value": json.dumps(value if value is not None else _snapshot())},
        }

    session.get_current_page_url = url
    session.get_current_page = AsyncMock(side_effect=AssertionError("Never create actor pages"))
    session.get_or_create_cdp_session = pooled_session
    session.pool_calls = []
    session.get_page_targets = lambda: [object() for _ in range(session.targets)]
    session.pooled = SimpleNamespace(
        target_id="private-target", session_id="private-cdp",
        cdp_client=SimpleNamespace(send=SimpleNamespace(Runtime=SimpleNamespace(evaluate=evaluate))),
    )
    session.cdp_client = SimpleNamespace(send=SimpleNamespace(Runtime=SimpleNamespace(
        evaluate=AsyncMock(side_effect=AssertionError("Use the pooled session's client")),
    )))
    return session, calls


def _read(session: Any) -> adapter.InventorySnapshot | None:
    return asyncio.run(adapter.read_inventory_snapshot(session))


def test_real_reader_captures_bounded_snapshot_from_explicit_cdp_session_privately(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session, calls = _session()
    result = _read(session)
    assert result is not None
    assert result.url == DETAIL
    assert result.text == _snapshot()["text"]
    assert [(link.url, link.text) for link in result.links] == [(HOTEL, "Private Hotel")]
    assert result.hotel_anchors == (("Private Hotel", HOTEL),)
    assert calls == [{
        "params": {"expression": adapter._READ, "returnByValue": True},
        "session_id": "private-cdp",
    }]
    assert session.pool_calls == [("private-target", False)]
    session.get_current_page.assert_not_called()
    session.cdp_client.send.Runtime.evaluate.assert_not_called()
    assert repr(result) == "InventorySnapshot()"
    assert repr(result.links[0]) == "RenderedLink()"
    assert caplog.text == ""
    with pytest.raises(FrozenInstanceError):
        result.text = "replacement"  # type: ignore[misc]


@pytest.mark.parametrize("url", [ROOT, TRIP, DETAIL])
def test_qualified_inventory_page_shapes_are_supported(url: str) -> None:
    session, _ = _session(value=_snapshot(url=url))
    session.url = url
    assert _read(session) is not None


@pytest.mark.parametrize("source", [
    "https://example.com/", "https://secure.booking.com/mysettings.html",
    ROOT + "?tab=past", DETAIL + "&action=cancel", ROOT + "#fragment",
])
def test_unqualified_source_is_rejected_before_reading(source: str) -> None:
    session, calls = _session()
    session.url = source
    assert _read(session) is None
    assert calls == []


@pytest.mark.parametrize("target", [None, "", 123])
def test_requires_nonempty_target_id_before_reading(target: object) -> None:
    session, calls = _session()
    session.agent_focus_target_id = target
    assert _read(session) is None
    assert calls == []


@pytest.mark.parametrize("tabs", [0, 2])
def test_requires_one_current_tab(tabs: int) -> None:
    session, calls = _session()
    session.targets = tabs
    assert _read(session) is None
    assert calls == []


def test_missing_pooled_session_is_rejected_without_cdp_read() -> None:
    session, calls = _session()
    session.pooled = None
    assert _read(session) is None
    assert calls == []


@pytest.mark.parametrize("sid", [None, "", 123, False, {}])
def test_requires_nonempty_string_cdp_session_id_before_evaluation(sid: object) -> None:
    session, calls = _session()

    session.pooled.session_id = sid
    assert _read(session) is None
    assert calls == []


@pytest.mark.parametrize("target", [None, "", 123, "different-caller-target"])
def test_pooled_session_must_belong_to_exact_captured_target(target: object) -> None:
    session, calls = _session()
    session.pooled.target_id = target
    assert _read(session) is None
    assert calls == []
    session.get_current_page.assert_not_called()


def test_repeated_snapshots_reuse_existing_pool_without_creating_actor_pages() -> None:
    session, calls = _session()
    original_pool_entry = session.pooled

    async def read_twice() -> None:
        first = await adapter.read_inventory_snapshot(session)
        second = await adapter.read_inventory_snapshot(session)
        assert first is not None and second == first

    asyncio.run(read_twice())
    assert session.pooled is original_pool_entry
    assert session.pool_calls == [("private-target", False)] * 2
    assert [call["session_id"] for call in calls] == ["private-cdp"] * 2
    session.get_current_page.assert_not_called()
    session.cdp_client.send.Runtime.evaluate.assert_not_called()


def test_pool_acquisition_failure_does_not_fall_back_to_actor_page() -> None:
    session, calls = _session()
    session.get_or_create_cdp_session = AsyncMock(side_effect=RuntimeError("pool unavailable"))
    assert _read(session) is None
    assert calls == []
    session.get_current_page.assert_not_called()


@pytest.mark.parametrize("stage", ["pool", "evaluate"])
@pytest.mark.parametrize("race", ["source", "focus", "tabs"])
def test_browser_binding_changes_during_awaits_discard_snapshot(stage: str, race: str) -> None:
    session, calls = _session(stage=stage, race=race)
    assert _read(session) is None
    if stage == "pool":
        assert calls == []


@pytest.mark.parametrize("read_number", [1, 2])
@pytest.mark.parametrize("race", ["focus", "tabs"])
def test_url_await_binding_mutation_prevents_evaluation(read_number: int, race: str) -> None:
    session, calls = _session()
    reads = 0

    async def url() -> str:
        nonlocal reads
        reads += 1
        if reads == read_number:
            if race == "focus":
                session.agent_focus_target_id = "other-caller-target"
            else:
                session.targets = 2
        return DETAIL

    session.get_current_page_url = url
    assert _read(session) is None
    assert calls == []
    if read_number == 1:
        assert session.pool_calls == []


def test_final_url_read_focus_change_is_rejected() -> None:
    session, _ = _session()
    reads = 0

    async def url() -> str:
        nonlocal reads
        reads += 1
        if reads == 3:
            session.agent_focus_target_id = "different-target"
        return DETAIL

    session.get_current_page_url = url
    assert _read(session) is None


@pytest.mark.parametrize("raw", [
    [], {}, {"result": []}, {"result": {}}, {"result": {"value": None}},
    {"result": {"value": 1}}, {"result": {"value": "{"}},
    {"result": {"value": "x" * 1_100_001}},
])
def test_malformed_cdp_or_serialized_result_fails_closed(raw: object) -> None:
    session, _ = _session(raw=raw)
    assert _read(session) is None


@pytest.mark.parametrize("value", [[], "private text", 1, {}])
def test_json_nonobject_or_missing_snapshot_fields_fails_closed(value: object) -> None:
    session, _ = _session(value=value)
    assert _read(session) is None


@pytest.mark.parametrize("url", [None, ROOT, DETAIL + "&aid=changed"])
def test_rendered_source_must_exactly_match_current_source(url: object) -> None:
    session, _ = _session(value=_snapshot(url=url))
    assert _read(session) is None


@pytest.mark.parametrize("body", [None, [], 123, "x" * 60_001])
def test_invalid_or_truncated_body_fails_closed(body: object) -> None:
    session, _ = _session(value=_snapshot(text=body))
    assert _read(session) is None


@pytest.mark.parametrize("field,limit", [("links", 250), ("hotels", 10)])
def test_anchor_count_overflow_is_rejected(field: str, limit: int) -> None:
    item = {"url": HOTEL, "text": "Private Hotel"}
    session, _ = _session(value=_snapshot(**{field: [item] * (limit + 1)}))
    assert _read(session) is None


@pytest.mark.parametrize("field", ["links", "hotels"])
@pytest.mark.parametrize("items", [
    None, {}, "private link", [None], [{}], [{"url": 1, "text": "name"}],
    [{"url": HOTEL, "text": None}], [{"url": "x" * 4001, "text": "name"}],
    [{"url": HOTEL, "text": "x" * 8001}],
])
def test_malformed_or_oversized_anchor_data_fails_closed(field: str, items: object) -> None:
    session, _ = _session(value=_snapshot(**{field: items}))
    assert _read(session) is None


def test_documented_size_boundaries_are_accepted_without_silent_truncation() -> None:
    links = [{"url": "x" * 4000, "text": "link"}] * 250
    hotels = [{"url": HOTEL, "text": "x" * 8000}]
    session, _ = _session(value=_snapshot(text="x" * 60_000, links=links, hotels=hotels))
    result = _read(session)
    assert result is not None
    assert len(result.text) == 60_000
    assert len(result.links) == 250
    assert len(result.hotel_anchors[0][0]) == 8000


def test_empty_collections_are_snapshot_evidence_not_account_completeness() -> None:
    session, _ = _session(value=_snapshot(text="", links=[], hotels=[]))
    result = _read(session)
    assert result is not None
    assert result.links == ()
    assert result.hotel_anchors == ()
    assert not hasattr(result, "complete")


@pytest.mark.parametrize("stage", ["url", "pool", "evaluate"])
def test_whole_operation_timeout_cancels_each_await_without_logging(
    stage: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    real_timeout = asyncio.timeout
    cancelled: list[bool] = []

    def short_timeout(delay: float) -> Any:
        assert delay == 5
        return real_timeout(0.001)

    async def block(*args: Any, **kwargs: Any) -> Any:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    session, _ = _session()
    if stage == "url":
        session.get_current_page_url = block
    elif stage == "pool":
        session.get_or_create_cdp_session = block
    else:
        session.pooled.cdp_client.send.Runtime.evaluate = block
    monkeypatch.setattr(adapter.asyncio, "timeout", short_timeout)
    assert _read(session) is None
    assert cancelled == [True]
    assert caplog.text == ""


def test_exception_containing_page_secret_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    session, _ = _session()

    async def fail(**kwargs: Any) -> Any:
        raise RuntimeError(DETAIL)

    session.pooled.cdp_client.send.Runtime.evaluate = fail
    assert _read(session) is None
    assert caplog.text == ""


@pytest.mark.parametrize("count", [True, False, 0, -1, 100, 3.0, "3", []])
def test_invalid_rendered_booking_count_fails_closed(count: object) -> None:
    session, _ = _session(value=_snapshot(links=[{
        "url": HOTEL, "text": "Private Hotel", "booking_count": count,
    }]))
    assert _read(session) is None


def test_rendered_booking_count_is_kept_as_bounded_metadata() -> None:
    session, _ = _session(value=_snapshot(links=[{
        "url": HOTEL, "text": "Private Hotel", "booking_count": 4,
    }]))
    result = _read(session)
    assert result is not None
    assert result.links[0].booking_count == 4
    assert repr(result.links[0]) == "RenderedLink()"
