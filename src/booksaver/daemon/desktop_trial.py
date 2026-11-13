"""Silent desktop price trial (intent 041, GitHub issue #7).

After a scheduled slot's normal checks, each checked booking's price is read once more in a
desktop browser profile and stored beside its mobile check.  Nothing here records history,
savings or alerts, counts as a check, or writes the saved session.  Delete with the trial.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from booksaver.application.browser_executor import (
    AgenticPriceExecutionService,
    InMemorySessionLeaseBroker,
    OwnerBoundAgenticPriceCheck,
)
from booksaver.application.ports import PriceBrowserExecutor
from booksaver.application.user_sessions import AuthenticatedSessionProvider
from booksaver.domain.browser_executor import ExecutionLimits
from booksaver.domain.check_result import CheckResult, FailureCode
from booksaver.domain.models import Booking
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteCheckHistoryRepository,
    SqliteStore,
)
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_check_job import BookingComSearchMonitor

logger = logging.getLogger(__name__)

READING_SECONDS = 120
# The session or the VPS address is in trouble: more page loads would only make it worse.
_STOP_CODES = frozenset({FailureCode.AUTH_REQUIRED, FailureCode.BOT_WALL})


def _stops(result: CheckResult) -> bool:
    return result.failure_reason is not None and result.failure_reason.code in _STOP_CODES


def run_desktop_trial(
    *,
    store: SqliteStore,
    executor_factory: Callable[[InMemorySessionLeaseBroker], PriceBrowserExecutor],
    sessions: AuthenticatedSessionProvider,
    user_id: int,
    checked: Sequence[tuple[Booking, CheckResult]],
    stop_event: threading.Event,
) -> None:
    """Store one desktop reading per checked booking; never raises into the slot."""
    try:
        # A blocked mobile check anywhere in the slot means no further page loads at all.
        if any(_stops(mobile) for _, mobile in checked):
            return
        history = SqliteCheckHistoryRepository(store)
        for booking, mobile in checked:
            if stop_event.is_set():
                return
            resolution = sessions.resolve(user_id)
            if not resolution.is_ready or resolution.snapshot is None:
                return
            leases = InMemorySessionLeaseBroker()
            # observe() uses neither the history nor the failure tracker; no trace repository.
            reading = BookingComSearchMonitor(
                check_history=history,
                failure_tracker=FailureTracker(history),
                agentic_price_check=OwnerBoundAgenticPriceCheck(
                    AgenticPriceExecutionService(executor_factory(leases), leases), leases
                ),
                agentic_owner_user_id=user_id,
                agentic_execution_limits=ExecutionLimits(
                    deadline=datetime.now(UTC) + timedelta(seconds=READING_SECONDS),
                    timeout_seconds=READING_SECONDS,
                ),
            ).observe(booking, resolution.snapshot)
            failure, price = reading.failure_reason, reading.live_price
            store.conn.execute(
                "INSERT OR REPLACE INTO desktop_trial_readings (check_id, user_id, booking_id, "
                "observed_at, outcome, failure_code, failure_detail, live_amount, live_currency, "
                "offer_room) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    mobile.check_id,
                    user_id,
                    booking.booking_id,
                    reading.checked_at.isoformat(),
                    reading.outcome.value,
                    failure.code.value if failure is not None else None,
                    failure.detail[:400] if failure is not None else None,
                    str(price.amount) if price is not None else None,
                    price.currency if price is not None else None,
                    reading.offer_room,
                ),
            )
            store.conn.commit()
            if _stops(reading):
                logger.warning(
                    "Desktop trial stopped for this slot user_id=%s reason=%s",
                    user_id,
                    failure.code.value if failure is not None else "",
                )
                return
    except Exception:
        logger.warning("Desktop trial reading failed user_id=%s", user_id, exc_info=True)
