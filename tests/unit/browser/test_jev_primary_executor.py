"""ADR-056: Jev as the authoritative price method — cap, ledger, and session refresh."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from tests.support.bookings import seed_booking
from tests.unit.browser.test_jev_price_executor import _request
from tests.unit.monitor.fakes import make_booking

from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.domain.browser_executor import (
    JEV_PRICE_POLICY_VERSION,
    ExecutionUsage,
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
    PriceExecutorKind,
)
from booksaver.domain.price_comparison import (
    JEV_ADAPTER_VERSION,
    CostCertainty,
    JevComparisonSettings,
    JevUsage,
)
from booksaver.domain.user import UserRole
from booksaver.infrastructure.browser.jev_primary_executor import JevPrimaryPriceExecutor
from booksaver.infrastructure.persistence.price_comparison import (
    JevPriceRun,
    SqliteJevPriceRunRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository

DIAGNOSTIC = "entry=property stage=done ready=0s end=rooms_found rooms=4 rates=16 priced=16"


class FakeJev:
    def __init__(self, status: PriceExecutionStatus = PriceExecutionStatus.TIMEOUT) -> None:
        self.status = status
        self.caps: list[int] = []
        self.requests: list[PriceExecutionRequest] = []
        self.last_usage = JevUsage()
        self.last_diagnostic = ""
        self.raises: BaseException | None = None

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        self.requests.append(request)
        self.last_usage = JevUsage(calls=21, input_tokens=23_587, cost_nano_usd=990_654)
        self.last_diagnostic = DIAGNOSTIC
        if self.raises is not None:
            raise self.raises
        return PriceExecutionResult(
            self.status, usage=ExecutionUsage(model_calls=21), latency_ms=31_000
        )


def _primary(
    tmp_path: Path, fake: FakeJev, *, cap_nano: int = 250_000_000, now: datetime | None = None
) -> JevPrimaryPriceExecutor:
    def factory(_broker: InMemorySessionLeaseBroker, cap: int) -> FakeJev:
        fake.caps.append(cap)
        return fake

    return JevPrimaryPriceExecutor(
        client=object(),  # type: ignore[arg-type]
        lease_broker=InMemorySessionLeaseBroker(),
        settings=JevComparisonSettings(max_daily_cost_nano_usd=cap_nano),
        db_path=tmp_path / "booksaver.db",
        executor_factory=factory,
        clock=lambda: now or datetime(2026, 10, 9, 12, 0, tzinfo=UTC),
    )


def _runs(tmp_path: Path) -> list[tuple[Any, ...]]:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        return [
            tuple(row)
            for row in store.conn.execute(
                "SELECT status, model_calls, cost_nano_usd, adapter, diagnostic, latency_ms "
                "FROM jev_price_runs ORDER BY created_at"
            )
        ]


def test_jev_is_a_selectable_price_executor_with_one_behavior_version() -> None:
    assert PriceExecutorKind.parse("jev") is PriceExecutorKind.JEV
    assert PriceExecutorKind.JEV.qualification_policy_version == JEV_PRICE_POLICY_VERSION
    assert JEV_PRICE_POLICY_VERSION == JEV_ADAPTER_VERSION
    with pytest.raises(ValueError, match="price_executor"):
        PriceExecutorKind.parse("claude")


def test_each_run_is_recorded_with_cost_and_diagnostic(tmp_path: Path) -> None:
    fake = FakeJev()
    result = _primary(tmp_path, fake).execute(_request())

    assert result.status is PriceExecutionStatus.TIMEOUT
    assert fake.caps == [250_000_000]
    assert _runs(tmp_path) == [("timeout", 21, 990_654, JEV_ADAPTER_VERSION, DIAGNOSTIC, 31_000)]


def test_daily_cap_counts_earlier_runs_and_then_refuses_without_running(tmp_path: Path) -> None:
    fake = FakeJev()
    primary = _primary(tmp_path, fake, cap_nano=1_500_000)
    primary.execute(_request())
    assert fake.caps == [1_500_000]
    primary.execute(_request())  # same execution id is replaced, spend still 990,654
    assert fake.caps[-1] == 1_500_000 - 990_654

    with SqliteStore(tmp_path / "booksaver.db") as store:
        SqliteJevPriceRunRepository(store).record(
            JevPriceRun(
                execution_id="earlier-today",
                user_id=1,
                booking_id="booking-1",
                created_at=datetime(2026, 10, 9, 1, 0, tzinfo=UTC),
                status="observed",
                usage=JevUsage(calls=5, cost_nano_usd=600_000),
                latency_ms=1,
                adapter=JEV_ADAPTER_VERSION,
            )
        )
    calls_before = len(fake.requests)
    refused = primary.execute(_request())
    assert refused.status is PriceExecutionStatus.BUDGET_EXHAUSTED
    assert len(fake.requests) == calls_before  # no browser, no provider call
    assert _runs(tmp_path)[-1][:3] == ("budget_exhausted", 0, 0)


def test_cap_resets_at_the_utc_day_boundary(tmp_path: Path) -> None:
    fake = FakeJev()
    _primary(tmp_path, fake, cap_nano=1_000_000).execute(_request())
    tomorrow = datetime(2026, 10, 10, 0, 5, tzinfo=UTC)
    _primary(tmp_path, fake, cap_nano=1_000_000, now=tomorrow).execute(_request())
    assert fake.caps == [1_000_000, 1_000_000]


def test_unreadable_ledger_fails_closed(tmp_path: Path) -> None:
    fake = FakeJev()
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("x")
    primary = JevPrimaryPriceExecutor(
        client=object(),  # type: ignore[arg-type]
        lease_broker=InMemorySessionLeaseBroker(),
        settings=JevComparisonSettings(),
        db_path=blocked / "booksaver.db",
        executor_factory=lambda _b, _c: fake,
    )
    assert primary.execute(_request()).status is PriceExecutionStatus.BUDGET_EXHAUSTED
    assert fake.requests == []


def test_a_raising_run_is_still_recorded_and_propagates(tmp_path: Path) -> None:
    fake = FakeJev()
    fake.raises = OSError("browser crashed")
    with pytest.raises(OSError):
        _primary(tmp_path, fake).execute(_request())
    [(status, calls, cost, *_rest)] = _runs(tmp_path)
    assert (status, calls, cost) == ("raised", 21, 990_654)


def test_purge_and_booking_removal_delete_run_records(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        user = users.get_or_create_by_telegram_id(404, UserRole.USER)
        booking = make_booking("00000004-1111-4111-8111-111111111111")
        seed_booking(store, booking, user_id=user.user_id)
        repository = SqliteJevPriceRunRepository(store)
        repository.record(
            JevPriceRun(
                execution_id="run-1",
                user_id=user.user_id,
                booking_id=booking.booking_id,
                created_at=datetime.now(UTC),
                status="no_valid_observation",
                usage=JevUsage(calls=6, cost_nano_usd=168_126, certainty=CostCertainty.EXACT),
                latency_ms=63_000,
                adapter=JEV_ADAPTER_VERSION,
                diagnostic="end=no_rooms_after_6_decisions(nosnap)",
            )
        )
        since = datetime.now(UTC) - timedelta(days=1)
        assert repository.summary(since) == (("no_valid_observation", 1, 168_126, 63.0),)
        [(_at, run_id, status, calls, seconds, detail)] = repository.unobserved(since)
        assert (run_id, status, calls, seconds) == ("run-1", "no_valid_observation", 6, 63.0)
        assert "no_rooms_after_6" in detail
        users.purge(user.user_id)
        assert store.conn.execute("SELECT COUNT(*) FROM jev_price_runs").fetchone()[0] == 0
