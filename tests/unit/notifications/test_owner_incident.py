from __future__ import annotations

from uuid import UUID

import pytest

from booksaver.domain.browser_resilience import (
    DomJourney,
    DomStepId,
    TerminalBrowserReason,
)
from booksaver.domain.dom_incident import (
    EvidenceState,
    IncidentBudgetState,
    IncidentProviderState,
    OwnerIncidentNotice,
)
from booksaver.domain.model_policy import ModelRole
from booksaver.infrastructure.notifications.owner_incident import (
    OwnerIncidentTelegramNotifier,
    render_owner_incident_notice,
)

_INCIDENT_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


def _notice() -> OwnerIncidentNotice:
    return OwnerIncidentNotice(
        incident_id=_INCIDENT_ID,
        journey=DomJourney.ACCOUNT_INVENTORY,
        step_id=DomStepId.INVENTORY_EXTRACTION,
        category=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
        recovered=True,
        occurrence_count=2,
        model_roles=(ModelRole.RECOVERY, ModelRole.DIAGNOSTIC),
        provider_state=IncidentProviderState.COMPLETED,
        budget_state=IncidentBudgetState.WITHIN_LIMIT,
        evidence_state=EvidenceState.UNAVAILABLE,
    )


class _Client:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[tuple[int, str]] = []
        self.error = error

    def send_message(self, chat_id: int, text: str):
        self.calls.append((chat_id, text))
        if self.error is not None:
            raise self.error
        return {"message_id": 1}


def test_renderer_contains_only_allowlisted_typed_fields() -> None:
    text = render_owner_incident_notice(_notice())

    assert str(_INCIDENT_ID) in text
    assert "account_inventory" in text
    assert "inventory.extraction" in text
    assert "code_maintenance_required" in text
    assert "Recovered: yes" in text
    assert "Occurrences: 2" in text
    assert "recovery, diagnostic" in text
    assert "Provider state: completed" in text
    assert "Budget state: within_limit" in text
    assert "Evidence: unavailable" in text
    assert f"booksaver incidents inspect {_INCIDENT_ID}" in text


def test_notifier_always_targets_configured_owner_directly() -> None:
    client = _Client()
    notifier = OwnerIncidentTelegramNotifier(  # type: ignore[arg-type]
        client=client,
        owner_chat_id=42,
    )

    notifier.send(_notice())

    assert client.calls == [(42, render_owner_incident_notice(_notice()))]


def test_notifier_rejects_untyped_payload() -> None:
    notifier = OwnerIncidentTelegramNotifier(  # type: ignore[arg-type]
        client=_Client(),
        owner_chat_id=42,
    )

    with pytest.raises(TypeError, match="OwnerIncidentNotice only"):
        notifier.send("private source text")  # type: ignore[arg-type]


@pytest.mark.parametrize("owner_chat_id", [0, -1, True])
def test_notifier_requires_positive_owner_chat(owner_chat_id: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        OwnerIncidentTelegramNotifier(  # type: ignore[arg-type]
            client=_Client(),
            owner_chat_id=owner_chat_id,
        )


def test_delivery_failure_logs_only_incident_id(caplog) -> None:
    secret = "https://example.test?confirmation=PRIVATE&token=SECRET"
    notifier = OwnerIncidentTelegramNotifier(  # type: ignore[arg-type]
        client=_Client(error=RuntimeError(secret)),
        owner_chat_id=42,
    )

    with pytest.raises(RuntimeError, match="PRIVATE"):
        notifier.send(_notice())

    assert str(_INCIDENT_ID) in caplog.text
    assert "PRIVATE" not in caplog.text
    assert "SECRET" not in caplog.text
