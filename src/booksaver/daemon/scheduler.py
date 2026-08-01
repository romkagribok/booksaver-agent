from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]
WakeHandler = Callable[[], datetime | None]
Waiter = Callable[[float], bool]

_DEFAULT_DISCOVERY_INTERVAL = timedelta(seconds=60)
_DEFAULT_MINIMUM_WAIT = timedelta(milliseconds=100)


@dataclass(frozen=True)
class _Job:
    name: str
    handler: WakeHandler


class Scheduler:
    """Run adaptive jobs with a prompt, interruptible discovery loop.

    Each job returns the next UTC instant at which it wants to be called. The
    loop still wakes at least once per discovery interval so newly created
    users or externally changed durable state are noticed without a restart.
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        waiter: Waiter | None = None,
        discovery_interval: timedelta = _DEFAULT_DISCOVERY_INTERVAL,
        minimum_wait: timedelta = _DEFAULT_MINIMUM_WAIT,
    ) -> None:
        if discovery_interval.total_seconds() <= 0:
            raise ValueError("discovery_interval must be positive")
        if discovery_interval > _DEFAULT_DISCOVERY_INTERVAL:
            raise ValueError("discovery_interval cannot exceed 60 seconds")
        if minimum_wait.total_seconds() <= 0:
            raise ValueError("minimum_wait must be positive")
        self._jobs: list[_Job] = []
        self._stop_event = threading.Event()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._waiter = waiter or self._stop_event.wait
        self._discovery_interval = discovery_interval
        self._minimum_wait = minimum_wait
        self._running = False
        self.started_at: datetime | None = None
        self._last_tick_at: datetime | None = None
        self._next_run_at: datetime | None = None

    @property
    def stop_event(self) -> threading.Event:
        """Shared shutdown signal watched by every daemon service."""
        return self._stop_event

    @property
    def last_tick_at(self) -> datetime | None:
        return self._last_tick_at

    @property
    def next_run_at(self) -> datetime | None:
        """Earliest job-requested wake, retained for operational diagnostics."""
        return self._next_run_at

    def register(self, name: str, handler: WakeHandler) -> None:
        if self._running:
            raise RuntimeError("Cannot register jobs after the scheduler loop has started")
        self._jobs.append(_Job(name=name, handler=handler))
        logger.debug("Registered job: %s", name)

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        if not self._jobs:
            raise RuntimeError("No jobs registered — call register() before run()")
        self._running = True
        self.started_at = self._utc_now()
        tick = 0
        logger.info(
            "Scheduler started (discovery_interval=%ss, jobs=%d)",
            self._discovery_interval.total_seconds(),
            len(self._jobs),
        )

        while not self._stop_event.is_set():
            tick += 1
            requested_wakes: list[datetime] = []
            logger.debug("Scheduler pass %d — running %d job(s)", tick, len(self._jobs))
            for job in self._jobs:
                if self._stop_event.is_set():
                    break
                try:
                    wake = job.handler()
                    if wake is not None:
                        requested_wakes.append(self._as_utc(wake))
                    logger.debug("Job '%s' completed (pass %d)", job.name, tick)
                except Exception:
                    logger.exception("Job '%s' failed (pass %d)", job.name, tick)

            now = self._utc_now()
            self._last_tick_at = now
            self._next_run_at = min(requested_wakes, default=None)
            if self._stop_event.is_set():
                break
            self._waiter(self._wait_seconds(now, self._next_run_at))

        logger.info("Scheduler stopped after %d pass(es)", tick)

    def _wait_seconds(self, now: datetime, requested_wake: datetime | None) -> float:
        timeout = self._discovery_interval
        if requested_wake is not None:
            until_requested = requested_wake - now
            timeout = min(timeout, max(until_requested, self._minimum_wait))
        return timeout.total_seconds()

    def _utc_now(self) -> datetime:
        return self._as_utc(self._clock())

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduler datetimes must be timezone-aware")
        return value.astimezone(UTC)
