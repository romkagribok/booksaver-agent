from argparse import Namespace
from datetime import UTC, datetime

from booksaver.cli import commands
from booksaver.domain.account_sync import (
    InventoryDiscoveryResult,
    InventoryRecoveryAudit,
    InventoryRecoveryOutcome,
    SynchronizationFailureCode,
    SynchronizationTrigger,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteStore,
    SqliteUserRepository,
)


def test_bookings_trace_prints_content_free_caller_audit(
    tmp_path, monkeypatch, capsys
) -> None:
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        invited = users.get_or_create_by_telegram_id(4242)
        repository = SqliteAccountReservationRepository(store)
        repository.reconcile(
            user_id=invited.user_id,
            run_id="sync-audit-invited",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="test-revision",
            result=InventoryDiscoveryResult.failed(
                SynchronizationFailureCode.UNSUPPORTED_LAYOUT,
                "Sanitized test failure.",
            ),
            observed_at=datetime.now(UTC),
        )
        audit = InventoryRecoveryAudit.from_operational_events(
            outcome=InventoryRecoveryOutcome.PROVIDER_ERROR,
            step="inventory_interpretation",
            providers=("anthropic",),
            models=("test-model",),
            roles=("inventory_interpreter",),
            prompt_versions=("inventory-v1",),
            llm_calls_used=1,
            input_tokens=120,
            output_tokens=20,
            action_count=0,
            duration_ms=350,
            operational_events=(
                {
                    "kind": "agent_outcome",
                    "outcome": "failed",
                    "progress": False,
                },
            ),
        )
        repository.attach_recovery_audit(
            user_id=invited.user_id,
            run_id="sync-audit-invited",
            audit=audit,
        )
        assert (
            repository.recovery_audit_for_run(
                user_id=owner.user_id, run_id="sync-audit-invited"
            )
            is None
        )

    monkeypatch.setattr(
        commands,
        "_db_path_for",
        lambda _args: (object(), db_path),
    )

    result = commands.cmd_bookings_trace(Namespace(run_id="sync-audit-invited"))

    assert result == 0
    output = capsys.readouterr().out
    assert "Providers: anthropic" in output
    assert "tokens=120in/20out" in output
    assert '"progress":false' in output
    assert "Sanitized test failure" not in output


def test_bookings_trace_parser_wires_operator_command() -> None:
    args = commands.create_parser().parse_args(
        ["bookings", "trace", "sync-audit"]
    )

    assert args.func is commands.cmd_bookings_trace
    assert args.run_id == "sync-audit"
