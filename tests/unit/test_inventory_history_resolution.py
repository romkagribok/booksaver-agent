from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any

import pytest

import booksaver.infrastructure.browser.inventory_history_resolution as adapter

ROOT = "https://secure.booking.com/mytrips.html"
TRIP = ROOT + "?trip_id=private-trip&aid=1"
DETAIL = "https://secure.booking.com/confirmation.en-us.html?auth_key=private-auth"
DESKTOP = DETAIL + "&prefer_site_type=www"


def _history(*urls: str) -> dict[str, Any]:
    return {
        "currentIndex": len(urls) - 1,
        "entries": [{"id": 100 + index, "url": url} for index, url in enumerate(urls)],
    }


def _session(
    history: object | None = None, *, source: str = DESKTOP,
    race: str | None = None, race_stage: str = "history",
) -> tuple[Any, list[dict[str, Any]]]:
    session = SimpleNamespace(agent_focus_target_id="private-focus", url=source, targets=1)
    calls: list[dict[str, Any]] = []

    def mutate(stage: str) -> None:
        if stage != race_stage:
            return
        if race == "focus":
            session.agent_focus_target_id = "different-focus"
        elif race == "source":
            session.url = DETAIL
        elif race == "tabs":
            session.targets = 2

    async def current_url() -> str:
        return session.url

    async def pooled_session(target_id: str, *, focus: bool) -> Any:
        session.pool_calls.append((target_id, focus))
        mutate("pool")
        return session.pooled

    async def forbidden_page() -> Any:
        raise AssertionError("actor page acquisition must never be used")

    async def get_history(**kwargs: Any) -> object:
        calls.append(kwargs)
        mutate("history")
        return history if history is not None else _history(ROOT, TRIP, DETAIL, DESKTOP)

    session.get_current_page_url = current_url
    session.get_page_targets = lambda: [object() for _ in range(session.targets)]
    session.get_current_page = forbidden_page
    # Deliberately no navigation methods: this helper must only qualify an entry.
    session.cdp_client = SimpleNamespace(
        send=SimpleNamespace(Page=SimpleNamespace(getNavigationHistory=get_history)),
    )
    session.pooled = SimpleNamespace(
        target_id="private-focus", session_id="private-cdp", cdp_client=session.cdp_client,
    )
    session.pool_calls = []
    session.get_or_create_cdp_session = pooled_session
    return session, calls


def _resolve(session: Any, parent: str = TRIP) -> adapter.ResolvedInventoryHistoryReturn | None:
    return asyncio.run(
        adapter.resolve_inventory_history_return(session, observed_parent_url=parent),
    )


def test_skips_mobile_reload_to_actual_parent_entry_without_navigation_or_secret_output(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session, calls = _session()
    result = _resolve(session, ROOT + "?label=changed&trip_id=private-trip")
    assert result is not None
    assert (result.source_url, result.target_url) == (DESKTOP, TRIP)
    assert (result.entry_id, result.target_id, result.session_id) == (
        101, "private-focus", "private-cdp",
    )
    assert calls == [{"params": {}, "session_id": "private-cdp"}]
    assert repr(result) == "ResolvedInventoryHistoryReturn()"
    assert caplog.text == ""
    with pytest.raises(FrozenInstanceError):
        result.entry_id = 999  # type: ignore[misc]


def test_trip_can_return_to_observed_root_with_tracking_alias() -> None:
    actual_root = ROOT + "?sid=private-session&aid=2"
    session, _ = _session(_history(actual_root, TRIP), source=TRIP)
    result = _resolve(session, ROOT)
    assert result is not None
    assert result.target_url == actual_root


def test_selects_latest_earlier_parent_not_forward_or_older_entry() -> None:
    actual_parent = TRIP + "&label=latest"
    history = _history(TRIP, DETAIL, actual_parent, DESKTOP, TRIP)
    history["currentIndex"] = 3
    session, _ = _session(history)
    result = _resolve(session)
    assert result is not None
    assert (result.entry_id, result.target_url) == (102, actual_parent)


@pytest.mark.parametrize("unsafe", [
    "https://example.com/", "https://secure.booking.com/mysettings.html",
    ROOT + "?tab=past", TRIP + "&status=cancelled", DETAIL + "&action=cancel",
])
def test_rejects_unsafe_or_noninventory_intermediate_history(unsafe: str) -> None:
    session, _ = _session(_history(ROOT, TRIP, unsafe, DESKTOP))
    assert _resolve(session) is None


def test_unrelated_history_before_parent_or_after_current_is_not_traversed() -> None:
    history = _history("https://example.com/", TRIP, DESKTOP, "https://example.com/")
    history["currentIndex"] = 2
    session, _ = _session(history)
    assert _resolve(session) is not None


@pytest.mark.parametrize("parent", [
    DETAIL, ROOT + "?trip_id=other", "https://www.booking.com/mytrips.html",
    ROOT + "?tab=past", ROOT + "#trip", ROOT + "?" + "a=1&" * 201,
    ROOT + "?label=" + "x" * 4_000,
])
def test_rejects_unqualified_or_unobserved_parent(parent: str) -> None:
    session, _ = _session()
    assert _resolve(session, parent) is None


@pytest.mark.parametrize("source", [ROOT, "https://example.com/", ROOT + "?tab=past"])
def test_rejects_unqualified_source(source: str) -> None:
    session, calls = _session(source=source)
    assert _resolve(session) is None
    assert calls == []


def test_does_not_use_matching_forward_entry() -> None:
    history = _history(DETAIL, DESKTOP, TRIP)
    history["currentIndex"] = 1
    session, _ = _session(history)
    assert _resolve(session) is None


@pytest.mark.parametrize("index", [-1, 4, True, 1.0, "3", None])
def test_rejects_malformed_current_index(index: object) -> None:
    history = _history(ROOT, TRIP, DETAIL, DESKTOP)
    history["currentIndex"] = index
    session, _ = _session(history)
    assert _resolve(session) is None


@pytest.mark.parametrize("value", [True, -1, 2_147_483_648, "101", None, 100])
def test_rejects_invalid_or_duplicate_entry_ids(value: object) -> None:
    history = _history(ROOT, TRIP, DETAIL, DESKTOP)
    history["entries"][1]["id"] = value
    session, _ = _session(history)
    assert _resolve(session) is None


@pytest.mark.parametrize("history", [
    [], {}, {"entries": [], "currentIndex": 0},
    {"entries": [None], "currentIndex": 0},
    {"entries": [{"id": 1, "url": None}], "currentIndex": 0},
    {"entries": [{"id": 1, "url": "x" * 4001}], "currentIndex": 0},
    _history(*([TRIP] * 100), DESKTOP),
    {**_history(TRIP, DESKTOP), "private-title": "x" * 1_100_000},
])
def test_rejects_malformed_or_oversized_history(history: object) -> None:
    session, _ = _session(history)
    assert _resolve(session) is None


def test_current_history_url_must_exactly_match_current_source() -> None:
    session, _ = _session(_history(TRIP, DESKTOP + "&aid=tracking-change"))
    assert _resolve(session) is None


@pytest.mark.parametrize("missing", ["focus", "pool", "session", "single_tab"])
def test_missing_current_browser_binding_fails_closed(missing: str) -> None:
    session, calls = _session()
    if missing == "focus":
        session.agent_focus_target_id = None
    elif missing == "single_tab":
        session.targets = 0
    else:
        async def pooled_session(target_id: str, *, focus: bool) -> Any:
            if missing == "pool":
                return None
            session.pooled.session_id = None
            return session.pooled

        session.get_or_create_cdp_session = pooled_session
    assert _resolve(session) is None
    assert calls == []


@pytest.mark.parametrize("race", ["source", "focus", "tabs"])
@pytest.mark.parametrize("stage", ["pool", "history"])
def test_rejects_source_focus_or_tab_change_during_awaits(race: str, stage: str) -> None:
    session, _ = _session(race=race, race_stage=stage)
    assert _resolve(session) is None


@pytest.mark.parametrize("stage", ["url", "pool", "history"])
def test_whole_resolution_timeout_bounds_every_acquisition(
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
        session.cdp_client.send.Page.getNavigationHistory = block
    monkeypatch.setattr(adapter.asyncio, "timeout", short_timeout)
    assert _resolve(session) is None
    assert cancelled == [True]
    assert caplog.text == ""


def test_cdp_exception_is_private_and_fails_closed(caplog: pytest.LogCaptureFixture) -> None:
    session, _ = _session()

    async def fail(**kwargs: Any) -> Any:
        raise RuntimeError(DESKTOP)

    session.cdp_client.send.Page.getNavigationHistory = fail
    assert _resolve(session) is None
    assert caplog.text == ""


@pytest.mark.parametrize("field,value", [
    ("target_id", "wrong-target"), ("target_id", None),
    ("session_id", None), ("session_id", ""), ("session_id", 123), ("session_id", False),
])
def test_rejects_unbound_pooled_session_before_reading_history(field: str, value: object) -> None:
    session, calls = _session()
    setattr(session.pooled, field, value)
    assert _resolve(session) is None
    assert calls == []


def test_repeated_history_reads_reuse_pool_without_actor_pages_or_root_client() -> None:
    session, calls = _session()
    session.cdp_client = None

    async def repeat() -> None:
        for _ in range(20):
            result = await adapter.resolve_inventory_history_return(
                session, observed_parent_url=TRIP,
            )
            assert result is not None
            assert result.session_id == "private-cdp"

    asyncio.run(repeat())
    assert session.pool_calls == [("private-focus", False)] * 20
    assert calls == [{"params": {}, "session_id": "private-cdp"}] * 20
