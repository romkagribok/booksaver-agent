from __future__ import annotations

import logging

from booksaver.application.ports import CheckHistoryRepository

logger = logging.getLogger(__name__)

DEFAULT_FAILURE_THRESHOLD = 3


class FailureTracker:
    """Counts consecutive check failures per booking and warns at a threshold.

    The count is derived from check history (no separate state), so it survives
    daemon restarts and stays consistent with what was actually recorded.
    """

    def __init__(
        self,
        history: CheckHistoryRepository,
        threshold: int = DEFAULT_FAILURE_THRESHOLD,
    ) -> None:
        if threshold < 1:
            raise ValueError(f"Failure threshold must be >= 1, got {threshold}")
        self._history = history
        self._threshold = threshold
        self._warned: set[str] = set()  # bookings already warned this streak

    def after_check(self, booking_id: str, succeeded: bool) -> bool:
        """Record the outcome of a check. Returns True if a warning was emitted."""
        if succeeded:
            self._warned.discard(booking_id)
            return False

        consecutive = self._history.count_consecutive_failures(booking_id)
        if consecutive >= self._threshold and booking_id not in self._warned:
            self._warned.add(booking_id)
            logger.warning(
                "Booking %s has failed %d consecutive checks (threshold %d). "
                "Checks still run — review failure reasons with "
                "'booksaver checks list %s'. Session OK? Run 'booksaver auth'.",
                booking_id,
                consecutive,
                self._threshold,
                booking_id,
            )
            return True
        return False
