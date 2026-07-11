from __future__ import annotations

from booksaver.infrastructure.telegram.access import OwnerGuard, RateLimiter


def test_rate_limiter_allows_first_event() -> None:
    limiter = RateLimiter(max_events=1, window_seconds=60.0)
    assert limiter.allow(key=1) is True


def test_rate_limiter_blocks_second_event_within_window() -> None:
    clock = iter([0.0, 1.0]).__next__
    limiter = RateLimiter(max_events=1, window_seconds=60.0, clock=clock)
    assert limiter.allow(key=1) is True
    assert limiter.allow(key=1) is False


def test_rate_limiter_allows_again_after_window_expires() -> None:
    times = iter([0.0, 100.0])
    limiter = RateLimiter(max_events=1, window_seconds=60.0, clock=lambda: next(times))
    assert limiter.allow(key=1) is True
    assert limiter.allow(key=1) is True  # 100s later, outside the 60s window


def test_rate_limiter_tracks_keys_independently() -> None:
    limiter = RateLimiter(max_events=1, window_seconds=60.0)
    assert limiter.allow(key=1) is True
    assert limiter.allow(key=2) is True  # different chat, independent budget


def test_owner_guard_recognizes_owner_chat() -> None:
    guard = OwnerGuard(owner_chat_id=100)
    assert guard.is_owner(100) is True
    assert guard.is_owner(999) is False


def test_owner_guard_refuses_stranger_once_then_rate_limits() -> None:
    limiter = RateLimiter(max_events=1, window_seconds=3600)
    guard = OwnerGuard(owner_chat_id=100, refusal_limiter=limiter)
    assert guard.should_send_refusal(999) is True
    assert guard.should_send_refusal(999) is False
    assert guard.should_send_refusal(999) is False
