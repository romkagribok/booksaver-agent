from __future__ import annotations

import threading
from datetime import timedelta

import pytest

from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.value_objects import CheckInterval

# Bypass the 15m minimum for tests — we need sub-second ticks to keep the suite fast.
_FAST = CheckInterval.__new__(CheckInterval)
object.__setattr__(_FAST, "duration", timedelta(seconds=1))


def test_register_adds_job() -> None:
    sched = Scheduler()
    called: list[str] = []
    sched.register("job_a", lambda: called.append("a"))
    # register doesn't call the handler
    assert called == []


def test_register_after_run_started_raises() -> None:
    sched = Scheduler()
    sched.register("job_a", lambda: None)

    started = threading.Event()
    original_run = sched.run

    def _run_briefly() -> None:
        # Patch stop immediately so run() exits after one iteration
        sched._stop_event.set()  # noqa: SLF001
        original_run(_FAST)

    t = threading.Thread(target=_run_briefly)
    t.start()
    t.join(timeout=3)

    with pytest.raises(RuntimeError, match="after the scheduler loop has started"):
        sched.register("late_job", lambda: None)


def test_run_with_no_jobs_raises() -> None:
    sched = Scheduler()
    with pytest.raises(RuntimeError, match="No jobs registered"):
        sched.run(_FAST)


def test_run_executes_all_registered_jobs() -> None:
    sched = Scheduler()
    results: list[str] = []

    sched.register("job_a", lambda: results.append("a"))
    sched.register("job_b", lambda: results.append("b"))

    def _stop_after_first_tick() -> None:
        # Wait until both jobs have run once, then stop
        import time
        deadline = time.monotonic() + 5
        while len(results) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        sched.request_stop()

    stopper = threading.Thread(target=_stop_after_first_tick)
    stopper.start()
    sched.run(_FAST)
    stopper.join(timeout=5)

    assert "a" in results
    assert "b" in results


def test_request_stop_terminates_loop() -> None:
    sched = Scheduler()
    tick_count = 0

    def _job() -> None:
        nonlocal tick_count
        tick_count += 1
        if tick_count >= 2:
            sched.request_stop()

    sched.register("counting_job", _job)
    sched.run(_FAST)

    assert tick_count >= 2


def test_job_exception_does_not_stop_loop() -> None:
    sched = Scheduler()
    good_calls: list[int] = []
    tick = 0

    def _bad_job() -> None:
        raise ValueError("intentional failure")

    def _good_job() -> None:
        nonlocal tick
        tick += 1
        good_calls.append(tick)
        if tick >= 2:
            sched.request_stop()

    sched.register("bad_job", _bad_job)
    sched.register("good_job", _good_job)
    sched.run(_FAST)

    # Loop continued despite bad_job raising on every tick
    assert len(good_calls) >= 2


def test_jobs_run_in_registration_order() -> None:
    sched = Scheduler()
    order: list[str] = []

    sched.register("first", lambda: order.append("first"))
    sched.register("second", lambda: order.append("second"))
    sched.register("third", lambda: order.append("third"))

    def _stopper() -> None:
        import time
        deadline = time.monotonic() + 5
        while len(order) < 3 and time.monotonic() < deadline:
            time.sleep(0.05)
        sched.request_stop()

    t = threading.Thread(target=_stopper)
    t.start()
    sched.run(_FAST)
    t.join(timeout=5)

    assert order[:3] == ["first", "second", "third"]
