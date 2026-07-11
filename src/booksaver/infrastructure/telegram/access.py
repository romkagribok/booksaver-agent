from __future__ import annotations

import time
from collections.abc import Callable


class RateLimiter:
    """In-memory sliding-window limiter: at most `max_events` per `window_seconds`,
    tracked independently per integer key (e.g. a Telegram chat id)."""

    def __init__(
        self,
        max_events: int = 1,
        window_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[int, list[float]] = {}

    def allow(self, key: int) -> bool:
        """Record an event for `key` and report whether it was within the limit."""
        now = self._clock()
        recent = [t for t in self._hits.get(key, []) if now - t < self._window_seconds]
        allowed = len(recent) < self._max_events
        recent.append(now)
        self._hits[key] = recent
        return allowed


class OwnerGuard:
    """Owner-only access guard (FR-2, until unit 002 adds real multi-user access modes).

    Every update is resolved to the sender's chat id; only the configured owner
    chat id may trigger commands or dialogs. Non-owner chats get exactly one
    polite refusal per rate-limit window and are silently dropped thereafter —
    no state change or LLM call is ever triggered for them.
    """

    def __init__(self, owner_chat_id: int, refusal_limiter: RateLimiter | None = None) -> None:
        self._owner_chat_id = owner_chat_id
        self._limiter = refusal_limiter or RateLimiter(max_events=1, window_seconds=3600.0)

    def is_owner(self, chat_id: int) -> bool:
        return chat_id == self._owner_chat_id

    def should_send_refusal(self, chat_id: int) -> bool:
        """Whether a refusal message should be sent now for `chat_id` (rate-limited)."""
        return self._limiter.allow(chat_id)
