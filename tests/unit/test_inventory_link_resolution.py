from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any

import pytest

import booksaver.infrastructure.browser.inventory_link_resolution as adapter
from booksaver.infrastructure.browser.inventory_link_resolution import (
    resolve_rendered_confirmation_view,
    resolve_rendered_inventory_link,
)

ROOT = "https://secure.booking.com/mytrips.html"
TRIP = ROOT + "?trip_id=private-trip"
DETAIL = "https://secure.booking.com/confirmation.en-us.html?auth_key=private-auth&aid=1"
MANAGE = "https://secure.booking.com/confirmation.html?auth_key=private-auth"
DESKTOP = DETAIL + "&prefer_site_type=www"


def _chain(target: str = TRIP) -> list[dict[str, Any]]:
    return [
        {
            "node_name": "a",
            "label": "Trip details",
            "attributes": {"href": target},
            "visible": True,
        },
        {"node_name": "body", "label": "", "attributes": {}, "visible": True},
        {"node_name": "html", "label": "", "attributes": {}, "visible": True},
    ]


def _evidence(target: str = TRIP) -> dict[str, Any]:
    return {
        "url": ROOT,
        "href": target,
        "matched": 1,
        "connected": True,
        "complete": True,
        "chain": _chain(target),
    }


def _session(
    responses: list[object] | None = None,
    *,
    race: str | None = None,
    race_read: int = 1,
) -> tuple[Any, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    responses = (
        responses
        if responses is not None
        else [
            {"url": ROOT, "hrefs": [TRIP]},
            _evidence(),
        ]
    )
    session = SimpleNamespace(agent_focus_target_id="current-target", url=ROOT, targets=1)

    async def current_url() -> str:
        return session.url

    async def pooled_session(target_id: str, *, focus: bool) -> Any:
        session.pool_calls.append((target_id, focus))
        return session.pooled

    async def forbidden_page() -> Any:
        raise AssertionError("actor page acquisition must never be used")

    async def evaluate(**kwargs: Any) -> object:
        calls.append(kwargs)
        if race and len(calls) == race_read:
            if race == "url":
                session.url = TRIP
            elif race == "focus":
                session.agent_focus_target_id = "different-target"
            else:
                session.targets = 2
        value = responses[(len(calls) - 1) % len(responses)]
        return {"result": {"value": json.dumps(value)}}

    session.get_current_page_url = current_url
    session.get_page_targets = lambda: [object() for _ in range(session.targets)]
    session.get_current_page = forbidden_page
    session.cdp_client = SimpleNamespace(
        send=SimpleNamespace(Runtime=SimpleNamespace(evaluate=evaluate)),
    )
    session.pooled = SimpleNamespace(
        target_id="current-target", session_id="current-page-cdp", cdp_client=session.cdp_client,
    )
    session.pool_calls = []
    session.get_or_create_cdp_session = pooled_session
    return session, calls


def test_resolves_real_anchor_without_navigation_or_exposing_private_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session, calls = _session()
    resolved = asyncio.run(
        resolve_rendered_inventory_link(
            session,
            source_url=ROOT,
            observed_target_url=TRIP,
        )
    )
    assert resolved is not None
    assert resolved.source_url == ROOT
    assert resolved.target_url == TRIP
    assert resolved.target_id == "current-target"
    assert resolved.chain[0]["attributes"]["href"] == TRIP
    assert len(calls) == 2
    assert all(call["session_id"] == "current-page-cdp" for call in calls)
    assert all(call["params"]["returnByValue"] is True for call in calls)
    assert "elementFromPoint" not in calls[1]["params"]["expression"]
    assert "getClientRects" in calls[1]["params"]["expression"]
    assert "private" not in repr(resolved)
    assert ROOT not in repr(resolved)
    assert not caplog.text
    with pytest.raises(FrozenInstanceError):
        resolved.target_url = "different"  # type: ignore[misc]
    with pytest.raises(TypeError):
        resolved.chain[0]["attributes"]["href"] = "different"


def test_canonical_alias_selects_fresh_full_href_but_never_other_confirmation_path() -> None:
    fresh = (
        "https://secure.booking.com/confirmation.en-us.html?aid=2&auth_key=private-auth&label=new"
    )
    session, _calls = _session([{"url": ROOT, "hrefs": [MANAGE, fresh]}, _evidence(fresh)])
    resolved = asyncio.run(
        resolve_rendered_inventory_link(
            session,
            source_url=ROOT,
            observed_target_url=DETAIL,
        )
    )
    assert resolved is not None
    assert resolved.target_url == fresh


@pytest.mark.parametrize("hrefs", [[], [TRIP, TRIP], [MANAGE], [TRIP + "&view=other"], [None]])
def test_missing_ambiguous_or_different_target_does_not_request_chain(hrefs: object) -> None:
    session, calls = _session([{"url": ROOT, "hrefs": hrefs}])
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=ROOT,
                observed_target_url=TRIP,
            )
        )
        is None
    )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "source,target",
    [
        (DETAIL, TRIP),
        (ROOT + "?tab=past", TRIP),
        (ROOT, ROOT),
        (ROOT, "https://outside.example/"),
        (ROOT, DETAIL + "&action=cancel"),
        (ROOT, DETAIL + "&auth_key=second"),
    ],
)
def test_only_qualified_root_or_trip_sources_and_targets_are_accepted(
    source: str,
    target: str,
) -> None:
    session, calls = _session()
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=source,
                observed_target_url=target,
            )
        )
        is None
    )
    assert not calls


@pytest.mark.parametrize("race", ["url", "focus", "tab"])
@pytest.mark.parametrize("race_read", [1, 2])
def test_changed_source_or_focus_during_either_read_is_rejected(race: str, race_read: int) -> None:
    session, calls = _session(race=race, race_read=race_read)
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=ROOT,
                observed_target_url=TRIP,
            )
        )
        is None
    )
    assert len(calls) == race_read


@pytest.mark.parametrize(
    "change",
    [
        {"url": TRIP},
        {"href": DETAIL},
        {"matched": 0},
        {"matched": 2},
        {"matched": True},
        {"connected": False},
        {"complete": False},
        {"overflow": True},
        {"chain": None},
        {"chain": []},
        {"chain": _chain() * 6},
    ],
)
def test_incomplete_or_changed_fresh_chain_evidence_is_rejected(change: dict[str, Any]) -> None:
    session, _calls = _session([{"url": ROOT, "hrefs": [TRIP]}, {**_evidence(), **change}])
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=ROOT,
                observed_target_url=TRIP,
            )
        )
        is None
    )


@pytest.mark.parametrize(
    "node,change",
    [
        (0, {"visible": False}),
        (1, {"visible": False}),
        (0, {"node_name": "div"}),
        (0, {"label": "Cancel booking"}),
        (0, {"label": "x" * 1001}),
        (0, {"attributes": {"href": DETAIL}}),
        (0, {"attributes": {}}),
        (0, {"attributes": {"href": TRIP, "title": "x" * 1001}}),
        (1, {"attributes": {"onclick": "private-handler()"}}),
        (1, {"node_name": "form"}),
        (1, {"attributes": {"action": "/payment"}}),
        (0, {"attributes": {"href": TRIP, "download": ""}}),
        (0, {"attributes": {"href": TRIP, "aria-disabled": "true"}}),
    ],
)
def test_real_anchor_and_ancestor_metadata_pass_unchanged_guard_or_fail(
    node: int,
    change: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    evidence = deepcopy(_evidence())
    evidence["chain"][node].update(change)
    session, _calls = _session([{"url": ROOT, "hrefs": [TRIP]}, evidence])
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=ROOT,
                observed_target_url=TRIP,
            )
        )
        is None
    )
    assert not caplog.text


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {},
        {"url": TRIP, "hrefs": [TRIP]},
        {"url": ROOT, "hrefs": None},
        {"url": ROOT, "hrefs": [TRIP] * 251},
        {"url": ROOT, "hrefs": ["x" * 4001]},
    ],
)
def test_malformed_first_read_fails_closed(response: object) -> None:
    session, _calls = _session([response])
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=ROOT,
                observed_target_url=TRIP,
            )
        )
        is None
    )


@pytest.mark.parametrize("stage", ["url", "pool"])
def test_whole_resolution_timeout_cancels_acquisition_without_logging(
    stage: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    original_timeout = asyncio.timeout
    cancelled: list[bool] = []

    def timeout(delay: float) -> Any:
        assert delay == 5
        return original_timeout(0.001)

    async def blocked_url(*args: Any, **kwargs: Any) -> str:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)
        return ROOT

    session, _calls = _session()
    if stage == "url":
        session.get_current_page_url = blocked_url
    else:
        session.get_or_create_cdp_session = blocked_url
    monkeypatch.setattr(adapter.asyncio, "timeout", timeout)

    async def bounded() -> Any:
        return await asyncio.wait_for(
            resolve_rendered_inventory_link(
                session,
                source_url=ROOT,
                observed_target_url=TRIP,
            ),
            timeout=0.5,
        )

    assert asyncio.run(bounded()) is None
    assert cancelled == [True]
    assert not caplog.text


@pytest.mark.parametrize("field,value", [
    ("target_id", "wrong-target"), ("target_id", None),
    ("session_id", None), ("session_id", ""), ("session_id", 123), ("session_id", False),
])
def test_rejects_unbound_pooled_session_before_any_anchor_read(field: str, value: object) -> None:
    session, calls = _session()
    setattr(session.pooled, field, value)
    assert asyncio.run(resolve_rendered_inventory_link(
        session, source_url=ROOT, observed_target_url=TRIP,
    )) is None
    assert calls == []


def test_repeated_link_reads_reuse_target_pool_without_actor_pages_or_root_client() -> None:
    session, calls = _session()
    session.cdp_client = None  # Reads must use the pooled client, not the root facade.

    async def repeat() -> None:
        for _ in range(20):
            result = await resolve_rendered_inventory_link(
                session, source_url=ROOT, observed_target_url=TRIP,
            )
            assert result is not None

    asyncio.run(repeat())
    assert session.pool_calls == [("current-target", False)] * 20
    assert len(calls) == 40
    assert all(call["session_id"] == "current-page-cdp" for call in calls)


@pytest.mark.parametrize(
    "state", ["missing_focus", "wrong_source", "missing_pool", "changed_focus"]
)
def test_unbound_or_changed_page_acquisition_never_reads_anchors(state: str) -> None:
    session, calls = _session()
    if state == "missing_focus":
        session.agent_focus_target_id = None
    elif state == "wrong_source":
        session.url = TRIP
    else:

        async def pooled_session(target_id: str, *, focus: bool) -> Any:
            if state == "missing_pool":
                return None
            session.agent_focus_target_id = "different-target"
            return session.pooled

        session.get_or_create_cdp_session = pooled_session
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=ROOT,
                observed_target_url=TRIP,
            )
        )
        is None
    )
    assert not calls


@pytest.mark.parametrize("raw", [None, [], {}, {"result": None}, {"result": {"value": "PRIVATE"}}])
def test_malformed_cdp_envelope_never_exposes_content(
    raw: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session, _calls = _session()

    async def evaluate(**_kwargs: Any) -> object:
        return raw

    session.cdp_client.send.Runtime.evaluate = evaluate
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=ROOT,
                observed_target_url=TRIP,
            )
        )
        is None
    )
    assert not caplog.text


def _view_session(
    *, source=DETAIL, target=DESKTOP, label="Desktop version", race=None, race_read=1
):
    evidence = _evidence(target)
    evidence["url"] = source
    evidence["chain"][0]["label"] = label
    session, calls = _session(
        [
            {"url": source, "hrefs": [target]},
            evidence,
        ],
        race=race,
        race_read=race_read,
    )
    session.url = source
    return session, calls


@pytest.mark.parametrize("source", [DETAIL, DETAIL + "&prefer_site_type=mdot"])
def test_desktop_view_is_separate_and_keeps_fresh_href(source, caplog):
    fresh = DESKTOP.replace("aid=1", "label=fresh&aid=2") + "&source=mobile"
    session, calls = _view_session(source=source, target=fresh)
    result = asyncio.run(
        resolve_rendered_confirmation_view(
            session,
            source_url=source,
            observed_target_url=DESKTOP,
        )
    )
    assert result is not None
    assert result.source_url == source
    assert result.target_url == fresh
    assert result.target_id == "current-target"
    assert result.chain[0]["label"] == "Desktop version"
    assert len(calls) == 2
    assert "private-auth" not in repr(result)
    assert not caplog.text
    session, calls = _view_session(source=source, target=fresh)
    assert (
        asyncio.run(
            resolve_rendered_inventory_link(
                session,
                source_url=source,
                observed_target_url=fresh,
            )
        )
        is None
    )
    assert not calls


@pytest.mark.parametrize(
    "source,target",
    [
        (ROOT, DESKTOP),
        (TRIP, DESKTOP),
        (DETAIL, DETAIL),
        (DESKTOP, DESKTOP),
        (DETAIL + "&prefer_site_type=WWW", DESKTOP),
        (DETAIL, MANAGE + "&prefer_site_type=www"),
        (DETAIL, DESKTOP.replace("secure.booking.com", "www.booking.com")),
        (DETAIL, DESKTOP.replace("private-auth", "different-auth")),
        (DETAIL, DESKTOP + "&hotel_id=123"),
        (DETAIL + "&hotel_id=123", DESKTOP + "&hotel_id=456"),
        (DETAIL, DESKTOP + "&sid=different-session"),
        (DETAIL, DESKTOP.replace("=www", "=mdot")),
        (DETAIL, DESKTOP.replace("=www", "=WWW")),
        (DETAIL, DESKTOP.replace("=www", "=%77ww")),
        (DETAIL, DESKTOP.replace("prefer_site_type", "%70refer_site_type")),
        (DETAIL, DESKTOP.replace("prefer_site_type", "Prefer_Site_Type")),
        (DETAIL, DESKTOP.replace("auth_key", "%61uth_key")),
        (DETAIL, DESKTOP.replace("private-auth", "%70rivate-auth")),
        (DETAIL.replace("auth_key", "AUTH_KEY"), DESKTOP),
        (DETAIL.replace("auth_key=private-auth&", ""), DESKTOP),
        (DETAIL, DESKTOP.replace("auth_key=private-auth&", "")),
        (DETAIL, DESKTOP + "&auth_key=private-auth"),
        (DETAIL, DESKTOP + "&prefer_site_type=www"),
        (DETAIL, DESKTOP + "&aid=1"),
        (DETAIL, DESKTOP + "&status=active"),
        (DETAIL, DESKTOP + "&action=cancel"),
        (DETAIL, DESKTOP + "#desktop"),
    ],
)
def test_desktop_view_rejects_identity_encoding_scope_or_other_view_changes(source, target):
    session, calls = _view_session(source=source, target=target)
    assert (
        asyncio.run(
            resolve_rendered_confirmation_view(
                session,
                source_url=source,
                observed_target_url=target,
            )
        )
        is None
    )
    assert not calls


@pytest.mark.parametrize(
    "label", ["", "Manage your booking", "desktop version", "Desktop version now"]
)
def test_desktop_view_requires_exact_link_label(label):
    session, calls = _view_session(label=label)
    assert (
        asyncio.run(
            resolve_rendered_confirmation_view(
                session,
                source_url=DETAIL,
                observed_target_url=DESKTOP,
            )
        )
        is None
    )
    assert len(calls) == 2


@pytest.mark.parametrize("race", ["focus", "url", "tab"])
@pytest.mark.parametrize("race_read", [1, 2])
def test_desktop_view_retains_source_and_focus_race_checks(race, race_read):
    session, calls = _view_session(race=race, race_read=race_read)
    assert (
        asyncio.run(
            resolve_rendered_confirmation_view(
                session,
                source_url=DETAIL,
                observed_target_url=DESKTOP,
            )
        )
        is None
    )
    assert len(calls) == race_read


@pytest.mark.parametrize(
    "hrefs",
    [
        [DESKTOP, DESKTOP],
        [DESKTOP.replace("private-auth", "different-auth")],
        [DESKTOP + "&prefer_site_type=www"],
        [MANAGE + "&prefer_site_type=www"],
    ],
)
def test_desktop_view_revalidates_actual_target_and_rejects_ambiguity(hrefs):
    session, calls = _session([{"url": DETAIL, "hrefs": hrefs}])
    session.url = DETAIL
    assert (
        asyncio.run(
            resolve_rendered_confirmation_view(
                session,
                source_url=DETAIL,
                observed_target_url=DESKTOP,
            )
        )
        is None
    )
    assert len(calls) == 1


def test_desktop_view_rejects_unsafe_real_ancestor():
    evidence = _evidence(DESKTOP)
    evidence["url"] = DETAIL
    evidence["chain"][0]["label"] = "Desktop version"
    evidence["chain"][1]["attributes"] = {"onclick": "private-handler()"}
    session, _calls = _session([{"url": DETAIL, "hrefs": [DESKTOP]}, evidence])
    session.url = DETAIL
    assert (
        asyncio.run(
            resolve_rendered_confirmation_view(
                session,
                source_url=DETAIL,
                observed_target_url=DESKTOP,
            )
        )
        is None
    )
