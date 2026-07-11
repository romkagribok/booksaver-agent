from __future__ import annotations

import os
import signal
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from booksaver.daemon import lifecycle
from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.models import Config
from booksaver.domain.value_objects import CheckInterval, DataDirectory, NotificationSettings

# Bypass the 15m minimum for tests — we need sub-second ticks to keep the suite fast.
_FAST = CheckInterval.__new__(CheckInterval)
object.__setattr__(_FAST, "duration", timedelta(seconds=1))


def _make_config(data_dir: DataDirectory) -> Config:
    return Config(
        check_interval=_FAST,
        data_directory=data_dir,
        notification_settings=NotificationSettings(),
        loaded_at=datetime.now(tz=UTC),
    )


def _make_data_dir(tmp_path: Path) -> DataDirectory:
    d = tmp_path / "booksaver"
    d.mkdir()
    return DataDirectory(path=d)


def _make_scheduler_that_stops_immediately() -> Scheduler:
    sched = Scheduler()

    def _job() -> None:
        sched.request_stop()

    sched.register("stop_job", _job)
    return sched


# ── PID file helpers ──────────────────────────────────────────────────────────

def test_pid_path_is_inside_data_directory(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    pid_file = lifecycle._pid_path(data_dir)  # noqa: SLF001
    assert pid_file.parent == data_dir.path
    assert pid_file.name == "booksaver.pid"


def test_write_pid_creates_file_with_correct_content(tmp_path: Path) -> None:
    pid_file = tmp_path / "booksaver.pid"
    lifecycle._write_pid(pid_file)  # noqa: SLF001
    assert pid_file.exists()
    assert int(pid_file.read_text().strip()) == os.getpid()
    assert oct(pid_file.stat().st_mode)[-3:] == "600"


def test_read_pid_returns_integer(tmp_path: Path) -> None:
    pid_file = tmp_path / "booksaver.pid"
    pid_file.write_text("12345\n")
    assert lifecycle._read_pid(pid_file) == 12345  # noqa: SLF001


def test_read_pid_returns_none_for_missing_file(tmp_path: Path) -> None:
    pid_file = tmp_path / "missing.pid"
    assert lifecycle._read_pid(pid_file) is None  # noqa: SLF001


def test_read_pid_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    pid_file = tmp_path / "bad.pid"
    pid_file.write_text("not-a-number\n")
    assert lifecycle._read_pid(pid_file) is None  # noqa: SLF001


# ── process alive detection ───────────────────────────────────────────────────

def test_process_alive_returns_true_for_current_process() -> None:
    assert lifecycle._process_alive(os.getpid()) is True  # noqa: SLF001


def test_process_alive_returns_false_for_nonexistent_pid() -> None:
    # PID 2147483647 is the max on Linux/macOS and virtually never running
    assert lifecycle._process_alive(2147483647) is False  # noqa: SLF001


# ── heartbeat file ────────────────────────────────────────────────────────────

def test_start_refreshes_heartbeat_while_running_and_removes_it_on_exit(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    heartbeat = data_dir.path / "heartbeat"
    seen_while_running: list[bool] = []
    sched = Scheduler()

    def _job() -> None:
        deadline = time.monotonic() + 5.0
        while not heartbeat.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        seen_while_running.append(heartbeat.exists())
        sched.request_stop()

    sched.register("wait_for_heartbeat", _job)

    with patch("signal.signal"):
        lifecycle.start(_make_config(data_dir), sched)

    assert seen_while_running == [True]
    assert not heartbeat.exists()


# ── start: PID file lifecycle ─────────────────────────────────────────────────

def test_start_writes_and_removes_pid_file(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    pid_file = lifecycle._pid_path(data_dir)  # noqa: SLF001
    sched = _make_scheduler_that_stops_immediately()

    with patch("signal.signal"):
        lifecycle.start(_make_config(data_dir), sched)

    assert not pid_file.exists()


def test_start_creates_pid_file_while_running(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    pid_file = lifecycle._pid_path(data_dir)  # noqa: SLF001
    pid_seen: list[int] = []
    sched = Scheduler()

    def _job() -> None:
        if pid_file.exists():
            pid_seen.append(int(pid_file.read_text().strip()))
        sched.request_stop()

    sched.register("check_pid", _job)

    with patch("signal.signal"):
        lifecycle.start(_make_config(data_dir), sched)

    assert pid_seen == [os.getpid()]


def test_start_refuses_when_process_already_running(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    pid_file = lifecycle._pid_path(data_dir)  # noqa: SLF001
    pid_file.write_text(f"{os.getpid()}\n")  # current process = definitely alive

    with pytest.raises(SystemExit) as exc_info:
        lifecycle.start(_make_config(data_dir), Scheduler())

    assert exc_info.value.code == 2
    assert pid_file.exists()


def test_start_removes_stale_pid_and_starts(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    pid_file = lifecycle._pid_path(data_dir)  # noqa: SLF001
    pid_file.write_text("2147483647\n")  # non-existent process
    sched = _make_scheduler_that_stops_immediately()

    with patch("signal.signal"):
        lifecycle.start(_make_config(data_dir), sched)  # must not raise

    assert not pid_file.exists()


# ── stop ─────────────────────────────────────────────────────────────────────

def test_stop_returns_1_when_no_pid_file(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    result = lifecycle.stop(data_dir, timeout=1.0)
    assert result == 1


def test_stop_removes_stale_pid_file_and_returns_1(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    pid_file = lifecycle._pid_path(data_dir)  # noqa: SLF001
    pid_file.write_text("2147483647\n")  # non-existent process

    result = lifecycle.stop(data_dir, timeout=1.0)
    assert result == 1
    assert not pid_file.exists()


# ── start: bot thread + watchdog (US-023) ─────────────────────────────────────

def test_start_runs_bot_runner_alongside_scheduler(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    sched = _make_scheduler_that_stops_immediately()
    bot_calls: list[threading.Event] = []

    def _bot_runner(stop_event: threading.Event) -> None:
        bot_calls.append(stop_event)
        stop_event.wait(timeout=5)  # scheduler's job requests stop almost immediately

    with patch("signal.signal"):
        lifecycle.start(_make_config(data_dir), sched, bot_runner=_bot_runner)

    assert len(bot_calls) == 1
    assert bot_calls[0] is sched.stop_event


def test_start_without_bot_runner_does_not_start_a_bot_thread(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    sched = _make_scheduler_that_stops_immediately()
    thread_names_before = {t.name for t in threading.enumerate()}

    with patch("signal.signal"):
        lifecycle.start(_make_config(data_dir), sched)

    thread_names_after = {t.name for t in threading.enumerate()}
    assert "telegram-bot" not in (thread_names_after - thread_names_before)


def test_start_exits_nonzero_when_bot_runner_crashes(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    sched = Scheduler()
    # A scheduler job that waits for the bot thread's crash to request stop.
    sched.register("noop", lambda: None)

    def _crashing_bot_runner(stop_event: threading.Event) -> None:
        raise RuntimeError("bot thread blew up")

    with patch("signal.signal"), pytest.raises(SystemExit) as exc_info:
        lifecycle.start(_make_config(data_dir), sched, bot_runner=_crashing_bot_runner)

    assert exc_info.value.code == 1


def test_start_exits_nonzero_when_scheduler_crashes(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    sched = Scheduler()

    # Scheduler.run() itself raising (not a job) is what the watchdog guards
    # against — jobs already have their own per-job try/except (see scheduler.py).
    def _crashing_run(interval):  # noqa: ANN001
        raise RuntimeError("scheduler run() blew up")

    sched.register("job", lambda: None)
    sched.run = _crashing_run  # type: ignore[method-assign]

    with patch("signal.signal"), pytest.raises(SystemExit) as exc_info:
        lifecycle.start(_make_config(data_dir), sched)

    assert exc_info.value.code == 1


def test_start_succeeds_when_bot_runner_completes_cleanly(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    sched = _make_scheduler_that_stops_immediately()

    def _bot_runner(stop_event: threading.Event) -> None:
        stop_event.wait(timeout=5)

    with patch("signal.signal"):
        lifecycle.start(_make_config(data_dir), sched, bot_runner=_bot_runner)  # must not raise


def test_stop_sends_sigterm_and_returns_0_when_pid_file_disappears(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    pid_file = lifecycle._pid_path(data_dir)  # noqa: SLF001

    # Simulate a running daemon: write current PID, remove file after SIGTERM
    pid_file.write_text(f"{os.getpid()}\n")
    received_signals: list[int] = []

    original_handler = signal.getsignal(signal.SIGTERM)

    def _fake_handler(signum: int, frame: object) -> None:
        received_signals.append(signum)
        pid_file.unlink(missing_ok=True)  # daemon would do this on clean stop

    signal.signal(signal.SIGTERM, _fake_handler)
    try:
        result = lifecycle.stop(data_dir, timeout=2.0)
    finally:
        signal.signal(signal.SIGTERM, original_handler)

    assert result == 0
    assert signal.SIGTERM in received_signals
