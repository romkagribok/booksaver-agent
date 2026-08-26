from __future__ import annotations

import json
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
    StagehandInventoryBrowserExecutor,
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
        self.url = self.redirect_url or url

    async def destination(self) -> DestinationSnapshot:
        return DestinationSnapshot(self.url)

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
    computer_model: _ComputerModel | None = None,
):
    ledger = _Ledger()
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


@pytest.mark.parametrize(
    "destination",
    [
        f"{INVENTORY_ENTRY_URL}?page=2&action=cancel",
        "https://secure.booking.com/confirmation.html?trip_id=6992391225&action=cancel",
        "https://secure.booking.com/not-myreservations/manage?page=2",
        "https://secure.booking.com/confirmation-delete.html?trip_id=6992391225",
        f"{INVENTORY_ENTRY_URL}#cancel",
        f"{INVENTORY_ENTRY_URL}#upcoming",
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
