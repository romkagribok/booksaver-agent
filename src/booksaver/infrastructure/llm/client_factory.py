from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from booksaver.application.ports import AgentBrain, LLMExtractor

if TYPE_CHECKING:
    from booksaver.domain.models import Booking, Config

logger = logging.getLogger(__name__)


class AnthropicLLMClientFactory:
    """LLMClientFactory seam (US-029): builds extraction/agent LLM clients.

    This slice always resolves the single owner env-var key
    (`BOOKSAVER_LLM_API_KEY`) for every booking — identical to the pre-v7
    behavior it replaces. `booking` is accepted (and currently unused) so a
    later slice (US-027, `/setkey`) can resolve booking -> owning user ->
    decrypted personal key, falling back to the owner key under per-user
    caps, without changing any call site. A missing key degrades to
    DOM-only/scripted-only mode (ADR-009) — it never raises.
    """

    def __init__(self, cfg: Config, api_key: str | None = None) -> None:
        self._cfg = cfg
        # Explicit api_key (mainly for tests); default resolves the owner's
        # env var, matching the pre-v7 _make_llm_extractor/_make_agent_brain.
        self._api_key = api_key if api_key is not None else os.environ.get("BOOKSAVER_LLM_API_KEY")

    def for_booking(self, booking: Booking | None) -> LLMExtractor | None:
        if not self._api_key:
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
            return AnthropicExtractor(api_key=self._api_key, model=model)
        except ImportError:
            logger.warning(
                "anthropic package not installed — LLM extraction disabled (DOM-only mode)"
            )
            return None

    def agent_brain_for_booking(self, booking: Booking | None) -> AgentBrain | None:
        if not self._api_key:
            logger.warning(
                "BOOKSAVER_LLM_API_KEY not set — agent escalation disabled (scripted-only)"
            )
            return None
        try:
            from booksaver.infrastructure.llm.anthropic_adapter import AnthropicAgentBrain

            model = self._cfg.agent_settings.model
            return AnthropicAgentBrain(api_key=self._api_key, model=model)
        except ImportError:
            logger.warning(
                "anthropic package not installed — agent escalation disabled (scripted-only)"
            )
            return None
