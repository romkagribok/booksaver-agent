from __future__ import annotations

import concurrent.futures
from collections.abc import Coroutine
from typing import Any

from booksaver.application.async_runner import AsyncLoopRunner


class _FinishesDuringCancellation:
    def __init__(self) -> None:
        self._finished = False
        self.result_calls = 0

    def result(self, timeout: float | None = None) -> str:
        del timeout
        self.result_calls += 1
        if self.result_calls == 1:
            raise concurrent.futures.TimeoutError
        return "completed-at-timeout-boundary"

    def done(self) -> bool:
        return self._finished

    def cancel(self) -> bool:
        self._finished = True
        return False


def test_timeout_boundary_reclaims_result_that_won_cancellation_race(monkeypatch) -> None:
    raced_future = _FinishesDuringCancellation()
    operation: Coroutine[Any, Any, str] | None = None

    async def complete() -> str:
        return "unused"

    operation = complete()
    monkeypatch.setattr(
        "booksaver.application.async_runner.asyncio.run_coroutine_threadsafe",
        lambda _operation, _loop: raced_future,
    )

    try:
        with AsyncLoopRunner() as runner:
            result = runner.run(operation, timeout=0.001)
    finally:
        operation.close()

    assert result == "completed-at-timeout-boundary"
    assert raced_future.result_calls == 2
