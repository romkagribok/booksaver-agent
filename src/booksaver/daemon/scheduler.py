from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from booksaver.domain.value_objects import CheckInterval

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    name: str
    handler: Callable[[], None]


class Scheduler:
    def __init__(self) -> None:
        self._jobs: list[_Job] = []
        self._stop_event = threading.Event()
        self._running = False
        self.started_at: datetime | None = None
        self._last_tick_at: datetime | None = None
        self._interval: CheckInterval | None = None

    @property
    def stop_event(self) -> threading.Event:
        """Shared shutdown signal (ADR-006) — other daemon threads (e.g. the
        Telegram bot loop) watch this to shut down alongside the scheduler."""
        return self._stop_event

    @property
    def last_tick_at(self) -> datetime | None:
        return self._last_tick_at

    @property
    def next_run_at(self) -> datetime | None:
        """Best-effort estimate for `/status`: None until the first tick completes."""
        if self._last_tick_at is None or self._interval is None:
            return None
        return self._last_tick_at + self._interval.duration

    def register(self, name: str, handler: Callable[[], None]) -> None:
        if self._running:
            raise RuntimeError("Cannot register jobs after the scheduler loop has started")
        self._jobs.append(_Job(name=name, handler=handler))
        logger.debug("Registered job: %s", name)

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self, interval: CheckInterval) -> None:
        if not self._jobs:
            raise RuntimeError("No jobs registered — call register() before run()")
        self._running = True
        self.started_at = datetime.now(UTC)
        self._interval = interval
        interval_seconds = interval.duration.total_seconds()
        tick = 0
        logger.info("Scheduler started (interval=%s, jobs=%d)", interval, len(self._jobs))

        while not self._stop_event.is_set():
            tick += 1
            logger.info("Tick %d — running %d job(s)", tick, len(self._jobs))
            for job in self._jobs:
                try:
                    job.handler()
                    logger.info("Job '%s' completed (tick %d)", job.name, tick)
                except Exception as exc:
                    logger.error("Job '%s' failed (tick %d): %s", job.name, tick, exc)
            self._last_tick_at = datetime.now(UTC)

            # Wait for the interval or until stop is requested
            self._stop_event.wait(timeout=interval_seconds)

        logger.info("Scheduler stopped after %d tick(s)", tick)
