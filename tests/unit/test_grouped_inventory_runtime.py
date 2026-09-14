"""Exercise grouped reading through the real runtime safety and mapping boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import booksaver.infrastructure.browser.browser_use_inventory_executor as adapter
from booksaver.application.browser_executor import ExecutionMeter, InMemorySessionLeaseBroker
from booksaver.domain.browser_executor import (
    EvidenceCompleteness,
    ExecutionLimits,
    ExecutorSafetyViolation,
)
from booksaver.domain.inventory_executor import (
    InventoryExecutionRequest,
    InventoryExecutionStatus,
    inventory_session_subject,
)
from booksaver.infrastructure.browser.browser_use_runtime import BrowserUseSessionStatus
from booksaver.infrastructure.browser.inventory_confirmation_facts import parse_confirmation_facts
from booksaver.infrastructure.browser.inventory_link_resolution import ResolvedInventoryLink

ROOT = "https://secure.booking.com/mytrips.html"
DETAIL = "https://secure.booking.com/confirmation.en-us.html?auth_key=synthetic"


def parsed_facts():
    # Independently exercise the real parser -> payload -> domain mapper path.
    facts = parse_confirmation_facts(
        "Your stay is confirmed\nSynthetic Hotel\nCheck-in\nFri, Oct 23, 2026\n"
        "Check-out\nSat, Oct 24, 2026\nBooking Details\n2 adults - 1 night, 1 rooms\n"
        "Confirmation number\n1234567890\nYour room details\n"
        "Standard Double Room\nGuest name\nSynthetic Guest",
        (("Synthetic Hotel", "https://www.booking.com/hotel/lt/synthetic.en-us.html"),),
        observed_at=datetime(2026, 9, 13, tzinfo=UTC),
    )
    assert facts is not None
    return facts


class Session:
    def __init__(self):
        self.url = ROOT
        self.target_count = 1
        self.agent_focus_target_id = "caller-page"
        self.url_reads = 0
        self.on_url_read = lambda count: None
        self.on_back = lambda: None
        self.navigations = []
        self.back_events = []
        self.event_bus = SimpleNamespace(dispatch=self.dispatch)

    async def get_current_page_url(self):
        self.url_reads += 1
        self.on_url_read(self.url_reads)
        return self.url

    def get_page_targets(self):
        return [object() for _ in range(self.target_count)]

    async def navigate_to(self, url, *, new_tab):
        self.navigations.append((url, new_tab))
        self.url = url

    def dispatch(self, event):
        navigating = hasattr(event, "url")
        if navigating:
            assert event.wait_until == "domcontentloaded"
            self.navigations.append((event.url, event.new_tab))
        else:
            self.back_events.append(event)
        session = self

        class Event:
            def __await__(self):
                async def complete():
                    if navigating:
                        session.url = event.url
                    else:
                        session.url = ROOT
                        session.on_back()
                return complete().__await__()

            async def event_result(self, **kwargs):
                assert kwargs == {"raise_if_any": True, "raise_if_none": False}

        return Event()


class Harness:
    def __init__(self, monkeypatch, *, action_limit=2, expired=False):
        self.runtime = adapter.LocalBrowserUseInventoryRuntime()
        self.session = Session()
        self.auth = AsyncMock(return_value=None)
        self.capture = AsyncMock(side_effect=AssertionError("Must retain original price session"))
        self.host = SimpleNamespace(
            dialog_rejected=False,
            verify_authentication=self.auth,
            capture_verified_session=self.capture,
        )
        monkeypatch.setattr(self.runtime, "_host", self.host)
        deadline = datetime.now(UTC) + timedelta(minutes=-1 if expired else 3)
        limits = ExecutionLimits(
            deadline=deadline, max_actions=action_limit, max_computer_use_actions=0,
        )
        lease = InMemorySessionLeaseBroker().issue(
            owner_user_id=7, subject_id=inventory_session_subject(7), execution_id="grouped-7",
            session_material=b"synthetic-caller-session",
        )
        self.request = InventoryExecutionRequest(
            execution_id="grouped-7", owner_user_id=7, session_lease=lease, limits=limits,
        )
        self.meter = ExecutionMeter(limits)
        self.payload = parsed_facts()
        self.desktop = True
        self.handled = True
        self.plan = None
        harness = self

        class Reader:
            def __init__(self, session, **kwargs):
                assert session is harness.session
                self.__dict__.update(kwargs)

            async def run(self):
                # Buffered positives must not override any later safety terminal.
                self.result.reservations.append(harness.payload)
                self.result.desktop_view_used = harness.desktop
                if harness.plan:
                    await harness.plan(self)
                return harness.handled

        monkeypatch.setattr(adapter, "GroupedInventoryReader", Reader)

    def mutate(self, kind):
        if kind == "dialog":
            self.host.dialog_rejected = True
        elif kind == "tab":
            self.session.target_count = 2
        elif kind == "focus":
            self.session.agent_focus_target_id = "other-caller-page"
        elif kind == "violation":
            self.runtime._state.safety_violations.add(
                ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED,
            )
        else:
            self.runtime._state.terminal = InventoryExecutionStatus(kind)

    def run(self):
        return asyncio.run(self.runtime._read_grouped_inventory(
            self.request, self.session, self.meter,
        ))

    def link(self, *, target=DETAIL):
        return ResolvedInventoryLink(
            self.session.url, target, self.session.agent_focus_target_id,
            ({"node_name": "a", "label": "View booking", "visible": True,
              "attributes": {"href": target}},),
        )


@pytest.mark.parametrize("desktop", [False, True])
def test_parsed_positive_uses_mapper_and_preserves_original_price_session(monkeypatch, desktop):
    h = Harness(monkeypatch)
    h.desktop = desktop

    async def plan(reader):
        await reader.check()
        await reader.navigate(h.link())
        await reader.back()

    h.plan = plan
    result = h.run()
    assert result.status is InventoryExecutionStatus.OBSERVED
    assert len(result.reservations) == 1
    reservation = result.reservations[0]
    assert reservation.remote_id == "1234567890"
    assert reservation.property_name == "Synthetic Hotel"
    assert reservation.lifecycle.value == "upcoming"
    assert reservation.completeness is EvidenceCompleteness.INCOMPLETE
    assert len(result.scopes) == 1
    assert result.scopes[0].completeness is EvidenceCompleteness.INCOMPLETE
    assert result.scopes[0].explicit_empty is False
    assert result.scopes[0].pagination_exhausted is not True
    assert result.refreshed_session is None
    assert h.session.navigations == [(DETAIL, False)]
    assert len(h.session.back_events) == 1
    assert h.meter.snapshot().total_actions == 2
    assert h.meter.snapshot().model_calls == 0
    h.auth.assert_awaited_once_with(h.request, h.session)
    h.capture.assert_not_called()


@pytest.mark.parametrize("kind", ["dialog", "tab", "violation", "timeout", "cost_limit"])
@pytest.mark.parametrize("when", ["reader", "final_url_await", "authentication_await"])
def test_post_await_safety_and_sticky_terminals_discard_buffered_positives(monkeypatch, kind, when):
    h = Harness(monkeypatch)
    if when == "reader":
        async def plan(reader):
            h.mutate(kind)
            await reader.check()
        h.plan = plan
    elif when == "final_url_await":
        h.session.on_url_read = lambda count: h.mutate(kind)
    else:
        async def verify(request, session):
            h.mutate(kind)
        h.auth.side_effect = verify
    result = h.run()
    expected = (
        InventoryExecutionStatus.UNSAFE_ACTION if kind in {"dialog", "tab", "violation"}
        else InventoryExecutionStatus(kind)
    )
    assert result.status is expected
    assert result.reservations == ()
    assert result.refreshed_session is None
    h.capture.assert_not_called()


@pytest.mark.parametrize("kind", ["dialog", "tab", "focus", "violation", "timeout", "cost_limit"])
def test_final_source_await_mutation_prevents_navigation_dispatch(monkeypatch, kind):
    h = Harness(monkeypatch)

    async def plan(reader):
        link = h.link()
        # navigate: first read is check(), second is the final source recheck.
        h.session.on_url_read = lambda count: h.mutate(kind) if count == 2 else None
        await reader.navigate(link)

    h.plan = plan
    result = h.run()
    assert result.status is not InventoryExecutionStatus.OBSERVED
    assert result.reservations == ()
    assert h.session.navigations == []
    assert h.meter.snapshot().total_actions == 0


@pytest.mark.parametrize("action", ["navigate", "back"])
def test_shared_action_budget_stops_dispatch_before_buffered_positive(monkeypatch, action):
    h = Harness(monkeypatch, action_limit=1)
    h.meter.record_action()  # Earlier work in the same episode already used this action.

    async def plan(reader):
        if action == "navigate":
            await reader.navigate(h.link())
        else:
            await reader.back()

    h.plan = plan
    result = h.run()
    assert result.status is InventoryExecutionStatus.ACTION_LIMIT
    assert result.reservations == ()
    assert h.session.navigations == h.session.back_events == []
    assert h.meter.snapshot().total_actions == 1


def test_expired_request_deadline_prevents_positive_mapping(monkeypatch):
    h = Harness(monkeypatch, expired=True)
    result = h.run()
    assert result.status is InventoryExecutionStatus.TIMEOUT
    assert result.reservations == ()
    h.auth.assert_not_called()


@pytest.mark.parametrize("kind", ["dialog", "tab", "violation", "timeout"])
def test_back_event_await_rechecks_safety_before_accepting_positive(monkeypatch, kind):
    h = Harness(monkeypatch)
    h.session.on_back = lambda: h.mutate(kind)

    async def plan(reader):
        await reader.back()

    h.plan = plan
    result = h.run()
    assert result.status is not InventoryExecutionStatus.OBSERVED
    assert result.reservations == ()
    assert len(h.session.back_events) == 1
    assert h.meter.snapshot().total_actions == 1


def test_source_url_changed_during_final_source_await_blocks_dispatch(monkeypatch):
    h = Harness(monkeypatch)

    async def plan(reader):
        link = h.link()

        def change_source(count):
            if count == 2:
                h.session.url = ROOT + "?trip_id=other"

        h.session.on_url_read = change_source
        await reader.navigate(link)

    h.plan = plan
    result = h.run()
    assert result.status is InventoryExecutionStatus.UNSAFE_ACTION
    assert h.session.navigations == []
    assert h.meter.snapshot().total_actions == 0


def test_authentication_await_redirect_to_login_is_rechecked(monkeypatch):
    h = Harness(monkeypatch)

    async def verify(request, session):
        h.session.url = "https://account.booking.com/sign-in"
        return None

    h.auth.side_effect = verify
    result = h.run()
    assert result.status is InventoryExecutionStatus.SIGNED_OUT
    assert result.reservations == ()
    h.capture.assert_not_called()


@pytest.mark.parametrize("status", list(BrowserUseSessionStatus))
def test_final_authentication_failure_overrides_parsed_positives(monkeypatch, status):
    h = Harness(monkeypatch)
    h.auth.return_value = status
    result = h.run()
    assert result.status.value == status.value
    assert result.reservations == ()
    h.auth.assert_awaited_once_with(h.request, h.session)
    h.capture.assert_not_called()


@pytest.mark.parametrize("url", [
    "https://account.booking.com/sign-in",
    "https://secure.booking.com/login.html",
    "https://secure.booking.com/mfa.html",
    "https://outside.example/confirmation.en-us.html?auth_key=synthetic",
    DETAIL + "&action=payment",
    DETAIL + "&login=true",
])
def test_real_login_or_unsafe_urls_never_pass_as_confirmation_auth_key(monkeypatch, url):
    h = Harness(monkeypatch)
    h.session.url = url
    result = h.run()
    assert result.status is not InventoryExecutionStatus.OBSERVED
    assert result.reservations == ()
    h.capture.assert_not_called()


def test_unhandled_reader_falls_back_without_exporting_session(monkeypatch):
    h = Harness(monkeypatch)
    h.handled = False
    assert h.run() is None
    h.auth.assert_not_called()
    h.capture.assert_not_called()


def test_invalid_identity_still_fails_normal_mapper(monkeypatch):
    h = Harness(monkeypatch)
    h.payload = {"remote_id": "unknown", "identity_evidence": "unknown"}
    result = h.run()
    assert result.status is InventoryExecutionStatus.VALIDATION_FAILURE
    assert result.reservations == ()


def history_harness(monkeypatch, h):
    async def resolve(session, *, observed_parent_url):
        assert observed_parent_url == ROOT
        return SimpleNamespace(source_url=session.url, target_url=ROOT,
                               target_id=session.agent_focus_target_id, entry_id=11,
                               session_id='local-cdp')
    async def jump(*, params, session_id):
        assert params == {'entryId': 11}
        assert session_id == 'local-cdp'
        h.session.back_events.append('history-jump')
        h.session.url = ROOT
        h.session.on_back()
    monkeypatch.setattr(adapter, 'resolve_inventory_history_return', resolve)
    h.session.cdp_client = SimpleNamespace(send=SimpleNamespace(
        Page=SimpleNamespace(navigateToHistoryEntry=jump)))


def test_history_return_uses_one_metered_native_action(monkeypatch):
    h = Harness(monkeypatch)
    history_harness(monkeypatch, h)
    h.session.url = DETAIL
    async def plan(reader):
        assert await reader.back(ROOT)
    h.plan = plan
    result = h.run()
    assert result.status is InventoryExecutionStatus.OBSERVED
    assert h.meter.snapshot().total_actions == 1
    assert h.session.back_events == ['history-jump']
    h.capture.assert_not_called()


@pytest.mark.parametrize('kind', ['dialog', 'tab', 'focus', 'violation', 'timeout', 'cost_limit'])
def test_history_final_source_await_cannot_race_safety_state(monkeypatch, kind):
    h = Harness(monkeypatch)
    history_harness(monkeypatch, h)
    h.session.url = DETAIL
    h.session.on_url_read = lambda count: h.mutate(kind) if count == 3 else None
    async def plan(reader):
        await reader.back(ROOT)
    h.plan = plan
    result = h.run()
    assert result.status is not InventoryExecutionStatus.OBSERVED
    assert h.meter.snapshot().total_actions == 0
    assert not h.session.back_events


def test_unresolved_history_does_not_dispatch_or_charge_an_action(monkeypatch):
    h = Harness(monkeypatch)
    history_harness(monkeypatch, h)
    monkeypatch.setattr(adapter, 'resolve_inventory_history_return', AsyncMock(return_value=None))
    async def plan(reader):
        assert not await reader.back(ROOT)
    h.plan = plan
    h.run()
    assert h.meter.snapshot().total_actions == 0
    assert not h.session.back_events


def test_history_return_cannot_reset_exhausted_allowance(monkeypatch):
    h = Harness(monkeypatch, action_limit=1)
    history_harness(monkeypatch, h)
    h.meter.record_action()
    async def plan(reader):
        await reader.back(ROOT)
    h.plan = plan
    result = h.run()
    assert result.status is InventoryExecutionStatus.ACTION_LIMIT
    assert not h.session.back_events
