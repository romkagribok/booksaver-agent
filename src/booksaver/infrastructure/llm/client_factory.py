from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from booksaver.application.ports import AgentBrain, LLMExtractor
from booksaver.domain.errors import SecretKeyError, UserKeyInvalidError

if TYPE_CHECKING:
    from booksaver.application.ports import UserRepository
    from booksaver.domain.models import Booking, Config
    from booksaver.domain.user import User
    from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore

logger = logging.getLogger(__name__)


class AnthropicLLMClientFactory:
    """LLMClientFactory seam (US-029/US-027): builds extraction/agent LLM
    clients, resolving a per-booking key when the booking's owner has one.

    Hybrid billing (US-027): when `user_repo`/`key_store` are supplied and a
    `booking` is given, the booking's owning user is resolved; if that user
    has `encrypted_key` set, it is decrypted and used for *that user's* LLM
    work instead of the owner's env-var key. Any other booking (or any
    caller that omits `user_repo`/`key_store`, e.g. CLI paths that don't yet
    have a `Booking` in hand) falls back to the single owner env-var key —
    byte-identical to pre-US-027 behavior.

    A user whose personal key cannot be decrypted (missing/invalid
    `BOOKSAVER_SECRET_KEY`, corrupt ciphertext) raises `UserKeyInvalidError`
    rather than silently falling back to the owner key — callers (the check
    job) map this to `FailureCode.USER_KEY_INVALID` so the failure is
    attributed to the right user and they're told to `/setkey` again or
    `/deletekey`. A missing/unset key (no personal key at all) is not an
    error — it degrades to DOM-only/scripted-only mode (ADR-009) exactly as
    before, never raises.
    """

    def __init__(
        self,
        cfg: Config,
        api_key: str | None = None,
        user_repo: UserRepository | None = None,
        key_store: FernetKeyStore | None = None,
    ) -> None:
        self._cfg = cfg
        # Explicit api_key (mainly for tests); default resolves the owner's
        # env var, matching the pre-v7 _make_llm_extractor/_make_agent_brain.
        self._owner_api_key = (
            api_key if api_key is not None else os.environ.get("BOOKSAVER_LLM_API_KEY")
        )
        self._user_repo = user_repo
        self._key_store = key_store

    def _resolve_api_key(self, booking: Booking | None) -> str | None:
        owner = self._resolve_owner(booking)
        if owner is not None and owner.encrypted_key is not None:
            if self._key_store is None:
                logger.warning(
                    "User %s has a personal key stored but no FernetKeyStore is "
                    "configured — falling back to the owner key",
                    owner.user_id,
                )
            else:
                try:
                    return self._key_store.decrypt(owner.encrypted_key)
                except SecretKeyError as exc:
                    raise UserKeyInvalidError(owner.user_id, str(exc)) from exc
        return self._owner_api_key

    def _resolve_owner(self, booking: Booking | None) -> User | None:
        if booking is None or self._user_repo is None:
            return None
        return self._user_repo.get_owner_of_booking(booking.booking_id)

    def for_booking(self, booking: Booking | None) -> LLMExtractor | None:
        api_key = self._resolve_api_key(booking)
        if not api_key:
            logger.warning(
                "BOOKSAVER_LLM_API_KEY not set — LLM extraction disabled (DOM-only mode)"
            )
            return None
        try:
            from booksaver.infrastructure.llm.anthropic_adapter import (
                DEFAULT_MODEL,
                AnthropicExtractor,
            )

            model = self._cfg.extraction_settings.get("model", DEFAULT_MODEL)
            return AnthropicExtractor(api_key=api_key, model=model)
        except ImportError:
            logger.warning(
                "anthropic package not installed — LLM extraction disabled (DOM-only mode)"
            )
            return None

    def agent_brain_for_booking(self, booking: Booking | None) -> AgentBrain | None:
        api_key = self._resolve_api_key(booking)
        if not api_key:
            logger.warning(
                "BOOKSAVER_LLM_API_KEY not set — agent escalation disabled (scripted-only)"
            )
            return None
        try:
            from booksaver.infrastructure.llm.anthropic_adapter import AnthropicAgentBrain

            model = self._cfg.agent_settings.model
            return AnthropicAgentBrain(api_key=api_key, model=model)
        except ImportError:
            logger.warning(
                "anthropic package not installed — agent escalation disabled (scripted-only)"
            )
            return None

