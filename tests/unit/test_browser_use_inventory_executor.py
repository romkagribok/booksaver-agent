from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.browser_executor import ExecutionMeter, InMemorySessionLeaseBroker
from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.domain.browser_executor import (
    EvidenceCompleteness,
    ExecutionLimits,
    ExecutorSafetyViolation,
    ObservationSource,
)
from booksaver.domain.inventory_executor import (
    InventoryExecutionRequest,
    InventoryExecutionStatus,
    InventoryScope,
    ObservedInventoryScope,
    inventory_session_subject,
)
from booksaver.domain.model_policy import (
    AdmissionDecision,
    BrowserJobKind,
    CallerKeyRef,
    CostReconciliation,
    CostReservation,
    ModelAttemptAudit,
    ModelCostEstimator,
    ModelStopReason,
    ReservationStatus,
    UsdAmount,
)
from booksaver.infrastructure.browser.browser_use_inventory_executor import (
    _BROWSER_USE_INVENTORY_ENTRY_URL,
    BrowserUseActionGuard,
    BrowserUseCostStop,
    BrowserUseInventoryBrowserExecutor,
    BrowserUseObservationPayload,
    BrowserUseReservationPayload,
    BrowserUseReservationSubmission,
    BrowserUseRuntimeResult,
    BrowserUseSavedReservationMatch,
    BrowserUseTerminalPayload,
    LocalBrowserUseRuntime,
    _agent_history_diagnostic,
    _browser_request_allowed,
    _continued_action_result,
    _hardened_session_type,
    _is_unsafe_watchdog_handler,
    _map_browser_use_observation,
    _map_observation,
    _model_type,
    _node_chain_allows_click,
    _node_chain_click_decision,
    _prepare_environment,
    _qualified_output_format,
    _same_tab_click_destination,
    _terminal_status,
    _validation_diagnostic,
)


class _Ledger:
    def __init__(self) -> None:
        self.reservations: list[Any] = []
        self.reconciliations: list[Any] = []

    def reserve_call(self, request: Any) -> AdmissionDecision:
        self.reservations.append(request)
        return AdmissionDecision(
            reservation=CostReservation(
                request.reservation_id,
                request.job_id,
                request.utc_date,
                request.profile,
                request.reserved_cost,
                ReservationStatus.RESERVED,
            )
        )

    def reconcile_call(self, request: Any) -> CostReconciliation:
        self.reconciliations.append(request)
        return CostReconciliation(
            request.reservation_id,
            request.charged_cost,
            ReservationStatus.CHARGED,
        )

    def list_attempts(self, _job_id: str) -> tuple[ModelAttemptAudit, ...]:
        return ()


def _budget(ledger: _Ledger | None = None) -> BrowserJobCostBudget:
    return BrowserJobCostBudget(
        job_id="browser-use-job",
        job_kind=BrowserJobKind.BOOKINGS_SYNC,
        caller_key_ref=CallerKeyRef(7, "owner", "deployment_key"),
        ledger=ledger or _Ledger(),
        estimator=ModelCostEstimator(),
        preserve_opus_diagnostic=False,
        clock=lambda: datetime(2026, 8, 30, 12, tzinfo=UTC),
    )


def _request(broker: InMemorySessionLeaseBroker) -> InventoryExecutionRequest:
    execution_id = "browser-use-inventory-1"
    lease = broker.issue(
        owner_user_id=7,
        subject_id=inventory_session_subject(7),
        execution_id=execution_id,
        session_material=b'[{"name":"session","value":"secret","domain":".booking.com"}]',
    )
    return InventoryExecutionRequest(
        execution_id=execution_id,
        owner_user_id=7,
        session_lease=lease,
        limits=ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3)),
    )


def _scopes() -> tuple[ObservedInventoryScope, ...]:
    return tuple(
        ObservedInventoryScope(
            scope=scope,
            requested_scope_visible=True,
            explicit_empty=True,
            pagination_exhausted=True,
            pages_observed=1,
            visible_reservation_count=0,
            detail_count=0,
            completeness=EvidenceCompleteness.COMPLETE,
        )
        for scope in InventoryScope
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://secure.booking.com/myreservations.html",
        "https://attacker.example/myreservations.html",
        "https://booking.com@attacker.example/myreservations.html",
        "https://secure.booking.com/cancel.html",
        "https://secure.booking.com/myreservations.html?action=payment",
        "https://secure.booking.com/apps.html?app_install=1",
        "https://secure.booking.com/myreservations.html#modify",
        "javascript:alert(1)",
    ],
)
def test_action_guard_rejects_unsafe_destinations(url: str) -> None:
    assert BrowserUseActionGuard.observable_url(url) is False


def test_action_guard_allows_read_only_inventory_navigation_without_exact_labels() -> None:
    guard = BrowserUseActionGuard()

    assert guard.allows_click(
        current_url="https://secure.booking.com/myreservations.html",
        label="Trip information",
        role="link",
        attributes={"href": "/confirmation.html?reservation_id=123"},
    )
    assert guard.allows_click(
        current_url="https://secure.booking.com/mytrips.html",
        label="Trip information",
        role="link",
        attributes={
            "href": "/confirmation.html?reservation_id=123",
            "target": "_blank",
        },
    )


def test_action_guard_rejects_overlong_and_multiply_encoded_unsafe_metadata() -> None:
    guard = BrowserUseActionGuard()

    assert not guard.observable_url(
        "https://secure.booking.com/%252563ancel-reservation"
    )
    assert not guard.observable_url(
        "https://secure.booking.com/myreservations.html?value=" + "x" * 4_001
    )
    assert not guard.allows_click(
        current_url="https://secure.booking.com/myreservations.html",
        label="x" * 1_001 + " cancel",
        role="button",
        attributes={},
    )


@pytest.mark.parametrize(
    ("label", "role", "attributes"),
    [
        ("Cancel reservation", "button", {}),
        ("Continue", "input", {}),
        ("Trip information", "link", {"target": "_blank"}),
        ("Trip information", "link", {"download": "receipt.pdf"}),
        ("Trip information", "link", {"href": "/payment"}),
        ("Trip information", "button", {"onclick": "confirmCancellation()"}),
    ],
)
def test_action_guard_rejects_mutating_or_escaping_clicks(
    label: str,
    role: str,
    attributes: dict[str, str],
) -> None:
    assert not BrowserUseActionGuard().allows_click(
        current_url="https://secure.booking.com/myreservations.html",
        label=label,
        role=role,
        attributes=attributes,
    )


@dataclass
class _Node:
    label: str
    attributes: dict[str, str]
    node_name: str = "span"
    target_id: str = "active-target"
    parent_node: _Node | None = None
    is_visible: bool = True

    def get_meaningful_text_for_llm(self) -> str:
        return self.label


def test_click_chain_rejects_nested_mutation_and_cross_target_frames() -> None:
    unsafe_parent = _Node(
        "Cancel reservation",
        {"href": "/cancel"},
        node_name="a",
    )
    nested_child = _Node("More", {}, parent_node=unsafe_parent)
    external_frame_child = _Node(
        "Trip details",
        {},
        target_id="cross-origin-frame",
    )

    assert not _node_chain_allows_click(
        BrowserUseActionGuard(),
        node=nested_child,
        current_url="https://secure.booking.com/myreservations.html",
        active_target_id="active-target",
    )
    assert not _node_chain_allows_click(
        BrowserUseActionGuard(),
        node=external_frame_child,
        current_url="https://secure.booking.com/myreservations.html",
        active_target_id="active-target",
    )


def test_click_chain_ignores_aggregate_text_on_structural_ancestors() -> None:
    structural_footer = _Node(
        "unrelated account footer content " * 60,
        {"class": "account-footer", "data-et-view": "footer"},
        node_name="footer",
    )
    safe_link = _Node(
        "Trip information",
        {"href": "/confirmation.html?reservation_id=123"},
        node_name="a",
        parent_node=structural_footer,
    )
    nested_child = _Node("More", {}, parent_node=safe_link)

    decision = _node_chain_click_decision(
        BrowserUseActionGuard(),
        node=nested_child,
        current_url="https://secure.booking.com/mytrips.html",
        active_target_id="active-target",
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_click_chain_requires_interactive_ancestor_and_still_checks_structural_attributes() -> None:
    plain_container = _Node("Trip information", {}, node_name="footer")
    unsafe_container = _Node(
        "Trip information",
        {"onclick": "cancelReservation()"},
        node_name="footer",
    )

    no_interactive = _node_chain_click_decision(
        BrowserUseActionGuard(),
        node=plain_container,
        current_url="https://secure.booking.com/mytrips.html",
        active_target_id="active-target",
    )
    unsafe_attribute = _node_chain_click_decision(
        BrowserUseActionGuard(),
        node=unsafe_container,
        current_url="https://secure.booking.com/mytrips.html",
        active_target_id="active-target",
    )

    assert no_interactive.allowed is False
    assert no_interactive.reason == "no_interactive_ancestor"
    assert unsafe_attribute.allowed is False
    assert unsafe_attribute.reason == "guard_event_handler"


def test_click_chain_classifies_app_install_link_before_execution() -> None:
    app_link = _Node(
        "Get the mobile app",
        {"href": "/apps.html?app_install=1"},
        node_name="a",
    )

    decision = _node_chain_click_decision(
        BrowserUseActionGuard(),
        node=app_link,
        current_url="https://secure.booking.com/mytrips.html",
        active_target_id="active-target",
    )

    assert decision.allowed is False
    assert decision.reason == "guard_unsafe_destination"


def test_safe_popup_link_is_normalized_to_guarded_same_tab_destination() -> None:
    safe_parent = _Node(
        "Trip information",
        {"href": "/confirmation.html?reservation_id=123", "target": "_blank"},
        node_name="a",
    )
    nested_child = _Node("More", {}, parent_node=safe_parent)
    guard = BrowserUseActionGuard()
    current_url = "https://secure.booking.com/mytrips.html"

    assert _node_chain_allows_click(
        guard,
        node=nested_child,
        current_url=current_url,
        active_target_id="active-target",
    )
    assert _same_tab_click_destination(
        guard,
        node=nested_child,
        current_url=current_url,
    ) == "https://secure.booking.com/confirmation.html?reservation_id=123"


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://secure.booking.com/myreservations.html", True),
        ("https://api.anthropic.com/v1/messages", False),
        ("http://127.0.0.1:8765/fixture", True),
        ("https://cdn.example/track.js", False),
        ("https://cf.bstatic.com/static/app.js", True),
        ("wss://booking.com/socket", True),
        ("data:text/plain,fixture", True),
    ],
)
def test_browser_network_egress_is_allowlisted(url: str, allowed: bool) -> None:
    assert _browser_request_allowed(url) is allowed


def test_browser_use_enters_canonical_https_inventory_without_allowing_legacy_redirect() -> None:
    assert _BROWSER_USE_INVENTORY_ENTRY_URL == "https://secure.booking.com/mytrips.html"
    assert _browser_request_allowed(_BROWSER_USE_INVENTORY_ENTRY_URL)
    assert not _browser_request_allowed("http://secure.booking.com/mytrips.html")


def test_typed_observation_maps_only_bounded_positive_evidence() -> None:
    payload = BrowserUseObservationPayload.model_validate(
        {
            "authenticated": "true",
            "scopes": [
                {
                    "scope": "upcoming",
                    "requested_scope_visible": "true",
                    "explicit_empty": "false",
                    "pagination_exhausted": "true",
                    "pages_observed": 1,
                    "visible_reservation_count": 1,
                    "detail_count": 1,
                    "completeness": "complete",
                }
            ],
            "reservations": [
                {
                    "remote_id": "6992391225",
                    "identity_evidence": "complete",
                    "scope": "upcoming",
                    "lifecycle": "upcoming",
                    "confirmation_id": "6992391225",
                    "property_name": "Hotel Example",
                    "property_reference": "hotel-example-ref",
                    "check_in": "2026-10-01",
                    "check_out": "2026-10-04",
                    "room_type": "Deluxe King Room",
                    "booked_total": "300.00",
                    "currency": "EUR",
                    "all_in": "explicit",
                    "refundability": "explicit_refundable",
                    "refundability_text": "Free cancellation",
                    "refund_deadline": "2026-09-30",
                    "adults": "2",
                    "children": "0",
                    "rooms": "1",
                    "completeness": "complete",
                }
            ],
        }
    )

    scopes, reservations = _map_observation(payload)

    assert scopes[0].scope is InventoryScope.UPCOMING
    assert reservations[0].booked_total is not None
    assert reservations[0].booked_total.amount == Decimal("300.00")

    with pytest.raises(ValueError, match="reservation count"):
        _map_observation(payload.model_copy(update={"reservations": payload.reservations * 101}))


def test_provider_reservation_payload_normalizes_scalars_and_discards_extras() -> None:
    payload = BrowserUseReservationPayload.model_validate(
        {
            "remote_id": 6992391225,
            "scope": "upcoming",
            "booked_total": 301.0,
            "adults": 2,
            "children": None,
            "refundability": {"status": "refundable"},
            "rooms": [1],
            "model_commentary": "discarded",
        }
    )
    missing = BrowserUseReservationPayload.model_validate({})

    assert payload.remote_id == "6992391225"
    assert payload.booked_total == "301.0"
    assert payload.adults == "2"
    assert payload.children == "unknown"
    assert payload.refundability == "unknown"
    assert payload.rooms == "unknown"
    assert "model_commentary" not in payload.model_dump()
    assert missing.remote_id == "unknown"
    assert missing.scope == "unknown"


def test_browser_use_strict_action_shapes_keep_only_required_reliable_fields() -> None:
    submission_schema = BrowserUseReservationSubmission.model_json_schema()
    terminal_schema = BrowserUseTerminalPayload.model_json_schema()
    saved_match_schema = BrowserUseSavedReservationMatch.model_json_schema()

    assert submission_schema["required"] == [
        "confirmation_id",
        "scope",
        "identity_evidence",
    ]
    assert set(submission_schema["properties"]) == {
        "confirmation_id",
        "scope",
        "identity_evidence",
    }
    assert terminal_schema["required"] == ["success"]
    assert set(terminal_schema["properties"]) == {"success"}
    assert saved_match_schema["required"] == ["candidate_index"]


def test_qualified_output_removes_disabled_planning_fields_before_strict_optimizer() -> None:
    from browser_use.llm.schema import SchemaOptimizer

    class _Output(BaseModel):
        evaluation_previous_goal: str
        memory: str
        next_goal: str
        action: list[str]
        current_plan_item: int | None = None
        plan_update: list[str] | None = None

    qualified = _qualified_output_format(_Output)
    schema = SchemaOptimizer.create_optimized_json_schema(qualified)

    assert "current_plan_item" not in schema["properties"]
    assert "plan_update" not in schema["properties"]
    assert schema["required"] == [
        "evaluation_previous_goal",
        "memory",
        "next_goal",
        "action",
    ]
    assert isinstance(
        qualified(
            evaluation_previous_goal="ok",
            memory="bounded",
            next_goal="act",
            action=["done"],
        ),
        _Output,
    )


def test_browser_use_mapping_downgrades_malformed_optional_facts_to_unknown() -> None:
    payload = BrowserUseObservationPayload.model_validate(
        {
            "authenticated": "yes",
            "scopes": [
                {
                    "scope": "upcoming",
                    "requested_scope_visible": "yes",
                    "explicit_empty": "no",
                    "pagination_exhausted": "unknown",
                    "pages_observed": 1,
                    "visible_reservation_count": 1,
                    "detail_count": 0,
                    "completeness": "partial",
                }
            ],
            "reservations": [
                {
                    "remote_id": "6992391225",
                    "identity_evidence": "complete",
                    "scope": "upcoming",
                    "confirmation_id": "6992391225",
                    "property_name": "Hotel Example",
                    "check_in": "November 24, 2026",
                    "booked_total": "$301",
                    "currency": "US dollars",
                    "refundability": "free cancellation",
                }
            ],
        }
    )

    scopes, reservations = _map_browser_use_observation(payload)

    assert scopes[0].requested_scope_visible is None
    assert scopes[0].visible_reservation_count == 1
    assert scopes[0].completeness is EvidenceCompleteness.INCOMPLETE
    assert reservations[0].remote_id == "6992391225"
    assert reservations[0].identity_evidence is EvidenceCompleteness.COMPLETE
    assert reservations[0].property_name == "Hotel Example"
    assert reservations[0].check_in is None
    assert reservations[0].booked_total is None


@pytest.mark.parametrize(
    "status",
    ["observed", "unsafe_action", "action_limit", "cost_limit", "timeout"],
)
def test_provider_cannot_claim_code_owned_terminal_status(status: str) -> None:
    with pytest.raises(ValueError, match="code-owned"):
        _terminal_status(status)


def test_continued_action_result_matches_qualified_browser_use_contract() -> None:
    from browser_use import ActionResult

    result = _continued_action_result(ActionResult, "Content-free correction")

    assert result.is_done is False
    assert result.success is None
    assert result.error is None
    assert result.extracted_content == "Content-free correction"
    with pytest.raises(ValueError, match="success=True can only be set when is_done=True"):
        ActionResult(is_done=False, success=True, extracted_content="invalid")


def test_agent_history_diagnostic_logs_only_bounded_categories() -> None:
    class _Action:
        def __init__(self, name: str) -> None:
            self.name = name

        def model_dump(self, **_kwargs: Any) -> dict[str, dict[str, str]]:
            return {self.name: {"secret": "must-not-appear"}}

    history = SimpleNamespace(
        history=[
            SimpleNamespace(
                model_output=SimpleNamespace(action=[_Action("guarded_click")]),
                result=[SimpleNamespace(error="content validation secret")],
            ),
            SimpleNamespace(
                model_output=SimpleNamespace(action=[_Action("unregistered_secret_action")]),
                result=[SimpleNamespace(error="page-content-secret")],
            ),
        ]
    )

    diagnostic = _agent_history_diagnostic(history)

    assert diagnostic.steps == 2
    assert diagnostic.actions == ("guarded_click", "unknown")
    assert diagnostic.errors == (
        "validation:unknown:unknown:unknown",
        "unknown",
    )


def test_validation_diagnostic_exposes_only_closed_schema_categories() -> None:
    raw = (
        "Invalid parameters {'booked_total': {'amount': 'SECRET'}} for action "
        "submit_inventory_observation: [type=string_type, input_value=SECRET]"
    )

    diagnostic = _validation_diagnostic(raw)

    assert diagnostic == (
        "validation:submit_inventory_observation:booked_total:string_type"
    )
    assert "SECRET" not in diagnostic
    assert "secret" not in repr(diagnostic)


def test_hardened_session_removes_unsafe_watchdogs() -> None:
    def safe_handler() -> None:
        return None

    def unsafe_handler() -> None:
        return None

    unsafe_handler.__name__ = "PopupsWatchdog.on_JavascriptDialogOpenedEvent"

    class PopupsWatchdog:
        def on_tab_created(self) -> None:
            return None

    bound_unsafe_handler = PopupsWatchdog().on_tab_created

    class _Bus:
        def __init__(self) -> None:
            self.handlers = {
                "dialog": [safe_handler, unsafe_handler, bound_unsafe_handler]
            }

    class _Base:
        def __init__(self) -> None:
            self.event_bus = _Bus()

        async def attach_all_watchdogs(self) -> None:
            return None

    session = _hardened_session_type(_Base)()
    asyncio.run(session.attach_all_watchdogs())

    assert session.event_bus.handlers["dialog"] == [safe_handler]


def test_unsafe_watchdog_recognition_covers_wrappers_and_bound_methods() -> None:
    def wrapped_handler() -> None:
        return None

    wrapped_handler.__name__ = "DownloadsWatchdog.on_BrowserLaunchEvent"

    class StorageStateWatchdog:
        def on_save(self) -> None:
            return None

    assert _is_unsafe_watchdog_handler(wrapped_handler) is True
    assert _is_unsafe_watchdog_handler(StorageStateWatchdog().on_save) is True
    assert _is_unsafe_watchdog_handler(lambda: None) is False


def test_qualified_browser_use_release_has_no_unsafe_watchdog_handlers(
    tmp_path: Path,
) -> None:
    from browser_use import BrowserProfile, BrowserSession

    async def inspect_handlers() -> set[str]:
        session_type = _hardened_session_type(BrowserSession)
        session = session_type(
            browser_profile=BrowserProfile(
                headless=True,
                user_data_dir=tmp_path / "profile",
                downloads_path=tmp_path / "downloads",
                accept_downloads=False,
                auto_download_pdfs=False,
                permissions=[],
                enable_default_extensions=False,
                captcha_solver=False,
            )
        )
        await session.attach_all_watchdogs()
        try:
            return {
                getattr(handler, "__name__", "")
                for handlers in session.event_bus.handlers.values()
                for handler in handlers
            }
        finally:
            await session.event_bus.stop(clear=True, timeout=0.5)

    names = asyncio.run(inspect_handlers())

    assert not any(
        name.startswith(prefix)
        for name in names
        for prefix in (
            "DownloadsWatchdog.",
            "StorageStateWatchdog.",
            "AboutBlankWatchdog.",
            "PopupsWatchdog.",
            "PermissionsWatchdog.",
        )
    )


def test_real_confirm_is_rejected_without_executing_mutation(tmp_path: Path) -> None:
    from browser_use import BrowserProfile, BrowserSession
    from playwright.async_api import async_playwright

    runtime_root = tmp_path / "runtime"
    profile_path = runtime_root / "browser-use-user-data-dir-profile"
    profile_path.mkdir(parents=True)

    async def run_fixture() -> tuple[int, bool, str, int]:
        playwright = await async_playwright().start()
        try:
            executable_path = playwright.chromium.executable_path
        finally:
            await playwright.stop()
        session_type = _hardened_session_type(BrowserSession)
        session = session_type(
            browser_profile=BrowserProfile(
                executable_path=executable_path,
                headless=True,
                chromium_sandbox=False,
                user_data_dir=profile_path,
                downloads_path=runtime_root / "downloads",
                accept_downloads=False,
                auto_download_pdfs=False,
                permissions=[],
                enable_default_extensions=False,
                captcha_solver=False,
            )
        )
        runtime = LocalBrowserUseRuntime()
        runtime._session = session  # noqa: SLF001 - real adapter safety fixture
        runtime._root = runtime_root  # noqa: SLF001 - real adapter teardown fixture
        try:
            await session.start()
            await runtime._install_network_guard(session)  # noqa: SLF001
            await runtime._install_dialog_guard(session)  # noqa: SLF001
            page_session = await session.get_or_create_cdp_session()
            result = await asyncio.wait_for(
                page_session.cdp_client.send.Runtime.evaluate(
                    params={
                        "expression": (
                            "window.mutationCounter=0;"
                            "if(confirm('Cancel reservation?')) window.mutationCounter++;"
                            "window.mutationCounter"
                        ),
                        "returnByValue": True,
                    },
                    session_id=page_session.session_id,
                ),
                timeout=5,
            )
            value = result.get("result", {}).get("value")
            blocked = await asyncio.wait_for(
                page_session.cdp_client.send.Runtime.evaluate(
                    params={
                        "expression": (
                            "fetch('https://example.com/sentinel-secret')"
                            ".then(() => 'escaped').catch(() => 'blocked')"
                        ),
                        "returnByValue": True,
                        "awaitPromise": True,
                    },
                    session_id=page_session.session_id,
                ),
                timeout=5,
            )
            blocked_value = blocked.get("result", {}).get("value")
            return (
                int(value),
                runtime._state.dialog_rejected,  # noqa: SLF001
                str(blocked_value),
                runtime._blocked_network_requests,  # noqa: SLF001
            )
        finally:
            await runtime.close()

    mutation_count, rejected, fetch_result, blocked_count = asyncio.run(run_fixture())

    assert mutation_count == 0
    assert rejected is True
    assert fetch_result == "blocked"
    assert blocked_count == 1
    assert not runtime_root.exists()


def test_budgeted_model_repr_never_contains_api_key() -> None:
    class _Base:
        def __init__(self, **_kwargs: Any) -> None:
            return None

    model = _model_type(_Base)(api_key="super-secret", budget=_budget(), meter=object())

    assert "super-secret" not in repr(model)
    assert "super-secret" not in str(model)


class _ProviderUsage:
    prompt_tokens = 100
    completion_tokens = 10
    prompt_cached_tokens = 20
    prompt_cache_creation_tokens = 40


class _ProviderResponse:
    usage = _ProviderUsage()


class _SuccessfulModelBase:
    def __init__(self, **_kwargs: Any) -> None:
        self.model = "claude-sonnet-5"

    async def ainvoke(self, *_args: Any, **_kwargs: Any) -> _ProviderResponse:
        return _ProviderResponse()


class _FailingModelBase(_SuccessfulModelBase):
    async def ainvoke(self, *_args: Any, **_kwargs: Any) -> _ProviderResponse:
        raise RuntimeError("provider-content-must-not-be-logged")


class _TimeoutModelBase(_SuccessfulModelBase):
    async def ainvoke(self, *_args: Any, **_kwargs: Any) -> _ProviderResponse:
        raise TimeoutError("provider-timeout-content")


class _BlockingModelBase(_SuccessfulModelBase):
    async def ainvoke(self, *_args: Any, **_kwargs: Any) -> _ProviderResponse:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class _DeniedLedger(_Ledger):
    def reserve_call(self, request: Any) -> AdmissionDecision:
        self.reservations.append(request)
        return AdmissionDecision(denied_reason=ModelStopReason.JOB_COST_LIMIT)


class _ReconciliationFailureLedger(_Ledger):
    def reconcile_call(self, request: Any) -> CostReconciliation:
        self.reconciliations.append(request)
        raise RuntimeError("ledger-sensitive-failure")


def test_budgeted_model_reconciles_cache_read_and_creation_pricing_exactly() -> None:
    ledger = _Ledger()
    meter = ExecutionMeter(
        ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3))
    )
    model = _model_type(_SuccessfulModelBase)(
        api_key="test-key",
        budget=_budget(ledger),
        meter=meter,
    )

    asyncio.run(model.ainvoke([]))

    usage = meter.snapshot()
    assert usage.tokens.input_tokens == 140
    assert usage.tokens.output_tokens == 10
    # Introductory Sonnet price: 80*2 + 20*0.2 + 40*2.5 + 10*10 micro-USD.
    assert usage.cost.micro_usd == 364
    assert ledger.reconciliations[0].charged_cost == UsdAmount(364)


def test_budgeted_model_failure_reconciles_conservatively_without_logging_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ledger = _Ledger()
    meter = ExecutionMeter(
        ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3))
    )
    model = _model_type(_FailingModelBase)(
        api_key="test-key",
        budget=_budget(ledger),
        meter=meter,
    )

    with pytest.raises(RuntimeError, match="provider-content"):
        asyncio.run(model.ainvoke([]))

    assert ledger.reconciliations[0].conservative is True
    assert "provider-content-must-not-be-logged" not in caplog.text


def test_budgeted_model_timeout_reconciles_conservatively() -> None:
    ledger = _Ledger()
    meter = ExecutionMeter(
        ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3))
    )
    model = _model_type(_TimeoutModelBase)(
        api_key="test-key",
        budget=_budget(ledger),
        meter=meter,
    )

    with pytest.raises(TimeoutError, match="provider-timeout"):
        asyncio.run(model.ainvoke([]))

    assert ledger.reconciliations[0].conservative is True


def test_budgeted_model_cancellation_reconciles_then_preserves_cancellation() -> None:
    ledger = _Ledger()
    meter = ExecutionMeter(
        ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3))
    )
    model = _model_type(_BlockingModelBase)(
        api_key="test-key",
        budget=_budget(ledger),
        meter=meter,
    )

    async def cancel_call() -> None:
        task = asyncio.create_task(model.ainvoke([]))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_call())

    assert ledger.reconciliations[0].conservative is True


def test_budgeted_model_admission_denial_stops_before_provider_call() -> None:
    ledger = _DeniedLedger()
    meter = ExecutionMeter(
        ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3))
    )
    model = _model_type(_SuccessfulModelBase)(
        api_key="test-key",
        budget=_budget(ledger),
        meter=meter,
    )

    with pytest.raises(BrowserUseCostStop) as stopped:
        asyncio.run(model.ainvoke([]))

    assert stopped.value.reason is ModelStopReason.JOB_COST_LIMIT
    assert ledger.reconciliations == []


def test_budgeted_model_reconciliation_failure_stops_fail_closed() -> None:
    ledger = _ReconciliationFailureLedger()
    meter = ExecutionMeter(
        ExecutionLimits(deadline=datetime.now(UTC) + timedelta(minutes=3))
    )
    model = _model_type(_SuccessfulModelBase)(
        api_key="test-key",
        budget=_budget(ledger),
        meter=meter,
    )

    with pytest.raises(BrowserUseCostStop) as stopped:
        asyncio.run(model.ainvoke([]))

    assert stopped.value.reason is ModelStopReason.COST_ACCOUNTING_ERROR


def test_budgeted_model_stops_when_reconciled_cost_exceeds_execution_cap() -> None:
    ledger = _Ledger()
    meter = ExecutionMeter(
        ExecutionLimits(
            deadline=datetime.now(UTC) + timedelta(minutes=3),
            max_job_cost=UsdAmount(1),
        )
    )
    model = _model_type(_SuccessfulModelBase)(
        api_key="test-key",
        budget=_budget(ledger),
        meter=meter,
    )

    with pytest.raises(BrowserUseCostStop) as stopped:
        asyncio.run(model.ainvoke([]))

    assert stopped.value.reason is ModelStopReason.JOB_COST_LIMIT


def test_initial_authentication_is_code_verified_before_agent_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    runtime = LocalBrowserUseRuntime()

    async def verified(_cdp_url: str) -> bytes | None:
        return b"verified-session"

    monkeypatch.setattr(runtime, "_verified_session_refresh", verified)
    terminal = asyncio.run(
        runtime._initial_authentication_terminal(  # noqa: SLF001 - trust-boundary test
            request,
            "ws://127.0.0.1/devtools/browser/test",
        )
    )

    assert terminal is None


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("signed_out", InventoryExecutionStatus.SIGNED_OUT),
        ("provider", InventoryExecutionStatus.PROVIDER_FAILURE),
    ],
)
def test_initial_authentication_failure_stops_before_agent(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected: InventoryExecutionStatus,
) -> None:
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    runtime = LocalBrowserUseRuntime()

    async def fail(_cdp_url: str) -> bytes | None:
        if failure == "provider":
            raise RuntimeError("content-bearing-probe-failure")
        return None

    monkeypatch.setattr(runtime, "_verified_session_refresh", fail)
    terminal = asyncio.run(
        runtime._initial_authentication_terminal(  # noqa: SLF001 - trust-boundary test
            request,
            "ws://127.0.0.1/devtools/browser/test",
        )
    )

    assert terminal is expected


def test_post_agent_refresh_failure_preserves_verified_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    runtime = LocalBrowserUseRuntime()
    observation = BrowserUseObservationPayload(
        authenticated="true",
        scopes=[],
        reservations=[],
    )
    runtime._state.observation = observation  # noqa: SLF001 - callback contract test

    async def fail(_cdp_url: str) -> bytes | None:
        raise TimeoutError("content-bearing-refresh-timeout")

    monkeypatch.setattr(runtime, "_verified_session_refresh", fail)
    asyncio.run(
        runtime._refresh_after_observation(  # noqa: SLF001 - callback contract test
            request,
            "ws://127.0.0.1/devtools/browser/test",
        )
    )

    assert runtime._state.observation is observation  # noqa: SLF001
    assert runtime._state.terminal is None  # noqa: SLF001
    assert runtime._state.refreshed_session is None  # noqa: SLF001


def test_confinement_environment_disables_external_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "ANONYMIZED_TELEMETRY",
        "BROWSER_USE_CLOUD_SYNC",
        "BROWSER_USE_VERSION_CHECK",
        "BROWSER_USE_CALCULATE_COST",
    ):
        monkeypatch.delenv(name, raising=False)

    _prepare_environment()

    assert __import__("os").environ["ANONYMIZED_TELEMETRY"] == "false"
    assert __import__("os").environ["BROWSER_USE_CLOUD_SYNC"] == "false"
    assert __import__("os").environ["BROWSER_USE_VERSION_CHECK"] == "false"
    assert __import__("os").environ["BROWSER_USE_CALCULATE_COST"] == "false"


def test_dependency_logs_cannot_propagate_page_or_provider_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    _prepare_environment()
    logging.getLogger("browser_use.agent.service").error(
        "https://secure.booking.com/?secret=session-content"
    )
    logging.getLogger("cdp_use.client").warning("provider-page-content")

    assert "session-content" not in caplog.text
    assert "provider-page-content" not in caplog.text


@dataclass
class _Runtime:
    result: BrowserUseRuntimeResult
    restored: bytes | None = None
    closed: bool = False

    def restore_session(self, data: bytes) -> None:
        self.restored = bytes(data)

    async def execute(self, *_args: Any, **_kwargs: Any) -> BrowserUseRuntimeResult:
        return self.result

    async def close(self) -> None:
        self.closed = True


def test_executor_uses_existing_contract_provenance_and_always_closes_runtime() -> None:
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    runtime = _Runtime(
        BrowserUseRuntimeResult(
            InventoryExecutionStatus.OBSERVED,
            scopes=_scopes(),
            refreshed_session=b'[{"name":"session","value":"refreshed"}]',
        )
    )
    with AsyncLoopRunner() as runner:
        result = BrowserUseInventoryBrowserExecutor(
            api_key="test-key",
            lease_broker=broker,
            budget=_budget(),
            runner=runner,
            runtime_factory=lambda: runtime,
        ).execute(request)

    assert result.status is InventoryExecutionStatus.OBSERVED
    assert result.provenance is not None
    assert result.provenance.source is ObservationSource.BROWSER_USE_INVENTORY_SUBMISSION
    assert result.refreshed_session_eligible is True
    assert runtime.restored is not None and b"secret" in runtime.restored
    assert runtime.closed is True
    assert broker.take_verified_refresh(request.session_lease) is not None


def test_executor_logs_content_free_runtime_stage_on_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _FailingRuntime(_Runtime):
        _failure_stage = "environment_prepare"

        async def execute(self, *_args: Any, **_kwargs: Any) -> BrowserUseRuntimeResult:
            raise PermissionError("content-bearing-path")

    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    runtime = _FailingRuntime(
        BrowserUseRuntimeResult(InventoryExecutionStatus.PROVIDER_FAILURE)
    )
    with AsyncLoopRunner() as runner:
        result = BrowserUseInventoryBrowserExecutor(
            api_key="test-key",
            lease_broker=broker,
            budget=_budget(),
            runner=runner,
            runtime_factory=lambda: runtime,
        ).execute(request)

    assert result.status is InventoryExecutionStatus.PROVIDER_FAILURE
    assert runtime.closed is True
    assert "failure_stage=environment_prepare" in caplog.text
    assert "failure_type=PermissionError" in caplog.text
    assert "content-bearing-path" not in caplog.text


def test_executor_preserves_safety_terminal_and_closes_runtime() -> None:
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    runtime = _Runtime(
        BrowserUseRuntimeResult(
            InventoryExecutionStatus.UNSAFE_ACTION,
            safety_violations=frozenset(
                {ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED}
            ),
        )
    )
    with AsyncLoopRunner() as runner:
        result = BrowserUseInventoryBrowserExecutor(
            api_key="test-key",
            lease_broker=broker,
            budget=_budget(),
            runner=runner,
            runtime_factory=lambda: runtime,
        ).execute(request)

    assert result.status is InventoryExecutionStatus.UNSAFE_ACTION
    assert result.safety_violations == frozenset(
        {ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED}
    )
    assert runtime.closed is True


def test_local_runtime_cleanup_deletes_only_owned_transient_paths(tmp_path: Path) -> None:
    runtime = LocalBrowserUseRuntime()
    owned = tmp_path / "browser-use-owned"
    owned.mkdir()
    (owned / "artifact.txt").write_text("ephemeral", encoding="utf-8")
    runtime._root = owned  # noqa: SLF001 - cleanup contract test

    asyncio.run(runtime.close())

    assert not owned.exists()


def test_local_runtime_cleanup_removes_constructor_failure_namespace_only() -> None:
    runtime = LocalBrowserUseRuntime()
    run_id = f"booksaver-{uuid.uuid4().hex}"
    owned = Path(tempfile.mkdtemp(prefix=f"browser_use_agent_{run_id}_"))
    neighbor = Path(tempfile.mkdtemp(prefix="browser_use_agent_neighbor_"))
    runtime._agent_run_id = run_id  # noqa: SLF001 - constructor-failure cleanup contract
    try:
        asyncio.run(runtime.close())

        assert not owned.exists()
        assert neighbor.exists()
    finally:
        shutil.rmtree(neighbor, ignore_errors=True)


def test_job_teardown_preserves_process_wide_content_free_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import booksaver.infrastructure.browser.browser_use_inventory_executor as adapter

    config_dir = tmp_path / "process-config"
    cache_dir = tmp_path / "process-cache"
    owned_root = tmp_path / "job-root"
    owned_root.mkdir()
    monkeypatch.setattr(adapter, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(adapter, "_CACHE_DIR", cache_dir)
    adapter._prepare_environment()  # noqa: SLF001 - process environment contract
    runtime = LocalBrowserUseRuntime()
    runtime._root = owned_root  # noqa: SLF001 - teardown contract test

    asyncio.run(runtime.close())

    assert not owned_root.exists()
    assert config_dir.is_dir() and list(config_dir.iterdir()) == []
    assert cache_dir.is_dir() and list(cache_dir.iterdir()) == []
