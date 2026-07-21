from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.models import Config
from booksaver.domain.value_objects import DataDirectory

logger = logging.getLogger(__name__)

_PID_FILENAME = "booksaver.pid"
_HEARTBEAT_FILENAME = "heartbeat"
_HEARTBEAT_INTERVAL_SECONDS = 15.0


def _pid_path(data_dir: DataDirectory) -> Path:
    return data_dir.path / _PID_FILENAME


def _read_pid(pid_file: Path) -> int | None:
    try:
        return int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return None


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but owned by another user — treat as alive.
        return True


def _write_pid(pid_file: Path) -> None:
    pid_file.write_text(str(os.getpid()) + "\n")
    pid_file.chmod(0o600)


def start(
    config: Config,
    scheduler: Scheduler,
    bot_runner: Callable[[threading.Event], None] | None = None,
    service_runners: dict[str, Callable[[threading.Event], None]] | None = None,
) -> None:
    """Start the daemon: check for existing instance, write PID file, run scheduler
    (and, if `bot_runner` is given, the Telegram bot update loop beside it — US-023).

    Fail-fast watchdog: if either thread dies from an unhandled error, the other
    is asked to stop too and the process exits nonzero once both have joined, so
    systemd/Docker restarts the whole daemon rather than leaving it half-alive.
    """
    pid_file = _pid_path(config.data_directory)
    config.data_directory.path.mkdir(mode=0o700, parents=True, exist_ok=True)

    if pid_file.exists():
        existing_pid = _read_pid(pid_file)
        if existing_pid is not None and _process_alive(existing_pid):
            logger.error("Daemon already running (PID %d)", existing_pid)
            print(
                f"Error: BookSaver daemon is already running (PID {existing_pid}).\n"
                f"Run 'booksaver stop' to stop it first.",
                file=sys.stderr,
            )
            sys.exit(2)
        else:
            logger.warning("Removing stale PID file (PID %s no longer running)", existing_pid)
            pid_file.unlink(missing_ok=True)

    _write_pid(pid_file)
    logger.info("Daemon started (PID %d, data_dir=%s)", os.getpid(), config.data_directory.path)

    def _handle_stop(signum: int, frame: object) -> None:
        logger.info("Received signal %d — stopping", signum)
        scheduler.request_stop()

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    failures: list[BaseException] = []

    def _run_scheduler() -> None:
        try:
            scheduler.run(config.check_interval)
        except BaseException as exc:  # noqa: BLE001 - watchdog must catch everything
            logger.error("Scheduler thread crashed: %s", exc, exc_info=True)
            failures.append(exc)
            scheduler.request_stop()

    threads = [threading.Thread(target=_run_scheduler, name="scheduler")]

    if bot_runner is not None:

        def _run_bot() -> None:
            try:
                bot_runner(scheduler.stop_event)
            except BaseException as exc:  # noqa: BLE001 - watchdog must catch everything
                logger.error("Telegram bot thread crashed: %s", exc, exc_info=True)
                failures.append(exc)
                scheduler.request_stop()

        threads.append(threading.Thread(target=_run_bot, name="telegram-bot"))

    for service_name, service_runner in (service_runners or {}).items():

        def _run_service(
            runner: Callable[[threading.Event], None] = service_runner,
            name: str = service_name,
        ) -> None:
            try:
                runner(scheduler.stop_event)
            except BaseException as exc:  # noqa: BLE001 - watchdog owns all services
                logger.error("%s thread crashed: %s", name, exc, exc_info=True)
                failures.append(exc)
                scheduler.request_stop()

        threads.append(threading.Thread(target=_run_service, name=service_name))

    for t in threads:
        t.start()

    # Liveness heartbeat: while every daemon thread is alive and healthy, the
    # main thread refreshes {data_dir}/heartbeat so an external freshness probe
    # (docker-compose healthcheck / systemd watchdog script) can distinguish a
    # making-progress daemon from a hung one. A crashed or wedged thread stops
    # the refresh, the probe goes stale, and the supervisor restarts us.
    heartbeat_file = config.data_directory.path / _HEARTBEAT_FILENAME
    try:
        while any(t.is_alive() for t in threads):
            if not failures and all(t.is_alive() for t in threads):
                try:
                    heartbeat_file.touch()
                except OSError as exc:
                    logger.warning("Could not refresh heartbeat file: %s", exc)
            for t in threads:
                t.join(timeout=_HEARTBEAT_INTERVAL_SECONDS / len(threads))
    finally:
        pid_file.unlink(missing_ok=True)
        heartbeat_file.unlink(missing_ok=True)
        logger.info("Daemon stopped cleanly")

    if failures:
        logger.error("Exiting nonzero — %d daemon thread(s) crashed", len(failures))
        sys.exit(1)


def stop(data_dir: DataDirectory, timeout: float = 10.0) -> int:
    """Send SIGTERM to the running daemon and wait for clean exit. Returns exit code."""
    import time

    pid_file = _pid_path(data_dir)

    if not pid_file.exists():
        print("No BookSaver daemon is running (no PID file found).")
        return 1

    pid = _read_pid(pid_file)
    if pid is None:
        print("PID file is unreadable — cannot stop daemon.")
        return 2

    if not _process_alive(pid):
        print(f"Daemon process {pid} is not running. Removing stale PID file.")
        pid_file.unlink(missing_ok=True)
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print(f"Process {pid} already gone.")
        pid_file.unlink(missing_ok=True)
        return 0

    logger.info("Sent SIGTERM to PID %d — waiting for clean exit", pid)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_file.exists():
            print(f"Daemon (PID {pid}) stopped cleanly.")
            return 0
        time.sleep(0.2)

    print(
        f"Error: daemon (PID {pid}) did not stop within {timeout:.0f}s.\n"
        "You may need to kill it manually.",
        file=sys.stderr,
    )
    return 2
