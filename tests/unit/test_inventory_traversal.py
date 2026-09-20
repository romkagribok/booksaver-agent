from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import booksaver.infrastructure.browser.inventory_traversal as adapter
from booksaver.infrastructure.browser.inventory_traversal import (
    ENTRY_URL,
    InventoryPageLinks,
    InventoryTraversal,
    inventory_page_kind,
    read_inventory_page_links,
)

TRIP_A = ENTRY_URL + "?trip_id=private-trip-a"
TRIP_B = ENTRY_URL + "?trip_id=private-trip-b"
DETAIL_A = "https://secure.booking.com/confirmation.en-us.html?bn=private-a&token=secret-a"
DETAIL_B = "https://secure.booking.com/confirmation.html?bn=private-b&token=secret-b"
DETAIL_C = "https://secure.booking.com/confirmation.en-gb.html?bn=private-c&token=secret-c"


def test_observed_root_and_trip_tracking_aliases_keep_one_target() -> None:
    root = ENTRY_URL + "?aid=123&label=private-label&sid=private-session"
    trip = TRIP_A + "&aid=123&label=private-label&sid=private-session"
    trip_alias = ENTRY_URL + "?sid=changed-session&trip_id=private-trip-a&label=changed&aid=456"
    traversal = InventoryTraversal()
    assert inventory_page_kind(root) == "root"
    traversal.observe(InventoryPageLinks(root, (trip, trip_alias, TRIP_B)))
    assert traversal.next_observed_url == trip
    traversal.observe(InventoryPageLinks(trip_alias, (DETAIL_A,)))
    traversal.observe(InventoryPageLinks(ENTRY_URL + "?sid=another", (TRIP_A, TRIP_B)))
    counts = traversal.diagnostic()
    assert counts["root_seen"] is True
    assert counts["trip_links"] == 2
    assert counts["trips_visited"] == 1
    assert counts["detail_links"] == 1
    assert counts["pending_pages"] == 2
    assert counts["unlinked_page_observations"] == 0


def test_localized_and_manage_confirmation_links_with_same_auth_key_are_one_target() -> None:
    detail = "https://secure.booking.com/confirmation.en-us.html?aid=1&auth_key=private-one&label=a"
    manage = (
        "https://secure.booking.com/confirmation.html?source=manage&label=b&auth_key=private-one"
    )
    other = "https://secure.booking.com/confirmation.en-us.html?auth_key=private-two"
    traversal = InventoryTraversal()
    traversal.observe(InventoryPageLinks(ENTRY_URL, (TRIP_A,)))
    traversal.observe(InventoryPageLinks(TRIP_A, (detail, manage, other)))
    assert traversal.diagnostic()["detail_links"] == 2
    assert traversal.next_observed_url == detail
    traversal.observe(InventoryPageLinks(manage, ()))
    traversal.observe(InventoryPageLinks(TRIP_A + "&label=back", (manage, detail, other)))
    assert traversal.diagnostic()["details_visited"] == 1
    assert traversal.diagnostic()["pending_pages"] == 1
    assert traversal.diagnostic()["unlinked_page_observations"] == 0
    assert traversal.next_observed_url == other
    output = repr(traversal) + json.dumps(traversal.diagnostic())
    assert "private-one" not in output
    assert "auth_key" not in output


@pytest.mark.parametrize(
    "first,alias",
    [
        (TRIP_A + "&view=summary&lang=en", TRIP_A + "&lang=en&view=summary"),
        (
            DETAIL_A + "&view=summary",
            DETAIL_A.replace("?bn=private-a&token=secret-a", "?token=secret-a&bn=private-a")
            + "&view=summary",
        ),
    ],
)
def test_query_order_alone_does_not_multiply_observed_targets(first: str, alias: str) -> None:
    traversal = InventoryTraversal()
    traversal.observe(InventoryPageLinks(ENTRY_URL, (first, alias)))
    assert traversal.diagnostic()["pending_pages"] == 1
    assert traversal.next_observed_url == first
    traversal.observe(InventoryPageLinks(alias, ()))
    assert traversal.diagnostic()["pending_pages"] == 0
    assert traversal.diagnostic()["unlinked_page_observations"] == 0


@pytest.mark.parametrize(
    "first,other",
    [
        (TRIP_A, TRIP_B),
        (TRIP_A + "&source=one", TRIP_A + "&source=two"),
        (TRIP_A + "&view=one", TRIP_A + "&view=two"),
        (TRIP_A + "&view=one&view=two", TRIP_A + "&view=two&view=one"),
        (
            "https://secure.booking.com/confirmation.html?auth_key=one",
            "https://secure.booking.com/confirmation.html?auth_key=two",
        ),
        (
            "https://secure.booking.com/confirmation.html?auth_key=one&hotel_id=1",
            "https://secure.booking.com/confirmation.en-us.html?auth_key=one&hotel_id=2",
        ),
        (
            "https://secure.booking.com/confirmation.html?bn=one",
            "https://secure.booking.com/confirmation.en-us.html?bn=one",
        ),
    ],
)
def test_distinct_or_unqualified_identities_are_not_collapsed(first: str, other: str) -> None:
    traversal = InventoryTraversal()
    traversal.observe(InventoryPageLinks(ENTRY_URL, (first, other)))
    assert traversal.diagnostic()["pending_pages"] == 2


@pytest.mark.parametrize(
    "url",
    [
        ENTRY_URL + "?unknown=value",
        ENTRY_URL + "?aid=1&tab=active",
        ENTRY_URL + "?sid=private#active",
        ENTRY_URL + "?trip_id=one&TRIP_ID=two",
        ENTRY_URL + "?trip_id=one&%2573tatus=active",
        "https://secure.booking.com/confirmation.html?auth_key=one&auth_key=two",
        "https://secure.booking.com/confirmation.html?auth_key=one&auth_key=one",
        "https://secure.booking.com/confirmation.html?auth_key=one&AUTH_KEY=two",
        "https://secure.booking.com/confirmation.html?auth_key=one&%2561uth_key=two",
        "https://secure.booking.com/confirmation.html?auth_key=",
        "https://secure.booking.com/confirmation.html?auth_key=%20",
        "https://secure.booking.com/confirmation.html?auth_key=one&status=active",
        "https://secure.booking.com/confirmation.html?auth_key=one&scope=upcoming",
        "https://secure.booking.com/confirmation.html?auth_key=one&tab=active",
        "https://secure.booking.com/confirmation.html?auth_key=one&action=cancel",
    ],
)
def test_scope_unsafe_and_ambiguous_identity_queries_cannot_create_aliases(url: str) -> None:
    assert inventory_page_kind(url) is None
    traversal = InventoryTraversal()
    traversal.observe(InventoryPageLinks(ENTRY_URL, (url,)))
    assert traversal.next_observed_url is None


def test_two_groups_leave_pending_navigation_when_only_first_group_was_visited() -> None:
    traversal = InventoryTraversal()
    traversal.observe(InventoryPageLinks(ENTRY_URL, (TRIP_A, TRIP_B)))
    assert traversal.next_observed_url == TRIP_A
    traversal.observe(InventoryPageLinks(TRIP_A, (DETAIL_A, DETAIL_B, ENTRY_URL)))
    traversal.observe(InventoryPageLinks(DETAIL_A, (DETAIL_C,)))

    assert traversal.diagnostic() == {
        "root_seen": True,
        "trip_links": 2,
        "trips_visited": 1,
        "detail_links": 2,
        "details_visited": 1,
        "pending_pages": 2,
        "truncated": False,
        "unlinked_page_observations": 0,
    }
    assert traversal.next_observed_url == TRIP_B
    traversal.observe(InventoryPageLinks(DETAIL_B, ()))
    traversal.observe(InventoryPageLinks(TRIP_B, (DETAIL_C,)))
    assert traversal.next_observed_url == DETAIL_C
    traversal.observe(InventoryPageLinks(DETAIL_C, ()))
    assert traversal.next_observed_url is None
    counts = traversal.diagnostic()
    assert counts["trips_visited"] == 2
    assert counts["details_visited"] == 3
    assert counts["pending_pages"] == 0
    # Link traversal has no authority to claim account or reservation-fact completeness.
    assert not any("complete" in key or "bookings" in key for key in counts)


def test_duplicate_links_and_back_navigation_do_not_add_pending_pages() -> None:
    traversal = InventoryTraversal()
    traversal.observe(InventoryPageLinks(ENTRY_URL, (TRIP_A, TRIP_A, ENTRY_URL)))
    traversal.observe(InventoryPageLinks(TRIP_A, (DETAIL_A, DETAIL_A, ENTRY_URL)))
    traversal.observe(InventoryPageLinks(DETAIL_A, (TRIP_B, DETAIL_B)))
    traversal.observe(InventoryPageLinks(TRIP_A, (DETAIL_A, ENTRY_URL)))
    traversal.observe(InventoryPageLinks(ENTRY_URL, (TRIP_A,)))

    assert traversal.diagnostic()["trip_links"] == 1
    assert traversal.diagnostic()["detail_links"] == 1
    assert traversal.diagnostic()["pending_pages"] == 0
    assert traversal.next_observed_url is None


@pytest.mark.parametrize(
    "url",
    [
        "https://cars.booking.com/manage-booking?id=private-car",
        "https://secure.booking.com/cars/confirmation.html?token=private-car",
        "https://secure.booking.com/confirmation.html?action=cancel",
        "https://secure.booking.com/confirmation.html?%61ction=%70ayment",
        ENTRY_URL + "?trip_id=private&tab=past",
        ENTRY_URL + "?trip_id=private&scope=past",
        ENTRY_URL + "?trip_id=private&status=cancelled",
        ENTRY_URL + "?trip_id=private#past",
        ENTRY_URL + "?trip_id=",
        ENTRY_URL + "?trip_id=a&trip_id=b",
        "https://booking.com/mytrips.html?trip_id=private",
        "https://secure.booking.com.evil.example/confirmation.html",
        "https://user:private@secure.booking.com/confirmation.html",
        "javascript:alert('private')",
        "https://[invalid",
        ENTRY_URL + "?trip_id=" + "a" * 4_000,
    ],
)
def test_unqualified_car_unsafe_and_inactive_routes_are_not_enqueued(url: str) -> None:
    assert inventory_page_kind(url) is None
    traversal = InventoryTraversal()
    traversal.observe(InventoryPageLinks(ENTRY_URL, (url,)))
    assert traversal.diagnostic()["pending_pages"] == 0


def test_unlinked_destinations_do_not_establish_root_or_group_coverage() -> None:
    traversal = InventoryTraversal()
    traversal.observe(InventoryPageLinks(TRIP_A, (DETAIL_A,)))
    traversal.observe(InventoryPageLinks(DETAIL_A, ()))
    assert traversal.diagnostic()["root_seen"] is False
    assert traversal.diagnostic()["trips_visited"] == 0
    assert traversal.diagnostic()["details_visited"] == 0
    assert traversal.diagnostic()["unlinked_page_observations"] == 2
    traversal.observe(InventoryPageLinks(ENTRY_URL, (TRIP_B,)))
    traversal.observe(InventoryPageLinks(TRIP_A, (DETAIL_A,)))
    assert traversal.diagnostic()["trips_visited"] == 0
    assert traversal.diagnostic()["pending_pages"] == 1
    assert traversal.diagnostic()["unlinked_page_observations"] == 3


def test_global_worklist_bound_and_page_truncation_remain_visible() -> None:
    traversal = InventoryTraversal()
    links = tuple(ENTRY_URL + f"?trip_id=private-{index}" for index in range(250))
    traversal.observe(InventoryPageLinks(ENTRY_URL, links))
    counts = traversal.diagnostic()
    assert counts["truncated"] is True
    assert 0 < counts["pending_pages"] <= 250
    assert counts["trip_links"] == counts["pending_pages"]
    traversal.observe(InventoryPageLinks(ENTRY_URL, ()))
    assert traversal.diagnostic()["truncated"] is True

    page_truncated = InventoryTraversal()
    page_truncated.observe(InventoryPageLinks(ENTRY_URL, (TRIP_A,), truncated=True))
    page_truncated.observe(InventoryPageLinks(TRIP_A, ()))
    assert page_truncated.diagnostic()["truncated"] is True
    assert page_truncated.diagnostic()["pending_pages"] == 0


def test_repr_and_diagnostics_do_not_expose_private_urls() -> None:
    page = InventoryPageLinks(ENTRY_URL, (TRIP_A, DETAIL_A))
    traversal = InventoryTraversal()
    traversal.observe(page)
    output = repr(page) + repr(traversal) + json.dumps(traversal.diagnostic())
    for private_value in (ENTRY_URL, TRIP_A, DETAIL_A, "private", "secret", "token", "https"):
        assert private_value not in output
    assert all(isinstance(value, (int, bool)) for value in traversal.diagnostic().values())


def _session(response: object) -> tuple[Any, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    async def evaluate(**kwargs: Any) -> object:
        calls.append(kwargs)
        return response

    client = SimpleNamespace(send=SimpleNamespace(Runtime=SimpleNamespace(evaluate=evaluate)))
    pooled = SimpleNamespace(
        target_id="target", session_id="qualified-current-page", cdp_client=client
    )

    async def get_pool(target_id, *, focus):
        assert target_id == "target" and focus is False
        return pooled

    async def get_url():
        return ENTRY_URL

    return SimpleNamespace(
        agent_focus_target_id="target",
        get_or_create_cdp_session=get_pool,
        get_page_targets=lambda: [object()],
        get_current_page_url=get_url,
        cdp_client=client,
    ), calls


def _response(url: object = ENTRY_URL, links: object = ()) -> dict[str, Any]:
    return {"result": {"value": json.dumps({"url": url, "links": links})}}


def test_cdp_reader_uses_fixed_passive_bounded_expression_without_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session, calls = _session(_response(links=[TRIP_A, DETAIL_A]))
    observed = asyncio.run(read_inventory_page_links(session))
    assert observed == InventoryPageLinks(ENTRY_URL, (TRIP_A, DETAIL_A))
    assert len(calls) == 1
    assert calls[0]["session_id"] == "qualified-current-page"
    assert calls[0]["params"] == {
        "expression": (
            "JSON.stringify({url:location.href,links:Array.from("
            "document.querySelectorAll('a[href]')).filter(a=>"
            "a.getClientRects().length && a.innerText.trim()).slice(0,251)"
            ".map(a=>a.href)})"
        ),
        "returnByValue": True,
    }
    assert not caplog.text


def test_cdp_reader_marks_sentinel_link_truncation() -> None:
    links = [TRIP_A] * 251
    session, _calls = _session(_response(links=links))
    observed = asyncio.run(read_inventory_page_links(session))
    assert observed is not None
    assert observed.truncated is True
    assert len(observed.urls) == 250


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {},
        {"result": None},
        {"result": {"value": "PRIVATE-MALFORMED-JSON"}},
        {"result": {"value": "[]"}},
        {"result": {"value": {"private": "secret"}}},
        _response(url=None),
        _response(url=ENTRY_URL + "?tab=past"),
        _response(links=None),
        _response(links="private-page-text"),
        _response(links=[None]),
        _response(links=[{"private": "secret"}]),
        _response(links=["x" * 4_001]),
        _response(links=[TRIP_A] * 252),
    ],
)
def test_invalid_cdp_shapes_fail_closed_without_logging_private_content(
    response: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session, _calls = _session(response)
    assert asyncio.run(read_inventory_page_links(session)) is None
    assert not caplog.text


def test_timeout_fails_closed_without_logging_exception(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session, _calls = _session({})

    async def timeout(awaitable: Any, *, timeout: float) -> Any:
        assert timeout == 5
        awaitable.close()
        raise TimeoutError("PRIVATE-SESSION-TOKEN")

    monkeypatch.setattr(adapter.asyncio, "wait_for", timeout)
    assert asyncio.run(read_inventory_page_links(session)) is None
    assert not caplog.text


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_unavailable_pool_fails_closed(missing, caplog):
    session, calls = _session({})

    async def pool(*args, **kwargs):
        if missing:
            return None
        raise RuntimeError("PRIVATE-PAGE-TEXT")

    session.get_or_create_cdp_session = pool
    assert asyncio.run(read_inventory_page_links(session)) is None
    assert not calls and not caplog.text


@pytest.mark.parametrize("stage", ["url", "pool"])
def test_whole_read_timeout_cancels_source_and_pool_acquisition(stage, monkeypatch, caplog):
    factory = asyncio.timeout
    entered, cancelled = [], []

    def short_timeout(delay):
        assert delay == 5
        return factory(0.001)

    async def block(*args, **kwargs):
        entered.append(stage)
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(stage)

    session, _calls = _session({})
    if stage == "url":
        session.get_current_page_url = block
    else:
        session.get_or_create_cdp_session = block
    monkeypatch.setattr(adapter.asyncio, "timeout", short_timeout)

    async def read():
        return await asyncio.wait_for(read_inventory_page_links(session), timeout=0.5)

    assert asyncio.run(read()) is None
    assert entered == cancelled == [stage]
    assert not caplog.text


def test_repeated_passive_reads_reuse_pool_without_actor_attachments():
    session, calls = _session(_response(links=[TRIP_A]))

    async def actor():
        raise AssertionError("Actor pages must not be attached for inventory reads")

    session.get_current_page = actor

    async def repeated():
        for _ in range(8):
            assert await read_inventory_page_links(session) is not None

    asyncio.run(repeated())
    assert len(calls) == 8
    assert {item["session_id"] for item in calls} == {"qualified-current-page"}


@pytest.mark.parametrize("event", ["dialog", "tab", "url"])
def test_runtime_rechecks_safety_after_passive_observation_before_dispatch(
    event: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import browser_use

    import booksaver.infrastructure.browser.browser_use_inventory_executor as runtime_adapter
    from booksaver.application.browser_executor import ExecutionMeter, InMemorySessionLeaseBroker
    from booksaver.domain.browser_executor import ExecutionLimits
    from booksaver.domain.inventory_executor import (
        InventoryExecutionRequest,
        InventoryExecutionStatus,
        inventory_session_subject,
    )

    class Session:
        cdp_url = None
        current_url = ENTRY_URL
        agent_focus_target_id = "current-target"
        targets = 1

        async def navigate_to(self, _url: str, **_kwargs: Any) -> None:
            pass

        async def get_current_page_url(self) -> str:
            return self.current_url

        def get_page_targets(self) -> list[object]:
            return [object() for _ in range(self.targets)]

        async def get_browser_state_summary(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                dom_state=SimpleNamespace(llm_representation=lambda: "Active trips")
            )

    class Tools:
        def __init__(self, **_kwargs: Any) -> None:
            self.registry = SimpleNamespace(registry=SimpleNamespace(actions={}))

        def action(self, *_args: Any, **_kwargs: Any) -> Any:
            def register(function: Any) -> Any:
                self.registry.registry.actions[function.__name__] = function
                return function

            return register

    session = Session()
    runtime = runtime_adapter.LocalBrowserUseInventoryRuntime()
    broker = InMemorySessionLeaseBroker()
    lease = broker.issue(
        owner_user_id=7,
        subject_id=inventory_session_subject(7),
        execution_id="observation-race",
        session_material=b"synthetic-unused",
    )
    request = InventoryExecutionRequest(
        execution_id="observation-race",
        owner_user_id=7,
        session_lease=lease,
        limits=ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3)),
    )
    observations: list[str] = []
    dispatched: list[str] = []

    async def read_links(_session: Any) -> InventoryPageLinks:
        observations.append(event)
        if event == "dialog":
            runtime._host.dialog_rejected = True
        elif event == "tab":
            session.targets = 2
        else:
            session.current_url = "https://outside-booking.example/"
        return InventoryPageLinks(ENTRY_URL, (TRIP_A,))

    async def start() -> Any:
        return SimpleNamespace(
            browser=session,
            viewport={"width": 360, "height": 800},
            file_system_dir=tmp_path,
        )

    async def verify(*_args: Any) -> None:
        return None

    def dispatch(_event: Any) -> None:
        dispatched.append("unsafe-browser-action")
        pytest.fail("Safety change during observation must stop before browser dispatch")

    session.event_bus = SimpleNamespace(dispatch=dispatch)

    def create_agent(_agent_type: Any, **kwargs: Any) -> Any:
        actions = kwargs["tools"].registry.registry.actions

        async def run(**_kwargs: Any) -> Any:
            result = await actions["guarded_back"](session)
            assert result.is_done is True
            assert result.success is False
            return SimpleNamespace(history=[])

        return SimpleNamespace(run=run)

    monkeypatch.setattr(browser_use, "Tools", Tools)
    monkeypatch.setattr(runtime_adapter, "read_inventory_page_links", read_links)
    monkeypatch.setattr(
        runtime_adapter,
        "budgeted_model_type",
        lambda *_args: lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime,
        "_host",
        SimpleNamespace(
            start=start,
            verify_authentication=verify,
            verified_mobile_session=None,
            create_agent=create_agent,
            dialog_rejected=False,
        ),
    )
    result = asyncio.run(
        runtime.execute(
            request,
            api_key="unused",
            budget=SimpleNamespace(),  # type: ignore[arg-type]
            meter=ExecutionMeter(request.limits),
        )
    )
    assert observations == [event]
    assert not dispatched
    assert result.status is InventoryExecutionStatus.UNSAFE_ACTION
    assert result.reservations == ()
    broker.close(lease)
