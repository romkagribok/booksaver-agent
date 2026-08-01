from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from booksaver.daemon.scheduler import Scheduler


def test_register_does_not_call_handler() -> None:
    scheduler = Scheduler()
    called: list[str] = []

    scheduler.register("job", lambda: called.append("called"))

    assert called == []


def test_register_after_run_started_raises() -> None:
    scheduler = Scheduler()

    def stop() -> None:
        scheduler.request_stop()

    scheduler.register("stop", stop)
    scheduler.run()

    with pytest.raises(RuntimeError, match="after the scheduler loop has started"):
        scheduler.register("late", lambda: None)


def test_run_with_no_jobs_raises() -> None:
    with pytest.raises(RuntimeError, match="No jobs registered"):
        Scheduler().run()


def test_startup_pass_runs_jobs_in_registration_order() -> None:
    scheduler = Scheduler()
    order: list[str] = []

    def first() -> None:
        order.append("first")

    def second() -> None:
        order.append("second")
        scheduler.request_stop()

    scheduler.register("first", first)
    scheduler.register("second", second)
    scheduler.run()

    assert order == ["first", "second"]


def test_waits_until_earliest_handler_wake() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    waits: list[float] = []
    scheduler: Scheduler

    def wait(timeout: float) -> bool:
        waits.append(timeout)
        scheduler.request_stop()
        return True

    scheduler = Scheduler(clock=lambda: now, waiter=wait)
    scheduler.register("later", lambda: now + timedelta(seconds=50))
    scheduler.register("earlier", lambda: now + timedelta(seconds=20))

    scheduler.run()

    assert waits == [20.0]
    assert scheduler.next_run_at == now + timedelta(seconds=20)


def test_discovery_interval_caps_distant_wake() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    waits: list[float] = []
    scheduler: Scheduler

    def wait(timeout: float) -> bool:
        waits.append(timeout)
        scheduler.request_stop()
        return True

    scheduler = Scheduler(clock=lambda: now, waiter=wait)
    scheduler.register("tomorrow", lambda: now + timedelta(days=1))

    scheduler.run()

    assert waits == [60.0]


def test_no_requested_wake_uses_discovery_interval() -> None:
    waits: list[float] = []
    scheduler: Scheduler

    def wait(timeout: float) -> bool:
        waits.append(timeout)
        scheduler.request_stop()
        return True

    scheduler = Scheduler(waiter=wait)
    scheduler.register("discovery-only", lambda: None)

    scheduler.run()

    assert waits == [60.0]
    assert scheduler.next_run_at is None


def test_past_wake_uses_small_nonzero_delay() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    waits: list[float] = []
    scheduler: Scheduler

    def wait(timeout: float) -> bool:
        waits.append(timeout)
        scheduler.request_stop()
        return True

    scheduler = Scheduler(clock=lambda: now, waiter=wait)
    scheduler.register("overdue", lambda: now - timedelta(hours=1))

    scheduler.run()

    assert waits == [0.1]


def test_job_exception_does_not_prevent_other_jobs_or_wait(
    caplog: pytest.LogCaptureFixture,
) -> None:
    waits: list[float] = []
    calls: list[str] = []
    scheduler: Scheduler

    def fail() -> None:
        raise ValueError("intentional failure")

    def wait(timeout: float) -> bool:
        waits.append(timeout)
        scheduler.request_stop()
        return True

    scheduler = Scheduler(waiter=wait)
    scheduler.register("bad", fail)
    scheduler.register("good", lambda: calls.append("good"))

    scheduler.run()

    assert calls == ["good"]
    assert waits == [60.0]
    assert "intentional failure" in caplog.text


def test_naive_handler_wake_is_isolated_as_job_error(caplog: pytest.LogCaptureFixture) -> None:
    waits: list[float] = []
    scheduler: Scheduler

    def wait(timeout: float) -> bool:
        waits.append(timeout)
        scheduler.request_stop()
        return True

    scheduler = Scheduler(waiter=wait)
    scheduler.register("naive", lambda: datetime(2026, 8, 1, 12))

    scheduler.run()

    assert waits == [60.0]
    assert "timezone-aware" in caplog.text


def test_request_stop_inside_handler_skips_remaining_jobs_and_wait() -> None:
    waited = False
    calls: list[str] = []

    def wait(_timeout: float) -> bool:
        nonlocal waited
        waited = True
        return False

    scheduler = Scheduler(waiter=wait)

    def stop() -> None:
        calls.append("stop")
        scheduler.request_stop()

    scheduler.register("stop", stop)
    scheduler.register("must-not-run", lambda: calls.append("late"))

    scheduler.run()

    assert calls == ["stop"]
    assert waited is False


def test_request_stop_interrupts_a_long_discovery_wait_promptly() -> None:
    scheduler = Scheduler()
    handler_ran = threading.Event()

    def idle() -> None:
        handler_ran.set()

    scheduler.register("idle", idle)
    worker = threading.Thread(target=scheduler.run)
    worker.start()
    assert handler_ran.wait(timeout=1)

    started_stopping = time.monotonic()
    scheduler.request_stop()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert time.monotonic() - started_stopping < 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "discovery_interval",
            timedelta(0),
            "discovery_interval must be positive",
        ),
        (
            "discovery_interval",
            timedelta(seconds=61),
            "discovery_interval cannot exceed 60 seconds",
        ),
        ("minimum_wait", timedelta(0), "minimum_wait must be positive"),
    ],
)
def test_invalid_loop_timing_is_rejected(field: str, value: timedelta, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        if field == "discovery_interval":
            Scheduler(discovery_interval=value)
        else:
            Scheduler(minimum_wait=value)
