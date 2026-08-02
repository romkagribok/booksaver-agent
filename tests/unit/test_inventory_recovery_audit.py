from __future__ import annotations

from dataclasses import replace

import pytest

from booksaver.domain.account_sync import (
    InventoryRecoveryAudit,
    InventoryRecoveryOutcome,
    InventoryRecoveryTraceEvent,
)


def _audit(**overrides: object) -> InventoryRecoveryAudit:
    base = InventoryRecoveryAudit(
        outcome=InventoryRecoveryOutcome.RECOVERED,
        step="inventory_scope",
        providers=("anthropic",),
        models=("claude-haiku-4-5",),
        roles=("agent_brain",),
        prompt_versions=("booking-browser-recovery-v2",),
        llm_calls_used=1,
        input_tokens=100,
        output_tokens=20,
        action_count=1,
        duration_ms=250,
        trace=(
            InventoryRecoveryTraceEvent.from_mapping(
                {
                    "kind": "agent_action",
                    "step": "inventory_scope",
                    "action": "click",
                    "target_present": True,
                }
            ),
        ),
    )
    return replace(base, **overrides)


def test_audit_accepts_aggregate_calls_not_represented_by_agent_events() -> None:
    audit = _audit(llm_calls_used=2, action_count=4)

    assert audit.llm_calls_used == 2
    assert audit.action_count == 4
    assert len(audit.trace) == 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"llm_calls_used": -1}, "out of bounds"),
        ({"duration_ms": 86_400_001}, "out of bounds"),
        ({"providers": ()}, "provider and model"),
        ({"roles": ()}, "role and prompt"),
        ({"step": "https://private.example/reservation"}, "machine code"),
    ],
)
def test_audit_rejects_invalid_or_content_shaped_metadata(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _audit(**overrides)


def test_trace_rejects_non_allowlisted_or_free_form_fields() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        InventoryRecoveryTraceEvent.from_mapping(
            {"kind": "agent_outcome", "page_text": "private reservation"}
        )

    with pytest.raises(ValueError, match="machine code"):
        InventoryRecoveryTraceEvent.from_mapping(
            {"kind": "agent_outcome", "step": "Confirmation ABC 123"}
        )


def test_not_needed_audit_is_empty_and_provider_neutral() -> None:
    audit = InventoryRecoveryAudit.from_operational_events(
        outcome=InventoryRecoveryOutcome.NOT_NEEDED,
        step=None,
        providers=(),
        models=(),
        roles=(),
        prompt_versions=(),
        llm_calls_used=0,
        input_tokens=0,
        output_tokens=0,
        action_count=0,
        duration_ms=0,
        operational_events=(),
    )

    assert audit.trace == ()
