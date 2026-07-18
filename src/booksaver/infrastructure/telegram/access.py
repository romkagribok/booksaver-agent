from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from booksaver.domain.user import UserAccessState

logger = logging.getLogger(__name__)


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
        self._lock = threading.Lock()

    def allow(self, key: int) -> bool:
        """Record an event for `key` and report whether it was within the limit."""
        with self._lock:
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


class AccessControl:
    """Real multi-user access control for a discoverable bot (US-026).

    Supersedes `OwnerGuard` for production wiring (kept above for its
    existing unit tests / bolt-008 compatibility). Every update is resolved
    to a `User` via `UserRepository`, never trusted from message content:

    - The owner (`owner_chat_id`) is always allowed — this is a chat-id
      check, not a `User` lookup, since the laptop-mode owner has no
      Telegram identity at all.
    - `owner` mode: anyone else is refused.
    - `invite` mode: a known, active user is allowed; a revoked user is
      refused; a stranger may redeem a single-use invite code via
      `/start <code>` (and only that one command/argument combination) to
      become an active user — everyone else is refused identically to
      `owner` mode, so a stranger can never distinguish "wrong code" from
      "invite mode is off" from probing.

    A `SqliteStore` is opened per `authorize()` call (mirroring
    `commands_readonly.py`'s per-command open/close pattern) rather than
    held open for the gateway's lifetime — and only when a lookup is
    actually needed: the owner fast-path and an `owner`-mode refusal never
    touch the database at all.
    """

    def __init__(
        self,
        owner_chat_id: int,
        db_path: Path,
        mode: str = "owner",
        refusal_limiter: RateLimiter | None = None,
    ) -> None:
        self._owner_chat_id = owner_chat_id
        self._db_path = db_path
        self._mode = mode
        self._limiter = refusal_limiter or RateLimiter(max_events=1, window_seconds=3600.0)
        self._owner_linked = False

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Runtime switch (US-028 `/admin mode`). Not persisted to config —
        reverts to the configured value on the next daemon restart."""
        if mode not in ("owner", "invite"):
            raise ValueError(f"Unknown access mode {mode!r}")
        self._mode = mode

    def is_owner(self, chat_id: int) -> bool:
        return chat_id == self._owner_chat_id

    def authorize(self, telegram_user_id: int, chat_id: int, command: str, args: str) -> bool:
        """Whether this sender may proceed. Never raises; never touches the
        database unless a stranger/known-user lookup is actually required."""
        if self.is_owner(chat_id):
            self._ensure_owner_linked(telegram_user_id)
            return True

        if self._mode == "owner":
            return False

        # invite mode
        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteStore,
            SqliteUserRepository,
        )

        with SqliteStore(self._db_path) as store:
            users = SqliteUserRepository(store)
            user = users.get_by_telegram_id(telegram_user_id)
            if user is not None:
                return user.access_state is UserAccessState.ACTIVE

            if command == "/start" and args.strip():
                from booksaver.infrastructure.persistence.sqlite_store import (
                    SqliteInviteCodeRepository,
                )

                code = args.strip()
                invites = SqliteInviteCodeRepository(store)
                now = datetime.now(UTC)
                invite = invites.get(code)
                if invite is not None and not invite.is_used and not invite.is_expired(now):
                    # Create the user row first — redeem() records `used_by`
                    # as a FK to it, and this order guarantees the row exists
                    # before the code is marked spent.
                    new_user = users.get_or_create_by_telegram_id(telegram_user_id)
                    redeemed = invites.redeem(code, used_by=new_user.user_id, now=now)
                    if redeemed is not None:
                        return True

            return False

    def _ensure_owner_linked(self, telegram_user_id: int) -> None:
        """Sender-scoped handlers (/register, /bookings, …) resolve users via
        `get_by_telegram_id`, but the v7 owner row is created with a NULL
        telegram_user_id (the laptop-mode owner has none). Link it on the
        owner's first authorized message so the owner is a first-class user
        on a VPS. Once per process; only fills NULL, never rebinds."""
        if self._owner_linked:
            return
        from booksaver.infrastructure.persistence.sqlite_store import (
            SqliteStore,
            SqliteUserRepository,
        )

        try:
            with SqliteStore(self._db_path) as store:
                users = SqliteUserRepository(store)
                owner = users.get_owner()
                if owner.telegram_user_id is None:
                    users.link_telegram_id(owner.user_id, telegram_user_id)
                    logger.info(
                        "Linked owner user row to Telegram user id %s", telegram_user_id
                    )
        except Exception:  # noqa: BLE001 - linking must never block the owner
            logger.warning("Could not link owner Telegram identity", exc_info=True)
            return
        self._owner_linked = True

    def should_send_refusal(self, chat_id: int) -> bool:
        return self._limiter.allow(chat_id)

    def log_refusal(self, telegram_user_id: int, command: str) -> None:
        """US-026: refused interactions are logged (user id + command),
        never message bodies."""
        logger.info("Access refused: user_id=%s command=%s", telegram_user_id, command)
