from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.application.inventory_executor import InventoryExecutionService
from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.domain.account_sync import ReservationLifecycle
from booksaver.domain.agent import LLMUsage
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionLimits,
    ExecutorSafetyViolation,
    ObservationSource,
    RefundabilityEvidence,
)
from booksaver.domain.browser_guard import (
    BrowserActionProposal,
    BrowserActionType,
    CoordinateHitTest,
    DestinationSnapshot,
    GuardRejection,
)
from booksaver.domain.inventory_executor import (
    InventoryExecutionRequest,
    InventoryExecutionStatus,
    InventoryScope,
    ObservedInventoryScope,
    ObservedReservation,
    inventory_session_subject,
)
from booksaver.domain.model_policy import (
    AdmissionDecision,
    BrowserJobKind,
    CallerKeyRef,
    CostReconciliation,
    CostReservation,
    ModelCostEstimator,
    ReservationStatus,
)
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.browser.agentic_executor import (
    BrowserNavigationFailure,
    BrowserNavigationFailureKind,
    ComputerActionRequest,
    InspectedElement,
    ProviderUsage,
    SemanticAction,
)
from booksaver.infrastructure.browser.agentic_inventory_executor import (
    INVENTORY_ENTRY_URL,
    InventoryActionGuard,
    InventoryComputerObservation,
    InventoryComputerTurn,
    InventoryComputerTurnKind,
    InventoryDetailObservation,
    InventoryScopePage,
    InventoryTaskKind,
    InventoryTraversalTask,
    LocalInventoryStagehandRuntime,
    StagehandInventoryBrowserExecutor,
    _computer_tools,
    _map_computer_observation,
    _map_scope_page,
)


class _Ledger:
    def __init__(self) -> None:
        self.reservations = []
        self.reconciliations = []

    def reserve_call(self, request):
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

    def reconcile_call(self, request):
        self.reconciliations.append(request)
        return CostReconciliation(
            request.reservation_id,
            request.charged_cost,
            ReservationStatus.CONSERVATIVE
            if request.conservative
            else ReservationStatus.CHARGED,
        )

    def list_attempts(self, _job_id):
        return ()


class _ProgrammingErrorLedger(_Ledger):
    def reserve_call(self, request):
        del request
        raise sqlite3.ProgrammingError("sensitive provider context must not be logged")


def _budget(ledger: _Ledger) -> BrowserJobCostBudget:
    return BrowserJobCostBudget(
        job_id="inventory-job-1",
        job_kind=BrowserJobKind.CHECK_NOW,
        caller_key_ref=CallerKeyRef(7, "owner", "deployment_key"),
        ledger=ledger,
        estimator=ModelCostEstimator(),
        preserve_opus_diagnostic=False,
    )


def _reservation() -> ObservedReservation:
    return ObservedReservation(
        remote_id="6992391225",
        identity_evidence=EvidenceCompleteness.COMPLETE,
        scope=InventoryScope.UPCOMING,
        lifecycle=ReservationLifecycle.UPCOMING,
        confirmation_id="6992391225",
        property_name="Hotel Example",
        property_reference="hotel-example-ref",
        check_in=date(2026, 10, 1),
        check_out=date(2026, 10, 4),
        room_type="Deluxe King Room",
        booked_total=Money(Decimal("300"), "EUR"),
        all_in=AllInEvidence.EXPLICIT,
        refundability=RefundabilityEvidence.EXPLICIT_REFUNDABLE,
        refundability_text="Free cancellation until 30 September",
        refund_deadline=date(2026, 9, 30),
        occupancy=Occupancy(2, 1, 1),
        completeness=EvidenceCompleteness.COMPLETE,
    )


def _scope_page(scope: InventoryScope) -> InventoryScopePage:
    reservations = (_reservation(),) if scope is InventoryScope.UPCOMING else ()
    return InventoryScopePage(
        scope=scope,
        authenticated=True,
        requested_scope_visible=True,
        explicit_empty=not reservations,
        pagination_exhausted=True,
        completeness=EvidenceCompleteness.COMPLETE,
        reservations=reservations,
        visible_reservation_count=len(reservations),
        detail_required_ids=(),
    )


def _scope_evidence(scope: InventoryScope) -> ObservedInventoryScope:
    visible = int(scope is InventoryScope.UPCOMING)
    return ObservedInventoryScope(
        scope=scope,
        requested_scope_visible=True,
        explicit_empty=not bool(visible),
        pagination_exhausted=True,
        pages_observed=1,
        visible_reservation_count=visible,
        detail_count=0,
        completeness=EvidenceCompleteness.COMPLETE,
    )


@dataclass
class _Runtime:
    no_action: bool = False
    fail_scope: InventoryScope | None = None
    unsafe_destination: bool = False
    replay_raises: bool = False
    redirect_url: str | None = None
    refreshed: bytes | None = (
        b'[{"name":"session","value":"refreshed","domain":".booking.com","path":"/"}]'
    )
    url: str = "about:blank"
    restored: bytes | None = None
    launched: bool = False
    attached: bool = False
    closed: bool = False
    replayed: int = 0
    visual_actions: list[ComputerActionRequest] = field(default_factory=list)
    current_task: InventoryTraversalTask | None = None
    provider_selector: str = "provider-generated-selector"
    inspected_scope_label: str | None = None
    scope_href_missing: bool = False
    extract_error: Exception | None = None
    navigation_failure: BrowserNavigationFailureKind | None = None

    def restore_session(self, data: bytes) -> None:
        self.restored = bytes(data)

    async def launch(self) -> None:
        self.launched = True

    async def apply_session(self) -> None:
        assert self.restored

    async def attach(self, _api_key: str) -> None:
        self.attached = True

    async def navigate(self, url: str) -> None:
        assert url == INVENTORY_ENTRY_URL
        if self.navigation_failure is not None:
            raise BrowserNavigationFailure(self.navigation_failure)
        self.url = self.redirect_url or url

    async def destination(self) -> DestinationSnapshot:
        return DestinationSnapshot(self.url)

    async def viewport_size(self) -> tuple[int, int]:
        return (412, 839)

    async def observe_inventory_action(self, task: InventoryTraversalTask):
        self.current_task = task
        if self.no_action or (
            task.kind is InventoryTaskKind.SCOPE and task.scope is self.fail_scope
        ):
            return None, ProviderUsage(LLMUsage(100, 20), 10)
        return (
            SemanticAction(
                f"Open {task.scope.value} {task.kind.value}",
                "click",
                self.provider_selector,
                task,
            ),
            ProviderUsage(LLMUsage(100, 20), 10),
        )

    async def inspect(self, _action: SemanticAction) -> InspectedElement:
        assert self.current_task is not None
        task = self.current_task
        if task.kind is InventoryTaskKind.DETAIL:
            label = "View confirmation details"
            href = "https://secure.booking.com/confirmation.html?trip_id=6992391225"
            role = "link"
        elif task.kind is InventoryTaskKind.PAGINATION:
            label = "Next page"
            href = f"{INVENTORY_ENTRY_URL}?page=2"
            role = "button"
        else:
            label = (
                self.inspected_scope_label
                if self.inspected_scope_label is not None
                else task.scope.value
            )
            href = (
                None
                if self.scope_href_missing
                else f"{INVENTORY_ENTRY_URL}?scope={task.scope.value}"
            )
            role = "tab"
        return InspectedElement(label, role, href, True, True)

    async def replay(self, _action: SemanticAction) -> None:
        self.replayed += 1
        if self.unsafe_destination:
            self.url = "https://attacker.example/capture"
        elif self.current_task is not None and self.current_task.kind is InventoryTaskKind.DETAIL:
            self.url = "https://secure.booking.com/confirmation.html?trip_id=6992391225"
        else:
            self.url = INVENTORY_ENTRY_URL
        if self.replay_raises:
            raise RuntimeError("provider action failed")

    async def extract_inventory_scope(self, scope: InventoryScope):
        if self.extract_error is not None:
            raise self.extract_error
        return _scope_page(scope), ProviderUsage(LLMUsage(200, 40), 20)

    async def extract_inventory_detail(self, _task: InventoryTraversalTask):
        return (
            InventoryDetailObservation(True, _reservation()),
            ProviderUsage(LLMUsage(200, 40), 20),
        )

    async def screenshot(self) -> bytes:
        return b"png"

    async def hit_test(self, _x: int, _y: int) -> CoordinateHitTest:
        return CoordinateHitTest(
            20,
            30,
            1280,
            800,
            label="Upcoming reservations",
            role="tab",
        )

    async def execute_action(self, action: ComputerActionRequest) -> None:
        self.visual_actions.append(action)

    async def verified_session_refresh(self) -> bytes | None:
        return self.refreshed

    async def close(self) -> None:
        self.closed = True


class _ComputerModel:
    def __init__(self, turns: list[InventoryComputerTurn]) -> None:
        self.turns = turns
        self.prior_ids: list[str | None] = []

    def next_turn(self, *, screenshot, request, prior_tool_use_id):
        assert screenshot == b"png"
        assert request.owner_user_id == 7
        self.prior_ids.append(prior_tool_use_id)
        return self.turns.pop(0)


class _FailingComputerModel:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def next_turn(self, *, screenshot, request, prior_tool_use_id):
        del screenshot, request, prior_tool_use_id
        raise self.error


class _SchemaCaptureStagehand:
    def __init__(self) -> None:
        self.schema: dict[str, object] | None = None

    async def extract(self, _instruction, schema, **_kwargs):
        self.schema = schema.model_json_schema()
        data = schema.model_validate(
            {
                "state": "inventory",
                "authenticated": "true",
                "requested_scope_visible": "true",
                "explicit_empty": "unknown",
                "pagination_exhausted": "false",
                "completeness": "unknown",
                "reservations": [],
            }
        )
        usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 2})()
        metadata = type("Metadata", (), {"usage": usage})()
        return type("Result", (), {"data": data, "metadata": metadata})()


class _DetailSchemaCaptureStagehand:
    def __init__(self) -> None:
        self.schema: dict[str, object] | None = None

    async def extract(self, _instruction, schema, **_kwargs):
        self.schema = schema.model_json_schema()
        data = schema.model_validate(
            {
                "state": "inventory",
                "authenticated": "true",
                "remote_id": "6992391225",
                "identity_evidence": "complete",
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
                "children": "1",
                "rooms": "1",
                "completeness": "complete",
            }
        )
        usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 2})()
        metadata = type("Metadata", (), {"usage": usage})()
        return type("Result", (), {"data": data, "metadata": metadata})()


def _union_parameter_count(value: object) -> int:
    if isinstance(value, dict):
        current = int(isinstance(value.get("type"), list) or "anyOf" in value)
        return current + sum(_union_parameter_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_union_parameter_count(item) for item in value)
    return 0


def _schema_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_schema_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_schema_keys(item) for item in value), set())
    return set()


def _request(broker: InMemorySessionLeaseBroker) -> InventoryExecutionRequest:
    execution_id = "inventory-execution-1"
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


def _execute(
    runtime: _Runtime,
    computer_model: _ComputerModel | _FailingComputerModel | None = None,
    ledger: _Ledger | None = None,
):
    ledger = ledger or _Ledger()
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    with AsyncLoopRunner() as runner:
        executor = StagehandInventoryBrowserExecutor(
            api_key="test-key",
            lease_broker=broker,
            budget=_budget(ledger),
            runner=runner,
            runtime_factory=lambda: runtime,
            computer_model_factory=(
                (lambda: computer_model) if computer_model is not None else None
            ),
        )
        outcome = InventoryExecutionService(executor, broker).execute(request)
    return outcome, ledger


def test_cost_admission_failure_logs_bounded_phase_without_exception_message(
    caplog,
) -> None:
    with caplog.at_level("WARNING"):
        outcome, _ledger = _execute(_Runtime(), ledger=_ProgrammingErrorLedger())

    assert outcome.result.status is InventoryExecutionStatus.PROVIDER_FAILURE
    assert "operation=admit" in caplog.text
    assert "model_role=extraction" in caplog.text
    assert "prompt_version=stagehand-inventory-extract-v1" in caplog.text
    assert "failure_type=ProgrammingError" in caplog.text
    assert "sensitive provider context" not in caplog.text


def test_stagehand_scope_schema_stays_below_union_limit_and_decodes_tri_state() -> None:
    runtime = LocalInventoryStagehandRuntime()
    stagehand = _SchemaCaptureStagehand()
    runtime._stagehand = stagehand  # noqa: SLF001 - isolated adapter contract test
    runtime._page = object()  # noqa: SLF001 - isolated adapter contract test

    page, usage = asyncio.run(runtime.extract_inventory_scope(InventoryScope.UPCOMING))

    assert stagehand.schema is not None
    assert _union_parameter_count(stagehand.schema) == 0
    properties = stagehand.schema["properties"]
    assert isinstance(properties, dict)
    for field_name in (
        "authenticated",
        "requested_scope_visible",
        "explicit_empty",
        "pagination_exhausted",
    ):
        field_schema = properties[field_name]
        assert isinstance(field_schema, dict)
        assert field_schema["type"] == "string"
        assert set(field_schema["enum"]) == {"true", "false", "unknown"}
    assert page.authenticated is True
    assert page.requested_scope_visible is True
    assert page.explicit_empty is None
    assert page.pagination_exhausted is False
    assert page.completeness is EvidenceCompleteness.INCOMPLETE
    assert usage.tokens == LLMUsage(10, 2)


def test_stagehand_detail_schema_has_no_provider_compiled_unions() -> None:
    runtime = LocalInventoryStagehandRuntime()
    stagehand = _DetailSchemaCaptureStagehand()
    runtime._stagehand = stagehand  # noqa: SLF001 - isolated adapter contract test
    runtime._page = object()  # noqa: SLF001 - isolated adapter contract test
    task = InventoryTraversalTask(
        InventoryTaskKind.DETAIL,
        InventoryScope.UPCOMING,
        "6992391225",
    )

    detail, usage = asyncio.run(runtime.extract_inventory_detail(task))

    assert stagehand.schema is not None
    assert _union_parameter_count(stagehand.schema) == 0
    assert detail.reservation is not None
    assert detail.reservation.remote_id == "6992391225"
    assert usage.tokens == LLMUsage(10, 2)


def test_computer_tool_schema_uses_supported_subset_and_union_budget() -> None:
    tools = _computer_tools(412, 839)
    strict_schemas = [
        tool["input_schema"]
        for tool in tools
        if tool.get("strict") is True and "input_schema" in tool
    ]
    observation_tool = next(
        tool for tool in tools if tool.get("name") == "submit_inventory_observation"
    )
    observation = observation_tool["input_schema"]

    forbidden = {"minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"}
    assert not (_schema_keys(observation) & forbidden)
    assert sum(_union_parameter_count(schema) for schema in strict_schemas) <= 16
    assert "strict" not in observation_tool
    reservation = observation["properties"]["reservations"]["items"]
    lifecycle = reservation["properties"]["lifecycle"]
    assert lifecycle["anyOf"][-1] == {"type": "null"}
    assert None not in lifecycle["anyOf"][0]["enum"]
    computer = next(tool for tool in tools if tool.get("name") == "computer")
    assert computer["display_width_px"] == 412
    assert computer["display_height_px"] == 839


def test_computer_observation_restores_tri_state_and_code_owned_bounds() -> None:
    raw = {
        "authenticated": True,
        "scopes": [
            {
                "scope": "upcoming",
                "requested_scope_visible": "true",
                "explicit_empty": "unknown",
                "pagination_exhausted": "false",
                "pages_observed": 1,
                "visible_reservation_count": 0,
                "detail_count": 0,
                "completeness": "incomplete",
            }
        ],
        "reservations": [],
    }

    observation = _map_computer_observation(raw)

    assert observation.scopes[0].requested_scope_visible is True
    assert observation.scopes[0].explicit_empty is None
    assert observation.scopes[0].pagination_exhausted is False

    with pytest.raises(ValueError, match="reservation count"):
        _map_computer_observation({**raw, "reservations": [{}] * 501})
    with pytest.raises(ValueError, match="scope count"):
        _map_computer_observation({**raw, "scopes": raw["scopes"] * 4})
    excessive_page = dict(raw["scopes"][0], pages_observed=21)
    with pytest.raises(ValueError, match="pages_observed"):
        _map_computer_observation({**raw, "scopes": [excessive_page]})


def test_computer_observation_accepts_json_boolean_scope_flags() -> None:
    raw = {
        "authenticated": True,
        "scopes": [
            {
                "scope": "upcoming",
                "requested_scope_visible": True,
                "explicit_empty": False,
                "pagination_exhausted": True,
                "pages_observed": 1,
                "visible_reservation_count": 0,
                "detail_count": 0,
                "completeness": "incomplete",
            }
        ],
        "reservations": [],
    }

    observation = _map_computer_observation(raw)

    assert observation.scopes[0].requested_scope_visible is True
    assert observation.scopes[0].explicit_empty is False
    assert observation.scopes[0].pagination_exhausted is True


def test_scope_page_keeps_reservation_when_occupancy_text_is_unparseable() -> None:
    page = _map_scope_page(
        InventoryScope.UPCOMING,
        {
            "state": "inventory",
            "authenticated": "true",
            "requested_scope_visible": "true",
            "explicit_empty": "false",
            "pagination_exhausted": "true",
            "completeness": "complete",
            "reservations": [
                {
                    "remote_id": "6992391225",
                    "identity_evidence": "complete",
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
                    "adults": "2.0",
                    "children": "2 adults",
                    "rooms": "unknown",
                    "completeness": "complete",
                    "needs_detail": False,
                }
            ],
        },
    )

    assert len(page.reservations) == 1
    assert page.reservations[0].remote_id == "6992391225"
    assert page.reservations[0].occupancy is None


def test_provider_schema_failures_log_only_closed_categories(caplog) -> None:
    semantic_error = RuntimeError(
        "Schemas contains too many parameters with union types (18; limit: 16) PRIVATE-CONTENT"
    )
    computer_error = RuntimeError(
        "tools.1.custom: property maxItems is not supported PRIVATE-CONTENT"
    )

    with caplog.at_level("WARNING"):
        outcome, _ledger = _execute(
            _Runtime(extract_error=semantic_error),
            _FailingComputerModel(computer_error),
        )

    assert outcome.result.status is InventoryExecutionStatus.PROVIDER_FAILURE
    assert "execution_id=inventory-execution-1" in caplog.text
    assert "phase=semantic_extract_scope" in caplog.text
    assert "category=stagehand_schema_union_limit" in caplog.text
    assert "phase=computer_use" in caplog.text
    assert "category=anthropic_tool_schema_keyword" in caplog.text
    assert "PRIVATE-CONTENT" not in caplog.text


def test_semantic_inventory_traverses_scopes_and_returns_positive_only_evidence() -> None:
    runtime = _Runtime()

    outcome, ledger = _execute(runtime)

    assert outcome.result.status is InventoryExecutionStatus.OBSERVED
    assert outcome.result.provenance is not None
    assert outcome.result.provenance.source is ObservationSource.STAGEHAND_INVENTORY_EXTRACT
    assert outcome.result.provenance.schema_version == "inventory-observation-v1"
    assert outcome.result.refreshed_session_eligible
    assert outcome.refreshed_session == runtime.refreshed
    assert outcome.validation.accepted_positive_count == 1
    assert outcome.validation.traversal_claim_complete
    assert outcome.discovery_result.observations[0].remote_id == "6992391225"
    assert runtime.replayed == 2
    assert runtime.restored is not None and b"secret" in runtime.restored
    assert runtime.closed
    assert len(ledger.reservations) == 5
    assert len(ledger.reconciliations) == 5


def test_semantic_failure_hands_same_browser_to_visual_inventory_submission() -> None:
    runtime = _Runtime(no_action=True)
    model = _ComputerModel(
        [
            InventoryComputerTurn(
                InventoryComputerTurnKind.SUBMISSION,
                ProviderUsage(LLMUsage(100, 20), 10),
                observation=InventoryComputerObservation(
                    authenticated=True,
                    scopes=tuple(_scope_evidence(scope) for scope in InventoryScope),
                    reservations=(_reservation(),),
                    evidence_item_count=42,
                ),
            )
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is InventoryExecutionStatus.OBSERVED
    assert outcome.result.fallback_used
    assert outcome.result.provenance is not None
    assert (
        outcome.result.provenance.source
        is ObservationSource.COMPUTER_USE_INVENTORY_SUBMISSION
    )
    assert outcome.validation.accepted_positive_count == 1
    assert runtime.visual_actions == []
    assert runtime.closed


def test_partial_positive_survives_non_security_visual_failure() -> None:
    runtime = _Runtime(fail_scope=InventoryScope.PAST)
    model = _ComputerModel(
        [
            InventoryComputerTurn(
                InventoryComputerTurnKind.TERMINAL,
                ProviderUsage(LLMUsage(100, 20), 10),
                terminal_status=InventoryExecutionStatus.PROVIDER_FAILURE,
            )
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is InventoryExecutionStatus.OBSERVED
    assert outcome.result.fallback_used
    assert len(outcome.result.scopes) == 1
    assert outcome.result.scopes[0].scope is InventoryScope.UPCOMING
    assert outcome.validation.accepted_positive_count == 1
    assert not outcome.validation.traversal_claim_complete


def test_inventory_computer_typing_is_terminal_and_never_executed() -> None:
    runtime = _Runtime(no_action=True)
    model = _ComputerModel(
        [
            InventoryComputerTurn(
                InventoryComputerTurnKind.ACTION,
                ProviderUsage(LLMUsage(100, 20), 10),
                action=ComputerActionRequest(
                    BrowserActionType.TYPE,
                    "tool-type",
                    value="invented text",
                ),
            )
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is InventoryExecutionStatus.UNSAFE_ACTION
    assert runtime.visual_actions == []
    assert runtime.closed


def test_semantic_escape_is_terminal_before_computer_use() -> None:
    runtime = _Runtime(unsafe_destination=True)

    outcome, _ledger = _execute(runtime)

    assert outcome.result.status is InventoryExecutionStatus.UNSAFE_ACTION
    assert outcome.result.safety_violations == frozenset(
        {
            ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED,
            ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION,
        }
    )
    assert runtime.closed


def test_failed_semantic_replay_still_checks_escaped_destination() -> None:
    runtime = _Runtime(unsafe_destination=True, replay_raises=True)

    outcome, _ledger = _execute(runtime)

    assert outcome.result.status is InventoryExecutionStatus.UNSAFE_ACTION
    assert outcome.result.safety_violations == frozenset(
        {
            ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED,
            ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION,
        }
    )
    assert runtime.closed


def test_provider_description_cannot_authorize_an_unlabelled_dom_target() -> None:
    runtime = _Runtime(inspected_scope_label="", scope_href_missing=True)
    model = _ComputerModel(
        [
            InventoryComputerTurn(
                InventoryComputerTurnKind.TERMINAL,
                ProviderUsage(LLMUsage(100, 20), 10),
                terminal_status=InventoryExecutionStatus.PROVIDER_FAILURE,
            )
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is InventoryExecutionStatus.OBSERVED
    assert outcome.validation.accepted_positive_count == 1
    assert runtime.replayed == 0


def test_code_owned_inventory_navigation_classifies_login_redirect() -> None:
    outcome, ledger = _execute(
        _Runtime(redirect_url="https://account.booking.com/signin")
    )

    assert outcome.result.status is InventoryExecutionStatus.SIGNED_OUT
    assert outcome.result.usage.total_actions == 1
    assert ledger.reservations == []


def test_inventory_redirect_loop_is_signed_out_before_model_cost() -> None:
    outcome, ledger = _execute(
        _Runtime(navigation_failure=BrowserNavigationFailureKind.REDIRECT_LOOP)
    )

    assert outcome.result.status is InventoryExecutionStatus.SIGNED_OUT
    assert outcome.result.usage.total_actions == 1
    assert outcome.result.usage.model_calls == 0
    assert ledger.reservations == []


def test_inventory_transport_failure_is_provider_failure_before_model_cost() -> None:
    outcome, ledger = _execute(
        _Runtime(navigation_failure=BrowserNavigationFailureKind.CONNECTION)
    )

    assert outcome.result.status is InventoryExecutionStatus.PROVIDER_FAILURE
    assert outcome.result.usage.total_actions == 1
    assert outcome.result.usage.model_calls == 0
    assert ledger.reservations == []


def test_inventory_model_auth_claim_cannot_replace_code_owned_session_proof() -> None:
    outcome, _ledger = _execute(_Runtime(refreshed=None))

    assert outcome.result.status is InventoryExecutionStatus.SESSION_UNAVAILABLE
    assert outcome.refreshed_session is None
    assert not outcome.validation.observations


def test_inventory_guard_allows_read_only_detail_but_rejects_mutation_and_typing() -> None:
    guard = InventoryActionGuard()
    current = DestinationSnapshot(INVENTORY_ENTRY_URL)
    detail = BrowserActionProposal(
        action=BrowserActionType.CLICK,
        current=current,
        label="View confirmation details",
        role="link",
        destination="https://secure.booking.com/confirmation.html?trip_id=6992391225",
    )
    mutation = BrowserActionProposal(
        action=BrowserActionType.CLICK,
        current=current,
        label="Cancel reservation",
        role="button",
    )
    typing = BrowserActionProposal(
        action=BrowserActionType.TYPE,
        current=current,
        label="Search",
        role="textbox",
        value="anything",
    )

    assert guard.evaluate(
        detail,
        task=InventoryTraversalTask(
            InventoryTaskKind.DETAIL,
            InventoryScope.UPCOMING,
            "6992391225",
        ),
    ).allowed
    assert guard.evaluate(mutation).rejection is GuardRejection.UNSAFE_LABEL
    assert guard.evaluate(typing).rejection is GuardRejection.UNSAFE_INPUT


def test_inventory_detail_task_allows_changed_read_only_booking_route() -> None:
    guard = InventoryActionGuard()
    proposal = BrowserActionProposal(
        action=BrowserActionType.CLICK,
        current=DestinationSnapshot(INVENTORY_ENTRY_URL),
        label="View reservation details",
        role="link",
        destination=(
            "https://secure.booking.com/travel-plan?item=6992391225&layout=compact"
        ),
    )

    assert guard.evaluate(
        proposal,
        task=InventoryTraversalTask(
            InventoryTaskKind.DETAIL,
            InventoryScope.UPCOMING,
            "6992391225",
        ),
    ).allowed


@pytest.mark.parametrize("label", ["Details", "See details", "View more details"])
def test_inventory_detail_task_accepts_common_labels_with_subject_proof(
    label: str,
) -> None:
    guard = InventoryActionGuard()
    proposal = BrowserActionProposal(
        action=BrowserActionType.CLICK,
        current=DestinationSnapshot(INVENTORY_ENTRY_URL),
        label=label,
        role="link",
        destination="https://secure.booking.com/travel-plan/6992391225",
    )

    assert guard.evaluate(
        proposal,
        task=InventoryTraversalTask(
            InventoryTaskKind.DETAIL,
            InventoryScope.UPCOMING,
            "6992391225",
        ),
    ).allowed


@pytest.mark.parametrize(
    "destination",
    [None, "https://secure.booking.com/travel-plan?item=opaque"],
)
def test_inventory_detail_task_requires_destination_subject_proof(
    destination: str | None,
) -> None:
    guard = InventoryActionGuard()
    proposal = BrowserActionProposal(
        action=BrowserActionType.CLICK,
        current=DestinationSnapshot(INVENTORY_ENTRY_URL),
        label="Details",
        role="button",
        destination=destination,
    )

    decision = guard.evaluate(
        proposal,
        task=InventoryTraversalTask(
            InventoryTaskKind.DETAIL,
            InventoryScope.UPCOMING,
            "6992391225",
        ),
    )

    assert decision.rejection is GuardRejection.UNSAFE_PATH


@pytest.mark.parametrize(
    "destination",
    [
        f"{INVENTORY_ENTRY_URL}?page=2&action=cancel",
        f"{INVENTORY_ENTRY_URL}?action=cancelReservation",
        "https://secure.booking.com/confirmation.html?trip_id=6992391225&action=cancel",
        "https://secure.booking.com/not-myreservations/manage?page=2",
        "https://secure.booking.com/confirmation-delete.html?trip_id=6992391225",
        f"{INVENTORY_ENTRY_URL}#cancel",
        "https://secure.booking.com/confirmation.html?trip_id=6992391225#payment",
    ],
)
def test_inventory_guard_rejects_mutating_or_lookalike_destinations(
    destination: str,
) -> None:
    guard = InventoryActionGuard()
    proposal = BrowserActionProposal(
        action=BrowserActionType.CLICK,
        current=DestinationSnapshot(INVENTORY_ENTRY_URL),
        label="Next page",
        role="link",
        destination=destination,
    )

    assert guard.evaluate(proposal).rejection is GuardRejection.INVALID_DESTINATION


@pytest.mark.parametrize(
    "destination",
    [
        "https://secure.booking.com/travel-plan?view=upcoming&layout=compact#upcoming",
        f"{INVENTORY_ENTRY_URL}?page=2&layout=compact#upcoming",
    ],
)
def test_inventory_guard_observes_benign_booking_destination_churn(
    destination: str,
) -> None:
    guard = InventoryActionGuard()

    assert guard.validate_destination(
        DestinationSnapshot("about:blank"),
        DestinationSnapshot(destination),
    ).allowed


def test_unknown_booking_page_is_observable_but_has_no_generic_action_authority() -> None:
    guard = InventoryActionGuard()
    unknown = DestinationSnapshot("https://secure.booking.com/travel-plan?layout=compact")
    proposal = BrowserActionProposal(
        action=BrowserActionType.SCROLL,
        current=unknown,
        delta_y=500,
    )

    assert guard.validate_destination(DestinationSnapshot("about:blank"), unknown).allowed
    assert guard.evaluate(proposal).rejection is GuardRejection.INVALID_DESTINATION


def test_generic_booking_funnel_is_observation_only() -> None:
    guard = InventoryActionGuard()
    funnel = DestinationSnapshot("https://secure.booking.com/booking.html")
    proposal = BrowserActionProposal(
        action=BrowserActionType.SCROLL,
        current=funnel,
        delta_y=500,
    )

    assert guard.validate_destination(DestinationSnapshot("about:blank"), funnel).allowed
    assert guard.evaluate(proposal).rejection is GuardRejection.INVALID_DESTINATION


def test_checkout_stay_date_query_is_not_a_mutation_signal() -> None:
    guard = InventoryActionGuard()
    destination = DestinationSnapshot(
        f"{INVENTORY_ENTRY_URL}?checkin=2026-11-24&checkout=2026-11-25&layout=compact"
    )

    assert guard.validate_destination(
        DestinationSnapshot("about:blank"),
        destination,
    ).allowed


@pytest.mark.parametrize(
    "destination",
    [
        "http://secure.booking.com/myreservations.html",
        "https://user:password@secure.booking.com/myreservations.html",
        "https://secure.booking.com:444/myreservations.html",
        "https://evil.example/myreservations.html",
        "https://secure.booking.com/sign-in",
        "https://secure.booking.com/two-factor",
        "https://secure.booking.com/captcha",
        "https://secure.booking.com/challenge",
        f"{INVENTORY_ENTRY_URL}?redirect=%2Fcheckout",
    ],
)
def test_inventory_guard_denies_sensitive_destination_families(
    destination: str,
) -> None:
    guard = InventoryActionGuard()

    assert not guard.validate_destination(
        DestinationSnapshot("about:blank"),
        DestinationSnapshot(destination),
    ).allowed


def test_inventory_guard_rejects_new_popup_on_otherwise_safe_destination() -> None:
    guard = InventoryActionGuard()

    decision = guard.validate_destination(
        DestinationSnapshot(INVENTORY_ENTRY_URL),
        DestinationSnapshot(INVENTORY_ENTRY_URL, popup_count=1),
    )

    assert decision.rejection is GuardRejection.UNEXPECTED_POPUP


def test_code_owned_navigation_tolerates_benign_booking_redirect() -> None:
    runtime = _Runtime(
        redirect_url=(
            "https://secure.booking.com/travel-plan"
            "?view=upcoming&layout=compact#upcoming"
        )
    )

    outcome, _ledger = _execute(runtime)

    assert outcome.result.status is InventoryExecutionStatus.OBSERVED
    assert outcome.validation.accepted_positive_count == 1


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        ("https://account.booking.com/sign-in", InventoryExecutionStatus.SIGNED_OUT),
        (
            f"{INVENTORY_ENTRY_URL}?redirect=%2Ftwo-factor",
            InventoryExecutionStatus.MFA_REQUIRED,
        ),
        ("https://secure.booking.com/captcha", InventoryExecutionStatus.CAPTCHA),
        ("https://secure.booking.com/challenge", InventoryExecutionStatus.BOT_WALL),
    ],
)
def test_code_owned_navigation_preserves_typed_sensitive_terminals(
    destination: str,
    expected: InventoryExecutionStatus,
) -> None:
    outcome, ledger = _execute(_Runtime(redirect_url=destination))

    assert outcome.result.status is expected
    assert ledger.reservations == []


def test_destination_diagnostic_is_useful_and_redacts_values(caplog) -> None:
    secret = "super-secret-cookie-value-0123456789"
    email = "dad@example.com"
    runtime = _Runtime(
        redirect_url=(
            f"https://evil.example/capture/{email}/{secret}"
            f"?session={secret}&email={email}#payment"
        )
    )

    with caplog.at_level("WARNING"):
        outcome, _ledger = _execute(runtime)

    message = caplog.text
    assert outcome.result.status is InventoryExecutionStatus.UNSAFE_ACTION
    assert "phase=entry_redirect" in message
    assert "category=external" in message
    assert "host_class=external" in message
    assert "query_keys=email,session" in message
    assert "fragment_present=True" in message
    assert secret not in message
    assert email not in message
    assert "evil.example" not in message


def test_inventory_computer_key_is_normalized_before_runtime_execution() -> None:
    runtime = _Runtime(no_action=True)
    model = _ComputerModel(
        [
            InventoryComputerTurn(
                InventoryComputerTurnKind.ACTION,
                ProviderUsage(LLMUsage(100, 20), 10),
                action=ComputerActionRequest(
                    BrowserActionType.KEY,
                    "tool-key",
                    value="PAGEDOWN",
                ),
            ),
            InventoryComputerTurn(
                InventoryComputerTurnKind.SUBMISSION,
                ProviderUsage(LLMUsage(100, 20), 10),
                observation=InventoryComputerObservation(
                    authenticated=True,
                    scopes=tuple(_scope_evidence(scope) for scope in InventoryScope),
                    reservations=(_reservation(),),
                    evidence_item_count=42,
                ),
            ),
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is InventoryExecutionStatus.OBSERVED
    assert len(runtime.visual_actions) == 1
    assert runtime.visual_actions[0].value == "PageDown"


_DOM_FIXTURES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "agentic_dom_resilience.json").read_text()
)


@pytest.mark.parametrize("fixture", _DOM_FIXTURES, ids=lambda item: item["id"])
def test_inventory_dom_resilience_corpus_requires_no_booksaver_selector_change(
    fixture: dict[str, object],
) -> None:
    usage = ProviderUsage(LLMUsage(100, 20), 10)
    if fixture["requires_visual"]:
        runtime = _Runtime(no_action=True)
        model = _ComputerModel(
            [
                InventoryComputerTurn(
                    InventoryComputerTurnKind.ACTION,
                    usage,
                    action=ComputerActionRequest(
                        BrowserActionType.WAIT,
                        f"{fixture['id']}-wait",
                        wait_ms=10,
                    ),
                ),
                InventoryComputerTurn(
                    InventoryComputerTurnKind.SUBMISSION,
                    usage,
                    observation=InventoryComputerObservation(
                        authenticated=True,
                        scopes=tuple(_scope_evidence(scope) for scope in InventoryScope),
                        reservations=(_reservation(),),
                        evidence_item_count=42,
                    ),
                ),
            ]
        )
    else:
        runtime = _Runtime(provider_selector=str(fixture["provider_selector"]))
        model = None

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is InventoryExecutionStatus.OBSERVED
    assert outcome.validation.accepted_positive_count == 1
    assert outcome.result.fallback_used is fixture["requires_visual"]
