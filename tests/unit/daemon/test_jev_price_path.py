from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionUsage,
    ObservationSource,
    ObservedOffer,
    ObservedQueryFacts,
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
    RedactedProvenance,
    RefundabilityEvidence,
)
from booksaver.domain.check_result import CheckResult
from booksaver.domain.model_policy import UsdAmount
from booksaver.domain.price_comparison import CostCertainty, JevUsage
from booksaver.domain.value_objects import Money
from booksaver.infrastructure.persistence.price_comparison import (
    JevPriceRun,
    SqliteJevPriceRunRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteCheckHistoryRepository,
    SqliteStore,
    SqliteUserRepository,
)
from tests.support.bookings import seed_booking
from tests.unit.daemon.test_check_coordinator import (
    BrowserContext,
    _build_coordinator,
    _complete_sync,
    _config,
    _seed_session,
    _session_repo,
)
from tests.unit.monitor.fakes import make_booking


class FakeJevExecutor:
    def __init__(self, broker: InMemorySessionLeaseBroker, total: str = "380.00") -> None:
        self.broker = broker
        self.total = total
        self.requests: list[PriceExecutionRequest] = []
        self.restored: list[bytes] = []
        self.last_usage = JevUsage()

    def restore_session(self, data: bytes) -> None:
        self.restored.append(data)

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        self.requests.append(request)
        self.broker.restore_into(request.session_lease, self)
        self.last_usage = JevUsage(calls=4, input_tokens=2_000, cost_nano_usd=84_000)
        query = request.query
        return PriceExecutionResult(
            PriceExecutionStatus.OBSERVED,
            query_facts=ObservedQueryFacts(
                property_name=query.property_name,
                property_reference=query.property_reference,
                check_in=query.stay_dates.check_in,
                check_out=query.stay_dates.check_out,
                occupancy=query.occupancy,
                currency=query.currency,
                authenticated=True,
                genius=None,
                completeness=EvidenceCompleteness.COMPLETE,
            ),
            offers=(
                ObservedOffer(
                    room_label="Standard Double",
                    total=Money(Decimal(self.total), query.currency),
                    all_in=AllInEvidence.EXPLICIT,
                    refundability=RefundabilityEvidence.EXPLICIT_REFUNDABLE,
                    refundability_text="Free cancellation",
                    completeness=EvidenceCompleteness.COMPLETE,
                ),
            ),
            provenance=RedactedProvenance(ObservationSource.JEV_PRICE_SUBMISSION, 1, 15),
            usage=ExecutionUsage(model_calls=4, total_actions=1, cost=UsdAmount(84)),
        )



def _run(tmp_path: Path, coordinator: Any, user: Any, booking: Any) -> CheckResult:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        result: CheckResult = coordinator._run_booking(store, object(), user.user_id, booking)
    return result



def test_jev_as_the_only_price_method_owns_every_canonical_effect(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """ADR-056: with price_executor = "jev" the real monitor path treats Jev as authority."""
    from booksaver.domain.browser_executor import (
        JEV_PRICE_POLICY_VERSION,
        AgenticBrowserSettings,
        PriceExecutorKind,
    )

    refreshed = b'[{"name":"bkng","value":"fresh","domain":".booking.com","path":"/"}]'
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        assert owner is not None
        booking = make_booking("00000005-1111-4111-8111-111111111111")
        seed_booking(store, booking, user_id=owner.user_id)
    sessions = _session_repo(tmp_path)
    _seed_session(sessions, owner.user_id)
    pipeline: list[list[CheckResult]] = []
    monkeypatch.setattr(
        "booksaver.daemon.check_coordinator.SavingsPipeline.process",
        lambda _self, results: pipeline.append(results),
    )

    class RefreshingJev(FakeJevExecutor):
        def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
            result = super().execute(request)
            self.broker.store_verified_refresh(request.session_lease, refreshed)
            return replace(result, refreshed_session_eligible=True)

    executors: list[RefreshingJev] = []

    def factory(broker: InMemorySessionLeaseBroker) -> RefreshingJev:
        executors.append(RefreshingJev(broker))
        return executors[-1]

    config = replace(
        _config(tmp_path),
        agentic_browser_settings=AgenticBrowserSettings(price_executor=PriceExecutorKind.JEV),
    )
    coordinator = _build_coordinator(
        config,
        browser_factory=BrowserContext,
        inventory_synchronizer=_complete_sync,
        session_repository=sessions,
        agentic_executor_factory=factory,
    )

    result = _run(tmp_path, coordinator, owner, booking)

    assert result.live_price == Money(Decimal("380.00"), "EUR")
    assert len(executors) == 1 and executors[0].restored == [b"[]"]
    assert pipeline == [[result]]  # Jev's validated result now feeds savings alerts
    assert sessions.resolve(owner.user_id).snapshot.cookies == refreshed
    with SqliteStore(tmp_path / "booksaver.db") as store:
        history = SqliteCheckHistoryRepository(store).get_recent(booking.booking_id)
        canary = store.conn.execute(
            "SELECT policy_version, valid_observation FROM agentic_canary_checks"
        ).fetchall()
    assert [row.live_price for row in history] == [result.live_price]
    assert [tuple(row) for row in canary] == [(JEV_PRICE_POLICY_VERSION, 1)]


def test_cli_report_lists_unobserved_jev_runs_with_their_diagnostic(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    import argparse

    from booksaver.cli import commands

    with SqliteStore(tmp_path / "booksaver.db") as store:
        SqliteJevPriceRunRepository(store).record(
            JevPriceRun(
                execution_id="exec-feedbeef",
                user_id=1,
                booking_id="booking-1",
                created_at=datetime.now(UTC),
                status="extraction_failed",
                usage=JevUsage(
                    calls=6, cost_nano_usd=168_126, certainty=CostCertainty.EXACT
                ),
                latency_ms=42_000,
                adapter="jev-price-v3",
                diagnostic="entry=property end=no_rooms_after_6_decisions(nosnap)",
            )
        )
    monkeypatch.setattr(commands, "_db_path_for", lambda _args: (None, tmp_path / "booksaver.db"))
    assert commands.cmd_comparison_report(argparse.Namespace(days=7)) == 0
    output = capsys.readouterr().out
    assert "Jev-only price runs since" in output
    assert "Runs that produced no observation" in output
    assert "feedbeef  extraction_failed  6 calls  42s" in output
    assert "end=no_rooms_after_6_decisions(nosnap)" in output
    assert "Paired" not in output
