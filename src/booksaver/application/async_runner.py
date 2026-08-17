"""A small synchronous-to-async boundary for daemon-owned browser runtimes."""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class AsyncLoopRunner:
    """Own one event-loop thread and propagate timeout cancellation deterministically."""

    def __init__(self, *, thread_name: str = "booksaver-agentic-browser") -> None:
        self._loop = asyncio.new_event_loop()
        self._started = threading.Event()
        self._closed = False
        self._thread = threading.Thread(
            target=self._serve,
            name=thread_name,
            daemon=True,
        )
        self._thread.start()
        self._started.wait(timeout=5)
        if not self._started.is_set():
            raise RuntimeError("agentic browser event loop did not start")

    def _serve(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self._loop.close()

    def run(self, operation: Coroutine[Any, Any, T], *, timeout: float) -> T:
        if self._closed:
            operation.close()
            raise RuntimeError("agentic browser event loop is closed")
        future = asyncio.run_coroutine_threadsafe(operation, self._loop)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError("agentic browser operation timed out") from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    def __enter__(self) -> AsyncLoopRunner:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
