import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

import booksaver.infrastructure.browser.inventory_empty_state as empty_adapter
from booksaver.infrastructure.browser.inventory_empty_state import (
    explicit_empty_upcoming,
    observe_empty_upcoming,
)

ROOT = "https://secure.booking.com/mytrips.html"
EMPTY = (
    "Bookings & Trips Find a booking Active Past Canceled Where to next? "
    "You haven’t started any trips yet. Once you make a booking, it'll appear here."
)


def test_explicit_initial_empty_trips_is_recognized():
    assert explicit_empty_upcoming(ROOT, EMPTY)


@pytest.mark.parametrize("text", [
    "Bookings & Trips Active Loading", "", "No bookings", EMPTY + " 1 booking",
    EMPTY.replace("Bookings & Trips", "Search"), EMPTY.replace("Active", ""),
    "x" * 250_001,
])
def test_missing_or_contradictory_empty_evidence_is_not_accepted(text):
    assert not explicit_empty_upcoming(ROOT, text)


@pytest.mark.parametrize("url", [
    ROOT + "?trip_id=abc", ROOT + "?tab=past", ROOT + "#past",
    "https://secure.booking.com/confirmation.en-us.html", "https://example.com/mytrips.html",
])
def test_empty_claim_outside_initial_trips_page_is_not_accepted(url):
    assert not explicit_empty_upcoming(url, EMPTY)


def test_provider_cannot_claim_code_owned_empty_result():
    from booksaver.infrastructure.browser.agentic_inventory_executor import _terminal_status

    with pytest.raises(ValueError, match="cannot submit an observation"):
        _terminal_status("empty_upcoming")


def _rendered_session(response: object) -> tuple[Any, list[dict[str, Any]]]:
    reads: list[dict[str, Any]] = []
    session = SimpleNamespace(agent_focus_target_id="current-target", url=ROOT, targets=1)

    async def evaluate(**kwargs: Any) -> object:
        reads.append(kwargs)
        return response

    async def current_url() -> str:
        return session.url

    async def pooled_session(target_id: str, *, focus: bool) -> Any:
        session.pool_calls.append((target_id, focus))
        return session.pooled

    async def forbidden_page() -> Any:
        raise AssertionError("Actor page acquisition must never be used")

    session.pooled = SimpleNamespace(
        target_id="current-target", session_id="qualified-current-page",
        cdp_client=SimpleNamespace(send=SimpleNamespace(Runtime=SimpleNamespace(evaluate=evaluate))),
    )
    session.pool_calls = []
    session.get_current_page_url = current_url
    session.get_page_targets = lambda: [object() for _ in range(session.targets)]
    session.get_current_page = forbidden_page
    session.get_or_create_cdp_session = pooled_session
    return session, reads


def test_rendered_empty_read_uses_bounded_fixed_expression_without_logging_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_marker = "PRIVATE-PAGE-CONTENT-MUST-NOT-BE-LOGGED"
    session, reads = _rendered_session({"result": {"value": json.dumps({
        "url": ROOT, "text": EMPTY + " " + private_marker,
    })}})

    assert asyncio.run(observe_empty_upcoming(session)) is True

    assert len(reads) == 1
    assert reads[0]["session_id"] == "qualified-current-page"
    params = reads[0]["params"]
    assert params["returnByValue"] is True
    assert params["expression"] == (
        "JSON.stringify({url: location.href, "
        "text: (document.body?.innerText || '').slice(0, 250001)})"
    )
    assert private_marker not in caplog.text
    assert EMPTY not in caplog.text
    assert ROOT not in caplog.text


@pytest.mark.parametrize("response", [
    None,
    [],
    {},
    {"result": None},
    {"result": {"value": "PRIVATE-MALFORMED-JSON"}},
    {"result": {"value": "[]"}},
    {"result": {"value": json.dumps({"url": ROOT, "text": None})}},
    {"result": {"value": json.dumps({"url": ROOT + "?tab=past", "text": EMPTY})}},
    {"result": {"value": json.dumps({"url": ROOT, "text": EMPTY + " 2 bookings"})}},
    {"result": {"value": json.dumps({"url": ROOT, "text": EMPTY + "x" * 250_001})}},
])
def test_unusable_rendered_result_fails_closed_without_exposing_content(
    response: object, caplog: pytest.LogCaptureFixture,
) -> None:
    session, _reads = _rendered_session(response)

    assert asyncio.run(observe_empty_upcoming(session)) is False

    assert "PRIVATE" not in caplog.text
    assert EMPTY not in caplog.text
    assert ROOT not in caplog.text


@pytest.mark.parametrize("stage", ["url", "pool", "evaluate"])
def test_rendered_read_timeout_fails_closed_without_logging_exception(
    stage: str,
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    session, _reads = _rendered_session({})

    real_timeout = asyncio.timeout
    cancelled = []

    def short_timeout(delay: float) -> Any:
        assert delay == 5
        return real_timeout(0.001)

    async def block(*args: Any, **kwargs: Any) -> Any:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    if stage == "url":
        session.get_current_page_url = block
    elif stage == "pool":
        session.get_or_create_cdp_session = block
    else:
        session.pooled.cdp_client.send.Runtime.evaluate = block
    monkeypatch.setattr(empty_adapter.asyncio, "timeout", short_timeout)

    assert asyncio.run(observe_empty_upcoming(session)) is False
    assert cancelled == [True]
    assert "PRIVATE" not in caplog.text


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_unavailable_pooled_session_fails_closed(
    missing: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    session, reads = _rendered_session({})

    async def get_session(target_id: str, *, focus: bool) -> None:
        if missing:
            return None
        raise RuntimeError("PRIVATE-PAGE-ERROR")

    session.get_or_create_cdp_session = get_session
    assert asyncio.run(observe_empty_upcoming(session)) is False
    assert reads == []
    assert "PRIVATE" not in caplog.text


def test_copyright_and_zero_booking_label_do_not_contradict_empty_account():
    assert explicit_empty_upcoming(
        ROOT, EMPTY + " 0 bookings Copyright © 1996–2026 Booking.com™. All rights reserved."
    )


@pytest.mark.parametrize("field,value", [
    ("target_id", "wrong-target"), ("target_id", None),
    ("session_id", None), ("session_id", ""), ("session_id", 123), ("session_id", False),
])
def test_unbound_pool_rejected_before_read(field: str, value: object) -> None:
    session, reads = _rendered_session({})
    setattr(session.pooled, field, value)
    assert asyncio.run(observe_empty_upcoming(session)) is False
    assert reads == []


@pytest.mark.parametrize("stage", ["pool", "read"])
@pytest.mark.parametrize("race", ["source", "focus", "tabs"])
def test_browser_binding_change_discards_empty_claim(stage: str, race: str) -> None:
    response = {"result": {"value": json.dumps({"url": ROOT, "text": EMPTY})}}
    session, _reads = _rendered_session(response)

    def mutate() -> None:
        if race == "source":
            session.url = ROOT + "?trip_id=changed"
        elif race == "focus":
            session.agent_focus_target_id = "changed-target"
        else:
            session.targets = 2

    if stage == "pool":
        async def pool(target_id: str, *, focus: bool) -> Any:
            mutate()
            return session.pooled
        session.get_or_create_cdp_session = pool
    else:
        async def evaluate(**kwargs: Any) -> object:
            mutate()
            return response
        session.pooled.cdp_client.send.Runtime.evaluate = evaluate
    assert asyncio.run(observe_empty_upcoming(session)) is False


def test_repeated_empty_reads_reuse_pool_without_actor_pages_or_root_client() -> None:
    session, reads = _rendered_session({
        "result": {"value": json.dumps({"url": ROOT, "text": EMPTY})},
    })
    assert not hasattr(session, "cdp_client")

    async def repeat() -> None:
        for _ in range(20):
            assert await observe_empty_upcoming(session) is True

    asyncio.run(repeat())
    assert session.pool_calls == [("current-target", False)] * 20
    assert len(reads) == 20
    assert all(read["session_id"] == "qualified-current-page" for read in reads)
