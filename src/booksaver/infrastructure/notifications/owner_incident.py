"""Dedicated owner-only Telegram delivery for content-free DOM incidents."""

from __future__ import annotations

import logging

from booksaver.domain.dom_incident import OwnerIncidentNotice
from booksaver.infrastructure.telegram.client import TelegramBotClient

logger = logging.getLogger(__name__)


def render_owner_incident_notice(notice: OwnerIncidentNotice) -> str:
    """Render only the closed, validated notice vocabulary.

    The renderer deliberately has no arbitrary subject/body/detail inputs. The
    domain value object is therefore the final payload allowlist.
    """

    roles = ", ".join(role.value for role in notice.model_roles) or "none"
    return "\n".join(
        (
            "BookSaver DOM maintenance required",
            f"Incident: {notice.incident_id}",
            f"Journey: {notice.journey.value}",
            f"Step: {notice.step_id.value}",
            f"Category: {notice.category.value}",
            f"Recovered: {'yes' if notice.recovered else 'no'}",
            f"Occurrences: {notice.occurrence_count}",
            f"Model roles: {roles}",
            f"Provider state: {notice.provider_state.value}",
            f"Budget state: {notice.budget_state.value}",
            f"Evidence: {notice.evidence_state.value}",
            f"Inspect locally: booksaver incidents inspect {notice.incident_id}",
        )
    )


class OwnerIncidentTelegramNotifier:
    """Send typed incident notices directly to the configured owner chat.

    This adapter intentionally bypasses caller routing, notification
    dispatchers, and the ordinary per-chat reply limiter. Delivery state and
    retries belong to the incident lifecycle worker.
    """

    def __init__(
        self,
        *,
        client: TelegramBotClient,
        owner_chat_id: int,
    ) -> None:
        if isinstance(owner_chat_id, bool) or owner_chat_id <= 0:
            raise ValueError("owner_chat_id must be a positive integer")
        self._client = client
        self._owner_chat_id = owner_chat_id

    def send(self, notice: OwnerIncidentNotice) -> None:
        if not isinstance(notice, OwnerIncidentNotice):
            raise TypeError("owner incident notifier accepts OwnerIncidentNotice only")
        try:
            self._client.send_message(
                self._owner_chat_id,
                render_owner_incident_notice(notice),
            )
        except Exception:
            # Never log Telegram response bodies, transport exception text, or
            # the rendered payload. Retry state uses only this stable incident ID.
            logger.warning(
                "Owner DOM-incident Telegram delivery failed for incident %s",
                notice.incident_id,
            )
            raise
