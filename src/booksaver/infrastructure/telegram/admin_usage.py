from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdminUsageSnapshot:
    """Actual in-memory usage counters for one BookSaver user."""

    checks_today: int
    llm_calls_today: int

    def __post_init__(self) -> None:
        if self.checks_today < 0 or self.llm_calls_today < 0:
            raise ValueError("Admin usage counters must be non-negative")


# ``None`` means the runtime counters are unavailable. It is deliberately
# distinct from a snapshot containing real zero counts.
AdminUsageProvider = Callable[[int], AdminUsageSnapshot | None]
