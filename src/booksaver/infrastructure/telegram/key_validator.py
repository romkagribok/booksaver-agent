from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class KeyValidator(Protocol):
    """Validates a candidate Anthropic API key with one minimal live call
    before `/setkey` accepts it (US-027). Tests fake this — no network."""

    def validate(self, api_key: str) -> bool: ...


class AnthropicKeyValidator:
    """Real implementation: one minimal live call (list models, capped to a
    single result) against the Anthropic API. Any failure (auth, network,
    missing `anthropic` package) is treated as "invalid" — `/setkey` never
    stores a key it couldn't confirm works."""

    def validate(self, api_key: str) -> bool:
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)
            client.models.list(limit=1)
            return True
        except Exception as exc:
            logger.info("Personal Anthropic key validation failed: %s", exc)
            return False
