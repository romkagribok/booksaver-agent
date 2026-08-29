from __future__ import annotations

import asyncio
import importlib.metadata
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.browser_executor import (
    AgenticPriceExecutionService,
    InMemorySessionLeaseBroker,
)
from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.domain.agent import LLMUsage
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionLimits,
    ExecutorSafetyViolation,
    ObservationSource,
    ObservedOffer,
    ObservedQueryFacts,
    PriceExecutionRequest,
    PriceExecutionStatus,
    RefundabilityEvidence,
    TrustedPriceQuery,
)
from booksaver.domain.browser_guard import (
    BrowserActionType,
    CoordinateHitTest,
    DestinationSnapshot,
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
from booksaver.domain.value_objects import Money, Occupancy, StayDates
from booksaver.infrastructure.browser.agentic_executor import (
    BrowserNavigationFailure,
    BrowserNavigationFailureKind,
    CodeOwnedSessionBootstrap,
    ComputerActionRequest,
    ComputerTurn,
    ComputerTurnKind,
    InspectedElement,
    LocalStagehandRuntime,
    ProviderUsage,
    SemanticAction,
    SemanticObservationResult,
    StagehandPriceBrowserExecutor,
    TypedObservation,
    _classify_navigation_failure,
    _parse_computer_action,
    build_trusted_search_url,
)
from booksaver.infrastructure.browser.agentic_executor import (
    _computer_tools as _price_computer_tools,
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
        job_id="agentic-job-1",
        job_kind=BrowserJobKind.CHECK_NOW,
        caller_key_ref=CallerKeyRef(7, "owner", "deployment_key"),
        ledger=ledger,
        estimator=ModelCostEstimator(),
        preserve_opus_diagnostic=False,
    )


def _query() -> TrustedPriceQuery:
    return TrustedPriceQuery(
        property_name="Hotel Example",
        property_reference="hotel-example-ref",
        stay_dates=StayDates(date(2026, 10, 1), date(2026, 10, 4)),
        occupancy=Occupancy(2, 1, 1),
        currency="EUR",
    )


def _observation() -> TypedObservation:
    query = _query()
    return TypedObservation(
        facts=ObservedQueryFacts(
            property_name=query.property_name,
            property_reference=query.property_reference,
            check_in=query.stay_dates.check_in,
            check_out=query.stay_dates.check_out,
            occupancy=query.occupancy,
            currency=query.currency,
            authenticated=True,
            genius=True,
            completeness=EvidenceCompleteness.COMPLETE,
        ),
        offers=(
            ObservedOffer(
                room_label="Deluxe King Room",
                total=Money(Decimal("300"), "EUR"),
                all_in=AllInEvidence.EXPLICIT,
                refundability=RefundabilityEvidence.EXPLICIT_REFUNDABLE,
                refundability_text="Free cancellation until 30 September",
                completeness=EvidenceCompleteness.COMPLETE,
            ),
        ),
        evidence_item_count=15,
    )


@dataclass
class _Runtime:
    observation: TypedObservation = _observation()
    observe_action: SemanticAction | None = SemanticAction(
        "Open Hotel Example details",
        "click",
        "a.hotel-example",
        object(),
    )
    inspected: InspectedElement | None = InspectedElement(
        "Hotel Example",
        "link",
        "https://www.booking.com/hotel/example.html",
        True,
        True,
    )
    hit: CoordinateHitTest | None = CoordinateHitTest(
        20,
        30,
        1280,
        800,
        label="See room details",
        role="button",
    )
    focused: InspectedElement | None = InspectedElement(
        "Destination",
        "searchbox",
        None,
        True,
        True,
    )
    url: str = "https://www.booking.com/searchresults.html"
    restored: bytes | None = None
    launched: bool = False
    attached: bool = False
    closed: bool = False
    replayed: int = 0
    visual_actions: int = 0
    refreshed: bytes | None = (
        b'[{"name":"session","value":"refreshed","domain":".booking.com","path":"/"}]'
    )
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
        assert url.startswith("https://www.booking.com/searchresults.html?")
        if self.navigation_failure is not None:
            raise BrowserNavigationFailure(self.navigation_failure)
        self.url = url

    async def destination(self) -> DestinationSnapshot:
        return DestinationSnapshot(self.url)

    async def viewport_size(self) -> tuple[int, int]:
        return (412, 839)

    async def observe_property(self, _property_name: str):
        return self.observe_action, ProviderUsage(LLMUsage(100, 20), 10)

    async def inspect(self, _action: SemanticAction):
        return self.inspected

    async def replay(self, _action: SemanticAction) -> None:
        self.replayed += 1
        self.url = "https://www.booking.com/hotel/example.html"

    async def extract(self) -> SemanticObservationResult:
        return SemanticObservationResult(
            self.observation,
            ProviderUsage(LLMUsage(200, 40), 20),
        )

    async def screenshot(self) -> bytes:
        return b"png"

    async def hit_test(self, _x: int, _y: int):
        return self.hit

    async def focused_element(self):
        return self.focused

    async def execute_action(self, _action: ComputerActionRequest) -> None:
        self.visual_actions += 1

    async def verified_session_refresh(self) -> bytes | None:
        return self.refreshed

    async def close(self) -> None:
        self.closed = True


class _ComputerModel:
    def __init__(self, turns: list[ComputerTurn]) -> None:
        self.turns = turns
        self.prior_ids: list[str | None] = []

    def next_turn(self, *, screenshot, request, prior_tool_use_id):
        assert screenshot == b"png"
        assert request.query == _query()
        self.prior_ids.append(prior_tool_use_id)
        return self.turns.pop(0)


def _request(broker: InMemorySessionLeaseBroker) -> PriceExecutionRequest:
    execution_id = "execution-1"
    lease = broker.issue(
        owner_user_id=7,
        booking_id="booking-1",
        execution_id=execution_id,
        session_material=b'[{"name":"session","value":"secret","domain":".booking.com","path":"/"}]',
    )
    return PriceExecutionRequest(
        execution_id=execution_id,
        owner_user_id=7,
        booking_id="booking-1",
        query=_query(),
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
        executor = StagehandPriceBrowserExecutor(
            api_key="test-key",
            lease_broker=broker,
            budget=_budget(ledger),
            runner=runner,
            runtime_factory=lambda: runtime,
            computer_model_factory=(
                (lambda: computer_model) if computer_model is not None else None
            ),
        )
        outcome = AgenticPriceExecutionService(executor, broker).execute(request)
    return outcome, ledger


def test_semantic_observation_uses_guarded_replay_and_typed_output() -> None:
    runtime = _Runtime()
    outcome, ledger = _execute(runtime)

    assert outcome.result.status is PriceExecutionStatus.OBSERVED
    assert outcome.result.provenance is not None
    assert outcome.result.provenance.source is ObservationSource.STAGEHAND_EXTRACT
    assert not outcome.result.fallback_used
    assert outcome.validation.accepted
    assert outcome.result.refreshed_session_eligible
    assert outcome.refreshed_session == runtime.refreshed
    assert runtime.replayed == 1
    assert runtime.restored is not None and b"secret" in runtime.restored
    assert runtime.closed
    assert len(ledger.reservations) == 2
    assert len(ledger.reconciliations) == 2


def test_model_authentication_claim_cannot_replace_code_owned_server_proof() -> None:
    outcome, _ledger = _execute(_Runtime(refreshed=None))

    assert outcome.result.status is PriceExecutionStatus.SESSION_UNAVAILABLE
    assert not outcome.validation.accepted
    assert outcome.refreshed_session is None


def test_semantic_failure_hands_same_browser_to_guarded_computer_use() -> None:
    runtime = _Runtime(observe_action=None)
    action_usage = ProviderUsage(LLMUsage(100, 20), 10)
    model = _ComputerModel(
        [
            ComputerTurn(
                ComputerTurnKind.ACTION,
                action_usage,
                action=ComputerActionRequest(
                    BrowserActionType.CLICK,
                    "tool-1",
                    x=20,
                    y=30,
                ),
            ),
            ComputerTurn(
                ComputerTurnKind.SUBMISSION,
                action_usage,
                observation=_observation(),
            ),
        ]
    )
    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is PriceExecutionStatus.OBSERVED
    assert outcome.result.fallback_used
    assert outcome.result.usage.computer_use_actions == 1
    assert outcome.result.provenance is not None
    assert outcome.result.provenance.source is ObservationSource.COMPUTER_USE_SUBMISSION
    assert runtime.visual_actions == 1
    assert model.prior_ids == [None, "tool-1"]


@pytest.mark.parametrize(
    "runtime",
    [
        _Runtime(
            observe_action=SemanticAction(
                "Scroll to Hotel Example",
                "scroll",
                "body",
                object(),
            )
        ),
        _Runtime(inspected=None),
    ],
    ids=("unsupported-semantic-method", "uninspectable-semantic-target"),
)
def test_rejected_semantic_proposal_uses_guarded_visual_fallback(
    runtime: _Runtime,
) -> None:
    model = _ComputerModel(
        [
            ComputerTurn(
                ComputerTurnKind.SUBMISSION,
                ProviderUsage(LLMUsage(100, 20), 10),
                observation=_observation(),
            )
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is PriceExecutionStatus.OBSERVED
    assert outcome.result.fallback_used
    assert runtime.replayed == 0
    assert runtime.visual_actions == 0


def test_unsafe_computer_click_is_terminal_and_never_executed() -> None:
    runtime = _Runtime(
        observe_action=None,
        hit=CoordinateHitTest(
            20,
            30,
            1280,
            800,
            label="Reserve now",
            role="button",
        ),
    )
    model = _ComputerModel(
        [
            ComputerTurn(
                ComputerTurnKind.ACTION,
                ProviderUsage(LLMUsage(100, 20), 10),
                action=ComputerActionRequest(
                    BrowserActionType.CLICK,
                    "tool-unsafe",
                    x=20,
                    y=30,
                ),
            )
        ]
    )
    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is PriceExecutionStatus.UNSAFE_ACTION
    assert runtime.visual_actions == 0
    assert not outcome.result.safety_violations


def test_executed_non_allowlisted_destination_is_a_critical_redacted_violation() -> None:
    class EscapingRuntime(_Runtime):
        async def replay(self, _action: SemanticAction) -> None:
            self.replayed += 1
            self.url = "https://attacker.example/capture"

    outcome, _ledger = _execute(EscapingRuntime())

    assert outcome.result.status is PriceExecutionStatus.UNSAFE_ACTION
    assert outcome.result.safety_violations == frozenset(
        {
            ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED,
            ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION,
        }
    )


def test_code_owned_cookie_bootstrap_is_content_safe_and_domain_scoped() -> None:
    bootstrap = CodeOwnedSessionBootstrap()
    bootstrap.restore_session(b'[{"name":"s","value":"secret","domain":".booking.com"}]')
    assert "secret" not in repr(bootstrap)

    invalid = CodeOwnedSessionBootstrap()
    invalid.restore_session(b'[{"name":"s","value":"secret","domain":"evil.example"}]')
    with pytest.raises(ValueError, match="outside Booking.com"):
        invalid._decode_cookies(  # noqa: SLF001 - direct pure validation fixture
            b'[{"name":"s","value":"secret","domain":"evil.example"}]'
        )


def test_trusted_search_url_contains_only_code_owned_query() -> None:
    broker = InMemorySessionLeaseBroker()
    url = build_trusted_search_url(_request(broker))
    assert "Hotel+Example" in url
    assert "checkin=2026-10-01" in url
    assert "group_adults=2" in url
    assert "selected_currency=EUR" in url


def test_stagehand_is_exactly_pinned() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    assert '"stagehand==4.0.1"' in pyproject.read_text()
    assert importlib.metadata.version("stagehand") == "4.0.1"


def test_local_stagehand_launch_explicitly_uses_container_compatible_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from playwright import async_api
    from stagehand import local_browser

    launch_arguments: dict[str, object] = {}

    class FakePlaywright:
        class Chromium:
            executable_path = "/opt/playwright-browsers/chromium/chrome"

        chromium = Chromium()
        devices = {
            "Pixel 7": {
                "user_agent": "Mozilla/5.0 Android Mobile test-agent",
                "viewport": {"width": 412, "height": 839},
                "device_scale_factor": 2.625,
                "is_mobile": True,
                "has_touch": True,
            }
        }
        stopped = False

        async def stop(self) -> None:
            self.stopped = True

    class FakePlaywrightStarter:
        async def start(self) -> FakePlaywright:
            return fake_playwright

    class FakeBrowser:
        closed = False

        async def close(self) -> None:
            self.closed = True

    fake_playwright = FakePlaywright()
    fake_browser = FakeBrowser()

    def fake_async_playwright() -> FakePlaywrightStarter:
        return FakePlaywrightStarter()

    async def fake_launch(**kwargs: object) -> FakeBrowser:
        launch_arguments.update(kwargs)
        return fake_browser

    monkeypatch.setattr(async_api, "async_playwright", fake_async_playwright)
    monkeypatch.setattr(local_browser, "launch", fake_launch)

    async def exercise() -> None:
        runtime = LocalStagehandRuntime()
        await runtime.launch()
        assert launch_arguments["chromium_sandbox"] is False
        assert launch_arguments["executable_path"] == fake_playwright.chromium.executable_path
        assert launch_arguments["headless"] is True
        assert launch_arguments["keep_alive"] is False
        assert launch_arguments["args"] == [
            "--user-agent=Mozilla/5.0 Android Mobile test-agent"
        ]
        assert launch_arguments["viewport_width"] == 412
        assert launch_arguments["viewport_height"] == 839
        assert launch_arguments["device_scale_factor"] == 2.625
        assert launch_arguments["has_touch"] is True
        assert launch_arguments["locale"] == "en-US"
        assert await runtime.viewport_size() == (412, 839)
        assert fake_playwright.stopped
        await runtime.close()
        assert fake_browser.closed

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ("net::ERR_TOO_MANY_REDIRECTS", BrowserNavigationFailureKind.REDIRECT_LOOP),
        ("net::ERR_TIMED_OUT", BrowserNavigationFailureKind.TIMEOUT),
        ("net::ERR_CONNECTION_RESET", BrowserNavigationFailureKind.CONNECTION),
        ("net::ERR_CERT_AUTHORITY_INVALID", BrowserNavigationFailureKind.CERTIFICATE),
        ("net::ERR_FAILED", BrowserNavigationFailureKind.TRANSPORT),
        ("provider wrapper stopped", BrowserNavigationFailureKind.UNKNOWN),
    ],
)
def test_navigation_failure_classifier_retains_only_closed_categories(
    detail: str,
    expected: BrowserNavigationFailureKind,
) -> None:
    assert _classify_navigation_failure(detail) is expected


def test_price_computer_tool_uses_launched_mobile_viewport() -> None:
    computer = next(
        tool for tool in _price_computer_tools(412, 839) if tool.get("name") == "computer"
    )

    assert computer["display_width_px"] == 412
    assert computer["display_height_px"] == 839


def test_price_navigation_failure_stops_before_model_cost() -> None:
    outcome, ledger = _execute(
        _Runtime(navigation_failure=BrowserNavigationFailureKind.CONNECTION)
    )

    assert outcome.result.status is PriceExecutionStatus.PROVIDER_FAILURE
    assert outcome.result.usage.total_actions == 1
    assert outcome.result.usage.model_calls == 0
    assert ledger.reservations == []


def test_computer_type_requires_exact_trusted_query_value_and_focused_input() -> None:
    runtime = _Runtime(observe_action=None)
    usage = ProviderUsage(LLMUsage(100, 20), 10)
    model = _ComputerModel(
        [
            ComputerTurn(
                ComputerTurnKind.ACTION,
                usage,
                action=ComputerActionRequest(
                    BrowserActionType.TYPE,
                    "tool-type",
                    value="Hotel Example",
                ),
            ),
            ComputerTurn(
                ComputerTurnKind.SUBMISSION,
                usage,
                observation=_observation(),
            ),
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is PriceExecutionStatus.OBSERVED
    assert runtime.visual_actions == 1


def test_computer_type_rejects_model_invented_input() -> None:
    runtime = _Runtime(observe_action=None)
    model = _ComputerModel(
        [
            ComputerTurn(
                ComputerTurnKind.ACTION,
                ProviderUsage(LLMUsage(100, 20), 10),
                action=ComputerActionRequest(
                    BrowserActionType.TYPE,
                    "tool-type",
                    value="model invented text",
                ),
            )
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is PriceExecutionStatus.UNSAFE_ACTION
    assert runtime.visual_actions == 0


def test_current_computer_tool_wait_scroll_and_zoom_fields_are_normalized() -> None:
    wait = _parse_computer_action("wait-1", {"action": "wait", "duration": 1.5})
    scroll = _parse_computer_action(
        "scroll-1",
        {"action": "scroll", "scroll_direction": "down", "scroll_amount": 4},
    )
    zoom = _parse_computer_action(
        "zoom-1",
        {"action": "zoom", "region": [100, 100, 500, 400]},
    )

    assert wait.wait_ms == 1_500
    assert scroll.delta_y == 400
    assert zoom.zoom_region == (100, 100, 500, 400)


def test_provider_failure_is_conservatively_included_in_result_cost() -> None:
    class FailingObserveRuntime(_Runtime):
        async def observe_property(self, _property_name: str):
            raise RuntimeError("provider unavailable")

    runtime = FailingObserveRuntime()
    model = _ComputerModel(
        [
            ComputerTurn(
                ComputerTurnKind.TERMINAL,
                ProviderUsage(LLMUsage(100, 20), 10),
                terminal_status=PriceExecutionStatus.PROVIDER_FAILURE,
            )
        ]
    )

    outcome, ledger = _execute(runtime, model)

    charged = sum(item.charged_cost.micro_usd for item in ledger.reconciliations)
    assert outcome.result.usage.model_calls == 2
    assert outcome.result.usage.cost.micro_usd == charged


def test_provider_exception_content_is_never_exported_to_logs(caplog) -> None:
    class UnsafeMessageRuntime(_Runtime):
        async def attach(self, _api_key: str) -> None:
            raise ValueError("ephemeral-secret visible page text")

    outcome, _ledger = _execute(UnsafeMessageRuntime())

    assert outcome.result.status is PriceExecutionStatus.PROVIDER_FAILURE
    assert "ephemeral-secret" not in caplog.text
    assert "visible page text" not in caplog.text
    assert "failure_type=ValueError" in caplog.text


def test_timeout_preserves_usage_incurred_before_cancellation() -> None:
    class SlowExtractRuntime(_Runtime):
        async def extract(self) -> SemanticObservationResult:
            await asyncio.sleep(0.1)
            return await super().extract()

    ledger = _Ledger()
    broker = InMemorySessionLeaseBroker()
    request = _request(broker)
    request = PriceExecutionRequest(
        execution_id=request.execution_id,
        owner_user_id=request.owner_user_id,
        booking_id=request.booking_id,
        query=request.query,
        session_lease=request.session_lease,
        limits=ExecutionLimits(
            deadline=datetime.now(UTC) + timedelta(milliseconds=20),
            timeout_seconds=1,
        ),
    )
    with AsyncLoopRunner() as runner:
        executor = StagehandPriceBrowserExecutor(
            api_key="test-key",
            lease_broker=broker,
            budget=_budget(ledger),
            runner=runner,
            runtime_factory=SlowExtractRuntime,
        )
        outcome = AgenticPriceExecutionService(executor, broker).execute(request)

    assert outcome.result.status is PriceExecutionStatus.TIMEOUT
    assert outcome.result.usage.model_calls == 2
    assert outcome.result.usage.cost.micro_usd > 0
    assert ledger.reconciliations[-1].conservative


_DOM_FIXTURES = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures"
        / "agentic_dom_resilience.json"
    ).read_text()
)


@pytest.mark.parametrize("fixture", _DOM_FIXTURES, ids=lambda item: item["id"])
def test_dom_resilience_corpus_requires_no_booksaver_selector_change(fixture) -> None:
    usage = ProviderUsage(LLMUsage(100, 20), 10)
    if fixture["requires_visual"]:
        runtime = _Runtime(observe_action=None)
        model = _ComputerModel(
            [
                ComputerTurn(
                    ComputerTurnKind.ACTION,
                    usage,
                    action=ComputerActionRequest(
                        BrowserActionType.WAIT,
                        f"{fixture['id']}-wait",
                        wait_ms=10,
                    ),
                ),
                ComputerTurn(
                    ComputerTurnKind.SUBMISSION,
                    usage,
                    observation=_observation(),
                ),
            ]
        )
    else:
        runtime = _Runtime(
            observe_action=SemanticAction(
                "Open exact visible Hotel Example result",
                "click",
                fixture["provider_selector"],
                object(),
            )
        )
        model = None

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is PriceExecutionStatus.OBSERVED
    assert outcome.validation.accepted
    assert outcome.result.fallback_used is fixture["requires_visual"]


@pytest.mark.parametrize(
    "status",
    [
        PriceExecutionStatus.SIGNED_OUT,
        PriceExecutionStatus.MFA_REQUIRED,
        PriceExecutionStatus.CAPTCHA,
        PriceExecutionStatus.BOT_WALL,
        PriceExecutionStatus.UNAVAILABLE,
        PriceExecutionStatus.NO_VALID_OBSERVATION,
        PriceExecutionStatus.PROVIDER_FAILURE,
    ],
)
def test_closed_visual_terminal_outcomes_remain_typed(status) -> None:
    runtime = _Runtime(observe_action=None)
    model = _ComputerModel(
        [
            ComputerTurn(
                ComputerTurnKind.TERMINAL,
                ProviderUsage(LLMUsage(100, 20), 10),
                terminal_status=status,
            )
        ]
    )

    outcome, _ledger = _execute(runtime, model)

    assert outcome.result.status is status
    assert not outcome.validation.accepted


def test_sixth_computer_action_may_be_followed_by_typed_submission() -> None:
    runtime = _Runtime(observe_action=None)
    usage = ProviderUsage(LLMUsage(10, 5), 1)
    turns = [
        ComputerTurn(
            ComputerTurnKind.ACTION,
            usage,
            action=ComputerActionRequest(
                BrowserActionType.WAIT,
                f"tool-{index}",
                wait_ms=1,
            ),
        )
        for index in range(6)
    ]
    turns.append(
        ComputerTurn(
            ComputerTurnKind.SUBMISSION,
            usage,
            observation=_observation(),
        )
    )

    outcome, _ledger = _execute(runtime, _ComputerModel(turns))

    assert outcome.result.status is PriceExecutionStatus.OBSERVED
    assert outcome.result.usage.computer_use_actions == 6
    assert runtime.visual_actions == 6
