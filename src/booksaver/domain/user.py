from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class UserRole(Enum):
    OWNER = "owner"
    USER = "user"


class UserAccessState(Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass
class User:
    """A BookSaver user (schema v7, US-029).

    The laptop-mode owner has no Telegram identity (``telegram_user_id`` is
    ``None``); a VPS-deployed owner and every invited user have one. Exactly
    one ``OWNER`` row exists per database (enforced by a partial unique index
    on ``users.role`` — see ``sqlite_store.py``).

    ``encrypted_key`` is an opaque, nullable blob reserved for the personal
    Anthropic-key intake slice (US-027, `/setkey`). This slice never reads or
    writes it beyond passing it through unchanged — no encryption/decryption
    logic lives here yet.
    """

    user_id: int
    telegram_user_id: int | None
    role: UserRole
    access_state: UserAccessState
    created_at: datetime
    encrypted_key: bytes | None = None

    @property
    def is_owner(self) -> bool:
        return self.role is UserRole.OWNER

    @property
    def is_active(self) -> bool:
        return self.access_state is UserAccessState.ACTIVE
