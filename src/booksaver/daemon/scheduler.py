from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

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

            # Wait for the interval or until stop is requested
            self._stop_event.wait(timeout=interval_seconds)

        logger.info("Scheduler stopped after %d tick(s)", tick)
