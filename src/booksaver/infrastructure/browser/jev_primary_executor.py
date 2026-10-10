"""Jev as the authoritative price method (ADR-056).

The provider-neutral port, validators, offer selection, history, savings, and alerts are
unchanged; this adapter only adds what the Anthropic ledger used to provide for the LLM method:
a daily spend cap, a durable per-run cost record, and the content-free run diagnostic.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.domain.browser_executor import (
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
)
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.price_comparison import (
    JEV_ADAPTER_VERSION,
    JevComparisonSettings,
    JevUsage,
)
from booksaver.infrastructure.browser.jev_price_executor import LocalJevPriceExecutor
from booksaver.infrastructure.llm.typesafe_client import TypeSafeClient
from booksaver.infrastructure.persistence.price_comparison import (
    JevPriceRun,
    SqliteJevPriceRunRepository,
    SqlitePriceComparisonRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore

logger = logging.getLogger(__name__)


class _JevExecutor(Protocol):
    last_usage: JevUsage
    last_diagnostic: str

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult: ...


JevExecutorFactory = Callable[[InMemorySessionLeaseBroker, int], _JevExecutor]


class JevPrimaryPriceExecutor:
    """Run one capped, recorded Jev price check that may refresh the owner's session."""

    def __init__(
        self,
        *,
        client: TypeSafeClient,
        lease_broker: InMemorySessionLeaseBroker,
        settings: JevComparisonSettings,
        db_path: Path,
        mobile_settings: MobileWebSettings | None = None,
        executor_factory: JevExecutorFactory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._leases = lease_broker
        self._settings = settings
        self._db_path = db_path
        self._clock = clock or (lambda: datetime.now(UTC))
        self._executor_factory: JevExecutorFactory = executor_factory or (
            lambda broker, cap: LocalJevPriceExecutor(
                client=client,
                lease_broker=broker,
                max_calls=settings.max_calls_per_arm,
                max_cost_nano_usd=cap,
                mobile_settings=mobile_settings,
                allow_session_refresh=True,
            )
        )

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        now = self._clock()
        started = time.monotonic()
        remaining = self._remaining_daily_nano_usd(now)
        if remaining <= 0:
            logger.warning(
                "Jev price run refused execution_id=%s reason=daily_cost_limit",
                request.execution_id,
            )
            result = PriceExecutionResult(PriceExecutionStatus.BUDGET_EXHAUSTED)
            self._record(request, now, result, JevUsage(), "refused=daily_cost_limit", 0)
            return result
        executor = self._executor_factory(self._leases, remaining)
        try:
            result = executor.execute(request)
        except BaseException:
            self._record(
                request,
                now,
                None,
                executor.last_usage,
                executor.last_diagnostic,
                round((time.monotonic() - started) * 1_000),
            )
            raise
        self._record(
            request, now, result, executor.last_usage, executor.last_diagnostic, result.latency_ms
        )
        return result

    def _remaining_daily_nano_usd(self, now: datetime) -> int:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            with SqliteStore(self._db_path) as store:
                spent = SqliteJevPriceRunRepository(store).cost_since(
                    day_start
                ) + SqlitePriceComparisonRepository(store).jev_cost_since(day_start)
        except Exception:
            # Without a readable ledger the cap cannot be proven; fail closed.
            logger.warning("Jev spend ledger unavailable; refusing the run", exc_info=True)
            return 0
        return self._settings.max_daily_cost_nano_usd - spent

    def _record(
        self,
        request: PriceExecutionRequest,
        now: datetime,
        result: PriceExecutionResult | None,
        usage: JevUsage,
        diagnostic: str,
        latency_ms: int,
    ) -> None:
        try:
            with SqliteStore(self._db_path) as store:
                SqliteJevPriceRunRepository(store).record(
                    JevPriceRun(
                        execution_id=request.execution_id,
                        user_id=request.owner_user_id,
                        booking_id=request.booking_id,
                        created_at=now,
                        status=result.status.value if result is not None else "raised",
                        usage=usage,
                        latency_ms=latency_ms,
                        adapter=JEV_ADAPTER_VERSION,
                        diagnostic=diagnostic,
                    )
                )
        except Exception:
            # The canonical check result must not depend on this operator record.
            logger.warning("Could not record the Jev price run", exc_info=True)
